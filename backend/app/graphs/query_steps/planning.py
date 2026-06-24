from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from app.core.config import Settings
from app.core.contracts import RetrievalStrategy
from app.graphs.query_steps.dependencies import QueryStepDependencies
from app.rag.formatting import normalize_text
from app.models.schemas import QueryPlan, QuerySubquery, RetrievalFilters

logger = logging.getLogger(__name__)


def _question_text(state: Mapping[str, Any]) -> str | None:
    return normalize_text(state.get("prepared_query") or state.get("question"))


def _resolve_settings(settings: Settings | None = None) -> Settings:
    from app.core.config import get_settings

    return settings if settings is not None else get_settings()


def _normalize_document_ids(
    document_ids: Any,
) -> list[str]:
    from app.graphs.query_steps.prepare import _normalize_document_ids as _norm

    return _norm(document_ids)


def _filters_model(filters: Any) -> RetrievalFilters:
    if isinstance(filters, RetrievalFilters):
        return filters
    return RetrievalFilters.model_validate(filters or {})


def _query_plan(state: Mapping[str, Any]) -> QueryPlan | None:
    from app.models.schemas import QueryPlan as _QueryPlan

    raw_plan = state.get("query_plan")
    if raw_plan is None:
        return None
    if isinstance(raw_plan, _QueryPlan):
        return raw_plan
    return _QueryPlan.model_validate(raw_plan)


def _subqueries_from_plan(plan: QueryPlan) -> list[QuerySubquery]:
    from app.models.schemas import QuerySubquery as _QuerySubquery

    return [_QuerySubquery.model_validate(item) for item in plan.subqueries]


def plan_query_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    prepared_query = _question_text(state)
    if prepared_query is None:
        return {"error_message": "prepared_query is required"}

    try:
        filters = _filters_model(state.get("filters") or {})
    except Exception:
        return {"error_message": "invalid retrieval filters"}

    plan = deps.query_planning.plan_query(
        prepared_query,
        _normalize_document_ids(state.get("document_ids")),
        filters,
        settings=resolved_settings,
    )
    return {
        "query_plan": plan,
        "subqueries": _subqueries_from_plan(plan),
        "route": plan.strategy,
        "filters": plan.inferred_filters.model_dump(mode="json", exclude_none=True),
    }


def resolve_relation_scope_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    plan = _query_plan(state)
    if plan is None:
        return {"error_message": "query_plan is required"}

    document_ids = _normalize_document_ids(state.get("document_ids"))
    if plan.strategy is not RetrievalStrategy.RELATION and not plan.needs_relations:
        return {"relation_document_ids": document_ids}

    try:
        scoped_document_ids = deps.relations.resolve_related_document_scope(
            document_ids,
            settings=resolved_settings,
        )
    except Exception as exc:
        logger.warning("Relation scope resolution failed; using original scope: %s", exc)
        scoped_document_ids = document_ids
        metrics = dict(state.get("retrieval_metrics") or {})
        metrics["relation_scope_fallback"] = "original_scope"
        return {
            "document_ids": scoped_document_ids,
            "relation_document_ids": scoped_document_ids,
            "retrieval_metrics": metrics,
        }

    return {
        "document_ids": scoped_document_ids,
        "relation_document_ids": scoped_document_ids,
    }
