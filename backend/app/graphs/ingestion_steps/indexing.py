from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.config import Settings, get_settings
from app.core.contracts import ChunkField, DocumentStatus, TableName
from app.core.errors import safe_detail
from app.core.retry import RetryAttempt, RetryExhaustedError, retry_sync
from app.graphs import ingestion_inputs, ingestion_payloads
from app.graphs.ingestion_state import IngestionState
from app.graphs.ingestion_steps.dependencies import IngestionStepDependencies

DOCUMENT_CHUNKS_TABLE = TableName.DOCUMENT_CHUNKS
DEFAULT_INGESTION_ERROR = "Ingestion failed"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_document_id(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_document_id(state)


def _resolve_file_name(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_file_name(state)


def _resolve_mime_type(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_mime_type(state)


def _failure_state(
    document_id: str | None,
    error_message: str | None,
    *,
    fallback: str = DEFAULT_INGESTION_ERROR,
    error_code: str | None = None,
    retry_attempts: dict[str, int] | None = None,
) -> dict[str, Any]:
    message = safe_detail(error_message, fallback=fallback)
    result: dict[str, Any] = {
        "status": DocumentStatus.FAILED,
        "error_message": message,
        "error_code": error_code or "ingestion_failed",
    }
    if document_id is not None:
        result["document_id"] = document_id
    if retry_attempts:
        result["retry_attempts"] = retry_attempts
    return result


def _attempt_count(attempts: list[RetryAttempt]) -> int:
    if not attempts:
        return 1
    return max(attempt.attempt for attempt in attempts)


def _retry_attempts_for(
    node_name: str,
    attempts: list[RetryAttempt],
) -> dict[str, int]:
    attempt_count = _attempt_count(attempts)
    return {node_name: attempt_count} if attempt_count > 1 else {}


def _with_retry_attempts(
    result: dict[str, Any],
    node_name: str,
    attempts: list[RetryAttempt],
) -> dict[str, Any]:
    retry_attempts = _retry_attempts_for(node_name, attempts)
    if retry_attempts:
        return {**result, "retry_attempts": retry_attempts}
    return result


def _retry_exhausted_failure(
    document_id: str | None,
    node_name: str,
    exc: RetryExhaustedError,
) -> dict[str, Any]:
    operation = "".join(
        character.lower() if character.isalnum() else "_"
        for character in exc.operation
    ).strip("_")
    error_code = f"{operation or node_name}_retry_exhausted"
    return _failure_state(
        document_id,
        str(exc),
        error_code=error_code,
        retry_attempts={node_name: exc.attempts},
    )


def embed_chunks_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    chunks = state.get("chunks") or []
    if not isinstance(chunks, list) or not chunks:
        return _failure_state(document_id, "chunks are required before embedding")

    chunk_texts: list[str] = []
    for chunk in chunks:
        content = chunk.get("content")
        if not isinstance(content, str) or not content.strip():
            return _failure_state(document_id, "Chunk content is required for embeddings")
        chunk_texts.append(content)

    try:
        client = deps.create_shopaikey_client(resolved_settings)
        attempts: list[RetryAttempt] = []
        response = retry_sync(
            "embedding_generation",
            lambda: client.embeddings.create(
                model=resolved_settings.SHOPAIKEY_EMBEDDING_MODEL,
                input=chunk_texts,
            ),
            settings=resolved_settings,
            on_attempt=attempts.append,
        )
        items = getattr(response, "data", response)
        embeddings: list[list[float]] = []
        for item in items:
            embedding = getattr(item, "embedding", None)
            if embedding is None and isinstance(item, Mapping):
                embedding = item.get("embedding")
            if embedding is None:
                return _failure_state(document_id, "Embedding response missing vectors")
            vector = [float(value) for value in embedding]
            if not vector:
                return _failure_state(document_id, "Embedding response contained empty vectors")
            embeddings.append(vector)

        if len(embeddings) != len(chunks):
            return _failure_state(document_id, "Embedding count does not match chunk count")

        dimension = len(embeddings[0])
        if dimension <= 0 or any(len(vector) != dimension for vector in embeddings):
            return _failure_state(document_id, "Embedding dimension is inconsistent")

        return _with_retry_attempts(
            {
                "embeddings": embeddings,
                "embedding_model": resolved_settings.SHOPAIKEY_EMBEDDING_MODEL,
                "embedding_dimension": dimension,
            },
            "embed_chunks",
            attempts,
        )
    except RetryExhaustedError as exc:
        return _retry_exhausted_failure(document_id, "embed_chunks", exc)
    except Exception as exc:  # pragma: no cover
        return _failure_state(document_id, f"Embedding generation failed: {exc}")


def upsert_qdrant_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    chunks = state.get("chunks") or []
    embeddings = state.get("embeddings") or []
    if not isinstance(chunks, list) or not chunks:
        return _failure_state(document_id, "chunks are required before Qdrant upsert")
    if not isinstance(embeddings, list) or not embeddings:
        return _failure_state(document_id, "embeddings are required before Qdrant upsert")
    if len(chunks) != len(embeddings):
        return _failure_state(document_id, "Embedding count does not match chunk count")

    file_name = _resolve_file_name(state)
    mime_type = _resolve_mime_type(state)
    if file_name is None:
        return _failure_state(document_id, "Document file_name is required")

    try:
        collection_name = state.get("qdrant_collection") or resolved_settings.QDRANT_COLLECTION
        points: list[Any] = []
        updated_chunks: list[dict[str, Any]] = []
        for chunk, vector in zip(chunks, embeddings, strict=True):
            chunk_id = chunk.get(ChunkField.ID) or chunk.get(ChunkField.QDRANT_POINT_ID)
            if chunk_id is None or not str(chunk_id).strip():
                return _failure_state(
                    document_id,
                    "Chunk ids are required before Qdrant upsert",
                )

            point_id = str(chunk_id)
            payload = ingestion_payloads.qdrant_payload(
                document_id,
                chunk=chunk,
                file_name=file_name,
                mime_type=mime_type,
            )
            point = ingestion_payloads.build_qdrant_point(
                chunk_id=point_id,
                vector=vector,
                payload=payload,
            )
            points.append(point)

            updated_chunk = dict(chunk)
            updated_chunk[ChunkField.QDRANT_POINT_ID] = point_id
            updated_chunks.append(updated_chunk)

        qdrant_client = deps.create_qdrant_client(resolved_settings)
        supabase_client = deps.create_supabase_client(resolved_settings)
        attempts: list[RetryAttempt] = []
        retry_sync(
            "qdrant_upsert",
            lambda: qdrant_client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True,
            ),
            settings=resolved_settings,
            on_attempt=attempts.append,
        )
        for chunk in updated_chunks:
            chunk_id = str(chunk[ChunkField.ID])
            retry_sync(
                "chunk_qdrant_point_persistence",
                lambda chunk=chunk, chunk_id=chunk_id: supabase_client.table(
                    DOCUMENT_CHUNKS_TABLE
                ).update(
                    {ChunkField.QDRANT_POINT_ID: chunk[ChunkField.QDRANT_POINT_ID]}
                ).eq(ChunkField.ID, chunk_id).execute(),
                settings=resolved_settings,
            )
    except RetryExhaustedError as exc:
        return _retry_exhausted_failure(document_id, "upsert_qdrant", exc)
    except Exception as exc:  # pragma: no cover
        return _failure_state(document_id, f"Qdrant upsert failed: {exc}")

    return _with_retry_attempts(
        {
            "chunks": updated_chunks,
            "qdrant_collection": collection_name,
        },
        "upsert_qdrant",
        attempts,
    )
