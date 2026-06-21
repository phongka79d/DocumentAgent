from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.contracts import TableName, WorkflowStatus
from app.services.supabase_client import create_supabase_client

WORKFLOW_RUNS_TABLE = TableName.WORKFLOW_RUNS
WORKFLOW_TYPES = frozenset({"ingestion", "query"})
LOGGER = logging.getLogger(__name__)


def _resolve_supabase_client(supabase_client: Any | None = None) -> Any:
    return supabase_client if supabase_client is not None else create_supabase_client()


def _response_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", response)
    if data is None:
        return []
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        return [dict(row) for row in data]
    return []


def _normalize_uuid(value: UUID | str, field_name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{field_name} must be a valid UUID") from exc


def _normalize_workflow_type(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in WORKFLOW_TYPES:
        raise ValueError("workflow_type must be ingestion or query")
    return normalized


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _normalize_datetime(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    cleaned = str(value).strip()
    return cleaned or None


def _normalize_trace(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return [dict(event) for event in value if isinstance(event, Mapping)]
    raise ValueError("trace must contain mapping events")


def _normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if normalized.get("id") is not None:
        normalized["id"] = _normalize_uuid(normalized["id"], "id")
    if normalized.get("workflow_type") is not None:
        normalized["workflow_type"] = _normalize_workflow_type(
            normalized["workflow_type"]
        )
    if normalized.get("status") is not None:
        normalized["status"] = WorkflowStatus(normalized["status"]).value
    normalized["trace"] = _normalize_trace(normalized.get("trace"))
    return normalized


def _warn_trace_write(operation: str, error: Exception) -> None:
    LOGGER.warning("Workflow trace %s failed; continuing: %s", operation, error)


def create_workflow_run(
    *,
    workflow_type: str,
    entity_id: str | UUID | None = None,
    status: WorkflowStatus | str = WorkflowStatus.RUNNING,
    trace: Iterable[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    started_at: datetime | str | None = None,
    finished_at: datetime | str | None = None,
    duration_ms: int | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {
        "workflow_type": _normalize_workflow_type(workflow_type),
        "entity_id": _normalize_optional_text(entity_id),
        "status": WorkflowStatus(status).value,
        "trace": _normalize_trace(trace),
    }
    optional_values = {
        "error_code": _normalize_optional_text(error_code),
        "error_message": _normalize_optional_text(error_message),
        "started_at": _normalize_datetime(started_at),
        "finished_at": _normalize_datetime(finished_at),
        "duration_ms": int(duration_ms) if duration_ms is not None else None,
    }
    payload.update({key: value for key, value in optional_values.items() if value is not None})
    try:
        client = _resolve_supabase_client(supabase_client)
        rows = _response_rows(client.table(WORKFLOW_RUNS_TABLE).insert(payload).execute())
    except Exception as exc:  # Observability persistence is explicitly best-effort.
        _warn_trace_write("create", exc)
        return None
    return _normalize_row(rows[0]) if rows else payload


def update_workflow_run(
    run_id: UUID | str,
    *,
    status: WorkflowStatus | str | None = None,
    trace: Iterable[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    finished_at: datetime | str | None = None,
    duration_ms: int | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any] | None:
    normalized_run_id = _normalize_uuid(run_id, "run_id")
    payload: dict[str, Any] = {}
    if status is not None:
        payload["status"] = WorkflowStatus(status).value
    if trace is not None:
        payload["trace"] = _normalize_trace(trace)
    if error_code is not None:
        payload["error_code"] = _normalize_optional_text(error_code)
    if error_message is not None:
        payload["error_message"] = _normalize_optional_text(error_message)
    if finished_at is not None:
        payload["finished_at"] = _normalize_datetime(finished_at)
    if duration_ms is not None:
        payload["duration_ms"] = int(duration_ms)
    if not payload:
        return {"id": normalized_run_id}
    try:
        client = _resolve_supabase_client(supabase_client)
        response = (
            client.table(WORKFLOW_RUNS_TABLE)
            .update(payload)
            .eq("id", normalized_run_id)
            .execute()
        )
        rows = _response_rows(response)
    except Exception as exc:  # Observability persistence is explicitly best-effort.
        _warn_trace_write("update", exc)
        return None
    if rows:
        return _normalize_row(rows[0])
    return {"id": normalized_run_id, **payload}


def list_workflow_runs(
    *,
    workflow_type: str | None = None,
    status: WorkflowStatus | str | None = None,
    limit: int = 100,
    supabase_client: Any | None = None,
) -> list[dict[str, Any]]:
    client = _resolve_supabase_client(supabase_client)
    query = client.table(WORKFLOW_RUNS_TABLE).select("*")
    if workflow_type is not None:
        query = query.eq("workflow_type", _normalize_workflow_type(workflow_type))
    if status is not None:
        query = query.eq("status", WorkflowStatus(status).value)
    response = query.order("created_at", desc=True).limit(max(1, min(int(limit), 1000))).execute()
    return [_normalize_row(row) for row in _response_rows(response)]


def get_workflow_run(
    run_id: UUID | str, *, supabase_client: Any | None = None
) -> dict[str, Any] | None:
    normalized_run_id = _normalize_uuid(run_id, "run_id")
    client = _resolve_supabase_client(supabase_client)
    response = (
        client.table(WORKFLOW_RUNS_TABLE)
        .select("*")
        .eq("id", normalized_run_id)
        .limit(1)
        .execute()
    )
    rows = _response_rows(response)
    return _normalize_row(rows[0]) if rows else None
