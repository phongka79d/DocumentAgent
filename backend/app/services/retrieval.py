from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from uuid import UUID

from qdrant_client.http import models as qdrant_models

from app.core.config import Settings, get_settings
from app.core.contracts import QdrantPayloadKey
from app.core.retry import RetryAttempt, retry_sync
from app.models.schemas import RetrievalFilters
from app.core.contracts import RetrievalPath
from app.services import keyword_search, score_fusion
from app.services.qdrant_client import (
    create_qdrant_client,
    ensure_qdrant_filter_indexes,
)
from app.services.jina_client import create_jina_client
from app.services.retrieval_context import (
    NEIGHBOR_CONTEXT_MODE,
    SECTION_AWARE_CONTEXT_MODE,
    RetrievalContextError,
    expand_neighbor_context as _expand_neighbor_context,
)
from app.services.retrieval_hints import (
    RETRIEVAL_HINT_SYSTEM_PROMPT,
    RETRIEVAL_HINT_USER_PROMPT_TEMPLATE,
    extract_retrieval_hints as _extract_retrieval_hints,
)
from app.services.shopaikey_client import create_shopaikey_client

from app.services.retrieval_normalization import (
    _normalize_document_ids,
    _normalize_filters,
    _normalize_float,
    _normalize_int,
    _normalize_section_path,
    _normalize_text,
    _normalize_uuid,
    _response_rows,
)

from app.services.retrieval_filters import (
    build_document_id_filter,
    build_qdrant_filter,
)

from app.services import semantic_retrieval
from app.services import reranking

logger = logging.getLogger(__name__)


class RetrievalError(RuntimeError):
    """Raised when semantic retrieval cannot be completed."""


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_qdrant_client(qdrant_client: Any | None = None) -> Any:
    return qdrant_client if qdrant_client is not None else create_qdrant_client()


def _resolve_shopaikey_client(shopaikey_client: Any | None = None) -> Any:
    return (
        shopaikey_client
        if shopaikey_client is not None
        else create_shopaikey_client()
    )


def _resolve_jina_client(jina_client: Any | None = None) -> Any:
    return jina_client if jina_client is not None else create_jina_client()


def extract_retrieval_hints(
    question: str,
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, list[str]]:
    normalized_question = _normalize_text(question)
    if normalized_question is None:
        raise RetrievalError("question is required")
    return _extract_retrieval_hints(
        normalized_question,
        settings=settings,
        shopaikey_client=shopaikey_client,
    )


def embed_question(
    question: str,
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
    retry_attempts: list[RetryAttempt] | None = None,
) -> list[float]:
    client = _resolve_shopaikey_client(shopaikey_client)
    return semantic_retrieval.embed_question(
        question,
        settings=settings,
        shopaikey_client=client,
        retry_attempts=retry_attempts,
    )


def search_semantic_chunks(
    query_embedding: Sequence[float],
    *,
    document_ids: Sequence[UUID | str] | None = None,
    filters: RetrievalFilters | Mapping[str, Any] | None = None,
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
    retry_attempts: list[RetryAttempt] | None = None,
) -> list[dict[str, Any]]:
    client = _resolve_qdrant_client(qdrant_client)
    return semantic_retrieval.search_semantic_chunks(
        query_embedding,
        document_ids=document_ids,
        filters=filters,
        settings=settings,
        qdrant_client=client,
        retry_attempts=retry_attempts,
    )


def retrieve_semantic_candidates(
    question: str,
    *,
    document_ids: Sequence[UUID | str] | None = None,
    filters: RetrievalFilters | Mapping[str, Any] | None = None,
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
    shopaikey_client: Any | None = None,
    retry_attempts: list[RetryAttempt] | None = None,
) -> tuple[list[float], list[dict[str, Any]]]:
    s_client = _resolve_shopaikey_client(shopaikey_client)
    q_client = _resolve_qdrant_client(qdrant_client)
    return semantic_retrieval.retrieve_semantic_candidates(
        question,
        document_ids=document_ids,
        filters=filters,
        settings=settings,
        qdrant_client=q_client,
        shopaikey_client=s_client,
        retry_attempts=retry_attempts,
    )


