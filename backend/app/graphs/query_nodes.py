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
    build_answer_messages,
)
from app.models.schemas import RetrievalFilters
from app.services import messages as message_service
from app.services import retrieval
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

    try:
        reranked_chunks = retrieval.rerank_chunks(
            question,
            retrieved_chunks,
            settings=resolved_settings,
            jina_client=jina_client,
        )
        return {"reranked_chunks": reranked_chunks}
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


def expand_neighbor_context_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    reranked_chunks = state.get("reranked_chunks")
    if not isinstance(reranked_chunks, list) or not reranked_chunks:
        return {"context_chunks": []}

    try:
        context_chunks = retrieval.expand_neighbor_context(
            reranked_chunks,
            settings=resolved_settings,
            supabase_client=supabase_client,
            retrieval_hints=state.get("retrieval_hints"),
            document_ids=_normalize_document_ids(state.get("document_ids")),
        )
        return {"context_chunks": context_chunks}
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
        if isinstance(sources, list) and sources:
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
    "expand_neighbor_context_node",
    "generate_answer_node",
    "jina_rerank_node",
    "prepare_query_node",
    "retrieve_qdrant_node",
    "save_message_optional_node",
]
