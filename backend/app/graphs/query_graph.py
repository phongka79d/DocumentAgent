from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.config import Settings, get_settings
from app.core.errors import safe_detail
from app.graphs.query_state import QueryState

from . import query_nodes

DEFAULT_QUERY_ERROR = "Query failed"
END_ROUTE = "end"
FAILURE_ROUTE = "end"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _call_node(
    node_fn: Callable[[Mapping[str, Any]], dict[str, Any] | None],
    state: Mapping[str, Any],
    *,
    settings: Settings | None,
) -> dict[str, Any] | None:
    if settings is None:
        return node_fn(state)

    try:
        return node_fn(state, settings=settings)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return node_fn(state)


def _wrap_node(
    node_name: str,
    node_fn: Callable[[Mapping[str, Any]], dict[str, Any] | None],
    *,
    settings: Settings | None = None,
) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    def _wrapped(state: Mapping[str, Any]) -> dict[str, Any]:
        try:
            result = _call_node(node_fn, state, settings=settings)
        except Exception as exc:  # pragma: no cover - defensive graph guard
            return {
                "error_message": safe_detail(
                    f"{node_name} failed: {exc}",
                    fallback=DEFAULT_QUERY_ERROR,
                )
            }

        if result is None:
            return {}
        if isinstance(result, Mapping):
            return dict(result)

        return {
            "error_message": safe_detail(
                f"{node_name} returned invalid state",
                fallback=DEFAULT_QUERY_ERROR,
            )
        }

    _wrapped.__name__ = getattr(node_fn, "__name__", node_name)
    return _wrapped


def _route_or_end(next_node: str) -> Callable[[Mapping[str, Any]], str]:
    def _router(state: Mapping[str, Any]) -> str:
        if state.get("error_message"):
            return END_ROUTE
        return next_node

    return _router


def build_query_graph(settings: Settings | None = None):
    resolved_settings = _resolve_settings(settings)

    graph = StateGraph(QueryState)

    graph.add_node(
        "prepare_query",
        _wrap_node(
            "prepare_query",
            query_nodes.prepare_query_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "plan_query",
        _wrap_node(
            "plan_query",
            query_nodes.plan_query_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "resolve_relation_scope",
        _wrap_node(
            "resolve_relation_scope",
            query_nodes.resolve_relation_scope_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "retrieve_candidates",
        _wrap_node(
            "retrieve_candidates",
            query_nodes.retrieve_candidates_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "fuse_candidates",
        _wrap_node(
            "fuse_candidates",
            query_nodes.fuse_candidates_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "rerank_candidates",
        _wrap_node(
            "rerank_candidates",
            query_nodes.rerank_candidates_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "expand_context",
        _wrap_node(
            "expand_context",
            query_nodes.expand_context_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "generate_answer",
        _wrap_node(
            "generate_answer",
            query_nodes.generate_answer_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "validate_citations",
        _wrap_node(
            "validate_citations",
            query_nodes.validate_citations_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "verify_grounding",
        _wrap_node(
            "verify_grounding",
            query_nodes.verify_grounding_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "finalize_answer",
        _wrap_node(
            "finalize_answer",
            query_nodes.finalize_answer_node,
            settings=resolved_settings,
        ),
    )
    graph.add_node(
        "save_message_optional",
        _wrap_node(
            "save_message_optional",
            query_nodes.save_message_optional_node,
            settings=resolved_settings,
        ),
    )

    graph.add_edge(START, "prepare_query")
    graph.add_conditional_edges(
        "prepare_query",
        _route_or_end("plan_query"),
        {
            "plan_query": "plan_query",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "plan_query",
        _route_or_end("resolve_relation_scope"),
        {
            "resolve_relation_scope": "resolve_relation_scope",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "resolve_relation_scope",
        _route_or_end("retrieve_candidates"),
        {
            "retrieve_candidates": "retrieve_candidates",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "retrieve_candidates",
        _route_or_end("fuse_candidates"),
        {
            "fuse_candidates": "fuse_candidates",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "fuse_candidates",
        _route_or_end("rerank_candidates"),
        {
            "rerank_candidates": "rerank_candidates",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "rerank_candidates",
        _route_or_end("expand_context"),
        {
            "expand_context": "expand_context",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "expand_context",
        _route_or_end("generate_answer"),
        {
            "generate_answer": "generate_answer",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "generate_answer",
        _route_or_end("validate_citations"),
        {
            "validate_citations": "validate_citations",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "validate_citations",
        _route_or_end("verify_grounding"),
        {
            "verify_grounding": "verify_grounding",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "verify_grounding",
        _route_or_end("finalize_answer"),
        {
            "finalize_answer": "finalize_answer",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "finalize_answer",
        _route_or_end("save_message_optional"),
        {
            "save_message_optional": "save_message_optional",
            END_ROUTE: END,
        },
    )
    graph.add_edge("save_message_optional", END)

    return graph.compile()


__all__ = ["build_query_graph"]
