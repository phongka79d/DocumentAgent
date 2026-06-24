from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from app.core.config import Settings
from app.core.errors import safe_detail
from app.core.retry import RetryAttempt, RetryExhaustedError, retry_sync
from app.core.contracts import RetrievalStrategy
from app.graphs.query_steps.dependencies import QueryStepDependencies
from app.rag.formatting import normalize_text
from app.models.schemas import QueryPlan, RetrievalFilters

logger = logging.getLogger(__name__)


def _resolve_settings(settings: Settings | None = None) -> Settings:
    from app.core.config import get_settings

    return settings if settings is not None else get_settings()


def _normalize_document_ids(document_ids: Any) -> list[str]:
    from app.graphs.query_steps.prepare import _normalize_document_ids as _norm

    return _norm(document_ids)


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


def _has_active_filter(filters: RetrievalFilters) -> bool:
    data = filters.model_dump(mode="json")
    return any(value not in (None, [], "") for value in data.values())


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


def _run_semantic_path(
    subquery: Any,
    *,
    document_ids: list[str],
    filters: RetrievalFilters,
    settings: Settings,
    deps: QueryStepDependencies,
    qdrant_client: Any | None,
    shopaikey_client: Any | None,
) -> tuple[list[float], list[dict[str, Any]], list[RetryAttempt]]:
    attempts: list[RetryAttempt] = []
    query_embedding, candidates = deps.retrieval.retrieve_semantic_candidates(
        subquery.text,
        document_ids=document_ids,
        filters=filters,
        settings=settings,
        qdrant_client=qdrant_client,
        shopaikey_client=shopaikey_client,
        retry_attempts=attempts,
    )
    return query_embedding, [
        _with_subquery_id(candidate, subquery.id) for candidate in candidates
    ], attempts


def _run_keyword_path(
    subquery: Any,
    *,
    document_ids: list[str],
    filters: RetrievalFilters,
    settings: Settings,
    deps: QueryStepDependencies,
    supabase_client: Any | None,
) -> tuple[list[dict[str, Any]], list[RetryAttempt]]:
    if not settings.ENABLE_KEYWORD_SEARCH:
        return [], []
    attempts: list[RetryAttempt] = []
    candidates = [
        _with_subquery_id(candidate, subquery.id)
        for candidate in deps.retrieval.keyword_search.search_keyword_chunks(
            subquery.text,
            document_ids=document_ids,
            filters=filters,
            settings=settings,
            supabase_client=supabase_client,
            retry_attempts=attempts,
        )
    ]
    return candidates, attempts