def rerank_chunks(
    question: str,
    chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
    jina_client: Any | None = None,
    retry_attempts: list[RetryAttempt] | None = None,
) -> dict[str, Any]:
    client = _resolve_jina_client(jina_client)
    return reranking.rerank_chunks(
        question,
        chunks,
        settings=settings,
        jina_client=client,
        retry_attempts=retry_attempts,
    )


def _semantic_search_path(
    question: str,
    *,
    document_ids: Sequence[UUID | str] | None,
    filters: RetrievalFilters | Mapping[str, Any] | None,
    settings: Settings,
    qdrant_client: Any | None,
    shopaikey_client: Any | None,
    retry_attempts: list[RetryAttempt] | None = None,
) -> tuple[list[float], list[dict[str, Any]]]:
    query_embedding = embed_question(
        question,
        settings=settings,
        shopaikey_client=shopaikey_client,
        retry_attempts=retry_attempts,
    )
    semantic_rows = search_semantic_chunks(
        query_embedding,
        document_ids=document_ids,
        filters=filters,
        settings=settings,
        qdrant_client=qdrant_client,
        retry_attempts=retry_attempts,
    )
    from app.services.semantic_retrieval import _normalize_semantic_candidate
    return query_embedding, [
        _normalize_semantic_candidate(candidate, rank=rank)
        for rank, candidate in enumerate(semantic_rows, start=1)
    ]


