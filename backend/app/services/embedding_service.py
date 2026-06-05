from uuid import UUID

from app.schemas.embeddings import ChunkIndexingError, DocumentIndexingResult
from app.services.qdrant_service import (
    build_chunk_payload,
    ensure_collection,
    upsert_chunk_vector,
)
from app.services.shopaikey_service import create_embedding
from app.services.supabase_service import (
    get_indexing_document,
    list_chunks_needing_indexing,
    update_chunk_qdrant_point_id,
)


class DocumentIndexingError(RuntimeError):
    """Raised when a document cannot enter the indexing flow."""


def _as_uuid(value: UUID | str, field_name: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except ValueError as exc:
        raise DocumentIndexingError(f"Invalid UUID for '{field_name}'.") from exc


def _require_text(row: dict, field_name: str, row_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise DocumentIndexingError(
            f"{row_name} row is missing required field '{field_name}'."
        )

    return value


def _chunk_error(chunk: dict, exc: Exception) -> ChunkIndexingError:
    chunk_id = chunk.get("id")
    chunk_index = chunk.get("chunk_index")
    try:
        parsed_chunk_id = _as_uuid(chunk_id, "chunk.id") if chunk_id else None
    except DocumentIndexingError:
        parsed_chunk_id = None

    return ChunkIndexingError(
        chunk_id=parsed_chunk_id,
        chunk_index=chunk_index if isinstance(chunk_index, int) else None,
        message=str(exc)[:200] or "Chunk indexing failed.",
    )


def _has_qdrant_point_id(chunk: dict) -> bool:
    value = chunk.get("qdrant_point_id")
    return isinstance(value, str) and bool(value.strip())


def _index_one_chunk(
    *,
    document: dict,
    document_id: UUID,
    chunk: dict,
    collection_ready: bool,
) -> tuple[str, bool]:
    chunk_id = _as_uuid(chunk.get("id"), "chunk.id")
    chunk_id_text = str(chunk_id)
    content = _require_text(chunk, "content", "Document chunk")

    vector = create_embedding(content)
    if not collection_ready:
        ensure_collection(len(vector))
        collection_ready = True

    payload = build_chunk_payload(
        user_id=_require_text(chunk, "user_id", "Document chunk"),
        document_id=document_id,
        chunk_id=chunk_id,
        file_name=_require_text(document, "file_name", "Document"),
        file_type=_require_text(document, "file_type", "Document"),
        page_number=chunk.get("page_number"),
        section_title=chunk.get("section_title"),
        chunk_index=chunk.get("chunk_index"),
        content=content,
    )
    point_id = upsert_chunk_vector(
        point_id=chunk_id_text,
        vector=vector,
        payload=payload,
    )
    update_chunk_qdrant_point_id(str(document_id), chunk_id_text, point_id)

    return point_id, collection_ready


def index_document_chunks(document_id: UUID | str) -> DocumentIndexingResult:
    document_uuid = _as_uuid(document_id, "document_id")
    document_id_text = str(document_uuid)
    document = get_indexing_document(document_id_text)
    if document is None:
        raise DocumentIndexingError("Document not found.")

    if document.get("status") != "ready":
        raise DocumentIndexingError("Document must be ready before indexing.")

    chunks = list_chunks_needing_indexing(document_id_text)
    indexed_count = 0
    errors: list[ChunkIndexingError] = []
    collection_ready = False

    for chunk in chunks:
        if _has_qdrant_point_id(chunk):
            continue

        try:
            _, collection_ready = _index_one_chunk(
                document=document,
                document_id=document_uuid,
                chunk=chunk,
                collection_ready=collection_ready,
            )
        except Exception as exc:
            errors.append(_chunk_error(chunk, exc))
            continue

        indexed_count += 1

    return DocumentIndexingResult(
        document_id=document_uuid,
        indexed_count=indexed_count,
        failed_count=len(errors),
        errors=errors,
    )


__all__ = [
    "DocumentIndexingError",
    "index_document_chunks",
]
