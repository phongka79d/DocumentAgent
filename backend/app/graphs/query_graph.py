from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.config import Settings, get_settings
from app.core.errors import safe_detail
from app.graphs.query_state import QueryState
from app.services import observability

from . import query_nodes

DEFAULT_QUERY_ERROR = "Query failed"
END_ROUTE = "end"
FAILURE_ROUTE = "end"
PROVIDER_BY_NODE = {
    "plan_query": "shopaikey",
    "retrieve_candidates": "qdrant/supabase",
    "rerank_candidates": "jina",
    "expand_context": "supabase",
    "generate_answer": "shopaikey",
    "verify_grounding": "shopaikey",
    "regenerate_answer": "shopaikey",
    "save_message_optional": "supabase",
}


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
        started_perf = observability.perf_now()
        started_at = observability.now_utc()
        status = "completed"
        error_code: str | None = None
        try:
            result = _call_node(node_fn, state, settings=settings)
        except Exception as exc:  # pragma: no cover - defensive graph guard
            status = "failed"
            error_code = f"{node_name}_exception"
            result = {
                "error_message": safe_detail(
                    f"{node_name} failed: {exc}",
                    fallback=DEFAULT_QUERY_ERROR,
                )
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
                    "error_message": safe_detail(
                        f"{node_name} returned invalid state",
                        fallback=DEFAULT_QUERY_ERROR,
                    )
                }
        if isinstance(result, Mapping) and result.get("error_message"):
            status = "failed"
            error_code = f"{node_name}_failed"

        finished_at = observability.now_utc()
        event = observability.node_trace_event(
            node_name=node_name,
            status=status,
            attempt=_attempt_value(node_name, state, result),
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=observability.duration_ms(started_perf),
            provider=PROVIDER_BY_NODE.get(node_name),
            input_count=_input_count(node_name, state),
            output_count=_output_count(node_name, result),
            route=_route_value(result.get("route") or state.get("route")),
            fallback=_fallback_value(result.get("retrieval_metrics") or state.get("retrieval_metrics")),
            error_code=error_code,
        )
        workflow_trace = [
            *list(state.get("workflow_trace") or []),
            event,
        ]
        return {**dict(result), "workflow_trace": workflow_trace}

    _wrapped.__name__ = getattr(node_fn, "__name__", node_name)
    return _wrapped


def _next_attempt(node_name: str, state: Mapping[str, Any]) -> int:
    trace = state.get("workflow_trace") or []
    if not isinstance(trace, list):
        return 1
    return 1 + sum(
        1
        for event in trace
        if isinstance(event, Mapping) and event.get("node_name") == node_name
    )


def _attempt_value(
    node_name: str,
    state: Mapping[str, Any],
    result: Mapping[str, Any],
) -> int:
    metrics = result.get("retrieval_metrics") or state.get("retrieval_metrics")
    if isinstance(metrics, Mapping):
        retry_attempts = metrics.get("retry_attempts")
        if isinstance(retry_attempts, Mapping):
            value = retry_attempts.get(node_name)
            if value is not None:
                try:
                    return max(1, int(value))
                except (TypeError, ValueError):
                    pass
    return _next_attempt(node_name, state)


def _route_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _fallback_value(metrics: Any) -> str | None:
    if not isinstance(metrics, Mapping):
        return None
    fallback = metrics.get("fallback_path") or metrics.get("relation_scope_fallback")
    return str(fallback) if fallback is not None else None


def _input_count(node_name: str, state: Mapping[str, Any]) -> int | None:
    if node_name == "retrieve_candidates":
        subqueries = state.get("subqueries")
        return len(subqueries) if isinstance(subqueries, list) else None
    if node_name in {"fuse_candidates", "rerank_candidates"}:
        chunks = state.get("retrieved_chunks")
        return len(chunks) if isinstance(chunks, list) else None
    if node_name in {"expand_context", "generate_answer", "validate_citations", "verify_grounding", "regenerate_answer"}:
        chunks = state.get("context_chunks") or state.get("reranked_chunks")
        return len(chunks) if isinstance(chunks, list) else None
    return None


def _output_count(node_name: str, result: Mapping[str, Any]) -> int | None:
    if node_name == "retrieve_candidates":
        candidates = result.get("path_candidates")
        if isinstance(candidates, Mapping):
            return sum(len(value) for value in candidates.values() if isinstance(value, list))
    if node_name in {"fuse_candidates"}:
        chunks = result.get("retrieved_chunks")
        return len(chunks) if isinstance(chunks, list) else None
    if node_name == "rerank_candidates":
        chunks = result.get("reranked_chunks")
        return len(chunks) if isinstance(chunks, list) else None
    if node_name == "expand_context":
        chunks = result.get("context_chunks")
        return len(chunks) if isinstance(chunks, list) else None
    if node_name in {"validate_citations", "generate_answer", "regenerate_answer"}:
        sources = result.get("sources")
        return len(sources) if isinstance(sources, list) else None
    return None


def _route_or_end(next_node: str) -> Callable[[Mapping[str, Any]], str]:
    def _router(state: Mapping[str, Any]) -> str:
        if state.get("error_message"):
            return END_ROUTE
        return next_node

    return _router


def _route_after_grounding(settings: Settings) -> Callable[[Mapping[str, Any]], str]:
    def _router(state: Mapping[str, Any]) -> str:
        if state.get("error_message"):
            return END_ROUTE
        if state.get("answer_verified") is True:
            return "finalize_answer"
        if state.get("grounding_provider_failed"):
            return "finalize_answer"
        if "answer_verified" not in state:
            return "finalize_answer"
        verification_attempt_count = int(state.get("verification_attempt_count") or 0)
        if verification_attempt_count <= settings.GROUNDING_MAX_REGENERATIONS:
            return "regenerate_answer"
        return "finalize_answer"

    return _router


def _route_after_finalize(state: Mapping[str, Any]) -> str:
    if state.get("error_message"):
        return END_ROUTE
    if state.get("answer_verified") is False:
        return END_ROUTE
    return "save_message_optional"


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
        "regenerate_answer",
        _wrap_node(
            "regenerate_answer",
            query_nodes.regenerate_answer_node,
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
        _route_after_grounding(resolved_settings),
        {
            "finalize_answer": "finalize_answer",
            "regenerate_answer": "regenerate_answer",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "regenerate_answer",
        _route_or_end("validate_citations"),
        {
            "validate_citations": "validate_citations",
            END_ROUTE: END,
        },
    )
    graph.add_conditional_edges(
        "finalize_answer",
        _route_after_finalize,
        {
            "save_message_optional": "save_message_optional",
            END_ROUTE: END,
        },
    )
    graph.add_edge("save_message_optional", END)

    return graph.compile()


__all__ = ["build_query_graph"]
