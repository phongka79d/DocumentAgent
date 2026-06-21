from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.core.config import Settings, get_settings
from app.core.contracts import ChunkField, DocumentStatus, TableName
from app.core.errors import safe_detail
from app.graphs import ingestion_inputs
from app.graphs import ingestion_payloads
from app.graphs.ingestion_state import IngestionState
from app.parsing import get_parser_for_file
from app.services import documents as document_service
from app.services.qdrant_client import create_qdrant_client
from app.services.shopaikey_client import create_shopaikey_client
from app.services.supabase_client import create_supabase_client

DOCUMENTS_TABLE = TableName.DOCUMENTS
DOCUMENT_CHUNKS_TABLE = TableName.DOCUMENT_CHUNKS
DEFAULT_INGESTION_ERROR = "Ingestion failed"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _document_id_text(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.document_id_text(state)


def _resolve_document_id(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_document_id(state)


def _resolve_document_record(state: Mapping[str, Any]) -> Mapping[str, Any]:
    return ingestion_inputs.resolve_document_record(state)


def _resolve_file_name(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_file_name(state)


def _resolve_mime_type(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_mime_type(state)


def _resolve_storage_path(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_storage_path(state)


def _resolve_rows(response: Any) -> list[dict[str, Any]]:
    return ingestion_inputs.resolve_rows(response)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _failure_state(
    document_id: str | None,
    error_message: str | None,
    *,
    fallback: str = DEFAULT_INGESTION_ERROR,
) -> dict[str, Any]:
    message = safe_detail(error_message, fallback=fallback)
    result: dict[str, Any] = {
        "status": DocumentStatus.FAILED,
        "error_message": message,
    }
    if document_id is not None:
        result["document_id"] = document_id
    return result


def _update_document_row(
    document_id: str,
    payload: dict[str, Any],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> None:
    resolved_settings = _resolve_settings(settings)
    client = supabase_client if supabase_client is not None else create_supabase_client(
        resolved_settings
    )
    client.table(DOCUMENTS_TABLE).update(jsonable_encoder(payload)).eq(
        "id", document_id
    ).execute()


def _normalize_bytes(downloaded: Any) -> bytes:
    return ingestion_inputs.normalize_bytes(downloaded)


def load_document_record_node(state: IngestionState) -> dict[str, Any]:
    settings = _resolve_settings()
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    try:
        client = create_supabase_client(settings)
        document = document_service.get_document(
            document_id,
            settings=settings,
            supabase_client=client,
        )
        if document is None:
            return _failure_state(document_id, f"Document {document_id} not found")

        document_record = document.model_dump(mode="json")
        qdrant_collection = document.qdrant_collection or settings.QDRANT_COLLECTION

        return {
            "document_id": str(document.id),
            "document_record": document_record,
            "storage_path": document.storage_path,
            "file_name": document.file_name,
            "mime_type": document.mime_type,
            "file_size": document.file_size,
            "file_hash": document.file_hash,
            "total_pages": document.total_pages,
            "total_chunks": document.total_chunks,
            "parser_name": document.parser_name,
            "parser_version": document.parser_version,
            "chunking_strategy": document.chunking_strategy,
            "chunking_version": document.chunking_version,
            "embedding_model": document.embedding_model,
            "embedding_dimension": document.embedding_dimension,
            "qdrant_collection": qdrant_collection,
            "status": document.status,
            "error_message": document.error_message,
        }
    except Exception as exc:  # pragma: no cover - defensive, exercised by failures
        return _failure_state(document_id, f"Failed to load document record: {exc}")


def mark_processing_node(state: IngestionState) -> dict[str, Any]:
    settings = _resolve_settings()
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    try:
        _update_document_row(
            document_id,
            ingestion_payloads.processing_document_payload(now=_now_utc()),
            settings=settings,
        )
        return {"status": DocumentStatus.PROCESSING, "error_message": None}
    except Exception as exc:  # pragma: no cover - defensive, exercised by failures
        return _failure_state(document_id, f"Failed to mark document processing: {exc}")


def parse_document_node(state: IngestionState) -> dict[str, Any]:
    settings = _resolve_settings()
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    storage_path = _resolve_storage_path(state)
    file_name = _resolve_file_name(state)
    mime_type = _resolve_mime_type(state)
    if storage_path is None:
        return _failure_state(document_id, "Document storage_path is required")
    if file_name is None:
        return _failure_state(document_id, "Document file_name is required")

    try:
        client = create_supabase_client(settings)
        bucket = client.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
        downloaded = bucket.download(storage_path)
        file_bytes = _normalize_bytes(downloaded)
        parser = get_parser_for_file(file_name, mime_type=mime_type)
        parsed_document = parser.parse(
            file_bytes,
            file_name=file_name,
            mime_type=mime_type,
        )
        pages = parsed_document.get("pages") or []
        metadata = parsed_document.get("metadata") or {}
        return {
            "parsed_document": parsed_document,
            "total_pages": len(pages),
            "parser_name": metadata.get("parser_name"),
            "parser_version": metadata.get("parser_version"),
        }
    except Exception as exc:
        return _failure_state(document_id, str(exc))


def chunk_document_node(state: IngestionState) -> dict[str, Any]:
    settings = _resolve_settings()
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    parsed_document = state.get("parsed_document")
    if not isinstance(parsed_document, Mapping):
        return _failure_state(document_id, "parsed_document is required")

    try:
        chunker, chunking_strategy, chunking_version = (
            ingestion_payloads.resolve_chunker_for_settings(settings)
        )
        chunks = chunker.chunk(dict(parsed_document))
        if not chunks:
            return _failure_state(document_id, "Chunking produced no chunks")
        return {
            "chunks": [dict(chunk) for chunk in chunks],
            "total_chunks": len(chunks),
            "chunking_strategy": chunking_strategy,
            "chunking_version": chunking_version,
        }
    except ValueError as exc:
        return _failure_state(document_id, str(exc))
    except Exception as exc:  # pragma: no cover - defensive, exercised by failure tests
        return _failure_state(document_id, str(exc))


def save_chunks_node(state: IngestionState) -> dict[str, Any]:
    settings = _resolve_settings()
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    chunks = state.get("chunks") or []
    if not isinstance(chunks, list) or not chunks:
        return _failure_state(document_id, "chunks are required before saving")

    metadata = ingestion_payloads.chunk_metadata(state)

    try:
        client = create_supabase_client(settings)
        client.table(DOCUMENT_CHUNKS_TABLE).delete().eq("document_id", document_id).execute()

        payload_rows = [
            ingestion_payloads.document_chunk_insert_payload(
                document_id,
                chunk=chunk,
                metadata=metadata,
            )
            for chunk in chunks
        ]
        response = client.table(DOCUMENT_CHUNKS_TABLE).insert(payload_rows).execute()
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

        return {
            "chunks": saved_chunks,
            "total_chunks": len(saved_chunks),
        }
    except Exception as exc:  # pragma: no cover - defensive, exercised by failures
        return _failure_state(document_id, f"Chunk save failed: {exc}")


def embed_chunks_node(state: IngestionState) -> dict[str, Any]:
    settings = _resolve_settings()
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
        client = create_shopaikey_client(settings)
        response = client.embeddings.create(
            model=settings.SHOPAIKEY_EMBEDDING_MODEL,
            input=chunk_texts,
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

        return {
            "embeddings": embeddings,
            "embedding_model": settings.SHOPAIKEY_EMBEDDING_MODEL,
            "embedding_dimension": dimension,
        }
    except Exception as exc:  # pragma: no cover - defensive, exercised by failure tests
        return _failure_state(document_id, f"Embedding generation failed: {exc}")


def upsert_qdrant_node(state: IngestionState) -> dict[str, Any]:
    settings = _resolve_settings()
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
        collection_name = state.get("qdrant_collection") or settings.QDRANT_COLLECTION
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

        qdrant_client = create_qdrant_client(settings)
        supabase_client = create_supabase_client(settings)
        qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
        )
        for chunk in updated_chunks:
            chunk_id = str(chunk[ChunkField.ID])
            supabase_client.table(DOCUMENT_CHUNKS_TABLE).update(
                {ChunkField.QDRANT_POINT_ID: chunk[ChunkField.QDRANT_POINT_ID]}
            ).eq(ChunkField.ID, chunk_id).execute()
    except Exception as exc:  # pragma: no cover - defensive, exercised by failure tests
        return _failure_state(document_id, f"Qdrant upsert failed: {exc}")

    return {
        "chunks": updated_chunks,
        "qdrant_collection": collection_name,
    }


def mark_ready_node(state: IngestionState) -> dict[str, Any]:
    settings = _resolve_settings()
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    resolved_collection = state.get("qdrant_collection") or settings.QDRANT_COLLECTION
    payload = ingestion_payloads.ready_document_payload(
        state,
        qdrant_collection=resolved_collection,
        now=_now_utc(),
    )
    try:
        _update_document_row(document_id, payload, settings=settings)
        return {
            "status": DocumentStatus.READY,
            "error_message": None,
            "qdrant_collection": resolved_collection,
            "indexed_at": payload["indexed_at"],
        }
    except Exception as exc:  # pragma: no cover - defensive, exercised by failures
        return _failure_state(document_id, f"Failed to mark document ready: {exc}")


def mark_failed_node(
    state: IngestionState,
    error_message: str | None = None,
) -> dict[str, Any]:
    settings = _resolve_settings()
    document_id = _resolve_document_id(state)
    message = safe_detail(
        error_message if error_message is not None else state.get("error_message"),
        fallback=DEFAULT_INGESTION_ERROR,
    )
    if document_id is None:
        return _failure_state(None, message)

    payload = ingestion_payloads.failed_document_payload(message, now=_now_utc())
    try:
        _update_document_row(document_id, payload, settings=settings)
    except Exception:  # pragma: no cover - defensive, failure state still returned
        pass
    return {
        "status": DocumentStatus.FAILED,
        "error_message": message,
    }
