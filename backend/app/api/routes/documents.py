from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
import io
from qdrant_client.http import models as qdrant_models

from app.core.config import Settings, get_settings
from app.core.errors import safe_http_exception
from app.core.retry import retry_sync
from app.graphs.ingestion_graph import build_ingestion_graph
from app.models.schemas import (
    DocumentChunkListResponse,
    DocumentListResponse,
    DocumentRelationListResponse,
    DocumentResponse,
    DocumentSummaryListResponse,
    UploadDocumentResponse,
)
from app.services.chunks import list_chunks_by_document
from app.services import documents as document_service
from app.services import observability
from app.services import relations as relation_service
from app.services import summaries as summary_service
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
    retry_sync(
        "qdrant_delete",
        lambda: client.delete(
            collection_name=collection_name,
            points_selector=payload_filter,
        ),
        settings=settings,
    )


def delete_document_chunks(
    document_id: UUID,
    *,
    settings: Settings,
    supabase_client: Any | None = None,
) -> None:
    client = supabase_client or create_supabase_client(settings)
    client.table(DOCUMENT_CHUNKS_TABLE).delete().eq("document_id", str(document_id)).execute()


def _invoke_ingestion_graph(document_id: UUID, *, settings: Settings) -> dict[str, Any]:
    started_perf = observability.perf_now()
    run_id = None
    if settings.ENABLE_WORKFLOW_TRACING:
        run = observability.create_workflow_run(
            workflow_type="ingestion",
            entity_id=str(document_id),
            started_at=observability.now_utc(),
        )
        run_id = run.get("id") if isinstance(run, Mapping) else None
    graph = build_ingestion_graph(settings=settings)
    initial_state: dict[str, Any] = {"document_id": str(document_id)}
    if run_id is not None:
        initial_state["trace_id"] = str(run_id)
    try:
        result = graph.invoke(initial_state)
    except Exception:
        if run_id is not None:
            observability.update_workflow_run(
                run_id,
                status="failed",
                trace=[],
                error_code="ingestion_api_exception",
                error_message="Document ingestion failed",
                finished_at=observability.now_utc(),
                duration_ms=observability.duration_ms(started_perf),
            )
        raise
    if run_id is not None:
        failed = isinstance(result, Mapping) and result.get("status") == "failed"
        observability.update_workflow_run(
            run_id,
            status="failed" if failed else "completed",
            trace=list(result.get("workflow_trace") or []) if isinstance(result, Mapping) else [],
            error_code="ingestion_failed" if failed else None,
            error_message="Document ingestion failed" if failed else None,
            finished_at=observability.now_utc(),
            duration_ms=observability.duration_ms(started_perf),
        )
        if isinstance(result, Mapping) and result.get("trace_id") is None:
            result = {**dict(result), "trace_id": str(run_id)}
    return result


def run_document_index(document_id: UUID, *, settings: Settings) -> Any:
    return _invoke_ingestion_graph(document_id, settings=settings)


def run_document_reindex(document_id: UUID, *, settings: Settings) -> Any:
    document = _get_document_or_404(document_id, settings=settings)
    delete_document_vectors(
        document.id,
        settings=settings,
        qdrant_collection=document.qdrant_collection,
    )
    delete_document_chunks(document.id, settings=settings)
    return _invoke_ingestion_graph(document.id, settings=settings)


def _raise_if_ingestion_failed(result: Any) -> None:
    if isinstance(result, Mapping) and result.get("status") == "failed":
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            str(result.get("error_message") or "Document ingestion failed"),
        )


@router.get("", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    settings = _resolve_settings()
    documents = document_service.list_documents(settings=settings)
    return DocumentListResponse(documents=documents)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID) -> DocumentResponse:
    settings = _resolve_settings()
    return _get_document_or_404(document_id, settings=settings)


@router.get("/{document_id}/file")
def get_document_file(document_id: UUID) -> StreamingResponse:
    settings = _resolve_settings()
    document = _get_document_or_404(document_id, settings=settings)
    
    # Download file from Supabase storage
    client = create_supabase_client(settings)
    bucket = client.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
    try:
        file_bytes = bucket.download(document.storage_path)
    except Exception as exc:
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Failed to download file from storage: {exc}",
        )
    
    # Return file as a streaming response
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=document.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{document.file_name}"'
        }
    )


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
    _raise_if_ingestion_failed(result)
    return _processing_response(document.id)


@router.post("/{document_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
def reindex_document(document_id: UUID) -> dict[str, str]:
    settings = _resolve_settings()
    result = run_document_reindex(document_id, settings=settings)
    _raise_if_ingestion_failed(result)
    return _processing_response(document_id)


@router.delete("/{document_id}", response_model=DocumentResponse)
def delete_document(document_id: UUID) -> DocumentResponse:
    settings = _resolve_settings()
    try:
        return document_service.delete_document_and_file(document_id, settings=settings)
    except document_service.DocumentNotFoundError as exc:
        raise _document_not_found(document_id) from exc


@router.get("/{document_id}/chunks", response_model=DocumentChunkListResponse)
def get_document_chunks(document_id: UUID) -> DocumentChunkListResponse:
    settings = _resolve_settings()
    _get_document_or_404(document_id, settings=settings)
    chunks = list_chunks_by_document(document_id, settings=settings)
    return DocumentChunkListResponse(document_id=str(document_id), chunks=chunks)


@router.get("/{document_id}/summaries", response_model=DocumentSummaryListResponse)
def get_document_summaries(document_id: UUID) -> DocumentSummaryListResponse:
    settings = _resolve_settings()
    _get_document_or_404(document_id, settings=settings)
    summaries = summary_service.list_summaries(document_id)
    return DocumentSummaryListResponse(
        document_id=str(document_id),
        summaries=summaries,
    )


@router.get("/{document_id}/relations", response_model=DocumentRelationListResponse)
def get_document_relations(document_id: UUID) -> DocumentRelationListResponse:
    settings = _resolve_settings()
    _get_document_or_404(document_id, settings=settings)
    normalized_document_id = str(document_id)
    rows = []
    for relation in relation_service.list_relations(document_id):
        source_document_id = str(relation["source_document_id"])
        target_document_id = str(relation["target_document_id"])
        related_document_id = (
            target_document_id
            if source_document_id == normalized_document_id
            else source_document_id
        )
        rows.append(
            {
                **relation,
                "related_document_id": related_document_id,
            }
        )
    return DocumentRelationListResponse(
        document_id=normalized_document_id,
        relations=rows,
    )
