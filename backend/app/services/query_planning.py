from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.config import Settings, get_settings
from app.core.contracts import RetrievalStrategy
from app.core.retry import retry_sync
from app.graphs.query_formatting import extract_chat_content, normalize_text
from app.graphs.query_prompts import (
    QUERY_PLANNING_RESPONSE_FORMAT,
    build_query_planning_messages,
)
from app.models.schemas import QueryPlan, QuerySubquery, RetrievalFilters
from app.services.shopaikey_client import create_shopaikey_client

logger = logging.getLogger(__name__)

_FILTER_FIELDS = frozenset(RetrievalFilters.model_fields)
_PLAN_FIELDS = frozenset(
    {"is_complex", "strategy", "subqueries", "inferred_filters", "needs_relations"}
)
_SUBQUERY_FIELDS = frozenset({"id", "text"})


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_shopaikey_client(
    settings: Settings,
    shopaikey_client: Any | None = None,
) -> Any:
    return (
        shopaikey_client
        if shopaikey_client is not None
        else create_shopaikey_client(settings)
    )


def _fallback_strategy(settings: Settings) -> RetrievalStrategy:
    if settings.ENABLE_KEYWORD_SEARCH:
        return RetrievalStrategy.HYBRID
    return RetrievalStrategy.SEMANTIC


def _fallback_plan(question: str, settings: Settings) -> QueryPlan:
    return QueryPlan(
        is_complex=False,
        strategy=_fallback_strategy(settings),
        subqueries=[QuerySubquery(id="q1", text=question)],
        inferred_filters=RetrievalFilters(),
        needs_relations=False,
    )


