import logging
from typing import Any
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.services.supabase_service import (
    SupabaseConnectionError,
    get_document_metadata,
    insert_document_metadata,
    list_document_metadata,
    upload_document_file,
)
from app.utils.file_validation import validate_upload_file


logger = logging.getLogger(__name__)


class DocumentServiceError(RuntimeError):
    """Raised when document service orchestration fails."""


class DocumentStorageError(DocumentServiceError):
    """Raised when the original upload cannot be stored."""


class DocumentMetadataError(DocumentServiceError):
    """Raised when document metadata cannot be persisted."""


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a document is not found for the configured user."""


def build_document_storage_path(
    user_id: str,
    document_id: UUID,
    file_name: str,
) -> str:
    return f"documents/{user_id}/{document_id}/{file_name}"


def build_uploaded_document_row(
    *,
    document_id: UUID,
    user_id: str,
    file_name: str,
    file_type: str,
    storage_path: str,
) -> dict[str, Any]:
    return {
        "id": str(document_id),
        "user_id": user_id,
        "file_name": file_name,
        "file_type": file_type,
        "storage_path": storage_path,
        "status": "uploaded",
        "chunk_count": 0,
        "error_message": None,
    }


def _document_list_item_from_row(row: dict[str, Any]) -> DocumentListItem:
    return DocumentListItem(
        id=row["id"],
        file_name=row["file_name"],
        file_type=row["file_type"],
        status=row["status"],
        chunk_count=row["chunk_count"],
        created_at=row["created_at"],
        error_message=row.get("error_message"),
    )


def _document_detail_from_row(row: dict[str, Any]) -> DocumentDetailResponse:
    return DocumentDetailResponse(
        id=row["id"],
        file_name=row["file_name"],
        file_type=row["file_type"],
        status=row["status"],
        chunk_count=row["chunk_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error_message=row.get("error_message"),
        chunks=[],
    )


async def upload_document(upload_file: Any) -> DocumentUploadResponse:
    settings = get_settings()
    validated_upload = await validate_upload_file(
        upload_file,
        settings.max_upload_bytes,
    )

    document_id = uuid4()
    storage_path = build_document_storage_path(
        settings.single_user_id,
        document_id,
        validated_upload.file_name,
    )

    try:
        upload_document_file(
            storage_path,
            validated_upload.content,
            content_type=validated_upload.content_type,
        )
    except SupabaseConnectionError as exc:
        logger.error(
            "Document storage upload failed for document_id=%s storage_path=%s",
            document_id,
            storage_path,
        )
        raise DocumentStorageError("Document storage upload failed.") from exc

    document_row = build_uploaded_document_row(
        document_id=document_id,
        user_id=settings.single_user_id,
        file_name=validated_upload.file_name,
        file_type=validated_upload.file_type,
        storage_path=storage_path,
    )

    try:
        inserted_row = insert_document_metadata(document_row)
    except SupabaseConnectionError as exc:
        logger.error(
            "Document metadata insert failed after storage upload for document_id=%s storage_path=%s",
            document_id,
            storage_path,
        )
        raise DocumentMetadataError(
            "Document metadata insert failed after storage upload completed."
        ) from exc

    return DocumentUploadResponse(
        document_id=document_id,
        file_name=validated_upload.file_name,
        status=inserted_row.get("status", "uploaded"),
    )


def list_documents() -> DocumentListResponse:
    settings = get_settings()

    try:
        rows = list_document_metadata(settings.single_user_id)
    except SupabaseConnectionError as exc:
        logger.error(
            "Document metadata list failed for user_id=%s",
            settings.single_user_id,
        )
        raise DocumentMetadataError("Document metadata list failed.") from exc

    return DocumentListResponse(
        documents=[_document_list_item_from_row(row) for row in rows]
    )


def get_document_detail(document_id: UUID) -> DocumentDetailResponse:
    settings = get_settings()

    try:
        row = get_document_metadata(str(document_id), settings.single_user_id)
    except SupabaseConnectionError as exc:
        logger.error(
            "Document metadata detail failed for document_id=%s user_id=%s",
            document_id,
            settings.single_user_id,
        )
        raise DocumentMetadataError("Document metadata detail failed.") from exc

    if row is None:
        raise DocumentNotFoundError("Document not found.")

    return _document_detail_from_row(row)
