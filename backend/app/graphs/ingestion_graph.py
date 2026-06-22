from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.config import Settings, get_settings
from app.core.errors import safe_detail
from app.services import observability
from . import ingestion_nodes
from app.graphs.ingestion_state import IngestionState

DEFAULT_INGESTION_ERROR = "Ingestion failed"
FAILURE_ROUTE = "mark_failed"
END_ROUTE = "end"
PROVIDER_BY_NODE = {
    "parse_document": "parser",
    "save_chunks": "supabase",
    "summarize_document": "shopaikey",
    "embed_chunks": "shopaikey",
    "upsert_qdrant": "qdrant",
    "update_document_relations": "shopaikey",
}


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _wrap_node(
    node_name: str,
    node_fn: Callable[[IngestionState], dict[str, Any] | None],
) -> Callable[[IngestionState], dict[str, Any]]:
    def _wrapped(state: IngestionState) -> dict[str, Any]:
        started_perf = observability.perf_now()
        started_at = observability.now_utc()
        status = "completed"
        error_code: str | None = None
        try:
            result = node_fn(state)
        except Exception as exc:  # pragma: no cover - defensive graph guard
            status = "failed"
            error_code = f"{node_name}_exception"
            result = {
                "status": "failed",
                "error_message": safe_detail(
                    f"{node_name} failed: {exc}",
                    fallback=DEFAULT_INGESTION_ERROR,
                ),
            }
        else:
            if result is None:
                result = {}
            elif isinstance(result, Mapping):
                result = dict(result)
            else:
                status = "failed"
                error_code = "invalid_state"
                result = {
                    "status": "failed",
                    "error_message": safe_detail(
                        f"{node_name} returned invalid state",
                        fallback=DEFAULT_INGESTION_ERROR,
                    ),
                }
        if isinstance(result, Mapping) and result.get("status") == "failed":
            status = "failed"
            error_code = f"{node_name}_failed"

        retry_attempts = result.get("retry_attempts") if isinstance(result, Mapping) else None
        if not isinstance(retry_attempts, Mapping):
            retry_attempts = state.get("retry_attempts") or {}
        finished_at = observability.now_utc()
        event = observability.node_trace_event(
            node_name=node_name,
            status=status,
            attempt=int(retry_attempts.get(node_name, 1)),
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=observability.duration_ms(started_perf),
            provider=PROVIDER_BY_NODE.get(node_name),
            input_count=_input_count(node_name, state),
            output_count=_output_count(node_name, result),
            route=END_ROUTE if node_name == "mark_ready" else None,
            fallback=FAILURE_ROUTE if node_name == "mark_failed" else None,
            error_code=error_code,
        )
        workflow_trace = [
            *list(state.get("workflow_trace") or []),
            event,
        ]
        return {**dict(result), "workflow_trace": workflow_trace}

    _wrapped.__name__ = getattr(node_fn, "__name__", node_name)
    return _wrapped


def _input_count(node_name: str, state: Mapping[str, Any]) -> int | None:
    if node_name in {"save_chunks", "summarize_document", "embed_chunks", "upsert_qdrant"}:
        chunks = state.get("chunks")
        return len(chunks) if isinstance(chunks, list) else 0
    if node_name == "update_document_relations":
        summaries = state.get("summary_records")
        return len(summaries) if isinstance(summaries, list) else 0
    return None


def _output_count(node_name: str, result: Mapping[str, Any]) -> int | None:
    if node_name in {"chunk_document", "save_chunks", "upsert_qdrant"}:
        chunks = result.get("chunks")
        return len(chunks) if isinstance(chunks, list) else None
    if node_name == "summarize_document":
        summaries = result.get("summary_records")
        return len(summaries) if isinstance(summaries, list) else 0
    if node_name == "embed_chunks":
        embeddings = result.get("embeddings")
        return len(embeddings) if isinstance(embeddings, list) else None
    if node_name == "update_document_relations":
        relation_result = result.get("relation_update_result")
        if isinstance(relation_result, Mapping):
            return int(relation_result.get("accepted_relation_count") or 0)
    return None


