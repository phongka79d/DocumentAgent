from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.config import Settings, get_settings
from app.core.retry import RetryAttempt, retry_sync
from app.services.jina_client import create_jina_client
from app.services.retrieval_normalization import (
    _normalize_float,
    _normalize_int,
    _normalize_text,
)

logger = logging.getLogger(__name__)


class RetrievalError(RuntimeError):
    """Raised when semantic retrieval cannot be completed."""


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_jina_client(jina_client: Any | None = None) -> Any:
    return jina_client if jina_client is not None else create_jina_client()


def _fallback_rerank_sort_key(candidate: Mapping[str, Any]) -> tuple[float, float, float, str]:
    fusion_score = _normalize_float(candidate.get("fusion_score"))
    qdrant_score = _normalize_float(candidate.get("qdrant_score"))
    if qdrant_score is None:
        qdrant_score = _normalize_float(candidate.get("semantic_score"))
    keyword_score = _normalize_float(candidate.get("keyword_score"))
    return (
        -(fusion_score if fusion_score is not None else float("-inf")),
        -(qdrant_score if qdrant_score is not None else float("-inf")),
        -(keyword_score if keyword_score is not None else float("-inf")),
        str(candidate.get("chunk_id") or candidate.get("id") or ""),
    )


def _sort_chunks_by_rerank_fallback(
    chunks: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [dict(chunk) for chunk in sorted(chunks, key=_fallback_rerank_sort_key)]


def _extract_jina_rankings(response_payload: Any) -> list[dict[str, Any]]:
    if isinstance(response_payload, Mapping):
        raw_results = (
            response_payload.get("results")
            or response_payload.get("data")
            or response_payload.get("rankings")
        )
    else:
        raw_results = response_payload

    if raw_results is None:
        return []
    if not isinstance(raw_results, list):
        raw_results = list(raw_results)

    normalized: list[dict[str, Any]] = []
    for position, item in enumerate(raw_results):
        if isinstance(item, Mapping):
            index = item.get("index")
            score = item.get("relevance_score")
            if score is None:
                score = item.get("score")
        else:
            index = getattr(item, "index", None)
            score = getattr(item, "relevance_score", None)
            if score is None:
                score = getattr(item, "score", None)

        normalized.append(
            {
                "index": _normalize_int(index) if index is not None else None,
                "score": _normalize_float(score),
            }
        )
    return normalized


def rerank_chunks(
    question: str,
    chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
    jina_client: Any | None = None,
    retry_attempts: list[RetryAttempt] | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    normalized_question = _normalize_text(question)
    if normalized_question is None:
        raise RetrievalError("question is required")

    if not chunks:
        return {"reranked_chunks": [], "rerank_scored_chunks": []}

    candidate_chunks = [
        dict(chunk)
        for chunk in chunks[: resolved_settings.RETRIEVAL_RERANK_CANDIDATE_TOP_K]
    ]
    fallback = _sort_chunks_by_rerank_fallback(candidate_chunks)[
        : resolved_settings.RETRIEVAL_FINAL_TOP_K
    ]
    if not resolved_settings.ENABLE_RERANK:
        return {"reranked_chunks": fallback, "rerank_scored_chunks": fallback}

    client = _resolve_jina_client(jina_client)
    transport = getattr(client, "http_client", client)
    model = getattr(client, "model", resolved_settings.JINA_RERANK_MODEL)

    documents = [
        str(chunk.get("content") or chunk.get("text") or "") for chunk in candidate_chunks
    ]
    try:
        def _post_rerank() -> Any:
            rerank_response = transport.post(
                "/rerank",
                json={
                    "model": model,
                    "query": normalized_question,
                    "documents": documents,
                    "top_n": len(documents),
                    "return_documents": False,
                },
            )
            rerank_response.raise_for_status()
            return rerank_response

        response = retry_sync(
            "jina_rerank",
            _post_rerank,
            settings=resolved_settings,
            on_attempt=retry_attempts.append if retry_attempts is not None else None,
        )
        payload = response.json()
        rankings = _extract_jina_rankings(payload)
    except Exception as exc:  # pragma: no cover - fallback exercised in tests
        logger.warning("Jina rerank failed, falling back to deterministic order: %s", exc)
        return {"reranked_chunks": fallback, "rerank_scored_chunks": fallback}

    if not rankings:
        return {"reranked_chunks": fallback, "rerank_scored_chunks": fallback}

    scored_chunks: list[dict[str, Any]] = []
    seen_indexes: set[int] = set()
    for ranking in rankings:
        index = ranking["index"]
        if index is None or index < 0 or index >= len(candidate_chunks) or index in seen_indexes:
            logger.warning(
                "Jina rerank returned invalid indexes, falling back to deterministic order"
            )
            return {"reranked_chunks": fallback, "rerank_scored_chunks": fallback}
        seen_indexes.add(index)
        chunk = dict(candidate_chunks[index])
        chunk["rerank_score"] = ranking["score"]
        scored_chunks.append(chunk)

    if not scored_chunks:
        return {"reranked_chunks": fallback, "rerank_scored_chunks": fallback}

    from app.services import retrieval_diversity

    grouped = retrieval_diversity.assign_evidence_groups(
        scored_chunks,
        settings=resolved_settings,
    )
    diverse = retrieval_diversity.select_group_diverse(
        grouped,
        limit=resolved_settings.RETRIEVAL_FINAL_TOP_K,
    )
    return {"reranked_chunks": diverse, "rerank_scored_chunks": scored_chunks}
