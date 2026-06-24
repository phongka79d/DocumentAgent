from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from app.core.config import Settings
from app.core.errors import safe_detail
from app.core.retry import RetryAttempt, retry_sync
from app.graphs.query_steps import (
    prepare as _prepare_steps,
    planning as _planning_steps,
    retrieval as _retrieval_steps,
    answering as _answering_steps,
    verification as _verification_steps,
    persistence as _persistence_steps,
)
from app.graphs.query_steps.dependencies import QueryStepDependencies
from app.rag.formatting import (
    build_context_prompt,
    build_source_citations,
    extract_chat_content,
    message_metadata,
    normalize_text,
    resolve_context_chunks,
)
from app.rag.prompts import (
    ANSWER_SYSTEM_PROMPT,
    ANSWER_USER_PROMPT_TEMPLATE,
    NO_RELEVANT_INFORMATION_MESSAGE,
    SAFE_INSUFFICIENT_CONTEXT_MESSAGE,
    build_answer_messages,
    build_regeneration_messages,
)
from app.core.contracts import RetrievalStrategy
from app.models.schemas import RetrievalFilters
from app.models.schemas import QueryPlan, QuerySubquery
from app.services import messages as message_service
from app.services import query_planning, retrieval, retrieval_context, score_fusion
from app.services import relations as relation_service
from app.services.citation_validation import assign_citation_keys, validate_answer_citations
from app.services import grounding
from app.services import citation_validation
from app.services.shopaikey_client import create_shopaikey_client

logger = logging.getLogger(__name__)

DEFAULT_QUERY_ERROR = "Query failed"

# Compatibility for callers that historically imported this through query_nodes.
_build_source_citations = build_source_citations


def _resolve_settings(settings: Settings | None = None) -> Settings:
    from app.core.config import get_settings

    return settings if settings is not None else get_settings()


def _normalize_document_ids(
    document_ids: Any,
) -> list[str]:
    from app.graphs.query_steps.prepare import _normalize_document_ids as _norm

    return _norm(document_ids)


def _normalize_filters(filters: Any) -> dict[str, Any]:
    if isinstance(filters, RetrievalFilters):
        model = filters
    else:
        model = RetrievalFilters.model_validate(filters)
    return model.model_dump(mode="json", exclude_none=True)


def _filters_model(filters: Any) -> RetrievalFilters:
    if isinstance(filters, RetrievalFilters):
        return filters
    return RetrievalFilters.model_validate(filters or {})


def _query_plan(state: Mapping[str, Any]) -> QueryPlan | None:
    raw_plan = state.get("query_plan")
    if raw_plan is None:
        return None
    if isinstance(raw_plan, QueryPlan):
        return raw_plan
    return QueryPlan.model_validate(raw_plan)


def _question_text(state: Mapping[str, Any]) -> str | None:
    return normalize_text(state.get("prepared_query") or state.get("question"))


def _subqueries_from_plan(plan: QueryPlan) -> list[QuerySubquery]:
    return [QuerySubquery.model_validate(item) for item in plan.subqueries]


def _has_active_filter(filters: RetrievalFilters) -> bool:
    data = filters.model_dump(mode="json")
    return any(value not in (None, [], "") for value in data.values())


def _with_subquery_id(candidate: Mapping[str, Any], subquery_id: str) -> dict[str, Any]:
    normalized = dict(candidate)
    existing_ids = normalized.get("subquery_ids") or []
    subquery_ids: list[str] = []
    for value in [*existing_ids, subquery_id]:
        text = normalize_text(value)
        if text is not None and text not in subquery_ids:
            subquery_ids.append(text)
    normalized["subquery_ids"] = subquery_ids
    return normalized


def _candidate_groups(path_candidates: Mapping[str, Any]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for candidates in path_candidates.values():
        if not isinstance(candidates, list):
            continue
        groups.append([dict(candidate) for candidate in candidates if isinstance(candidate, Mapping)])
    return groups


def _subquery_ids(plan: QueryPlan | None) -> list[str]:
    if plan is None:
        return []
    ids: list[str] = []
    for subquery in plan.subqueries:
        text = normalize_text(subquery.id)
        if text is not None and text not in ids:
            ids.append(text)
    return ids


def _select_with_subquery_coverage(
    fused_candidates: list[dict[str, Any]],
    *,
    subquery_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    if len(subquery_ids) <= 1:
        return fused_candidates[:limit]

    selected: list[dict[str, Any]] = []
    selected_chunks: set[str] = set()
    for subquery_id in subquery_ids:
        candidate = next(
            (
                item
                for item in fused_candidates
                if subquery_id in (item.get("subquery_ids") or [])
                and normalize_text(item.get("chunk_id")) not in selected_chunks
            ),
            None,
        )
        if candidate is None:
            continue
        selected.append(candidate)
        selected_chunks.add(str(candidate["chunk_id"]))
        if len(selected) >= limit:
            return selected

    for candidate in fused_candidates:
        chunk_id = normalize_text(candidate.get("chunk_id"))
        if chunk_id is None or chunk_id in selected_chunks:
            continue
        selected.append(candidate)
        selected_chunks.add(chunk_id)
        if len(selected) >= limit:
            break
    return selected


def _path_name(path_key: str) -> str:
    return path_key.rsplit(":", 1)[-1]


def _attempt_count(attempts: list[RetryAttempt]) -> int:
    if not attempts:
        return 1
    return max(attempt.attempt for attempt in attempts)


def _merge_retry_metrics(
    metrics: dict[str, Any],
    node_name: str,
    attempts: list[RetryAttempt],
) -> dict[str, Any]:
    if not attempts:
        return metrics
    attempt_count = _attempt_count(attempts)
    if attempt_count <= 1 and attempts[-1].error_code == "ok":
        return metrics
    retry_attempts = dict(metrics.get("retry_attempts") or {})
    retry_attempts[node_name] = max(
        int(retry_attempts.get(node_name, 1)),
        attempt_count,
    )
    metrics["retry_attempts"] = retry_attempts
    return metrics


def _route_failure_message(strategy: RetrievalStrategy) -> str:
    if strategy is RetrievalStrategy.SEMANTIC:
        return "semantic retrieval failed"
    if strategy is RetrievalStrategy.KEYWORD:
        return "keyword retrieval failed"
    if strategy is RetrievalStrategy.RELATION:
        return "relation retrieval failed"
    if strategy is RetrievalStrategy.METADATA:
        return "metadata retrieval failed"
    return "hybrid retrieval failed"


def _query_step_dependencies() -> QueryStepDependencies:
    return QueryStepDependencies(
        retrieval=retrieval,
        retrieval_context=retrieval_context,
        query_planning=query_planning,
        relations=relation_service,
        grounding=grounding,
        citation_validation=citation_validation,
        message_service=message_service,
        build_context_prompt=build_context_prompt,
        build_source_citations=build_source_citations,
        extract_chat_content=extract_chat_content,
        message_metadata=message_metadata,
        create_shopaikey_client=create_shopaikey_client,
    )


# --- Preparation ---


def prepare_query_node(state: Mapping[str, Any], *, settings: Settings | None = None) -> dict[str, Any]:
    return _prepare_steps.prepare_query_node(state, settings=settings)


# --- Planning ---


def plan_query_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    return _planning_steps.plan_query_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
    )


def resolve_relation_scope_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    return _planning_steps.resolve_relation_scope_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
    )


