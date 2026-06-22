from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.errors import safe_detail
from app.graphs.query_formatting import (
    build_context_prompt,
    build_source_citations,
    extract_chat_content,
    message_metadata,
    normalize_text,
    resolve_context_chunks,
)
from app.graphs.query_prompts import (
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
from app.services.shopaikey_client import create_shopaikey_client

logger = logging.getLogger(__name__)

DEFAULT_QUERY_ERROR = "Query failed"

# Compatibility for callers that historically imported this through query_nodes.
_build_source_citations = build_source_citations


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _normalize_document_ids(
    document_ids: Sequence[UUID | str] | UUID | str | bytes | None,
) -> list[str]:
    if document_ids is None:
        return []

    if isinstance(document_ids, (str, bytes)):
        text = normalize_text(document_ids)
        return [text] if text is not None else []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in document_ids:
        text = normalize_text(value)
        if text is None or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def _question_text(state: Mapping[str, Any]) -> str | None:
    return normalize_text(state.get("prepared_query") or state.get("question"))


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


def prepare_query_node(state: Mapping[str, Any], *, settings: Settings | None = None) -> dict[str, Any]:
    _resolve_settings(settings)

    question = normalize_text(state.get("question"))
    if question is None:
        return {"error_message": "question is required"}

    document_ids = _normalize_document_ids(state.get("document_ids"))
    save_message = bool(state.get("save_message", False))
    result = {
        "question": question,
        "prepared_query": question,
        "document_ids": document_ids,
        "save_message": save_message,
    }
    if "filters" in state:
        try:
            result["filters"] = _normalize_filters(state.get("filters") or {})
        except Exception:
            return {"error_message": "invalid retrieval filters"}
    return result


def plan_query_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    prepared_query = _question_text(state)
    if prepared_query is None:
        return {"error_message": "prepared_query is required"}

    try:
        filters = _filters_model(state.get("filters") or {})
    except Exception:
        return {"error_message": "invalid retrieval filters"}

    plan = query_planning.plan_query(
        prepared_query,
        _normalize_document_ids(state.get("document_ids")),
        filters,
        settings=resolved_settings,
        shopaikey_client=shopaikey_client,
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
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    plan = _query_plan(state)
    if plan is None:
        return {"error_message": "query_plan is required"}

    document_ids = _normalize_document_ids(state.get("document_ids"))
    if plan.strategy is not RetrievalStrategy.RELATION and not plan.needs_relations:
        return {"relation_document_ids": document_ids}

    try:
        scoped_document_ids = relation_service.resolve_related_document_scope(
            document_ids,
            settings=resolved_settings,
            supabase_client=supabase_client,
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


def _run_semantic_path(
    subquery: QuerySubquery,
    *,
    document_ids: list[str],
    filters: RetrievalFilters,
    settings: Settings,
    qdrant_client: Any | None,
    shopaikey_client: Any | None,
) -> tuple[list[float], list[dict[str, Any]]]:
    query_embedding, candidates = retrieval.retrieve_semantic_candidates(
        subquery.text,
        document_ids=document_ids,
        filters=filters,
        settings=settings,
        qdrant_client=qdrant_client,
        shopaikey_client=shopaikey_client,
    )
    return query_embedding, [
        _with_subquery_id(candidate, subquery.id) for candidate in candidates
    ]


def _run_keyword_path(
    subquery: QuerySubquery,
    *,
    document_ids: list[str],
    filters: RetrievalFilters,
    settings: Settings,
    supabase_client: Any | None,
) -> list[dict[str, Any]]:
    if not settings.ENABLE_KEYWORD_SEARCH:
        return []
    return [
        _with_subquery_id(candidate, subquery.id)
        for candidate in retrieval.keyword_search.search_keyword_chunks(
            subquery.text,
            document_ids=document_ids,
            filters=filters,
            settings=settings,
            supabase_client=supabase_client,
        )
    ]


def retrieve_candidates_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
    shopaikey_client: Any | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    plan = _query_plan(state)
    if plan is None:
        return {"error_message": "query_plan is required"}

    filters = _filters_model(plan.inferred_filters)
    document_ids = _normalize_document_ids(state.get("document_ids"))
    subqueries = _subqueries_from_plan(plan)
    path_candidates: dict[str, list[dict[str, Any]]] = {}
    path_errors: dict[str, str] = {}
    attempted_paths: list[str] = []
    successful_paths: list[str] = []
    query_embedding: list[float] = []
    metadata_skipped_count = 0

    def _record(path_key: str, candidates: list[dict[str, Any]]) -> None:
        path_candidates[path_key] = candidates
        successful_paths.append(path_key)

    for subquery in subqueries:
        strategy = plan.strategy
        if strategy is RetrievalStrategy.METADATA and not _has_active_filter(filters):
            metadata_skipped_count += 1
            continue

        run_semantic = strategy in {
            RetrievalStrategy.SEMANTIC,
            RetrievalStrategy.HYBRID,
            RetrievalStrategy.METADATA,
            RetrievalStrategy.RELATION,
        }
        run_keyword = strategy in {
            RetrievalStrategy.KEYWORD,
            RetrievalStrategy.HYBRID,
            RetrievalStrategy.METADATA,
            RetrievalStrategy.RELATION,
        }

        if run_semantic:
            path_key = f"{subquery.id}:semantic"
            attempted_paths.append(path_key)
            try:
                embedding, candidates = _run_semantic_path(
                    subquery,
                    document_ids=document_ids,
                    filters=filters,
                    settings=resolved_settings,
                    qdrant_client=qdrant_client,
                    shopaikey_client=shopaikey_client,
                )
                if embedding and not query_embedding:
                    query_embedding = embedding
                _record(path_key, candidates)
            except Exception as exc:
                path_errors[path_key] = safe_detail(
                    str(exc), fallback="semantic retrieval failed"
                )

        if run_keyword:
            path_key = f"{subquery.id}:keyword"
            attempted_paths.append(path_key)
            try:
                _record(
                    path_key,
                    _run_keyword_path(
                        subquery,
                        document_ids=document_ids,
                        filters=filters,
                        settings=resolved_settings,
                        supabase_client=supabase_client,
                    ),
                )
            except Exception as exc:
                path_errors[path_key] = safe_detail(
                    str(exc), fallback="keyword retrieval failed"
                )

    metrics = {
        "path_count": len(path_candidates),
        "candidate_count": sum(len(candidates) for candidates in path_candidates.values()),
        "path_error_count": len(path_errors),
        "metadata_skipped_count": metadata_skipped_count,
        "attempted_paths": attempted_paths,
        "successful_paths": successful_paths,
        "attempted_path_count": len(attempted_paths),
        "successful_path_count": len(successful_paths),
    }
    if path_errors:
        metrics["path_errors"] = path_errors
    if path_errors and successful_paths:
        metrics["fallback_path"] = _path_name(successful_paths[0])

    if attempted_paths and not successful_paths:
        return {
            "error_message": _route_failure_message(plan.strategy),
            "query_embedding": query_embedding,
            "path_candidates": path_candidates,
            "retrieval_metrics": metrics,
        }

    return {
        "query_embedding": query_embedding,
        "path_candidates": path_candidates,
        "retrieval_metrics": metrics,
    }


def fuse_candidates_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    path_candidates = state.get("path_candidates") or {}
    if not isinstance(path_candidates, Mapping):
        return {"error_message": "path_candidates must be a mapping"}

    groups = _candidate_groups(path_candidates)
    uncapped_settings = resolved_settings.model_copy(
        update={"RETRIEVAL_FUSION_TOP_K": 1000}
    )
    fused_candidates = score_fusion.fuse_candidates(groups, settings=uncapped_settings)
    plan = _query_plan(state)
    retrieved_chunks = _select_with_subquery_coverage(
        fused_candidates,
        subquery_ids=_subquery_ids(plan),
        limit=resolved_settings.RETRIEVAL_FUSION_TOP_K,
    )

    metrics = dict(state.get("retrieval_metrics") or {})
    metrics["fused_candidate_count"] = len(fused_candidates)
    metrics["retrieved_candidate_count"] = len(retrieved_chunks)
    return {
        "fused_candidates": fused_candidates,
        "retrieved_chunks": retrieved_chunks,
        "retrieval_metrics": metrics,
    }


def retrieve_qdrant_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
    shopaikey_client: Any | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    prepared_query = _question_text(state)
    if prepared_query is None:
        return {"error_message": "prepared_query is required"}

    document_ids = _normalize_document_ids(state.get("document_ids"))
    filters: dict[str, Any] | None = None
    if "filters" in state:
        try:
            filters = _normalize_filters(state.get("filters") or {})
        except Exception:
            return {"error_message": "invalid retrieval filters"}
    try:
        retrieval_result = retrieval.retrieve_hybrid_chunks(
            prepared_query,
            document_ids=document_ids,
            filters=filters,
            settings=resolved_settings,
            qdrant_client=qdrant_client,
            shopaikey_client=shopaikey_client,
            supabase_client=supabase_client,
        )
        result = {
            "prepared_query": prepared_query,
            "document_ids": document_ids,
            "query_embedding": retrieval_result.get("query_embedding", []),
            "retrieval_hints": retrieval_result.get("retrieval_hints", {}),
            "path_candidates": retrieval_result.get("path_candidates", {}),
            "fused_candidates": retrieval_result.get("fused_candidates", []),
            "retrieved_chunks": retrieval_result.get("retrieved_chunks", []),
            "retrieval_metrics": retrieval_result.get("retrieval_metrics", {}),
        }
        if filters is not None:
            result["filters"] = filters
        return result
    except retrieval.RetrievalError as exc:
        return {
            "error_message": safe_detail(
                str(exc),
                fallback=DEFAULT_QUERY_ERROR,
            )
        }
    except Exception as exc:  # pragma: no cover - defensive guard
        return {
            "error_message": safe_detail(
                f"Failed to retrieve chunks: {exc}",
                fallback=DEFAULT_QUERY_ERROR,
            )
        }


def jina_rerank_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    jina_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    question = _question_text(state)
    if question is None:
        return {"error_message": "prepared_query is required"}

    retrieved_chunks = state.get("retrieved_chunks")
    if not isinstance(retrieved_chunks, list) or not retrieved_chunks:
        return {"reranked_chunks": []}

    candidate_count = min(
        len(retrieved_chunks),
        resolved_settings.RETRIEVAL_RERANK_CANDIDATE_TOP_K,
    )
    try:
        reranked_chunks = retrieval.rerank_chunks(
            question,
            retrieved_chunks,
            settings=resolved_settings,
            jina_client=jina_client,
        )
        metrics = dict(state.get("retrieval_metrics") or {})
        metrics["rerank_candidate_count"] = candidate_count
        metrics["final_reranked_count"] = len(reranked_chunks)
        return {
            "reranked_chunks": reranked_chunks,
            "retrieval_metrics": metrics,
        }
    except retrieval.RetrievalError as exc:
        return {
            "error_message": safe_detail(
                str(exc),
                fallback=DEFAULT_QUERY_ERROR,
            )
        }
    except Exception as exc:  # pragma: no cover - defensive guard
        return {
            "error_message": safe_detail(
                f"Failed to rerank chunks: {exc}",
                fallback=DEFAULT_QUERY_ERROR,
            )
        }


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
    resolved_settings = _resolve_settings(settings)
    metrics = dict(state.get("retrieval_metrics") or {})
    reranked_chunks = state.get("reranked_chunks")
    if not isinstance(reranked_chunks, list) or not reranked_chunks:
        return {"context_chunks": [], "retrieval_metrics": metrics}

    try:
        context_result = retrieval_context.expand_neighbor_context_result(
            reranked_chunks,
            settings=resolved_settings,
            supabase_client=supabase_client,
            retrieval_hints=state.get("retrieval_hints"),
            document_ids=_normalize_document_ids(state.get("document_ids")),
        )
        metrics.update(context_result.get("retrieval_metrics") or {})
        return {
            "context_chunks": context_result.get("context_chunks", []),
            "retrieval_metrics": metrics,
        }
    except retrieval.RetrievalError as exc:
        return {
            "error_message": safe_detail(
                str(exc),
                fallback=DEFAULT_QUERY_ERROR,
            )
        }
    except Exception as exc:  # pragma: no cover - defensive guard
        return {
            "error_message": safe_detail(
                f"Failed to expand context: {exc}",
                fallback=DEFAULT_QUERY_ERROR,
            )
        }


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


def generate_answer_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    question = _question_text(state)
    if question is None:
        return {"error_message": "prepared_query is required"}

    context_chunks = resolve_context_chunks(state)
    if not context_chunks:
        return {
            "answer": NO_RELEVANT_INFORMATION_MESSAGE,
            "sources": [],
        }

    try:
        client = (
            shopaikey_client
            if shopaikey_client is not None
            else create_shopaikey_client(resolved_settings)
        )
        context_chunks = assign_citation_keys(context_chunks)
        context = build_context_prompt(context_chunks)
        response = client.chat.completions.create(
            model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
            messages=build_answer_messages(context=context, question=question),
            temperature=resolved_settings.TEMPERATURE,
            max_tokens=resolved_settings.MAX_OUTPUT_TOKENS,
        )
        answer = extract_chat_content(response)
        if answer is None:
            return {
                "error_message": safe_detail(
                    "Chat completion returned empty content",
                    fallback=DEFAULT_QUERY_ERROR,
                )
            }
        return {
            "answer": answer,
            "sources": build_source_citations(context_chunks),
        }
    except Exception as exc:  # pragma: no cover - defensive guard
        return {
            "error_message": safe_detail(
                f"Failed to generate answer: {exc}",
                fallback=DEFAULT_QUERY_ERROR,
            )
        }


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


def regenerate_answer_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    question = _question_text(state)
    if question is None:
        return {"error_message": "prepared_query is required"}

    context_chunks = resolve_context_chunks(state)
    if not context_chunks:
        return {
            "answer": NO_RELEVANT_INFORMATION_MESSAGE,
            "sources": [],
        }

    try:
        client = (
            shopaikey_client
            if shopaikey_client is not None
            else create_shopaikey_client(resolved_settings)
        )
        context_chunks = assign_citation_keys(context_chunks)
        context = build_context_prompt(context_chunks)
        response = client.chat.completions.create(
            model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
            messages=build_regeneration_messages(
                context=context,
                question=question,
                feedback=_compact_grounding_feedback(state),
            ),
            temperature=resolved_settings.TEMPERATURE,
            max_tokens=resolved_settings.MAX_OUTPUT_TOKENS,
        )
        answer = extract_chat_content(response)
        if answer is None:
            return {
                "error_message": safe_detail(
                    "Chat completion returned empty content",
                    fallback=DEFAULT_QUERY_ERROR,
                )
            }
        return {
            "answer": answer,
            "sources": build_source_citations(context_chunks),
        }
    except Exception as exc:  # pragma: no cover - defensive guard
        return {
            "error_message": safe_detail(
                f"Failed to regenerate answer: {exc}",
                fallback=DEFAULT_QUERY_ERROR,
            )
        }


def validate_citations_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    _resolve_settings(settings)
    answer = state.get("answer")
    context_chunks = resolve_context_chunks(state)
    validation_output = validate_answer_citations(
        str(answer) if answer is not None else None,
        context_chunks,
    )
    return {
        "citation_validation_result": validation_output.validation,
        "sources": validation_output.sources,
    }


def verify_grounding_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    answer = normalize_text(state.get("answer"))
    validation = state.get("citation_validation_result")
    verification_attempt_count = int(state.get("verification_attempt_count") or 0) + 1

    if answer is None:
        return {
            "answer_verified": False,
            "verification_attempt_count": verification_attempt_count,
        }

    if answer == NO_RELEVANT_INFORMATION_MESSAGE or "indexed documents do not contain enough information" in answer.lower():
        return {
            "grounding_result": grounding.GroundingResult(
                grounded=True,
                score=1.0,
                unsupported_claims=[],
                missing_citations=[],
            ),
            "answer_verified": True,
            "verification_attempt_count": verification_attempt_count,
        }

    citations_valid = bool(getattr(validation, "valid", False))
    cited_keys = list(getattr(validation, "cited_keys", []) or [])
    evidence = grounding.cited_evidence_from_sources(
        context_chunks=resolve_context_chunks(state),
        cited_keys=cited_keys,
    )
    if not citations_valid or not evidence:
        result = grounding.GroundingResult(
            grounded=False,
            score=0.0,
            unsupported_claims=[],
            missing_citations=[] if cited_keys else ["valid citations"],
        )
        return {
            "grounding_result": result,
            "answer_verified": False,
            "verification_attempt_count": verification_attempt_count,
        }

    try:
        result = grounding.verify_answer_grounding(
            answer,
            evidence=evidence,
            settings=resolved_settings,
            shopaikey_client=shopaikey_client,
        )
    except grounding.GroundingProviderError:
        return {
            "answer_verified": False,
            "grounding_provider_failed": True,
            "verification_attempt_count": verification_attempt_count,
        }

    return {
        "grounding_result": result,
        "answer_verified": result.grounded and result.score >= resolved_settings.GROUNDING_MIN_SCORE,
        "verification_attempt_count": verification_attempt_count,
    }


def finalize_answer_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    _resolve_settings(settings)
    if state.get("answer_verified") is False:
        return {
            "answer": SAFE_INSUFFICIENT_CONTEXT_MESSAGE,
            "sources": [],
        }
    return {}


def save_message_optional_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    if not state.get("save_message"):
        return {}

    question = _question_text(state)
    answer = normalize_text(state.get("answer"))
    if question is None or answer is None:
        return {}

    try:
        sources = state.get("sources")
        if isinstance(sources, list):
            normalized_sources = [
                dict(source) for source in sources if isinstance(source, Mapping)
            ]
        else:
            normalized_sources = build_source_citations(resolve_context_chunks(state))

        message_service.create_message(
            question=question,
            answer=answer,
            sources=normalized_sources,
            metadata=message_metadata(state),
            settings=resolved_settings,
            supabase_client=supabase_client,
        )
    except Exception as exc:  # pragma: no cover - message save must not fail chat
        logger.warning("Message save failed: %s", exc)
    return {}


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
