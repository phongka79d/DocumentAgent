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


def mark_ready_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    resolved_collection = state.get("qdrant_collection") or resolved_settings.QDRANT_COLLECTION
    payload = ingestion_payloads.ready_document_payload(
        state,
        qdrant_collection=resolved_collection,
        now=_now_utc(),
    )
    payload["error_code"] = None
    try:
        _update_document_row(document_id, payload, settings=resolved_settings, deps=deps)
        return {
            "status": DocumentStatus.READY,
            "error_message": None,
            "qdrant_collection": resolved_collection,
            "indexed_at": payload["indexed_at"],
        }
    except Exception as exc:  # pragma: no cover
        return _failure_state(document_id, f"Failed to mark document ready: {exc}")


def mark_failed_node(
    state: IngestionState,
    error_message: str | None = None,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    document_id = _resolve_document_id(state)
    message = safe_detail(
        error_message if error_message is not None else state.get("error_message"),
        fallback=DEFAULT_INGESTION_ERROR,
    )
    if document_id is None:
        return _failure_state(None, message)

    error_code = safe_detail(state.get("error_code"), fallback="ingestion_failed")
    payload = ingestion_payloads.failed_document_payload(message, now=_now_utc())
    payload["error_code"] = error_code
    try:
        _update_document_row(document_id, payload, settings=resolved_settings, deps=deps)
    except Exception:  # pragma: no cover
        pass
    return {
        "status": DocumentStatus.FAILED,
        "error_message": message,
        "error_code": error_code,
    }
