import logging
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.documents import (
    DocumentDeleteAuditSuccessRow,
    DocumentDeleteResponse,
    DocumentDeleteRpcSuccessRow,
    DocumentDetailResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.services.qdrant_service import QdrantDeleteError, delete_document_vectors
from app.services.supabase_service import (
    SupabaseConnectionError,
    delete_owned_document_cascade,
    get_document_metadata,
    get_successful_deletion_log,
    insert_deletion_log,
    insert_document_metadata,
    list_document_metadata,
    remove_document_file,
    upload_document_file,
)
from app.utils.file_validation import sanitize_filename, validate_upload_file


logger = logging.getLogger(__name__)
SAFE_DOCUMENT_DELETION_MESSAGE = "Document deletion failed. Please try again."


class DocumentServiceError(RuntimeError):
    """Raised when document service orchestration fails."""


class DocumentStorageError(DocumentServiceError):
    """Raised when the original upload cannot be stored."""


class DocumentMetadataError(DocumentServiceError):
    """Raised when document metadata cannot be persisted."""


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a document is not found for the configured user."""


class DocumentDeletionError(DocumentServiceError):
    """Raised when permanent document deletion cannot be completed."""


def build_document_storage_path(
    user_id: str,
    document_id: UUID,
    file_name: str,
) -> str:
    safe_file_name = sanitize_filename(file_name)
    return f"documents/{user_id}/{document_id}/{safe_file_name}"


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


def _ensure_uploaded_metadata_inserted(
    *,
    inserted_row: dict[str, Any],
    document_id: UUID,
) -> None:
    inserted_id = inserted_row.get("id")
    inserted_status = inserted_row.get("status")
    if str(inserted_id) == str(document_id) and inserted_status == "uploaded":
        return

    logger.error(
        "Document metadata insert returned unexpected row for document_id=%s",
        document_id,
    )
    raise DocumentMetadataError(
        "Document metadata insert did not return the uploaded document row."
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

    _ensure_uploaded_metadata_inserted(
        inserted_row=inserted_row,
        document_id=document_id,
    )

    return DocumentUploadResponse(
        document_id=document_id,
        file_name=validated_upload.file_name,
        status=inserted_row["status"],
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


def _failed_deletion_log_row(
    *,
    user_id: str,
    document_id: UUID,
    file_name: str,
    failure_stage: str,
    deleted_qdrant_points: bool,
    deleted_storage_file: bool,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "document_id": str(document_id),
        "file_name": file_name,
        "status": "failed",
        "failure_stage": failure_stage,
        "error_message": SAFE_DOCUMENT_DELETION_MESSAGE,
        "deleted_storage_file": deleted_storage_file,
        "deleted_qdrant_points": deleted_qdrant_points,
        "deleted_chunks": 0,
        "deleted_entities": 0,
        "deleted_relationships": 0,
        "deleted_agent_runs": 0,
        "deleted_agent_steps": 0,
        "deleted_chat_messages": 0,
        "deleted_chat_sessions": 0,
    }


def _record_failed_deletion(
    *,
    user_id: str,
    document_id: UUID,
    file_name: str,
    failure_stage: str,
    deleted_qdrant_points: bool,
    deleted_storage_file: bool,
) -> None:
    try:
        insert_deletion_log(
            _failed_deletion_log_row(
                user_id=user_id,
                document_id=document_id,
                file_name=file_name,
                failure_stage=failure_stage,
                deleted_qdrant_points=deleted_qdrant_points,
                deleted_storage_file=deleted_storage_file,
            )
        )
    except SupabaseConnectionError:
        logger.error(
            "Failed to record document deletion audit for document_id=%s. "
            "Provider details were suppressed for safety.",
            document_id,
        )


def _raise_deletion_failure(
    *,
    user_id: str,
    document_id: UUID,
    file_name: str,
    failure_stage: str,
    deleted_qdrant_points: bool,
    deleted_storage_file: bool,
    cause: Exception,
) -> None:
    logger.error(
        "Document deletion failed at stage=%s for document_id=%s. "
        "Provider details were suppressed for safety.",
        failure_stage,
        document_id,
    )
    _record_failed_deletion(
        user_id=user_id,
        document_id=document_id,
        file_name=file_name,
        failure_stage=failure_stage,
        deleted_qdrant_points=deleted_qdrant_points,
        deleted_storage_file=deleted_storage_file,
    )
    raise DocumentDeletionError(SAFE_DOCUMENT_DELETION_MESSAGE) from cause


def _delete_response_from_row(
    document_id: UUID,
    row: DocumentDeleteRpcSuccessRow | DocumentDeleteAuditSuccessRow,
) -> DocumentDeleteResponse:
    return DocumentDeleteResponse(
        document_id=document_id,
        deleted=True,
        deleted_agent_runs=row.deleted_agent_runs,
        deleted_agent_steps=row.deleted_agent_steps,
        deleted_chat_messages=row.deleted_chat_messages,
        deleted_chat_sessions=row.deleted_chat_sessions,
        deleted_chunks=row.deleted_chunks,
        deleted_entities=row.deleted_entities,
        deleted_relationships=row.deleted_relationships,
        deleted_qdrant_points=row.deleted_qdrant_points,
        deleted_storage_file=row.deleted_storage_file,
    )


def _validate_rpc_deletion_row(
    document_id: UUID,
    row: dict[str, Any],
) -> DocumentDeleteResponse:
    validated = DocumentDeleteRpcSuccessRow.model_validate(row)
    if (
        validated.document_id != document_id
        or validated.deleted is not True
        or validated.deleted_qdrant_points is not True
        or validated.deleted_storage_file is not True
    ):
        raise ValueError("Deletion response did not match the requested document.")
    return _delete_response_from_row(document_id, validated)


def _validate_audit_deletion_row(
    document_id: UUID,
    row: dict[str, Any],
) -> DocumentDeleteResponse:
    validated = DocumentDeleteAuditSuccessRow.model_validate(row)
    if (
        validated.document_id != document_id
        or validated.deleted_qdrant_points is not True
        or validated.deleted_storage_file is not True
    ):
        raise ValueError("Deletion audit did not match the requested document.")
    return _delete_response_from_row(document_id, validated)


def _reconcile_successful_deletion(
    *,
    user_id: str,
    document_id: UUID,
) -> DocumentDeleteResponse | None:
    try:
        row = get_successful_deletion_log(user_id, str(document_id))
    except SupabaseConnectionError:
        logger.error(
            "Document deletion reconciliation lookup failed for document_id=%s. "
            "Provider details were suppressed for safety.",
            document_id,
        )
        return None

    if row is None:
        return None

    try:
        return _validate_audit_deletion_row(document_id, row)
    except (ValidationError, ValueError):
        logger.error(
            "Document deletion reconciliation returned an invalid success row "
            "for document_id=%s. Details were suppressed for safety.",
            document_id,
        )
        return None


def delete_document(document_id: UUID) -> DocumentDeleteResponse:
    settings = get_settings()
    user_id = settings.single_user_id

    try:
        document = get_document_metadata(str(document_id), user_id)
    except SupabaseConnectionError as exc:
        logger.error(
            "Document deletion preflight failed for document_id=%s. "
            "Provider details were suppressed for safety.",
            document_id,
        )
        raise DocumentDeletionError(SAFE_DOCUMENT_DELETION_MESSAGE) from exc

    if document is None:
        raise DocumentNotFoundError("Document not found.")

    file_name = str(document.get("file_name") or "")
    storage_path = str(document.get("storage_path") or "")
    deleted_qdrant_points = False
    deleted_storage_file = False

    try:
        delete_document_vectors(document_id)
        deleted_qdrant_points = True
    except QdrantDeleteError as exc:
        _raise_deletion_failure(
            user_id=user_id,
            document_id=document_id,
            file_name=file_name,
            failure_stage="qdrant",
            deleted_qdrant_points=deleted_qdrant_points,
            deleted_storage_file=deleted_storage_file,
            cause=exc,
        )

    try:
        remove_document_file(storage_path)
        deleted_storage_file = True
    except SupabaseConnectionError as exc:
        _raise_deletion_failure(
            user_id=user_id,
            document_id=document_id,
            file_name=file_name,
            failure_stage="storage",
            deleted_qdrant_points=deleted_qdrant_points,
            deleted_storage_file=deleted_storage_file,
            cause=exc,
        )

    try:
        deletion_row = delete_owned_document_cascade(str(document_id), user_id)
    except SupabaseConnectionError as exc:
        reconciled_response = _reconcile_successful_deletion(
            user_id=user_id,
            document_id=document_id,
        )
        if reconciled_response is not None:
            return reconciled_response
        _raise_deletion_failure(
            user_id=user_id,
            document_id=document_id,
            file_name=file_name,
            failure_stage="database",
            deleted_qdrant_points=deleted_qdrant_points,
            deleted_storage_file=deleted_storage_file,
            cause=exc,
        )

    if deletion_row is None:
        raise DocumentNotFoundError("Document not found.")

    try:
        return _validate_rpc_deletion_row(document_id, deletion_row)
    except (ValidationError, ValueError) as exc:
        logger.error(
            "Document deletion returned an invalid success row for document_id=%s. "
            "Details were suppressed for safety.",
            document_id,
        )
        reconciled_response = _reconcile_successful_deletion(
            user_id=user_id,
            document_id=document_id,
        )
        if reconciled_response is not None:
            return reconciled_response
        _raise_deletion_failure(
            user_id=user_id,
            document_id=document_id,
            file_name=file_name,
            failure_stage="database",
            deleted_qdrant_points=deleted_qdrant_points,
            deleted_storage_file=deleted_storage_file,
            cause=exc,
        )
