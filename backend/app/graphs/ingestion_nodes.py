from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from qdrant_client.http import models as qdrant_models

from app.chunking.token_chunker import FixedTokenChunker
from app.core.config import Settings, get_settings
from app.core.errors import safe_detail
from app.graphs.ingestion_state import IngestionState
from app.parsing import get_parser_for_file
from app.services import documents as document_service
from app.services.qdrant_client import create_qdrant_client
from app.services.shopaikey_client import create_shopaikey_client
from app.services.supabase_client import create_supabase_client

DOCUMENTS_TABLE = "documents"
DOCUMENT_CHUNKS_TABLE = "document_chunks"
DEFAULT_INGESTION_ERROR = "Ingestion failed"
DEFAULT_CHUNKING_STRATEGY = "fixed_token"
DEFAULT_CHUNKING_VERSION = "v1"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _document_id_text(state: Mapping[str, Any]) -> str | None:
    document_id = state.get("document_id")
    if document_id is None:
        return None
    return str(document_id).strip() or None


def _resolve_document_id(state: Mapping[str, Any]) -> str | None:
    return _document_id_text(state)


def _resolve_document_record(state: Mapping[str, Any]) -> Mapping[str, Any]:
    document_record = state.get("document_record")
    if isinstance(document_record, Mapping):
        return document_record
    return {}


def _resolve_file_name(state: Mapping[str, Any]) -> str | None:
    file_name = state.get("file_name")
    if isinstance(file_name, str) and file_name.strip():
        return file_name.strip()

    document_record = _resolve_document_record(state)
    record_file_name = document_record.get("file_name")
    if isinstance(record_file_name, str) and record_file_name.strip():
        return record_file_name.strip()
    return None


def _resolve_mime_type(state: Mapping[str, Any]) -> str | None:
    mime_type = state.get("mime_type")
    if isinstance(mime_type, str) and mime_type.strip():
        return mime_type.strip()

    document_record = _resolve_document_record(state)
    record_mime_type = document_record.get("mime_type")
    if isinstance(record_mime_type, str) and record_mime_type.strip():
        return record_mime_type.strip()
    return None


def _resolve_storage_path(state: Mapping[str, Any]) -> str | None:
    storage_path = state.get("storage_path")
    if isinstance(storage_path, str) and storage_path.strip():
        return storage_path.strip()

    document_record = _resolve_document_record(state)
    record_storage_path = document_record.get("storage_path")
    if isinstance(record_storage_path, str) and record_storage_path.strip():
        return record_storage_path.strip()
    return None


def _resolve_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", response)
    if data is None:
        return []
    if isinstance(data, list):
        return [dict(row) for row in data]
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
        return [dict(row) for row in data]
    return [dict(data)]


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
        "status": "failed",
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
    client.table(DOCUMENTS_TABLE).update(payload).eq("id", document_id).execute()


def _normalize_bytes(downloaded: Any) -> bytes:
    if isinstance(downloaded, bytes):
        return downloaded
    if isinstance(downloaded, bytearray):
        return bytes(downloaded)
    if isinstance(downloaded, memoryview):
        return downloaded.tobytes()
    if hasattr(downloaded, "read"):
        data = downloaded.read()
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
    if isinstance(downloaded, str):
        return downloaded.encode("utf-8")
    raise TypeError("Downloaded document bytes could not be normalized")


