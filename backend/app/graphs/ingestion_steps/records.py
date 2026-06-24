from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.core.config import Settings, get_settings
from app.core.contracts import DocumentStatus, TableName
from app.core.errors import safe_detail
from app.core.retry import retry_sync
from app.graphs import ingestion_inputs, ingestion_payloads
from app.graphs.ingestion_state import IngestionState
from app.graphs.ingestion_steps.dependencies import IngestionStepDependencies
from app.services import documents as document_service

DOCUMENTS_TABLE = TableName.DOCUMENTS
DEFAULT_INGESTION_ERROR = "Ingestion failed"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_document_id(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_document_id(state)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _failure_state(
    document_id: str | None,
    error_message: str | None,
    *,
    fallback: str = DEFAULT_INGESTION_ERROR,
    error_code: str | None = None,
    retry_attempts: dict[str, int] | None = None,
) -> dict[str, Any]:
    message = safe_detail(error_message, fallback=fallback)
    result: dict[str, Any] = {
        "status": DocumentStatus.FAILED,
        "error_message": message,
        "error_code": error_code or "ingestion_failed",
    }
    if document_id is not None:
        result["document_id"] = document_id
    if retry_attempts:
        result["retry_attempts"] = retry_attempts
    return result


def _update_document_row(
    document_id: str,
    payload: dict[str, Any],
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> None:
    resolved_settings = _resolve_settings(settings)
    client = deps.create_supabase_client(resolved_settings)
    retry_sync(
        "document_update",
        lambda: client.table(DOCUMENTS_TABLE).update(jsonable_encoder(payload)).eq(
            "id", document_id
        ).execute(),
        settings=resolved_settings,
    )


def load_document_record_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    try:
        client = deps.create_supabase_client(resolved_settings)
        document = document_service.get_document(
            document_id,
            settings=resolved_settings,
            supabase_client=client,
        )
        if document is None:
            return _failure_state(document_id, f"Document {document_id} not found")

        document_record = document.model_dump(mode="json")
        qdrant_collection = document.qdrant_collection or resolved_settings.QDRANT_COLLECTION

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
    except Exception as exc:  # pragma: no cover
        return _failure_state(document_id, f"Failed to load document record: {exc}")


def mark_processing_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    try:
        _update_document_row(
            document_id,
            ingestion_payloads.processing_document_payload(now=_now_utc()),
            settings=resolved_settings,
            deps=deps,
        )
        return {"status": DocumentStatus.PROCESSING, "error_message": None}
    except Exception as exc:  # pragma: no cover
        return _failure_state(document_id, f"Failed to mark document processing: {exc}")