def retrieve_hybrid_chunks(
    question: str,
    *,
    document_ids: Sequence[UUID | str] | None = None,
    filters: RetrievalFilters | Mapping[str, Any] | None = None,
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
    shopaikey_client: Any | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    """Run semantic and keyword retrieval independently and fuse successful paths."""

    resolved_settings = _resolve_settings(settings)
    normalized_question = _normalize_text(question)
    if normalized_question is None:
        raise RetrievalError("question is required")

    normalized_document_ids = _normalize_document_ids(document_ids)
    normalized_filters = _normalize_filters(filters) if filters is not None else None
    query_embedding: list[float] = []
    semantic_candidates: list[dict[str, Any]] = []
    keyword_candidates: list[dict[str, Any]] = []
    semantic_error: Exception | None = None
    keyword_error: Exception | None = None
    fused_candidates: list[dict[str, Any]] | None = None

    try:
        query_embedding, semantic_candidates = _semantic_search_path(
            normalized_question,
            document_ids=normalized_document_ids,
            filters=normalized_filters,
            settings=resolved_settings,
            qdrant_client=qdrant_client,
            shopaikey_client=shopaikey_client,
            retry_attempts=None,
        )
    except Exception as exc:
        semantic_error = exc

    if resolved_settings.ENABLE_KEYWORD_SEARCH:
        try:
            keyword_candidates = keyword_search.search_keyword_chunks(
                normalized_question,
                document_ids=normalized_document_ids,
                filters=normalized_filters,
                settings=resolved_settings,
                supabase_client=supabase_client,
            )
        except Exception as exc:
            keyword_error = exc

    if not resolved_settings.ENABLE_KEYWORD_SEARCH:
        if semantic_error is not None:
            raise RetrievalError("semantic retrieval failed") from None
        retrieved_chunks = semantic_candidates[: resolved_settings.RETRIEVAL_FUSION_TOP_K]
        fallback_path: str | None = RetrievalPath.SEMANTIC.value
    elif semantic_error is not None and keyword_error is not None:
        raise RetrievalError("hybrid retrieval failed") from None
    elif semantic_error is not None:
        retrieved_chunks = keyword_candidates[: resolved_settings.RETRIEVAL_FUSION_TOP_K]
        fallback_path = RetrievalPath.KEYWORD.value
    elif keyword_error is not None:
        retrieved_chunks = semantic_candidates[: resolved_settings.RETRIEVAL_FUSION_TOP_K]
        fallback_path = RetrievalPath.SEMANTIC.value
    else:
        fused_candidates = score_fusion.fuse_candidates(
            [semantic_candidates, keyword_candidates],
            settings=resolved_settings,
        )
        path_candidates_for_pool = {
            f"query:{RetrievalPath.SEMANTIC.value}": semantic_candidates,
            f"query:{RetrievalPath.KEYWORD.value}": keyword_candidates,
        }
        retrieved_chunks = score_fusion.select_rerank_candidates(
            path_candidates_for_pool,
            fused_candidates=fused_candidates,
            settings=resolved_settings,
        )
        fallback_path = None

    fused_for_metrics = (
        fused_candidates
        if fused_candidates is not None
        else retrieved_chunks
    )

    return {
        "question": normalized_question,
        "document_ids": normalized_document_ids,
        "query_embedding": query_embedding,
        "path_candidates": {
            RetrievalPath.SEMANTIC.value: semantic_candidates,
            RetrievalPath.KEYWORD.value: keyword_candidates,
        },
        "fused_candidates": fused_for_metrics,
        "retrieved_chunks": retrieved_chunks,
        "retrieval_metrics": {
            "semantic_candidate_count": len(semantic_candidates),
            "keyword_candidate_count": len(keyword_candidates),
            "fused_candidate_count": len(fused_for_metrics),
            "rerank_candidate_count": len(retrieved_chunks),
            "fallback_path": fallback_path,
        },
        **({"filters": normalized_filters} if normalized_filters is not None else {}),
    }


def _sort_chunks_by_qdrant_score(chunks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    enumerated_chunks = list(enumerate(chunks))

    def _sort_key(item: tuple[int, Mapping[str, Any]]) -> tuple[float, int]:
        index, chunk = item
        score = _normalize_float(chunk.get("qdrant_score"))
        return (-(score if score is not None else float("-inf")), index)

    return [dict(chunk) for _, chunk in sorted(enumerated_chunks, key=_sort_key)]


def expand_neighbor_context(
    reranked_chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
    retrieval_hints: Mapping[str, Any] | None = None,
    document_ids: Sequence[UUID | str] | None = None,
) -> list[dict[str, Any]]:
    try:
        return _expand_neighbor_context(
            reranked_chunks,
            settings=settings,
            supabase_client=supabase_client,
            retrieval_hints=retrieval_hints,
            document_ids=document_ids,
        )
    except RetrievalContextError as exc:
        raise RetrievalError(str(exc)) from exc


def retrieve_context_chunks(
    question: str,
    *,
    document_ids: Sequence[UUID | str] | None = None,
    filters: RetrievalFilters | Mapping[str, Any] | None = None,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
    qdrant_client: Any | None = None,
    shopaikey_client: Any | None = None,
    jina_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    normalized_question = _normalize_text(question)
    if normalized_question is None:
        raise RetrievalError("question is required")

    normalized_document_ids = _normalize_document_ids(document_ids)
    query_embedding = embed_question(
        normalized_question,
        settings=resolved_settings,
        shopaikey_client=shopaikey_client,
    )
    retrieval_hints = extract_retrieval_hints(
        normalized_question,
        settings=resolved_settings,
        shopaikey_client=shopaikey_client,
    )
    retrieved_chunks = search_semantic_chunks(
        query_embedding,
        document_ids=normalized_document_ids,
        filters=filters,
        settings=resolved_settings,
        qdrant_client=qdrant_client,
    )
    rerank_result = rerank_chunks(
        normalized_question,
        retrieved_chunks,
        settings=resolved_settings,
        jina_client=jina_client,
    )
    reranked_chunks = rerank_result["reranked_chunks"]
    context_chunks = expand_neighbor_context(
        reranked_chunks,
        settings=resolved_settings,
        supabase_client=supabase_client,
        retrieval_hints=retrieval_hints,
        document_ids=normalized_document_ids,
    )
    result = {
        "question": normalized_question,
        "document_ids": normalized_document_ids,
        "query_embedding": query_embedding,
        "retrieval_hints": retrieval_hints,
        "retrieved_chunks": retrieved_chunks,
        "reranked_chunks": reranked_chunks,
        "context_chunks": context_chunks,
    }
    if filters is not None:
        result["filters"] = _normalize_filters(filters)
    return result