# --- Retrieval ---


def retrieve_candidates_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
    shopaikey_client: Any | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    return _retrieval_steps.retrieve_candidates_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
        qdrant_client=qdrant_client,
        shopaikey_client=shopaikey_client,
        supabase_client=supabase_client,
    )


def fuse_candidates_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _retrieval_steps.fuse_candidates_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
    )


def retrieve_qdrant_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
    shopaikey_client: Any | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    return _retrieval_steps.retrieve_qdrant_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
        qdrant_client=qdrant_client,
        shopaikey_client=shopaikey_client,
        supabase_client=supabase_client,
    )


def jina_rerank_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    jina_client: Any | None = None,
) -> dict[str, Any]:
    return _retrieval_steps.jina_rerank_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
        jina_client=jina_client,
    )


def rerank_candidates_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    jina_client: Any | None = None,
) -> dict[str, Any]:
    return jina_rerank_node(state, settings=settings, jina_client=jina_client)


def expand_neighbor_context_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    return _retrieval_steps.expand_neighbor_context_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
        supabase_client=supabase_client,
    )


def expand_context_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    return expand_neighbor_context_node(
        state,
        settings=settings,
        supabase_client=supabase_client,
    )


# --- Answering ---


def generate_answer_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    return _answering_steps.generate_answer_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
        shopaikey_client=shopaikey_client,
    )


def regenerate_answer_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    return _answering_steps.regenerate_answer_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
        shopaikey_client=shopaikey_client,
    )


# --- Verification ---


def _compact_grounding_feedback(state: Mapping[str, Any]) -> str:
    validation = state.get("citation_validation_result")
    result = state.get("grounding_result")
    parts: list[str] = []
    if validation is not None and not getattr(validation, "valid", False):
        invalid_keys = getattr(validation, "invalid_keys", [])
        if invalid_keys:
            parts.append(f"Invalid citation keys: {', '.join(invalid_keys)}.")
        if getattr(validation, "missing_citations", False):
            parts.append("Factual claims need valid [S<number>] citations.")
    if result is not None:
        unsupported = getattr(result, "unsupported_claims", [])
        missing = getattr(result, "missing_citations", [])
        if unsupported:
            parts.append(f"Unsupported claims: {'; '.join(unsupported[:3])}.")
        if missing:
            parts.append(f"Missing citations: {'; '.join(missing[:3])}.")
    return " ".join(parts) or "Previous answer was not verified. Use only cited context."


def validate_citations_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _verification_steps.validate_citations_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
    )


def verify_grounding_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    return _verification_steps.verify_grounding_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
        shopaikey_client=shopaikey_client,
    )


def finalize_answer_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _verification_steps.finalize_answer_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
    )


# --- Persistence ---


def save_message_optional_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    return _persistence_steps.save_message_optional_node(
        state,
        settings=settings,
        deps=_query_step_dependencies(),
        supabase_client=supabase_client,
    )


__all__ = [
    "ANSWER_SYSTEM_PROMPT",
    "ANSWER_USER_PROMPT_TEMPLATE",
    "DEFAULT_QUERY_ERROR",
    "NO_RELEVANT_INFORMATION_MESSAGE",
    "SAFE_INSUFFICIENT_CONTEXT_MESSAGE",
    "expand_neighbor_context_node",
    "expand_context_node",
    "finalize_answer_node",
    "fuse_candidates_node",
    "generate_answer_node",
    "jina_rerank_node",
    "plan_query_node",
    "prepare_query_node",
    "regenerate_answer_node",
    "rerank_candidates_node",
    "retrieve_qdrant_node",
    "retrieve_candidates_node",
    "resolve_relation_scope_node",
    "save_message_optional_node",
    "validate_citations_node",
    "verify_grounding_node",
]