def _json_payload_from_content(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, character in enumerate(content):
            if character != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(content[index:])
            except json.JSONDecodeError:
                continue
            return payload
        raise


def _explicit_filter_keys(explicit_filters: Any) -> set[str]:
    if explicit_filters is None:
        return set()
    if isinstance(explicit_filters, RetrievalFilters):
        return {field for field in explicit_filters.model_fields_set if field in _FILTER_FIELDS}
    if isinstance(explicit_filters, Mapping):
        return {str(field) for field in explicit_filters if field in _FILTER_FIELDS}
    return set(_FILTER_FIELDS)


def _normalize_explicit_filters(
    explicit_filters: RetrievalFilters | Mapping[str, Any] | None,
) -> tuple[RetrievalFilters | None, set[str]]:
    keys = _explicit_filter_keys(explicit_filters)
    if explicit_filters is None:
        return None, keys
    if isinstance(explicit_filters, RetrievalFilters):
        return explicit_filters, keys
    return RetrievalFilters.model_validate(explicit_filters), keys


def _merge_filters(
    inferred_filters: RetrievalFilters,
    explicit_filters: RetrievalFilters | None,
    explicit_keys: set[str],
) -> RetrievalFilters:
    merged = inferred_filters.model_dump(mode="json")
    if explicit_filters is not None:
        explicit_data = explicit_filters.model_dump(mode="json")
        for key in explicit_keys:
            merged[key] = explicit_data[key]
    return RetrievalFilters.model_validate(merged)


def _normalize_subqueries(
    raw_subqueries: Any,
    *,
    original_question: str,
    max_subqueries: int,
) -> list[QuerySubquery]:
    normalized: list[QuerySubquery] = []
    seen_text: set[str] = set()

    if isinstance(raw_subqueries, Sequence) and not isinstance(
        raw_subqueries, (str, bytes)
    ):
        for raw_subquery in raw_subqueries:
            if not isinstance(raw_subquery, Mapping):
                continue
            text = normalize_text(raw_subquery.get("text"))
            if text is None:
                continue
            text_key = text.casefold()
            if text_key in seen_text:
                continue
            subquery_id = normalize_text(raw_subquery.get("id")) or f"q{len(normalized) + 1}"
            normalized.append(QuerySubquery(id=subquery_id, text=text))
            seen_text.add(text_key)
            if len(normalized) >= max_subqueries:
                break

    if not normalized:
        return [QuerySubquery(id="q1", text=original_question)]
    return normalized


def _validate_response_shape(payload: Mapping[str, Any]) -> None:
    extra_plan_fields = set(payload) - _PLAN_FIELDS
    if extra_plan_fields:
        raise ValueError("planner response included unsupported fields")

    raw_subqueries = payload.get("subqueries")
    if raw_subqueries is None:
        return
    if not isinstance(raw_subqueries, Sequence) or isinstance(
        raw_subqueries, (str, bytes)
    ):
        raise ValueError("planner subqueries must be a list")
    for raw_subquery in raw_subqueries:
        if not isinstance(raw_subquery, Mapping):
            raise ValueError("planner subquery must be an object")
        if set(raw_subquery) != _SUBQUERY_FIELDS:
            raise ValueError("planner subquery shape is invalid")


def _plan_from_payload(
    payload: Any,
    *,
    question: str,
    settings: Settings,
    explicit_filters: RetrievalFilters | None,
    explicit_filter_keys: set[str],
) -> QueryPlan:
    if not isinstance(payload, Mapping):
        raise ValueError("planner response must be a JSON object")
    _validate_response_shape(payload)

    strategy = RetrievalStrategy(str(payload["strategy"]))
    inferred_filters = RetrievalFilters.model_validate(
        payload.get("inferred_filters") or {}
    )
    merged_filters = _merge_filters(
        inferred_filters,
        explicit_filters,
        explicit_filter_keys,
    )

    return QueryPlan(
        is_complex=bool(payload.get("is_complex", False)),
        strategy=strategy,
        subqueries=_normalize_subqueries(
            payload.get("subqueries"),
            original_question=question,
            max_subqueries=settings.QUERY_MAX_SUBQUERIES,
        ),
        inferred_filters=merged_filters,
        needs_relations=bool(payload.get("needs_relations", False)),
    )


def plan_query(
    question: str,
    document_ids: Sequence[Any] | None,
    explicit_filters: RetrievalFilters | Mapping[str, Any] | None,
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> QueryPlan:
    resolved_settings = _resolve_settings(settings)
    normalized_question = normalize_text(question)
    if normalized_question is None:
        raise ValueError("question is required")

    try:
        normalized_explicit_filters, explicit_filter_keys = _normalize_explicit_filters(
            explicit_filters
        )
        client = _resolve_shopaikey_client(resolved_settings, shopaikey_client)
        response = retry_sync(
            "query_planner",
            lambda: client.chat.completions.create(
                model=resolved_settings.SHOPAIKEY_INPUT_MODEL,
                messages=build_query_planning_messages(
                    question=normalized_question,
                    document_ids=list(document_ids or []),
                    explicit_filters=(
                        normalized_explicit_filters.model_dump(mode="json")
                        if normalized_explicit_filters is not None
                        else None
                    ),
                    max_subqueries=resolved_settings.QUERY_MAX_SUBQUERIES,
                ),
                temperature=resolved_settings.QUERY_PLANNER_TEMPERATURE,
                max_tokens=resolved_settings.QUERY_PLANNER_MAX_TOKENS,
                response_format=QUERY_PLANNING_RESPONSE_FORMAT,
            ),
            settings=resolved_settings,
        )
        content = extract_chat_content(response)
        if content is None:
            raise ValueError("planner response was empty")
        return _plan_from_payload(
            _json_payload_from_content(content),
            question=normalized_question,
            settings=resolved_settings,
            explicit_filters=normalized_explicit_filters,
            explicit_filter_keys=explicit_filter_keys,
        )
    except Exception as exc:
        logger.warning("Query planning failed; using deterministic fallback: %s", exc)
        return _fallback_plan(normalized_question, resolved_settings)


__all__ = ["plan_query"]
