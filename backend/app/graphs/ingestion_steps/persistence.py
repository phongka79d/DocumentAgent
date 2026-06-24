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


def _resolve_rows(response: Any) -> list[dict[str, Any]]:
    return ingestion_inputs.resolve_rows(response)


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


def save_chunks_node(
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
        return _failure_state(document_id, "chunks are required before saving")

    metadata = ingestion_payloads.chunk_metadata(state)

    try:
        client = deps.create_supabase_client(resolved_settings)
        attempts: list[RetryAttempt] = []

        def _replace_chunks() -> Any:
            client.table(DOCUMENT_CHUNKS_TABLE).delete().eq("document_id", document_id).execute()
            payload_rows = [
                ingestion_payloads.document_chunk_insert_payload(
                    document_id,
                    chunk=chunk,
                    metadata=metadata,
                )
                for chunk in chunks
            ]
            return client.table(DOCUMENT_CHUNKS_TABLE).insert(payload_rows).execute()

        response = retry_sync(
            "chunk_persistence",
            _replace_chunks,
            settings=resolved_settings,
            on_attempt=attempts.append,
        )
        rows = _resolve_rows(response)
        if len(rows) != len(chunks):
            return _failure_state(document_id, "Chunk save did not return inserted rows")

        rows_by_index = {
            row.get(ChunkField.CHUNK_INDEX): row
            for row in rows
            if row.get(ChunkField.CHUNK_INDEX) is not None
        }
        saved_chunks: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks):
            row = rows_by_index.get(chunk.get(ChunkField.CHUNK_INDEX))
            if row is None and index < len(rows):
                row = rows[index]
            if row is None or row.get(ChunkField.ID) is None:
                return _failure_state(document_id, "Inserted chunks are missing ids")

            saved_chunk = dict(chunk)
            saved_chunk[ChunkField.ID] = str(row[ChunkField.ID])
            saved_chunk[ChunkField.DOCUMENT_ID] = document_id
            saved_chunks.append(saved_chunk)

        return _with_retry_attempts(
            {
                "chunks": saved_chunks,
                "total_chunks": len(saved_chunks),
            },
            "save_chunks",
            attempts,
        )
    except RetryExhaustedError as exc:
        return _retry_exhausted_failure(document_id, "save_chunks", exc)
    except Exception as exc:  # pragma: no cover
        return _failure_state(document_id, f"Chunk save failed: {exc}")
