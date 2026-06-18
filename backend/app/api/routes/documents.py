from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from qdrant_client.http import models as qdrant_models

from app.core.config import Settings, get_settings
from app.core.errors import safe_http_exception
from app.models.schemas import DocumentListResponse, DocumentResponse, UploadDocumentResponse
from app.services import documents as document_service
from app.services.hashing import compute_sha256
from app.services.qdrant_client import create_qdrant_client
from app.services.supabase_client import create_supabase_client
from app.services.validation import UploadValidationError, validate_upload_file

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)

DOCUMENT_CHUNKS_TABLE = "document_chunks"


def _resolve_settings() -> Settings:
    return get_settings()


def _response_rows(response: Any) -> list[Mapping[str, Any]]:
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


def _document_not_found(document_id: UUID) -> HTTPException:
    return safe_http_exception(
        status.HTTP_404_NOT_FOUND,
        f"Document {document_id} not found",
    )


def _get_document_or_404(
    document_id: UUID,
    *,
    settings: Settings,
) -> DocumentResponse:
    document = document_service.get_document(document_id, settings=settings)
    if document is None:
        raise _document_not_found(document_id)
    return document


def _processing_response(document_id: UUID) -> dict[str, str]:
    return {"document_id": str(document_id), "status": "processing"}


def delete_document_vectors(
    document_id: UUID,
    *,
    settings: Settings,
    qdrant_collection: str | None = None,
    qdrant_client: Any | None = None,
) -> None:
    client = qdrant_client or create_qdrant_client(settings)
    collection_name = qdrant_collection or settings.QDRANT_COLLECTION
    payload_filter = qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="document_id",
                match=qdrant_models.MatchValue(value=str(document_id)),
            )
        ]
    )
    client.delete(
        collection_name=collection_name,
        points_selector=payload_filter,
    )


def delete_document_chunks(
    document_id: UUID,
    *,
    settings: Settings,
    supabase_client: Any | None = None,
) -> None:
    client = supabase_client or create_supabase_client(settings)
    client.table(DOCUMENT_CHUNKS_TABLE).delete().eq("document_id", str(document_id)).execute()


def run_document_index(document_id: UUID, *, settings: Settings) -> Any:
    _ = document_id, settings
    return None


def run_document_reindex(document_id: UUID, *, settings: Settings) -> Any:
    _ = document_id, settings
    return None


@router.get("", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    settings = _resolve_settings()
    documents = document_service.list_documents(settings=settings)
    return DocumentListResponse(documents=documents)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID) -> DocumentResponse:
    settings = _resolve_settings()
    return _get_document_or_404(document_id, settings=settings)


@router.post("/upload", response_model=UploadDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
) -> UploadDocumentResponse:
    settings = _resolve_settings()
    file_bytes = await file.read()

    try:
        validation = validate_upload_file(
            file_name=file.filename or "",
            file_bytes=file_bytes,
            content_type=file.content_type,
            max_upload_bytes=settings.MAX_UPLOAD_BYTES,
        )
    except UploadValidationError as exc:
        raise safe_http_exception(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    upload_result = document_service.register_uploaded_document(
        file_name=validation.file_name,
        mime_type=validation.content_type,
        file_size=validation.file_size,
        file_hash=compute_sha256(file_bytes),
        file_bytes=file_bytes,
        title=title,
        content_type=validation.content_type,
        settings=settings,
    )
    return UploadDocumentResponse(
        document_id=upload_result.document.id,
        status=upload_result.document.status,
        duplicate=upload_result.duplicate,
    )


@router.post("/{document_id}/index", status_code=status.HTTP_202_ACCEPTED)
def index_document(document_id: UUID) -> dict[str, str]:
    settings = _resolve_settings()
    document = _get_document_or_404(document_id, settings=settings)
    result = run_document_index(document.id, settings=settings)
    if result is not None:
        return result
    return _processing_response(document.id)


@router.post("/{document_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
def reindex_document(document_id: UUID) -> dict[str, str]:
    settings = _resolve_settings()
    document = _get_document_or_404(document_id, settings=settings)
    delete_document_vectors(
        document.id,
        settings=settings,
        qdrant_collection=document.qdrant_collection,
    )
    delete_document_chunks(document.id, settings=settings)
    result = run_document_reindex(document.id, settings=settings)
    if result is not None:
        return result
    return _processing_response(document.id)


@router.delete("/{document_id}", response_model=DocumentResponse)
def delete_document(document_id: UUID) -> DocumentResponse:
    settings = _resolve_settings()
    try:
        return document_service.delete_document_and_file(document_id, settings=settings)
    except document_service.DocumentNotFoundError as exc:
        raise _document_not_found(document_id) from exc


@router.get("/{document_id}/chunks")
def get_document_chunks(document_id: UUID) -> dict[str, Any]:
    settings = _resolve_settings()
    _get_document_or_404(document_id, settings=settings)
    client = create_supabase_client(settings)
    response = (
        client.table(DOCUMENT_CHUNKS_TABLE)
        .select("*")
        .eq("document_id", str(document_id))
        .order("chunk_index")
        .execute()
    )
    return {
        "document_id": str(document_id),
        "chunks": _response_rows(response),
    }
