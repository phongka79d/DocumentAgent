from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import UUID
from urllib.parse import urlsplit
import re

from app.core.contracts import TableName, WorkflowStatus
from app.services.supabase_client import create_supabase_client

WORKFLOW_RUNS_TABLE = TableName.WORKFLOW_RUNS
WORKFLOW_TYPES = frozenset({"ingestion", "query"})
LOGGER = logging.getLogger(__name__)
SAFE_ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
REDACTED = "[REDACTED]"
REDACTED_URL = "[REDACTED_URL]"
PROHIBITED_KEY_PARTS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "secret",
        "credential",
        "password",
        "prompt",
        "response",
        "answer",
        "content",
        "text",
        "chunk_text",
        "parsed_text",
        "raw",
        "headers",
        "messages",
    }
)
SAFE_EVENT_KEYS = frozenset(
    {
        "node_name",
        "status",
        "attempt",
        "started_at",
        "finished_at",
        "duration_ms",
        "provider",
        "input_count",
        "output_count",
        "route",
        "fallback",
        "error_code",
        "event_type",
        "workflow_type",
        "subquery_count",
        "semantic_count",
        "keyword_count",
        "fused_count",
        "reranked_count",
        "context_count",
        "selected_strategy",
        "fallback_path",
        "context_tokens",
        "grounding_score",
        "citation_valid",
        "total_query_latency_ms",
    }
)


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


def _has_credential_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username or parsed.password:
        return True
    query = parsed.query.lower()
    return any(
        token in query
        for token in (
            "api_key=",
            "apikey=",
            "key=",
            "token=",
            "access_token=",
            "signature=",
            "sig=",
        )
    )


def _is_prohibited_key(key: Any) -> bool:
    normalized = str(key).lower().replace("-", "_")
    if normalized.endswith("_count") or normalized in {"count", "context_count"}:
        return False
    return any(part in normalized for part in PROHIBITED_KEY_PARTS)


def redact_trace_value(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _is_prohibited_key(key):
        return REDACTED
    if isinstance(value, str):
        return REDACTED_URL if _has_credential_url(value) else value
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_trace_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return [redact_trace_value(item) for item in value]
    return value


def _safe_event(event: Mapping[str, Any]) -> dict[str, Any]:
    redacted = redact_trace_value(event)
    if not isinstance(redacted, Mapping):
        return {}
    return {
        key: value
        for key, value in redacted.items()
        if key in SAFE_EVENT_KEYS and value is not None
    }


def _normalize_trace(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [_safe_event(value)]
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return [_safe_event(event) for event in value if isinstance(event, Mapping)]
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
    clamped_limit = max(1, min(int(limit), 100))
    query = client.table(WORKFLOW_RUNS_TABLE).select("*")
    if workflow_type is not None:
        query = query.eq("workflow_type", _normalize_workflow_type(workflow_type))
    if status is not None:
        query = query.eq("status", WorkflowStatus(status).value)
    response = query.order("created_at", desc=True).limit(clamped_limit).execute()
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


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def perf_now() -> float:
    return perf_counter()


def duration_ms(started: float, finished: float | None = None) -> int:
    end = perf_counter() if finished is None else finished
    return max(0, int((end - started) * 1000))


def safe_error_code(value: Any, *, node_name: str | None = None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if SAFE_ERROR_CODE_RE.fullmatch(normalized) and not _is_prohibited_key(normalized):
        return normalized
    if node_name is not None:
        safe_node_name = "".join(
            character.lower() if character.isalnum() else "_"
            for character in str(node_name).strip()
        ).strip("_")
        if safe_node_name:
            return f"{safe_node_name[:64]}_failed"
    return "workflow_failed"


def node_trace_event(
    *,
    node_name: str,
    status: str,
    attempt: int,
    started_at: datetime,
    finished_at: datetime,
    duration_ms: int,
    provider: str | None = None,
    input_count: int | None = None,
    output_count: int | None = None,
    route: str | None = None,
    fallback: str | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    return _safe_event(
        {
            "node_name": node_name,
            "status": status,
            "attempt": max(1, int(attempt)),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": duration_ms,
            "provider": provider,
            "input_count": input_count,
            "output_count": output_count,
            "route": route,
            "fallback": fallback,
            "error_code": safe_error_code(error_code, node_name=node_name),
        }
    )


def retrieval_totals_event(state: Mapping[str, Any], *, total_query_latency_ms: int) -> dict[str, Any]:
    metrics = state.get("retrieval_metrics") or {}
    if not isinstance(metrics, Mapping):
        metrics = {}
    path_candidates = state.get("path_candidates") or {}
    semantic_count = 0
    keyword_count = 0
    if isinstance(path_candidates, Mapping):
        for path_key, candidates in path_candidates.items():
            count = len(candidates) if isinstance(candidates, list) else 0
            if str(path_key).endswith(":semantic"):
                semantic_count += count
            if str(path_key).endswith(":keyword"):
                keyword_count += count

    route = state.get("route")
    if hasattr(route, "value"):
        route = route.value
    citation = state.get("citation_validation_result")
    grounding = state.get("grounding_result")
    subqueries = state.get("subqueries") or []
    event = {
        "event_type": "retrieval_totals",
        "node_name": "retrieval_totals",
        "status": "completed",
        "attempt": 1,
        "subquery_count": len(subqueries) if isinstance(subqueries, list) else 0,
        "semantic_count": semantic_count,
        "keyword_count": keyword_count,
        "fused_count": len(state.get("fused_candidates") or []),
        "reranked_count": len(state.get("reranked_chunks") or []),
        "context_count": len(state.get("context_chunks") or []),
        "selected_strategy": str(route) if route is not None else None,
        "fallback_path": metrics.get("fallback_path") or metrics.get("relation_scope_fallback"),
        "context_tokens": metrics.get("context_token_count")
        or metrics.get("selected_token_count"),
        "grounding_score": getattr(grounding, "score", None)
        if grounding is not None
        else None,
        "citation_valid": getattr(citation, "valid", None)
        if citation is not None
        else None,
        "total_query_latency_ms": total_query_latency_ms,
    }
    return _safe_event(event)