def retrieve_candidates_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
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
    from app.models.schemas import QuerySubquery

    subqueries = [QuerySubquery.model_validate(item) for item in plan.subqueries]
    path_candidates: dict[str, list[dict[str, Any]]] = {}
    path_errors: dict[str, str] = {}
    attempted_paths: list[str] = []
    successful_paths: list[str] = []
    query_embedding: list[float] = []
    metadata_skipped_count = 0
    retry_attempts: list[RetryAttempt] = []

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
                embedding, candidates, attempts = _run_semantic_path(
                    subquery,
                    document_ids=document_ids,
                    filters=filters,
                    settings=resolved_settings,
                    deps=deps,
                    qdrant_client=qdrant_client,
                    shopaikey_client=shopaikey_client,
                )
                if embedding and not query_embedding:
                    query_embedding = embedding
                _record(path_key, candidates)
                retry_attempts.extend(attempts)
            except Exception as exc:
                path_errors[path_key] = safe_detail(
                    str(exc), fallback="semantic retrieval failed"
                )
                if isinstance(exc, RetryExhaustedError):
                    retry_attempts.append(
                        RetryAttempt(
                            operation=exc.operation,
                            attempt=exc.attempts,
                            max_attempts=exc.attempts,
                            retryable=True,
                            error_code=exc.error_code,
                        )
                    )

        if run_keyword:
            path_key = f"{subquery.id}:keyword"
            attempted_paths.append(path_key)
            try:
                candidates, attempts = _run_keyword_path(
                    subquery,
                    document_ids=document_ids,
                    filters=filters,
                    settings=resolved_settings,
                    deps=deps,
                    supabase_client=supabase_client,
                )
                retry_attempts.extend(attempts)
                _record(path_key, candidates)
            except Exception as exc:
                logger.warning("Keyword retrieval path failed for %s: %s", path_key, exc)
                path_errors[path_key] = safe_detail(
                    str(exc), fallback="keyword retrieval failed"
                )
                if isinstance(exc, RetryExhaustedError):
                    retry_attempts.append(
                        RetryAttempt(
                            operation=exc.operation,
                            attempt=exc.attempts,
                            max_attempts=exc.attempts,
                            retryable=True,
                            error_code=exc.error_code,
                        )
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
    _merge_retry_metrics(metrics, "retrieve_candidates", retry_attempts)

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
    deps: QueryStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    path_candidates_raw = state.get("path_candidates") or {}
    if not isinstance(path_candidates_raw, Mapping):
        return {"error_message": "path_candidates must be a mapping"}

    def _subquery_ids(plan: QueryPlan | None) -> list[str]:
        if plan is None:
            return []
        ids: list[str] = []
        for subquery in plan.subqueries:
            text = normalize_text(subquery.id)
            if text is not None and text not in ids:
                ids.append(text)
        return ids

    def _candidate_groups(path_candidates: Mapping[str, Any]) -> list[list[dict[str, Any]]]:
        groups: list[list[dict[str, Any]]] = []
        for candidates in path_candidates.values():
            if not isinstance(candidates, list):
                continue
            groups.append([dict(candidate) for candidate in candidates if isinstance(candidate, Mapping)])
        return groups

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

    groups = _candidate_groups(path_candidates_raw)
    uncapped_settings = resolved_settings.model_copy(
        update={"RETRIEVAL_FUSION_TOP_K": 1000}
    )
    fused_candidates = deps.retrieval.score_fusion.fuse_candidates(groups, settings=uncapped_settings)
    plan = _query_plan(state)
    retrieved_chunks = _select_with_subquery_coverage(
        fused_candidates,
        subquery_ids=_subquery_ids(plan),
        limit=resolved_settings.RETRIEVAL_FUSION_TOP_K,
    )

    metrics = dict(state.get("retrieval_metrics") or {})
    metrics["fused_candidate_count"] = len(fused_candidates)
    metrics["retrieved_candidate_count"] = len(retrieved_chunks)

    if isinstance(path_candidates_raw, Mapping) and path_candidates_raw:
        diverse_pool = deps.retrieval.score_fusion.select_rerank_candidates(
            path_candidates_raw,
            fused_candidates=fused_candidates,
            settings=resolved_settings,
        )
    else:
        diverse_pool = retrieved_chunks

    metrics["rerank_candidate_count"] = len(diverse_pool)
    return {
        "fused_candidates": fused_candidates,
        "retrieved_chunks": diverse_pool,
        "retrieval_metrics": metrics,
    }


def retrieve_qdrant_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
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
            from app.graphs.query_steps.prepare import _normalize_filters as _norm_filters

            filters = _norm_filters(state.get("filters") or {})
        except Exception:
            return {"error_message": "invalid retrieval filters"}
    try:
        retrieval_result = deps.retrieval.retrieve_hybrid_chunks(
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
    except deps.retrieval.RetrievalError as exc:
        return {
            "error_message": safe_detail(
                str(exc),
                fallback="Query failed",
            )
        }
    except Exception as exc:
        return {
            "error_message": safe_detail(
                f"Failed to retrieve chunks: {exc}",
                fallback="Query failed",
            )
        }


def jina_rerank_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
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
        attempts: list[RetryAttempt] = []
        rerank_result = deps.retrieval.rerank_chunks(
            question,
            retrieved_chunks,
            settings=resolved_settings,
            jina_client=jina_client,
            retry_attempts=attempts,
        )
        reranked_chunks = rerank_result["reranked_chunks"]
        rerank_scored_chunks = rerank_result.get("rerank_scored_chunks", reranked_chunks)
        metrics = dict(state.get("retrieval_metrics") or {})
        metrics["rerank_candidate_count"] = candidate_count
        metrics["final_reranked_count"] = len(reranked_chunks)
        _merge_retry_metrics(metrics, "rerank_candidates", attempts)
        if attempts and attempts[-1].error_code != "ok":
            metrics["fallback_path"] = "deterministic_fused_score"
        return {
            "reranked_chunks": reranked_chunks,
            "rerank_scored_chunks": rerank_scored_chunks,
            "retrieval_metrics": metrics,
        }
    except deps.retrieval.RetrievalError as exc:
        return {
            "error_message": safe_detail(
                str(exc),
                fallback="Query failed",
            )
        }
    except Exception as exc:
        return {
            "error_message": safe_detail(
                f"Failed to rerank chunks: {exc}",
                fallback="Query failed",
            )
        }


def expand_neighbor_context_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    metrics = dict(state.get("retrieval_metrics") or {})
    reranked_chunks = state.get("reranked_chunks")
    if not isinstance(reranked_chunks, list) or not reranked_chunks:
        return {"context_chunks": [], "retrieval_metrics": metrics}

    try:
        context_result = deps.retrieval_context.expand_neighbor_context_result(
            reranked_chunks,
            settings=resolved_settings,
            supabase_client=supabase_client,
            retrieval_hints=state.get("retrieval_hints"),
            document_ids=_normalize_document_ids(state.get("document_ids")),
            rerank_scored_chunks=state.get("rerank_scored_chunks"),
        )
        metrics.update(context_result.get("retrieval_metrics") or {})
        return {
            "context_chunks": context_result.get("context_chunks", []),
            "retrieval_metrics": metrics,
        }
    except deps.retrieval.RetrievalError as exc:
        return {
            "error_message": safe_detail(
                str(exc),
                fallback="Query failed",
            )
        }
    except Exception as exc:
        return {
            "error_message": safe_detail(
                f"Failed to expand context: {exc}",
                fallback="Query failed",
            )
        }
