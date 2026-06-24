from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.contracts import QdrantPayloadKey, RetrievalPath
from app.core.retry import RetryAttempt, retry_sync
from app.models.schemas import RetrievalFilters
from app.services.qdrant_client import (
    create_qdrant_client,
    ensure_qdrant_filter_indexes,
)
from app.services.shopaikey_client import create_shopaikey_client
from app.services.retrieval_normalization import (
    _normalize_filters,
    _normalize_float,
    _normalize_int,
    _normalize_section_path,
    _normalize_text,
    _response_rows,
)
from app.services.retrieval_filters import build_qdrant_filter


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


def embed_question(
    question: str,
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
    retry_attempts: list[RetryAttempt] | None = None,
) -> list[float]:
    resolved_settings = _resolve_settings(settings)
    normalized_question = _normalize_text(question)
    if normalized_question is None:
        raise RetrievalError("question is required")

    client = _resolve_shopaikey_client(shopaikey_client)
    response = retry_sync(
        "embedding_generation",
        lambda: client.embeddings.create(
            model=resolved_settings.SHOPAIKEY_EMBEDDING_MODEL,
            input=[normalized_question],
        ),
        settings=resolved_settings,
        on_attempt=retry_attempts.append if retry_attempts is not None else None,
    )
    items = getattr(response, "data", response)
    if not items:
        raise RetrievalError("Embedding response missing vectors")

    first_item = items[0]
    embedding = getattr(first_item, "embedding", None)
    if embedding is None and isinstance(first_item, Mapping):
        embedding = first_item.get("embedding")
    if embedding is None:
        raise RetrievalError("Embedding response missing vectors")

    vector = [float(value) for value in embedding]
    if not vector:
        raise RetrievalError("Embedding response contained empty vectors")
    return vector


def search_semantic_chunks(
    query_embedding: Sequence[float],
    *,
    document_ids: Sequence[UUID | str] | None = None,
    filters: RetrievalFilters | Mapping[str, Any] | None = None,
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
    retry_attempts: list[RetryAttempt] | None = None,
) -> list[dict[str, Any]]:
    from app.services import retrieval
    payload_key = getattr(retrieval, "QdrantPayloadKey", QdrantPayloadKey)

    resolved_settings = _resolve_settings(settings)
    client = _resolve_qdrant_client(qdrant_client)

    if filters is not None:
        normalized = _normalize_filters(filters)
        if any(value not in (None, [], "") for value in normalized.values()):
            try:
                ensure_qdrant_filter_indexes(
                    client,
                    collection_name=resolved_settings.QDRANT_COLLECTION,
                    filters=normalized,
                )
            except Exception as exc:
                raise RetrievalError(
                    f"Failed to ensure Qdrant filter indexes: {exc}"
                ) from exc

    query_filter = build_qdrant_filter(document_ids, filters)
    response = retry_sync(
        "qdrant_search",
        lambda: client.query_points(
            collection_name=resolved_settings.QDRANT_COLLECTION,
            query=list(query_embedding),
            query_filter=query_filter,
            limit=resolved_settings.RETRIEVAL_SEMANTIC_TOP_K,
            with_payload=True,
            with_vectors=False,
        ),
        settings=resolved_settings,
        on_attempt=retry_attempts.append if retry_attempts is not None else None,
    )

    results: list[dict[str, Any]] = []
    for point in _response_rows(response):
        payload = point.get("payload") if isinstance(point, Mapping) else None
        if not isinstance(payload, Mapping):
            payload = {}

        point_score = point.get("score") if isinstance(point, Mapping) else None

        chunk_id = _normalize_text(
            payload.get(payload_key.CHUNK_ID) or point.get("id")
        )
        document_id = _normalize_text(payload.get(payload_key.DOCUMENT_ID))
        if chunk_id is None or document_id is None:
            continue

        content = _normalize_text(payload.get(payload_key.TEXT)) or ""
        results.append(
            {
                "id": chunk_id,
                "chunk_id": chunk_id,
                "document_id": document_id,
                "file_name": _normalize_text(payload.get(payload_key.FILE_NAME)),
                "chunk_index": _normalize_int(payload.get(payload_key.CHUNK_INDEX)),
                "content": content,
                "text": content,
                "heading": payload.get(payload_key.HEADING),
                "section_path": _normalize_section_path(
                    payload.get(payload_key.SECTION_PATH)
                ),
                "page_start": _normalize_int(payload.get(payload_key.PAGE_START)),
                "page_end": _normalize_int(payload.get(payload_key.PAGE_END)),
                "chunk_type": _normalize_text(payload.get(payload_key.CHUNK_TYPE)),
                "token_count": _normalize_int(payload.get(payload_key.TOKEN_COUNT)),
                "qdrant_score": _normalize_float(point_score),
                "semantic_score": _normalize_float(point_score),
                "rerank_score": None,
                "semantic_rank": len(results) + 1,
                "keyword_rank": None,
                "keyword_score": None,
                "fusion_score": None,
                "retrieval_paths": [RetrievalPath.SEMANTIC],
                "subquery_ids": [],
            }
        )
    return results


def _normalize_semantic_candidate(
    candidate: Mapping[str, Any],
    *,
    rank: int,
) -> dict[str, Any]:
    normalized = dict(candidate)
    chunk_id = _normalize_text(normalized.get("chunk_id") or normalized.get("id"))
    if chunk_id is not None:
        normalized["id"] = chunk_id
        normalized["chunk_id"] = chunk_id
    normalized.setdefault("file_name", _normalize_text(normalized.get("file_name")) or "")
    normalized.setdefault("content", normalized.get("text") or "")
    normalized["semantic_rank"] = _normalize_int(normalized.get("semantic_rank")) or rank
    semantic_score = _normalize_float(
        normalized.get("semantic_score") if normalized.get("semantic_score") is not None else normalized.get("qdrant_score")
    )
    normalized["semantic_score"] = semantic_score
    if normalized.get("qdrant_score") is None:
        normalized["qdrant_score"] = semantic_score
    normalized.setdefault("keyword_rank", None)
    normalized.setdefault("keyword_score", None)
    normalized.setdefault("fusion_score", None)
    normalized["retrieval_paths"] = [RetrievalPath.SEMANTIC]
    normalized.setdefault("subquery_ids", [])
    return normalized


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
    return query_embedding, [
        _normalize_semantic_candidate(candidate, rank=rank)
        for rank, candidate in enumerate(semantic_rows, start=1)
    ]


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
    resolved_settings = _resolve_settings(settings)
    return _semantic_search_path(
        question,
        document_ids=document_ids,
        filters=filters,
        settings=resolved_settings,
        qdrant_client=qdrant_client,
        shopaikey_client=shopaikey_client,
        retry_attempts=retry_attempts,
    )
