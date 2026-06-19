from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.errors import safe_detail
from app.services import retrieval
from app.services.shopaikey_client import create_shopaikey_client
from app.services.supabase_client import create_supabase_client

logger = logging.getLogger(__name__)

ANSWER_SYSTEM_PROMPT = (
    "You are a personal document RAG assistant.\n\n"
    "Rules:\n"
    "- Answer using only the provided context.\n"
    "- If the context does not contain enough information, say that the indexed documents do not contain enough information.\n"
    "- Do not invent facts.\n"
    "- Do not invent sources.\n"
    "- Cite the source chunks used in the answer.\n"
    "- Keep the answer clear and practical."
)
ANSWER_USER_PROMPT_TEMPLATE = (
    "Context:\n"
    "{context}\n\n"
    "Question:\n"
    "{question}\n\n"
    "Answer using only the context."
)
NO_RELEVANT_INFORMATION_MESSAGE = (
    "No relevant information found in indexed documents."
)
DEFAULT_QUERY_ERROR = "Query failed"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


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


def _normalize_document_ids(
    document_ids: Sequence[UUID | str] | UUID | str | bytes | None,
) -> list[str]:
    if document_ids is None:
        return []

    if isinstance(document_ids, (str, bytes)):
        text = _normalize_text(document_ids)
        return [text] if text is not None else []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in document_ids:
        text = _normalize_text(value)
        if text is None or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def _question_text(state: Mapping[str, Any]) -> str | None:
    return _normalize_text(state.get("prepared_query") or state.get("question"))


def _resolve_context_chunks(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("context_chunks", "reranked_chunks", "retrieved_chunks"):
        chunks = state.get(key)
        if not isinstance(chunks, list) or not chunks:
            continue
        normalized_chunks: list[dict[str, Any]] = []
        for chunk in chunks:
            if isinstance(chunk, Mapping):
                normalized_chunks.append(dict(chunk))
        if normalized_chunks:
            return normalized_chunks
    return []


def _chunk_content(chunk: Mapping[str, Any]) -> str:
    return _normalize_text(chunk.get("content") or chunk.get("text")) or ""


def _format_page_range(
    page_start: Any,
    page_end: Any,
) -> str | None:
    start = _normalize_int(page_start)
    end = _normalize_int(page_end)
    if start is None and end is None:
        return None
    if start is not None and end is not None and start != end:
        return f"Pages: {start}-{end}"
    page = start if start is not None else end
    if page is None:
        return None
    return f"Pages: {page}"


def _format_context_chunk(chunk: Mapping[str, Any], position: int) -> str:
    file_name = _normalize_text(chunk.get("file_name")) or "unknown"
    chunk_id = _normalize_text(chunk.get("chunk_id") or chunk.get("id")) or "unknown"
    chunk_index = _normalize_int(chunk.get("chunk_index"))
    heading = _normalize_text(chunk.get("heading"))
    parts = [
        f"Source {position}",
        f"File: {file_name}",
        f"Chunk ID: {chunk_id}",
    ]
    if chunk_index is not None:
        parts.append(f"Chunk index: {chunk_index}")
    page_range = _format_page_range(chunk.get("page_start"), chunk.get("page_end"))
    if page_range is not None:
        parts.append(page_range)
    if heading is not None:
        parts.append(f"Heading: {heading}")
    parts.append("Text:")
    parts.append(_chunk_content(chunk))
    return "\n".join(parts)


def _build_context_prompt(context_chunks: Sequence[Mapping[str, Any]]) -> str:
    blocks = [
        _format_context_chunk(chunk, position=index)
        for index, chunk in enumerate(context_chunks, start=1)
    ]
    return "\n\n".join(blocks)


def _source_citation_from_chunk(chunk: Mapping[str, Any]) -> dict[str, Any]:
    document_id = _normalize_text(chunk.get("document_id"))
    chunk_id = _normalize_text(chunk.get("chunk_id") or chunk.get("id"))
    chunk_index = _normalize_int(chunk.get("chunk_index"))
    if document_id is None or chunk_id is None or chunk_index is None:
        raise ValueError("context chunks must include document_id, chunk_id, and chunk_index")

    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "file_name": _normalize_text(chunk.get("file_name")) or "unknown",
        "chunk_index": chunk_index,
        "page_start": _normalize_int(chunk.get("page_start")),
        "page_end": _normalize_int(chunk.get("page_end")),
        "heading": chunk.get("heading"),
        "qdrant_score": _normalize_float(chunk.get("qdrant_score")),
        "rerank_score": _normalize_float(chunk.get("rerank_score")),
    }


