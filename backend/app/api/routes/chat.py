from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, status
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import safe_http_exception
from app.graphs.query_graph import build_query_graph
from app.models.schemas import ChatRequest, ChatResponse
from app.services import observability

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)

DEFAULT_CHAT_ERROR = "Query failed"


def _resolve_settings() -> Settings:
    return get_settings()


def _response_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    error_message = result.get("error_message")
    if error_message:
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            str(error_message),
        )

    payload = {
        "answer": result.get("answer"),
        "sources": result.get("sources") or [],
    }
    if result.get("trace_id") is not None:
        payload["trace_id"] = result["trace_id"]
    return payload


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    settings = _resolve_settings()
    started_perf = observability.perf_now()
    run = None
    run_id = None
    if settings.ENABLE_WORKFLOW_TRACING:
        run = observability.create_workflow_run(
            workflow_type="query",
            entity_id=request.question[:120],
            started_at=observability.now_utc(),
        )
        run_id = run.get("id") if isinstance(run, Mapping) else None
    try:
        graph = build_query_graph(settings=settings)
        initial_state = request.model_dump(mode="json", exclude_none=True)
        if run_id is not None:
            initial_state["trace_id"] = str(run_id)
        result = graph.invoke(initial_state)
    except Exception as exc:  # pragma: no cover - defensive API boundary
        if run_id is not None:
            observability.update_workflow_run(
                run_id,
                status="failed",
                error_code="query_api_exception",
                error_message=DEFAULT_CHAT_ERROR,
                finished_at=observability.now_utc(),
                duration_ms=observability.duration_ms(started_perf),
            )
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            str(exc) or DEFAULT_CHAT_ERROR,
        ) from exc

    if not isinstance(result, Mapping):
        if run_id is not None:
            observability.update_workflow_run(
                run_id,
                status="failed",
                error_code="query_invalid_result",
                error_message=DEFAULT_CHAT_ERROR,
                finished_at=observability.now_utc(),
                duration_ms=observability.duration_ms(started_perf),
            )
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            DEFAULT_CHAT_ERROR,
        )

    if run_id is not None:
        final_status = "failed" if result.get("error_message") else "completed"
        trace = list(result.get("workflow_trace") or [])
        if final_status == "completed":
            trace.append(
                observability.retrieval_totals_event(
                    result,
                    total_query_latency_ms=observability.duration_ms(started_perf),
                )
            )
        observability.update_workflow_run(
            run_id,
            status=final_status,
            trace=trace,
            error_code="query_failed" if final_status == "failed" else None,
            error_message=DEFAULT_CHAT_ERROR if final_status == "failed" else None,
            finished_at=observability.now_utc(),
            duration_ms=observability.duration_ms(started_perf),
        )
        if result.get("trace_id") is None:
            result = {**dict(result), "trace_id": str(run_id)}

    try:
        return ChatResponse.model_validate(_response_payload(result))
    except ValidationError as exc:
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            DEFAULT_CHAT_ERROR,
        ) from exc
