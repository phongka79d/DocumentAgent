from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
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


@router.post("")
def chat(request: ChatRequest) -> StreamingResponse:
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

    def event_generator():
        graph = build_query_graph(settings=settings)
        initial_state = request.model_dump(mode="json", exclude_none=True)
        if run_id is not None:
            initial_state["trace_id"] = str(run_id)

        last_state = {}
        try:
            for event in graph.stream(initial_state, stream_mode="updates"):
                for node_name, state_update in event.items():
                    yield json.dumps({"type": "node", "node": node_name}) + "\n"
                    if isinstance(state_update, Mapping):
                        last_state.update(state_update)

            error_message = last_state.get("error_message")
            if error_message:
                yield json.dumps({"type": "error", "message": str(error_message)}) + "\n"
                if run_id is not None:
                    observability.update_workflow_run(
                        run_id,
                        status="failed",
                        trace=list(last_state.get("workflow_trace") or []),
                        error_code="query_failed",
                        error_message=str(error_message),
                        finished_at=observability.now_utc(),
                        duration_ms=observability.duration_ms(started_perf),
                    )
                return

            if run_id is not None:
                trace = list(last_state.get("workflow_trace") or [])
                trace.append(
                    observability.retrieval_totals_event(
                        last_state,
                        total_query_latency_ms=observability.duration_ms(started_perf),
                    )
                )
                observability.update_workflow_run(
                    run_id,
                    status="completed",
                    trace=trace,
                    finished_at=observability.now_utc(),
                    duration_ms=observability.duration_ms(started_perf),
                )

            response_payload = {
                "answer": last_state.get("answer"),
                "sources": last_state.get("sources") or [],
            }
            if last_state.get("trace_id") is not None:
                response_payload["trace_id"] = last_state["trace_id"]
            elif run_id is not None:
                response_payload["trace_id"] = str(run_id)

            yield json.dumps({"type": "result", "data": response_payload}) + "\n"

        except Exception as exc:
            yield json.dumps({"type": "error", "message": str(exc) or "Query failed"}) + "\n"
            if run_id is not None:
                observability.update_workflow_run(
                    run_id,
                    status="failed",
                    error_code="query_api_exception",
                    error_message=str(exc) or "Query failed",
                    finished_at=observability.now_utc(),
                    duration_ms=observability.duration_ms(started_perf),
                )

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