def _build_source_citations(context_chunks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()
    for chunk in context_chunks:
        citation = _source_citation_from_chunk(chunk)
        chunk_id = citation["chunk_id"]
        if chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk_id)
        citations.append(citation)
    return citations


def _message_metadata(state: Mapping[str, Any]) -> dict[str, Any]:
    document_ids = state.get("document_ids")
    if not isinstance(document_ids, list):
        document_ids = []

    return {
        "document_ids": list(document_ids),
        "prepared_query": _question_text(state),
        "retrieved_chunk_count": len(state.get("retrieved_chunks") or []),
        "reranked_chunk_count": len(state.get("reranked_chunks") or []),
        "context_chunk_count": len(state.get("context_chunks") or []),
    }


def _extract_chat_content(response: Any) -> str | None:
    output_text = getattr(response, "output_text", None)
    normalized_output_text = _normalize_text(output_text)
    if normalized_output_text is not None:
        return normalized_output_text

    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, Mapping):
        choices = response.get("choices")
    if not choices:
        return None

    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None and isinstance(first_choice, Mapping):
        message = first_choice.get("message")

    if message is not None:
        content = getattr(message, "content", None)
        if content is None and isinstance(message, Mapping):
            content = message.get("content")
        normalized_content = _normalize_text(content)
        if normalized_content is not None:
            return normalized_content

    text = getattr(first_choice, "text", None)
    if text is None and isinstance(first_choice, Mapping):
        text = first_choice.get("text")
    return _normalize_text(text)


def prepare_query_node(state: Mapping[str, Any], *, settings: Settings | None = None) -> dict[str, Any]:
    _resolve_settings(settings)

    question = _normalize_text(state.get("question"))
    if question is None:
        return {"error_message": "question is required"}

    document_ids = _normalize_document_ids(state.get("document_ids"))
    save_message = bool(state.get("save_message", False))
    return {
        "question": question,
        "prepared_query": question,
        "document_ids": document_ids,
        "save_message": save_message,
    }


def retrieve_qdrant_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    prepared_query = _question_text(state)
    if prepared_query is None:
        return {"error_message": "prepared_query is required"}

    document_ids = _normalize_document_ids(state.get("document_ids"))
    try:
        query_embedding = retrieval.embed_question(
            prepared_query,
            settings=resolved_settings,
            shopaikey_client=shopaikey_client,
        )
        retrieved_chunks = retrieval.search_semantic_chunks(
            query_embedding,
            document_ids=document_ids,
            settings=resolved_settings,
            qdrant_client=qdrant_client,
        )
        retrieval_hints = retrieval.extract_retrieval_hints(
            prepared_query,
            settings=resolved_settings,
            shopaikey_client=shopaikey_client,
        )
        return {
            "prepared_query": prepared_query,
            "document_ids": document_ids,
            "query_embedding": query_embedding,
            "retrieval_hints": retrieval_hints,
            "retrieved_chunks": retrieved_chunks,
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

    context_chunks = _resolve_context_chunks(state)
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
        context = _build_context_prompt(context_chunks)
        user_prompt = ANSWER_USER_PROMPT_TEMPLATE.format(
            context=context,
            question=question,
        )
        response = client.chat.completions.create(
            model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
            messages=[
                {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=resolved_settings.TEMPERATURE,
            max_tokens=resolved_settings.MAX_OUTPUT_TOKENS,
        )
        answer = _extract_chat_content(response)
        if answer is None:
            return {
                "error_message": safe_detail(
                    "Chat completion returned empty content",
                    fallback=DEFAULT_QUERY_ERROR,
                )
            }
        return {
            "answer": answer,
            "sources": _build_source_citations(context_chunks),
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
    answer = _normalize_text(state.get("answer"))
    if question is None or answer is None:
        return {}

    try:
        sources = state.get("sources")
        if isinstance(sources, list) and sources:
            normalized_sources = [
                dict(source) for source in sources if isinstance(source, Mapping)
            ]
        else:
            normalized_sources = _build_source_citations(_resolve_context_chunks(state))

        payload = {
            "question": question,
            "answer": answer,
            "sources": normalized_sources,
            "metadata": _message_metadata(state),
        }

        client = (
            supabase_client
            if supabase_client is not None
            else create_supabase_client(resolved_settings)
        )
        client.table("messages").insert(payload).execute()
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
