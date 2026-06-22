from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from uuid import UUID

from qdrant_client.http import models as qdrant_models

from app.core.config import Settings, get_settings
from app.core.contracts import QdrantPayloadKey
from app.models.schemas import RetrievalFilters
from app.core.contracts import RetrievalPath
from app.services import keyword_search, score_fusion
from app.services.qdrant_client import create_qdrant_client
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


def _response_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "points", response)
    if data is None:
        return []
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, list):
        items = data
    elif isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        items = list(data)
    else:
        items = [data]

    rows: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, Mapping):
            rows.append(dict(item))
            continue
        if hasattr(item, "model_dump"):
            rows.append(dict(item.model_dump()))
            continue
        if hasattr(item, "__dict__"):
            rows.append(
                {
                    key: value
                    for key, value in vars(item).items()
                    if not key.startswith("_")
                }
            )
            continue
        try:
            rows.append(dict(item))
        except Exception:
            rows.append({"value": item})
    return rows


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _normalize_section_path(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        text = str(value).strip()
        return [text] if text else []
    if isinstance(value, Sequence):
        path: list[str] = []
        for item in value:
            text = _normalize_text(item)
            if text is not None:
                path.append(text)
        return path
    text = _normalize_text(value)
    return [text] if text is not None else []


def _normalize_document_ids(document_ids: Sequence[UUID | str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    if not document_ids:
        return normalized

    for value in document_ids:
        text = _normalize_text(value)
        if text is None or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def _normalize_filters(filters: RetrievalFilters | Mapping[str, Any] | None) -> dict[str, Any]:
    if filters is None:
        return {}
    if isinstance(filters, RetrievalFilters):
        model = filters
    elif isinstance(filters, Mapping):
        model = RetrievalFilters.model_validate(dict(filters))
    else:
        model = RetrievalFilters.model_validate(filters)
    return model.model_dump(mode="json", exclude_none=True)


def build_qdrant_filter(
    document_ids: Sequence[UUID | str] | None,
    filters: RetrievalFilters | Mapping[str, Any] | None = None,
) -> qdrant_models.Filter | None:
    conditions: list[qdrant_models.Condition] = []

    normalized_document_ids = _normalize_document_ids(document_ids)
    if normalized_document_ids:
        conditions.append(
            qdrant_models.FieldCondition(
                key=QdrantPayloadKey.DOCUMENT_ID,
                match=qdrant_models.MatchAny(any=normalized_document_ids),
            )
        )

    normalized_filters = _normalize_filters(filters)
    mime_types = _normalize_section_path(normalized_filters.get("mime_types"))
    if mime_types:
        conditions.append(
            qdrant_models.FieldCondition(
                key=QdrantPayloadKey.MIME_TYPE,
                match=qdrant_models.MatchAny(any=mime_types),
            )
        )

    heading = _normalize_text(normalized_filters.get("heading"))
    if heading is not None:
        conditions.append(
            qdrant_models.FieldCondition(
                key=QdrantPayloadKey.HEADING,
                match=qdrant_models.MatchText(text=heading),
            )
        )

    for section_segment in _normalize_section_path(normalized_filters.get("section_path")):
        conditions.append(
            qdrant_models.FieldCondition(
                key=QdrantPayloadKey.SECTION_PATH,
                match=qdrant_models.MatchValue(value=section_segment),
            )
        )

    page_start = _normalize_int(normalized_filters.get("page_start"))
    page_end = _normalize_int(normalized_filters.get("page_end"))
    if page_end is not None:
        conditions.append(
            qdrant_models.FieldCondition(
                key=QdrantPayloadKey.PAGE_START,
                range=qdrant_models.Range(lte=page_end),
            )
        )
    if page_start is not None:
        conditions.append(
            qdrant_models.FieldCondition(
                key=QdrantPayloadKey.PAGE_END,
                range=qdrant_models.Range(gte=page_start),
            )
        )

    if not conditions:
        return None

    return qdrant_models.Filter(must=conditions)


def build_document_id_filter(
    document_ids: Sequence[UUID | str] | None,
) -> qdrant_models.Filter | None:
    return build_qdrant_filter(document_ids)


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
) -> list[float]:
    resolved_settings = _resolve_settings(settings)
    normalized_question = _normalize_text(question)
    if normalized_question is None:
        raise RetrievalError("question is required")

    client = _resolve_shopaikey_client(shopaikey_client)
    response = client.embeddings.create(
        model=resolved_settings.SHOPAIKEY_EMBEDDING_MODEL,
        input=[normalized_question],
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
) -> list[dict[str, Any]]:
    resolved_settings = _resolve_settings(settings)
    client = _resolve_qdrant_client(qdrant_client)
    query_filter = build_qdrant_filter(document_ids, filters)
    response = client.query_points(
        collection_name=resolved_settings.QDRANT_COLLECTION,
        query=list(query_embedding),
        query_filter=query_filter,
        limit=resolved_settings.RETRIEVAL_SEMANTIC_TOP_K,
        with_payload=True,
        with_vectors=False,
    )

    results: list[dict[str, Any]] = []
    for point in _response_rows(response):
        payload = point.get("payload") if isinstance(point, Mapping) else None
        if not isinstance(payload, Mapping):
            payload = {}

        point_score = point.get("score") if isinstance(point, Mapping) else None

        chunk_id = _normalize_text(
            payload.get(QdrantPayloadKey.CHUNK_ID) or point.get("id")
        )
        document_id = _normalize_text(payload.get(QdrantPayloadKey.DOCUMENT_ID))
        if chunk_id is None or document_id is None:
            continue

        content = _normalize_text(payload.get(QdrantPayloadKey.TEXT)) or ""
        results.append(
            {
                "id": chunk_id,
                "chunk_id": chunk_id,
                "document_id": document_id,
                "file_name": _normalize_text(payload.get(QdrantPayloadKey.FILE_NAME)),
                "chunk_index": _normalize_int(payload.get(QdrantPayloadKey.CHUNK_INDEX)),
                "content": content,
                "text": content,
                "heading": payload.get(QdrantPayloadKey.HEADING),
                "section_path": _normalize_section_path(
                    payload.get(QdrantPayloadKey.SECTION_PATH)
                ),
                "page_start": _normalize_int(payload.get(QdrantPayloadKey.PAGE_START)),
                "page_end": _normalize_int(payload.get(QdrantPayloadKey.PAGE_END)),
                "chunk_type": _normalize_text(payload.get(QdrantPayloadKey.CHUNK_TYPE)),
                "token_count": _normalize_int(payload.get(QdrantPayloadKey.TOKEN_COUNT)),
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


def _sort_chunks_by_rerank_fallback(
    chunks: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [dict(chunk) for chunk in sorted(chunks, key=_fallback_rerank_sort_key)]


def _semantic_search_path(
    question: str,
    *,
    document_ids: Sequence[UUID | str] | None,
    filters: RetrievalFilters | Mapping[str, Any] | None,
    settings: Settings,
    qdrant_client: Any | None,
    shopaikey_client: Any | None,
) -> tuple[list[float], list[dict[str, Any]]]:
    query_embedding = embed_question(
        question,
        settings=settings,
        shopaikey_client=shopaikey_client,
    )
    semantic_rows = search_semantic_chunks(
        query_embedding,
        document_ids=document_ids,
        filters=filters,
        settings=settings,
        qdrant_client=qdrant_client,
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
) -> tuple[list[float], list[dict[str, Any]]]:
    resolved_settings = _resolve_settings(settings)
    return _semantic_search_path(
        question,
        document_ids=document_ids,
        filters=filters,
        settings=resolved_settings,
        qdrant_client=qdrant_client,
        shopaikey_client=shopaikey_client,
    )


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

    try:
        query_embedding, semantic_candidates = _semantic_search_path(
            normalized_question,
            document_ids=normalized_document_ids,
            filters=normalized_filters,
            settings=resolved_settings,
            qdrant_client=qdrant_client,
            shopaikey_client=shopaikey_client,
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
        retrieved_chunks = score_fusion.fuse_candidates(
            [semantic_candidates, keyword_candidates],
            settings=resolved_settings,
        )
        fallback_path = None

    return {
        "question": normalized_question,
        "document_ids": normalized_document_ids,
        "query_embedding": query_embedding,
        "path_candidates": {
            RetrievalPath.SEMANTIC.value: semantic_candidates,
            RetrievalPath.KEYWORD.value: keyword_candidates,
        },
        "fused_candidates": retrieved_chunks,
        "retrieved_chunks": retrieved_chunks,
        "retrieval_metrics": {
            "semantic_candidate_count": len(semantic_candidates),
            "keyword_candidate_count": len(keyword_candidates),
            "fused_candidate_count": len(retrieved_chunks),
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
) -> list[dict[str, Any]]:
    resolved_settings = _resolve_settings(settings)
    normalized_question = _normalize_text(question)
    if normalized_question is None:
        raise RetrievalError("question is required")

    if not chunks:
        return []

    candidate_chunks = [
        dict(chunk)
        for chunk in chunks[: resolved_settings.RETRIEVAL_RERANK_CANDIDATE_TOP_K]
    ]
    fallback_chunks = _sort_chunks_by_rerank_fallback(candidate_chunks)[
        : resolved_settings.RETRIEVAL_FINAL_TOP_K
    ]
    if not resolved_settings.ENABLE_RERANK:
        return fallback_chunks

    client = _resolve_jina_client(jina_client)
    transport = getattr(client, "http_client", client)
    model = getattr(client, "model", resolved_settings.JINA_RERANK_MODEL)

    documents = [
        str(chunk.get("content") or chunk.get("text") or "") for chunk in candidate_chunks
    ]
    try:
        response = transport.post(
            "/rerank",
            json={
                "model": model,
                "query": normalized_question,
                "documents": documents,
                "top_n": min(resolved_settings.RETRIEVAL_FINAL_TOP_K, len(documents)),
                "return_documents": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
        rankings = _extract_jina_rankings(payload)
    except Exception as exc:  # pragma: no cover - fallback exercised in tests
        logger.warning("Jina rerank failed, falling back to deterministic order: %s", exc)
        return fallback_chunks

    if not rankings:
        return fallback_chunks

    ranked_chunks: list[dict[str, Any]] = []
    seen_indexes: set[int] = set()
    for ranking in rankings:
        index = ranking["index"]
        if index is None or index < 0 or index >= len(candidate_chunks) or index in seen_indexes:
            logger.warning(
                "Jina rerank returned invalid indexes, falling back to deterministic order"
            )
            return fallback_chunks
        seen_indexes.add(index)
        chunk = dict(candidate_chunks[index])
        chunk["rerank_score"] = ranking["score"]
        ranked_chunks.append(chunk)
        if len(ranked_chunks) >= resolved_settings.RETRIEVAL_FINAL_TOP_K:
            break

    if not ranked_chunks:
        return fallback_chunks

    return ranked_chunks


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
    reranked_chunks = rerank_chunks(
        normalized_question,
        retrieved_chunks,
        settings=resolved_settings,
        jina_client=jina_client,
    )
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
