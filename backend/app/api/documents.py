from uuid import UUID

import logging

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status

from app.schemas.embeddings import DocumentIndexingResult
from app.schemas.documents import (
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.services import document_processing_service, document_service, embedding_service
from app.utils.file_validation import UploadTooLargeError, UploadValidationError


router = APIRouter()
logger = logging.getLogger(__name__)


def _indexing_error_detail(result: DocumentIndexingResult) -> dict:
    return {
        "message": "Indexing failed for all chunks.",
        "errors": [error.model_dump(mode="json") for error in result.errors],
    }


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    try:
        response = await document_service.upload_document(file)
        background_tasks.add_task(_process_uploaded_document, response.document_id)
        return response
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (
        document_service.DocumentStorageError,
        document_service.DocumentMetadataError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def _process_uploaded_document(document_id: UUID) -> None:
    try:
        document_processing_service.process_document(document_id)
        embedding_service.index_document_chunks(document_id)
    except Exception:
        logger.exception(
            "Background document processing failed for document_id=%s",
            document_id,
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
)
def list_documents() -> DocumentListResponse:
    try:
        return document_service.list_documents()
    except document_service.DocumentMetadataError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_document_detail(document_id: UUID) -> DocumentDetailResponse:
    try:
        return document_service.get_document_detail(document_id)
    except document_service.DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except document_service.DocumentMetadataError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    status_code=status.HTTP_200_OK,
)
def delete_document(document_id: UUID) -> DocumentDeleteResponse:
    try:
        return document_service.delete_document(document_id)
    except document_service.DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except document_service.DocumentDeletionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=document_service.SAFE_DOCUMENT_DELETION_MESSAGE,
        ) from exc


@router.post(
    "/{document_id}/index",
    response_model=DocumentIndexingResult,
    status_code=status.HTTP_200_OK,
)
def internal_development_index_document(
    document_id: UUID,
) -> DocumentIndexingResult:
    """Development/internal indexing trigger; frontend must not call this route."""
    try:
        result = embedding_service.index_document_chunks(document_id)
    except embedding_service.DocumentIndexingError as exc:
        error_message = str(exc)
        if error_message == "Document not found.":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_message,
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        ) from exc

    if result.indexed_count == 0 and result.failed_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no chunks to index.",
        )

    if result.indexed_count == 0 and result.failed_count > 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_indexing_error_detail(result),
        )

    return result