def _chunk_metadata(state: Mapping[str, Any]) -> dict[str, Any]:
    metadata = {
        "parser_name": state.get("parser_name"),
        "parser_version": state.get("parser_version"),
        "chunking_strategy": state.get("chunking_strategy"),
        "chunking_version": state.get("chunking_version"),
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _document_chunk_insert_payload(
    document_id: str,
    *,
    chunk: Mapping[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "chunk_index": chunk.get("chunk_index"),
        "content": chunk.get("content"),
        "content_hash": chunk.get("content_hash"),
        "token_count": chunk.get("token_count"),
        "chunk_type": chunk.get("chunk_type"),
        "heading": chunk.get("heading"),
        "section_path": list(chunk.get("section_path") or []),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "token_start": chunk.get("token_start"),
        "token_end": chunk.get("token_end"),
        "metadata": metadata or None,
    }


def _qdrant_payload(
    document_id: str,
    *,
    chunk: Mapping[str, Any],
    file_name: str,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "chunk_id": str(chunk.get("id") or chunk.get("qdrant_point_id") or ""),
        "chunk_index": chunk.get("chunk_index"),
        "file_name": file_name,
        "heading": chunk.get("heading"),
        "section_path": list(chunk.get("section_path") or []),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "chunk_type": chunk.get("chunk_type"),
        "token_count": chunk.get("token_count"),
        "text": chunk.get("content"),
    }


def _build_qdrant_point(
    *,
    chunk_id: str,
    vector: Sequence[float],
    payload: dict[str, Any],
) -> qdrant_models.PointStruct:
    return qdrant_models.PointStruct(
        id=chunk_id,
        vector=list(vector),
        payload=payload,
    )


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
            {
                "status": "processing",
                "error_message": None,
                "updated_at": _now_utc(),
            },
            settings=settings,
        )
        return {"status": "processing", "error_message": None}
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
        chunker = FixedTokenChunker(settings=settings)
        chunks = chunker.chunk(dict(parsed_document))
        if not chunks:
            return _failure_state(document_id, "Chunking produced no chunks")
        return {
            "chunks": [dict(chunk) for chunk in chunks],
            "total_chunks": len(chunks),
            "chunking_strategy": getattr(chunker, "chunk_type", DEFAULT_CHUNKING_STRATEGY)
            or DEFAULT_CHUNKING_STRATEGY,
            "chunking_version": DEFAULT_CHUNKING_VERSION,
        }
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

    metadata = _chunk_metadata(state)

    try:
        client = create_supabase_client(settings)
        client.table(DOCUMENT_CHUNKS_TABLE).delete().eq("document_id", document_id).execute()

        payload_rows = [
            _document_chunk_insert_payload(
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
            row.get("chunk_index"): row
            for row in rows
            if row.get("chunk_index") is not None
        }
        saved_chunks: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks):
            row = rows_by_index.get(chunk.get("chunk_index"))
            if row is None and index < len(rows):
                row = rows[index]
            if row is None or row.get("id") is None:
                return _failure_state(document_id, "Inserted chunks are missing ids")

            saved_chunk = dict(chunk)
            saved_chunk["id"] = str(row["id"])
            saved_chunk["document_id"] = document_id
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
    if file_name is None:
        return _failure_state(document_id, "Document file_name is required")

    try:
        collection_name = state.get("qdrant_collection") or settings.QDRANT_COLLECTION
        qdrant_client = create_qdrant_client(settings)
        supabase_client = create_supabase_client(settings)

        points: list[qdrant_models.PointStruct] = []
        updated_chunks: list[dict[str, Any]] = []
        for chunk, vector in zip(chunks, embeddings, strict=True):
            chunk_id = chunk.get("id") or chunk.get("qdrant_point_id")
            if chunk_id is None or not str(chunk_id).strip():
                return _failure_state(
                    document_id,
                    "Chunk ids are required before Qdrant upsert",
                )

            point_id = str(chunk_id)
            payload = _qdrant_payload(
                document_id,
                chunk=chunk,
                file_name=file_name,
            )
            point = _build_qdrant_point(chunk_id=point_id, vector=vector, payload=payload)
            points.append(point)

            updated_chunk = dict(chunk)
            updated_chunk["qdrant_point_id"] = point_id
            updated_chunks.append(updated_chunk)

        qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
        )
        for chunk in updated_chunks:
            chunk_id = str(chunk["id"])
            supabase_client.table(DOCUMENT_CHUNKS_TABLE).update(
                {"qdrant_point_id": chunk["qdrant_point_id"]}
            ).eq("id", chunk_id).execute()
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
    payload = {
        "status": "ready",
        "total_pages": state.get("total_pages"),
        "total_chunks": state.get("total_chunks"),
        "parser_name": state.get("parser_name"),
        "parser_version": state.get("parser_version"),
        "chunking_strategy": state.get("chunking_strategy"),
        "chunking_version": state.get("chunking_version"),
        "embedding_model": state.get("embedding_model"),
        "embedding_dimension": state.get("embedding_dimension"),
        "qdrant_collection": resolved_collection,
        "indexed_at": _now_utc(),
        "error_message": None,
        "updated_at": _now_utc(),
    }
    try:
        _update_document_row(document_id, payload, settings=settings)
        return {
            "status": "ready",
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

    payload = {
        "status": "failed",
        "error_message": message,
        "updated_at": _now_utc(),
    }
    try:
        _update_document_row(document_id, payload, settings=settings)
    except Exception:  # pragma: no cover - defensive, failure state still returned
        pass
    return {
        "status": "failed",
        "error_message": message,
    }
