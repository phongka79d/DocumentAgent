from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from uuid import UUID

from qdrant_client.http import models as qdrant_models

from app.core.config import Settings, get_settings
from app.services import chunks as chunk_service
from app.services.qdrant_client import create_qdrant_client
from app.services.shopaikey_client import create_shopaikey_client
from app.services.jina_client import create_jina_client

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


def build_document_id_filter(
    document_ids: Sequence[UUID | str] | None,
) -> qdrant_models.Filter | None:
    normalized_document_ids = _normalize_document_ids(document_ids)
    if not normalized_document_ids:
        return None

    return qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="document_id",
                match=qdrant_models.MatchAny(any=normalized_document_ids),
            )
        ]
    )


def _normalize_context_chunk(
    chunk: Mapping[str, Any],
    *,
    file_name_override: str | None = None,
    is_neighbor_context: bool | None = None,
) -> dict[str, Any]:
    chunk_id = _normalize_text(chunk.get("chunk_id") or chunk.get("id"))
    if chunk_id is None:
        raise RetrievalError("Chunk id is required")

    document_id = _normalize_text(chunk.get("document_id"))
    if document_id is None:
        raise RetrievalError("Document id is required")

    content = _normalize_text(chunk.get("content") or chunk.get("text")) or ""
    file_name = _normalize_text(chunk.get("file_name") or file_name_override)

    normalized: dict[str, Any] = {
        "id": chunk_id,
        "chunk_id": chunk_id,
        "document_id": document_id,
        "file_name": file_name,
        "chunk_index": _normalize_int(chunk.get("chunk_index")),
        "content": content,
        "text": content,
        "heading": chunk.get("heading"),
        "section_path": _normalize_section_path(chunk.get("section_path")),
        "page_start": _normalize_int(chunk.get("page_start")),
        "page_end": _normalize_int(chunk.get("page_end")),
        "chunk_type": _normalize_text(chunk.get("chunk_type")),
        "token_count": _normalize_int(chunk.get("token_count")),
        "qdrant_score": _normalize_float(chunk.get("qdrant_score")),
        "rerank_score": _normalize_float(chunk.get("rerank_score")),
    }
    if is_neighbor_context is not None:
        normalized["is_neighbor_context"] = is_neighbor_context
    return normalized


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
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
) -> list[dict[str, Any]]:
    resolved_settings = _resolve_settings(settings)
    client = _resolve_qdrant_client(qdrant_client)
    query_filter = build_document_id_filter(document_ids)
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

        chunk_id = _normalize_text(payload.get("chunk_id") or point.get("id"))
        document_id = _normalize_text(payload.get("document_id"))
        if chunk_id is None or document_id is None:
            continue

        content = _normalize_text(payload.get("text")) or ""
        results.append(
            {
                "id": chunk_id,
                "chunk_id": chunk_id,
                "document_id": document_id,
                "file_name": _normalize_text(payload.get("file_name")),
                "chunk_index": _normalize_int(payload.get("chunk_index")),
                "content": content,
                "text": content,
                "heading": payload.get("heading"),
                "section_path": _normalize_section_path(payload.get("section_path")),
                "page_start": _normalize_int(payload.get("page_start")),
                "page_end": _normalize_int(payload.get("page_end")),
                "chunk_type": _normalize_text(payload.get("chunk_type")),
                "token_count": _normalize_int(payload.get("token_count")),
                "qdrant_score": _normalize_float(point_score),
                "rerank_score": None,
            }
        )
    return results


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
                "index": _normalize_int(index) if index is not None else position,
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

    fallback_chunks = _sort_chunks_by_qdrant_score(chunks)[
        : resolved_settings.RETRIEVAL_FINAL_TOP_K
    ]
    if not resolved_settings.ENABLE_RERANK:
        return fallback_chunks

    client = _resolve_jina_client(jina_client)
    transport = getattr(client, "http_client", client)
    model = getattr(client, "model", resolved_settings.JINA_RERANK_MODEL)

    documents = [str(chunk.get("content") or chunk.get("text") or "") for chunk in chunks]
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
        logger.warning("Jina rerank failed, falling back to Qdrant scores: %s", exc)
        return fallback_chunks

    if not rankings:
        return fallback_chunks

    ranked_chunks: list[dict[str, Any]] = []
    for ranking in rankings:
        index = ranking["index"]
        if index is None or index < 0 or index >= len(chunks):
            continue
        chunk = dict(chunks[index])
        chunk["rerank_score"] = ranking["score"]
        ranked_chunks.append(chunk)
        if len(ranked_chunks) >= resolved_settings.RETRIEVAL_FINAL_TOP_K:
            break

    if not ranked_chunks:
        return fallback_chunks

    return ranked_chunks


def _neighbor_indexes(chunk_index: int, window: int) -> list[int]:
    if window <= 0:
        return []

    indexes: list[int] = []
    for offset in range(1, window + 1):
        if chunk_index - offset >= 0:
            indexes.append(chunk_index - offset)
        indexes.append(chunk_index + offset)
    return indexes


def expand_neighbor_context(
    reranked_chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> list[dict[str, Any]]:
    resolved_settings = _resolve_settings(settings)
    if not reranked_chunks:
        return []

    selected: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()

    normalized_reranked_chunks = [
        _normalize_context_chunk(chunk)
        for chunk in reranked_chunks
        if _normalize_text(chunk.get("chunk_id") or chunk.get("id")) is not None
    ]

    for chunk in normalized_reranked_chunks:
        chunk_id = chunk["chunk_id"]
        if chunk_id in seen_chunk_ids:
            continue
        selected.append(chunk)
        seen_chunk_ids.add(chunk_id)
        if len(selected) >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
            return selected

    for chunk in normalized_reranked_chunks:
        if len(selected) >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
            break

        document_id = chunk["document_id"]
        chunk_index = chunk.get("chunk_index")
        if chunk_index is None:
            continue

        neighbor_indexes = _neighbor_indexes(
            chunk_index,
            resolved_settings.RETRIEVAL_CONTEXT_WINDOW,
        )
        if not neighbor_indexes:
            continue

        neighbor_rows = chunk_service.get_chunks_by_document_and_indexes(
            document_id,
            neighbor_indexes,
            settings=resolved_settings,
            supabase_client=supabase_client,
        )
        for neighbor_row in neighbor_rows:
            if len(selected) >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
                break

            neighbor_chunk = _normalize_context_chunk(
                neighbor_row,
                file_name_override=chunk.get("file_name"),
                is_neighbor_context=True,
            )
            neighbor_chunk_id = neighbor_chunk["chunk_id"]
            if neighbor_chunk_id in seen_chunk_ids:
                continue
            selected.append(neighbor_chunk)
            seen_chunk_ids.add(neighbor_chunk_id)

    return selected


def retrieve_context_chunks(
    question: str,
    *,
    document_ids: Sequence[UUID | str] | None = None,
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
    retrieved_chunks = search_semantic_chunks(
        query_embedding,
        document_ids=normalized_document_ids,
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
    )
    return {
        "question": normalized_question,
        "document_ids": normalized_document_ids,
        "query_embedding": query_embedding,
        "retrieved_chunks": retrieved_chunks,
        "reranked_chunks": reranked_chunks,
        "context_chunks": context_chunks,
    }
