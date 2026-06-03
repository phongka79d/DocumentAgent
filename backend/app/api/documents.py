from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.services import document_service
from app.utils.file_validation import UploadTooLargeError, UploadValidationError


router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    try:
        return await document_service.upload_document(file)
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
