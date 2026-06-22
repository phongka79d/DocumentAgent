from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.config import Settings, get_settings
from app.core.errors import safe_detail
from . import ingestion_nodes
from app.graphs.ingestion_state import IngestionState

DEFAULT_INGESTION_ERROR = "Ingestion failed"
FAILURE_ROUTE = "mark_failed"
END_ROUTE = "end"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _wrap_node(
    node_name: str,
    node_fn: Callable[[IngestionState], dict[str, Any] | None],
) -> Callable[[IngestionState], dict[str, Any]]:
    def _wrapped(state: IngestionState) -> dict[str, Any]:
        try:
            result = node_fn(state)
        except Exception as exc:  # pragma: no cover - defensive graph guard
            return {
                "status": "failed",
                "error_message": safe_detail(
                    f"{node_name} failed: {exc}",
                    fallback=DEFAULT_INGESTION_ERROR,
                ),
            }

        if result is None:
            return {}
        if isinstance(result, Mapping):
            return dict(result)

        return {
            "status": "failed",
            "error_message": safe_detail(
                f"{node_name} returned invalid state",
                fallback=DEFAULT_INGESTION_ERROR,
            ),
        }

    _wrapped.__name__ = getattr(node_fn, "__name__", node_name)
    return _wrapped


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
