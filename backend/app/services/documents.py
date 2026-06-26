from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping
from uuid import UUID, uuid4

from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import Settings, get_settings
from app.core.retry import retry_sync
from app.models.schemas import DocumentResponse
from app.services.qdrant_client import create_qdrant_client
from app.services.supabase_client import create_supabase_client

DOCUMENTS_TABLE = "documents"
DOCUMENT_STORAGE_PREFIX = "documents"
DOCUMENT_STORAGE_SUBDIRECTORY = "original"


@dataclass(slots=True)
class DocumentUploadResult:
    document: DocumentResponse
    duplicate: bool = False


class DocumentServiceError(RuntimeError):
    """Raised when a document service operation cannot be completed."""


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a requested document row does not exist."""


class InvalidDocumentStoragePathError(DocumentServiceError):
    """Raised when a storage path does not match the document path contract."""


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_supabase_client(supabase_client: Any | None = None) -> Any:
    return supabase_client if supabase_client is not None else create_supabase_client()


def _resolve_qdrant_client(qdrant_client: Any | None = None) -> Any:
    return qdrant_client if qdrant_client is not None else create_qdrant_client()


def _response_data(response: Any) -> list[Mapping[str, Any]]:
    data = getattr(response, "data", response)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, Mapping):
        return [data]
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        return list(data)
    return [data]


def _document_from_row(row: Mapping[str, Any]) -> DocumentResponse:
    return DocumentResponse.model_validate(row)


def _normalize_title(title: str | None) -> str | None:
    if title is None:
        return None

    cleaned = title.strip()
    return cleaned or None


def _normalize_file_hash(file_hash: str) -> str:
    cleaned = file_hash.strip().lower()
    if not cleaned:
        raise DocumentServiceError("file_hash is required")
    return cleaned


def build_document_storage_path(document_id: UUID | str, file_name: str) -> str:
    normalized_file_name = Path(file_name).name.strip()
    if not normalized_file_name:
        raise DocumentServiceError("file_name is required")

    return str(
        PurePosixPath(
            DOCUMENT_STORAGE_PREFIX,
            str(document_id),
            DOCUMENT_STORAGE_SUBDIRECTORY,
            normalized_file_name,
        )
    )


def _extract_document_id_from_storage_path(storage_path: str) -> UUID:
    parts = PurePosixPath(storage_path).parts
    if len(parts) != 4:
        raise InvalidDocumentStoragePathError(
            "Storage path must match documents/{document_id}/original/{file_name}"
        )

    prefix, document_id_text, subdirectory, file_name = parts
    if (
        prefix != DOCUMENT_STORAGE_PREFIX
        or subdirectory != DOCUMENT_STORAGE_SUBDIRECTORY
        or not file_name
    ):
        raise InvalidDocumentStoragePathError(
            "Storage path must match documents/{document_id}/original/{file_name}"
        )

    try:
        return UUID(document_id_text)
    except ValueError as exc:
        raise InvalidDocumentStoragePathError(
            "Storage path document_id must be a valid UUID"
        ) from exc


def _documents_table(supabase_client: Any) -> Any:
    return supabase_client.table(DOCUMENTS_TABLE)


def list_documents(
    *, settings: Settings | None = None, supabase_client: Any | None = None
) -> list[DocumentResponse]:
    _resolve_settings(settings)
    client = _resolve_supabase_client(supabase_client)
    response = (
        _documents_table(client).select("*").order("created_at", desc=True).execute()
    )
    return [_document_from_row(row) for row in _response_data(response)]


def get_document(
    document_id: UUID | str,
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> DocumentResponse | None:
    _resolve_settings(settings)
    client = _resolve_supabase_client(supabase_client)
    response = (
        _documents_table(client)
        .select("*")
        .eq("id", str(document_id))
        .limit(1)
        .execute()
    )
    rows = _response_data(response)
    if not rows:
        return None
    return _document_from_row(rows[0])


def find_document_by_hash(
    file_hash: str,
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> DocumentResponse | None:
    _resolve_settings(settings)
    client = _resolve_supabase_client(supabase_client)
    normalized_hash = _normalize_file_hash(file_hash)
    response = (
        _documents_table(client)
        .select("*")
        .eq("file_hash", normalized_hash)
        .limit(1)
        .execute()
    )
    rows = _response_data(response)
    if not rows:
        return None
    return _document_from_row(rows[0])


def upload_original_file(
    storage_path: str,
    file_bytes: bytes,
    content_type: str | None,
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> Any:
    resolved_settings = _resolve_settings(settings)
    client = _resolve_supabase_client(supabase_client)
    bucket = client.storage.from_(resolved_settings.SUPABASE_STORAGE_BUCKET)
    file_options: dict[str, Any] | None = None
    if content_type:
        file_options = {"content-type": content_type}

    return bucket.upload(storage_path, file_bytes, file_options=file_options)


def create_uploaded_document(
    file_name: str,
    mime_type: str | None,
    file_size: int,
    file_hash: str,
    storage_path: str,
    title: str | None,
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> DocumentResponse:
    existing_document = find_document_by_hash(
        file_hash,
        settings=settings,
        supabase_client=supabase_client,
    )
    if existing_document is not None:
        return existing_document

    resolved_settings = _resolve_settings(settings)
    client = _resolve_supabase_client(supabase_client)
    document_id = _extract_document_id_from_storage_path(storage_path)
    normalized_file_name = Path(file_name).name.strip()
    normalized_title = _normalize_title(title)
    normalized_hash = _normalize_file_hash(file_hash)

    if normalized_file_name != PurePosixPath(storage_path).name:
        raise DocumentServiceError(
            "storage_path file_name must match the provided file_name"
        )

    payload = {
        "id": str(document_id),
        "title": normalized_title,
        "file_name": normalized_file_name,
        "mime_type": mime_type,
        "file_size": file_size,
        "file_hash": normalized_hash,
        "storage_path": storage_path,
        "status": "uploaded",
        "total_chunks": 0,
        "qdrant_collection": None,
    }
    response = _documents_table(client).insert(payload).execute()
    rows = _response_data(response)
    if rows:
        return _document_from_row(rows[0])

    inserted_document = get_document(
        document_id,
        settings=resolved_settings,
        supabase_client=client,
    )
    if inserted_document is None:
        raise DocumentServiceError("Document insert did not return a row")

    return inserted_document


def register_uploaded_document(
    *,
    file_name: str,
    mime_type: str | None,
    file_size: int,
    file_hash: str,
    file_bytes: bytes,
    title: str | None = None,
    content_type: str | None = None,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> DocumentUploadResult:
    resolved_settings = _resolve_settings(settings)
    client = _resolve_supabase_client(supabase_client)
    existing_document = find_document_by_hash(
        file_hash,
        settings=resolved_settings,
        supabase_client=client,
    )
    if existing_document is not None:
        return DocumentUploadResult(document=existing_document, duplicate=True)

    document_id = uuid4()
    storage_path = build_document_storage_path(document_id, file_name)
    upload_original_file(
        storage_path,
        file_bytes,
        content_type or mime_type,
        settings=resolved_settings,
        supabase_client=client,
    )
    document = create_uploaded_document(
        file_name=file_name,
        mime_type=mime_type,
        file_size=file_size,
        file_hash=file_hash,
        storage_path=storage_path,
        title=title,
        settings=resolved_settings,
        supabase_client=client,
    )
    return DocumentUploadResult(
        document=document,
        duplicate=document.id != document_id,
    )


def delete_document_and_file(
    document_id: UUID | str,
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
    qdrant_client: Any | None = None,
) -> DocumentResponse:
    resolved_settings = _resolve_settings(settings)
    client = _resolve_supabase_client(supabase_client)
    document = get_document(
        document_id,
        settings=resolved_settings,
        supabase_client=client,
    )
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    resolved_qdrant_client = _resolve_qdrant_client(qdrant_client)
    collection_name = document.qdrant_collection or resolved_settings.QDRANT_COLLECTION
    payload_filter = qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="document_id",
                match=qdrant_models.MatchValue(value=str(document.id)),
            )
        ]
    )
    try:
        retry_sync(
            "qdrant_delete",
            lambda: resolved_qdrant_client.delete(
                collection_name=collection_name,
                points_selector=payload_filter,
            ),
            settings=resolved_settings,
        )
    except UnexpectedResponse as exc:
        if exc.status_code != 404:
            raise

    bucket = client.storage.from_(resolved_settings.SUPABASE_STORAGE_BUCKET)
    bucket.remove([document.storage_path])

    _documents_table(client).delete().eq("id", str(document.id)).execute()

    return document