def _route_or_fail(next_node: str) -> Callable[[Mapping[str, Any]], str]:
    def _router(state: Mapping[str, Any]) -> str:
        if state.get("status") == "failed":
            return FAILURE_ROUTE
        return next_node

    return _router


def build_ingestion_graph(settings: Settings | None = None):
    _resolve_settings(settings)

    graph = StateGraph(IngestionState)

    graph.add_node(
        "load_document_record",
        _wrap_node("load_document_record", ingestion_nodes.load_document_record_node),
    )
    graph.add_node(
        "mark_processing",
        _wrap_node("mark_processing", ingestion_nodes.mark_processing_node),
    )
    graph.add_node(
        "parse_document",
        _wrap_node("parse_document", ingestion_nodes.parse_document_node),
    )
    graph.add_node(
        "chunk_document",
        _wrap_node("chunk_document", ingestion_nodes.chunk_document_node),
    )
    graph.add_node(
        "save_chunks",
        _wrap_node("save_chunks", ingestion_nodes.save_chunks_node),
    )
    graph.add_node(
        "summarize_document",
        _wrap_node("summarize_document", ingestion_nodes.summarize_document_node),
    )
    graph.add_node(
        "embed_chunks",
        _wrap_node("embed_chunks", ingestion_nodes.embed_chunks_node),
    )
    graph.add_node(
        "upsert_qdrant",
        _wrap_node("upsert_qdrant", ingestion_nodes.upsert_qdrant_node),
    )
    graph.add_node(
        "update_document_relations",
        _wrap_node(
            "update_document_relations",
            ingestion_nodes.update_document_relations_node,
        ),
    )
    graph.add_node("mark_ready", _wrap_node("mark_ready", ingestion_nodes.mark_ready_node))
    graph.add_node("mark_failed", _wrap_node("mark_failed", ingestion_nodes.mark_failed_node))

    graph.add_edge(START, "load_document_record")
    graph.add_conditional_edges(
        "load_document_record",
        _route_or_fail("mark_processing"),
        {
            "mark_processing": "mark_processing",
            FAILURE_ROUTE: "mark_failed",
        },
    )
    graph.add_conditional_edges(
        "mark_processing",
        _route_or_fail("parse_document"),
        {
            "parse_document": "parse_document",
            FAILURE_ROUTE: "mark_failed",
        },
    )
    graph.add_conditional_edges(
        "parse_document",
        _route_or_fail("chunk_document"),
        {
            "chunk_document": "chunk_document",
            FAILURE_ROUTE: "mark_failed",
        },
    )
    graph.add_conditional_edges(
        "chunk_document",
        _route_or_fail("save_chunks"),
        {
            "save_chunks": "save_chunks",
            FAILURE_ROUTE: "mark_failed",
        },
    )
    graph.add_conditional_edges(
        "save_chunks",
        _route_or_fail("summarize_document"),
        {
            "summarize_document": "summarize_document",
            FAILURE_ROUTE: "mark_failed",
        },
    )
    graph.add_conditional_edges(
        "summarize_document",
        _route_or_fail("embed_chunks"),
        {
            "embed_chunks": "embed_chunks",
            FAILURE_ROUTE: "mark_failed",
        },
    )
    graph.add_conditional_edges(
        "embed_chunks",
        _route_or_fail("upsert_qdrant"),
        {
            "upsert_qdrant": "upsert_qdrant",
            FAILURE_ROUTE: "mark_failed",
        },
    )
    graph.add_conditional_edges(
        "upsert_qdrant",
        _route_or_fail("update_document_relations"),
        {
            "update_document_relations": "update_document_relations",
            FAILURE_ROUTE: "mark_failed",
        },
    )
    graph.add_conditional_edges(
        "update_document_relations",
        _route_or_fail("mark_ready"),
        {
            "mark_ready": "mark_ready",
            FAILURE_ROUTE: "mark_failed",
        },
    )
    graph.add_conditional_edges(
        "mark_ready",
        _route_or_fail(END_ROUTE),
        {
            END_ROUTE: END,
            FAILURE_ROUTE: "mark_failed",
        },
    )
    graph.add_edge("mark_failed", END)

    return graph.compile()
