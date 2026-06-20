from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.contracts import SOURCE_PREVIEW_CHARS


def normalize_text(value: Any) -> str | None:
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
        text = normalize_text(value)
        return [text] if text is not None else []
    if isinstance(value, Sequence):
        normalized: list[str] = []
        for item in value:
            text = normalize_text(item)
            if text is not None:
                normalized.append(text)
        return normalized
    text = normalize_text(value)
    return [text] if text is not None else []


def _chunk_content_preview(chunk: Mapping[str, Any]) -> str:
    content = chunk.get("content")
    if content is None:
        content = chunk.get("text")
    if content is None:
        return ""
    return str(content)[:SOURCE_PREVIEW_CHARS]


def resolve_context_chunks(state: Mapping[str, Any]) -> list[dict[str, Any]]:
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
    return normalize_text(chunk.get("content") or chunk.get("text")) or ""


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
    file_name = normalize_text(chunk.get("file_name")) or "unknown"
    chunk_id = normalize_text(chunk.get("chunk_id") or chunk.get("id")) or "unknown"
    chunk_index = _normalize_int(chunk.get("chunk_index"))
    heading = normalize_text(chunk.get("heading"))
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


def build_context_prompt(context_chunks: Sequence[Mapping[str, Any]]) -> str:
    blocks = [
        _format_context_chunk(chunk, position=index)
        for index, chunk in enumerate(context_chunks, start=1)
    ]
    return "\n\n".join(blocks)


def _source_citation_from_chunk(chunk: Mapping[str, Any]) -> dict[str, Any]:
    document_id = normalize_text(chunk.get("document_id"))
    chunk_id = normalize_text(chunk.get("chunk_id") or chunk.get("id"))
    chunk_index = _normalize_int(chunk.get("chunk_index"))
    if document_id is None or chunk_id is None or chunk_index is None:
        raise ValueError("context chunks must include document_id, chunk_id, and chunk_index")

    section_path = _normalize_section_path(chunk.get("section_path"))
    content_preview = _chunk_content_preview(chunk)
    is_neighbor_context = bool(chunk.get("is_neighbor_context"))

    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "file_name": normalize_text(chunk.get("file_name")) or "unknown",
        "chunk_index": chunk_index,
        "page_start": _normalize_int(chunk.get("page_start")),
        "page_end": _normalize_int(chunk.get("page_end")),
        "heading": chunk.get("heading"),
        "qdrant_score": _normalize_float(chunk.get("qdrant_score")),
        "rerank_score": _normalize_float(chunk.get("rerank_score")),
        "section_path": section_path,
        "content_preview": content_preview,
        "is_neighbor_context": is_neighbor_context,
    }


def build_source_citations(context_chunks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
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


def message_metadata(state: Mapping[str, Any]) -> dict[str, Any]:
    document_ids = state.get("document_ids")
    if not isinstance(document_ids, list):
        document_ids = []

    return {
        "document_ids": list(document_ids),
        "prepared_query": normalize_text(state.get("prepared_query") or state.get("question")),
        "retrieved_chunk_count": len(state.get("retrieved_chunks") or []),
        "reranked_chunk_count": len(state.get("reranked_chunks") or []),
        "context_chunk_count": len(state.get("context_chunks") or []),
    }


def extract_chat_content(response: Any) -> str | None:
    output_text = getattr(response, "output_text", None)
    normalized_output_text = normalize_text(output_text)
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
        normalized_content = normalize_text(content)
        if normalized_content is not None:
            return normalized_content

    text = getattr(first_choice, "text", None)
    if text is None and isinstance(first_choice, Mapping):
        text = first_choice.get("text")
    return normalize_text(text)


_build_context_prompt = build_context_prompt
_build_source_citations = build_source_citations
_extract_chat_content = extract_chat_content
_message_metadata = message_metadata
_normalize_text = normalize_text
_resolve_context_chunks = resolve_context_chunks


__all__ = [
    "build_context_prompt",
    "build_source_citations",
    "extract_chat_content",
    "message_metadata",
    "normalize_text",
    "resolve_context_chunks",
    "_build_context_prompt",
    "_build_source_citations",
    "_chunk_content",
    "_chunk_content_preview",
    "_extract_chat_content",
    "_format_context_chunk",
    "_format_page_range",
    "_message_metadata",
    "_normalize_float",
    "_normalize_int",
    "_normalize_section_path",
    "_normalize_text",
    "_resolve_context_chunks",
    "_source_citation_from_chunk",
]
