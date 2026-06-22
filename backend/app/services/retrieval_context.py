from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any
from uuid import UUID

from app.chunking.token_chunker import DEFAULT_ENCODING_NAME, _load_default_tokenizer
from app.core.config import Settings, get_settings
from app.core.contracts import ContextMode, RetrievalPath
from app.services import chunks as chunk_service
from app.services.retrieval_boundaries import resolve_boundary_chunks
from app.services.retrieval_hints import normalize_retrieval_hints


class RetrievalContextError(RuntimeError):
    """Raised when retrieval context expansion cannot be completed."""


NEIGHBOR_CONTEXT_MODE = ContextMode.NEIGHBOR
SECTION_AWARE_CONTEXT_MODE = ContextMode.SECTION_AWARE


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


def _normalize_retrieval_paths(value: Any) -> list[str]:
    allowed_paths = {path.value for path in RetrievalPath}
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        text = _normalize_text(value)
        return [text] if text in allowed_paths else []
    if isinstance(value, Sequence):
        paths: list[str] = []
        for item in value:
            if isinstance(item, RetrievalPath):
                text = item.value
            else:
                text = _normalize_text(item)
            if text is not None and text in allowed_paths and text not in paths:
                paths.append(text)
        return paths
    text = _normalize_text(value)
    return [text] if text in allowed_paths else []


def _normalize_context_mode(value: Any) -> ContextMode:
    mode = _normalize_text(value)
    if mode is None:
        return SECTION_AWARE_CONTEXT_MODE
    try:
        return ContextMode(mode.lower())
    except ValueError as exc:
        raise RetrievalContextError(f"Unsupported retrieval context mode: {value}") from exc


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


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        text = _normalize_text(value)
        return [text] if text is not None else []
    if isinstance(value, Sequence):
        values: list[str] = []
        for item in value:
            text = _normalize_text(item)
            if text is not None and text not in values:
                values.append(text)
        return values
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


@lru_cache(maxsize=1)
def _context_tokenizer() -> Any:
    return _load_default_tokenizer(DEFAULT_ENCODING_NAME)


def _count_text_tokens(text: str) -> int:
    normalized = _normalize_text(text)
    if normalized is None:
        return 0
    try:
        return len(_context_tokenizer().encode(normalized))
    except Exception:
        return len(normalized.split())


def _truncate_prompt_text_to_tokens(text: str, max_tokens: int) -> str:
    normalized = _normalize_text(text) or ""
    if max_tokens <= 0 or not normalized:
        return ""
    try:
        tokenizer = _context_tokenizer()
        tokens = tokenizer.encode(normalized)
        if len(tokens) <= max_tokens:
            return normalized
        return tokenizer.decode(tokens[:max_tokens]).strip()
    except Exception:
        return " ".join(normalized.split()[:max_tokens])


def _normalize_context_chunk(
    chunk: Mapping[str, Any],
    *,
    file_name_override: str | None = None,
    is_neighbor_context: bool | None = None,
) -> dict[str, Any]:
    chunk_id = _normalize_text(chunk.get("chunk_id") or chunk.get("id"))
    if chunk_id is None:
        raise RetrievalContextError("Chunk id is required")

    document_id = _normalize_text(chunk.get("document_id"))
    if document_id is None:
        raise RetrievalContextError("Document id is required")

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
        "subquery_ids": _normalize_string_list(chunk.get("subquery_ids")),
    }
    fusion_score = _normalize_float(chunk.get("fusion_score"))
    if fusion_score is not None:
        normalized["fusion_score"] = fusion_score
    retrieval_paths = _normalize_retrieval_paths(chunk.get("retrieval_paths"))
    if retrieval_paths:
        normalized["retrieval_paths"] = retrieval_paths
    citation_key = _normalize_text(chunk.get("citation_key"))
    if citation_key is not None:
        normalized["citation_key"] = citation_key
    prompt_content = _normalize_text(chunk.get("prompt_content"))
    if prompt_content is not None:
        normalized["prompt_content"] = prompt_content
    if chunk.get("context_truncated"):
        normalized["context_truncated"] = True
    if is_neighbor_context is not None:
        normalized["is_neighbor_context"] = is_neighbor_context
    return normalized


def _neighbor_indexes(chunk_index: int, window: int) -> list[int]:
    if window <= 0:
        return []

    indexes: list[int] = []
    for offset in range(1, window + 1):
        if chunk_index - offset >= 0:
            indexes.append(chunk_index - offset)
        indexes.append(chunk_index + offset)
    return indexes


def _chunk_text(chunk: Mapping[str, Any]) -> str:
    return _normalize_text(chunk.get("content") or chunk.get("text")) or ""


def _chunk_token_cost(chunk: Mapping[str, Any]) -> int:
    stored_token_count = _normalize_int(chunk.get("token_count"))
    if stored_token_count is not None:
        return stored_token_count
    return _count_text_tokens(_chunk_text(chunk))


def _ordered_subquery_ids(chunks: Sequence[Mapping[str, Any]]) -> list[str]:
    ordered: list[str] = []
    for chunk in chunks:
        for subquery_id in _normalize_string_list(chunk.get("subquery_ids")):
            if subquery_id not in ordered:
                ordered.append(subquery_id)
    return ordered


def _subquery_coverage(
    context_chunks: Sequence[Mapping[str, Any]],
    *,
    subquery_ids: Sequence[str],
) -> dict[str, int]:
    coverage = {subquery_id: 0 for subquery_id in subquery_ids}
    for chunk in context_chunks:
        for subquery_id in _normalize_string_list(chunk.get("subquery_ids")):
            if subquery_id in coverage:
                coverage[subquery_id] += 1
    return coverage


def _collect_boundary_chunks(
    normalized_reranked_chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings,
    supabase_client: Any | None,
    retrieval_hints: Mapping[str, Any] | None,
    document_ids: Sequence[UUID | str] | None,
) -> list[dict[str, Any]]:
    normalized_hints = normalize_retrieval_hints(retrieval_hints or {})
    boundary_positions = normalized_hints["boundary_positions"]
    if not boundary_positions:
        return []

    hint_document_ids = _normalize_document_ids(document_ids)
    if not hint_document_ids:
        hint_document_ids = list(
            dict.fromkeys(chunk["document_id"] for chunk in normalized_reranked_chunks)
        )

    boundary_chunks: list[dict[str, Any]] = []
    for document_id in hint_document_ids:
        boundary_rows = resolve_boundary_chunks(
            document_id,
            boundary_positions,
            settings=settings,
            supabase_client=supabase_client,
        )
        for boundary_row in boundary_rows:
            boundary_chunks.append(
                _normalize_context_chunk(boundary_row, is_neighbor_context=True)
            )
    return boundary_chunks


def _collect_neighbor_chunks(
    normalized_reranked_chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings,
    supabase_client: Any | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    same_section_neighbors: list[dict[str, Any]] = []
    generic_neighbors: list[dict[str, Any]] = []
    section_window = settings.RETRIEVAL_SECTION_SIBLING_WINDOW
    context_window = settings.RETRIEVAL_CONTEXT_WINDOW

    for chunk in normalized_reranked_chunks:
        document_id = chunk["document_id"]
        chunk_index = chunk.get("chunk_index")
        if chunk_index is None:
            continue

        section_indexes = set(_neighbor_indexes(chunk_index, section_window))
        context_indexes = set(_neighbor_indexes(chunk_index, context_window))
        candidate_indexes = sorted(section_indexes | context_indexes)
        if not candidate_indexes:
            continue

        candidate_rows = chunk_service.get_chunks_by_document_and_indexes(
            document_id,
            candidate_indexes,
            settings=settings,
            supabase_client=supabase_client,
        )

        anchor_section_path = chunk["section_path"]
        for candidate_row in candidate_rows:
            candidate_chunk = _normalize_context_chunk(
                candidate_row,
                file_name_override=chunk.get("file_name"),
                is_neighbor_context=True,
            )
            candidate_index = candidate_chunk.get("chunk_index")
            if candidate_index is None:
                continue

            if (
                candidate_index in section_indexes
                and candidate_chunk["section_path"] == anchor_section_path
            ):
                same_section_neighbors.append(candidate_chunk)
                continue

            if candidate_index in context_indexes:
                generic_neighbors.append(candidate_chunk)

    return same_section_neighbors, generic_neighbors


def expand_neighbor_context_result(
    reranked_chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
    retrieval_hints: Mapping[str, Any] | None = None,
    document_ids: Sequence[UUID | str] | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    if not reranked_chunks:
        return {
            "context_chunks": [],
            "retrieval_metrics": {
                "context_token_count": 0,
                "context_candidate_count": 0,
                "context_neighbor_count": 0,
                "context_subquery_coverage": {},
            },
        }

    normalized_reranked_chunks = [
        _normalize_context_chunk(chunk)
        for chunk in reranked_chunks
        if _normalize_text(chunk.get("chunk_id") or chunk.get("id")) is not None
    ]
    context_mode = _normalize_context_mode(resolved_settings.RETRIEVAL_CONTEXT_MODE)
    ordered_subqueries = _ordered_subquery_ids(normalized_reranked_chunks)

    selected: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()
    selected_token_count = 0

    def can_select_more() -> bool:
        return (
            len(selected) < resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES
            and selected_token_count < resolved_settings.RETRIEVAL_CONTEXT_MAX_TOKENS
        )

    def try_add_chunk(
        chunk: Mapping[str, Any],
        *,
        allow_oversized_top: bool = False,
    ) -> bool:
        nonlocal selected_token_count

        if len(selected) >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
            return False

        chunk_id = _normalize_text(chunk.get("chunk_id") or chunk.get("id"))
        if chunk_id is None:
            raise RetrievalContextError("Chunk id is required")
        if chunk_id in seen_chunk_ids:
            return False

        token_cost = _chunk_token_cost(chunk)
        remaining_tokens = resolved_settings.RETRIEVAL_CONTEXT_MAX_TOKENS - selected_token_count
        if token_cost > remaining_tokens:
            if allow_oversized_top and not selected:
                truncated_chunk = dict(chunk)
                truncated_chunk["prompt_content"] = _truncate_prompt_text_to_tokens(
                    _chunk_text(chunk),
                    resolved_settings.RETRIEVAL_CONTEXT_MAX_TOKENS,
                )
                truncated_chunk["context_truncated"] = True
                selected.append(truncated_chunk)
                seen_chunk_ids.add(chunk_id)
                selected_token_count = resolved_settings.RETRIEVAL_CONTEXT_MAX_TOKENS
                return True
            return False

        selected.append(dict(chunk))
        seen_chunk_ids.add(chunk_id)
        selected_token_count += token_cost
        return True

    def queued_neighbors_fill_context(
        same_section_neighbors: Sequence[Mapping[str, Any]],
        generic_neighbors: Sequence[Mapping[str, Any]],
    ) -> bool:
        simulated_selected_count = len(selected)
        simulated_seen = set(seen_chunk_ids)
        simulated_tokens = selected_token_count

        for candidate in [*same_section_neighbors, *generic_neighbors]:
            if simulated_selected_count >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
                return True

            chunk_id = _normalize_text(candidate.get("chunk_id") or candidate.get("id"))
            if chunk_id is None or chunk_id in simulated_seen:
                continue

            token_cost = _chunk_token_cost(candidate)
            remaining_tokens = resolved_settings.RETRIEVAL_CONTEXT_MAX_TOKENS - simulated_tokens
            if token_cost > remaining_tokens:
                continue

            simulated_selected_count += 1
            simulated_seen.add(chunk_id)
            simulated_tokens += token_cost
            if (
                simulated_selected_count >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES
                or simulated_tokens >= resolved_settings.RETRIEVAL_CONTEXT_MAX_TOKENS
            ):
                return True

        return False

    # Preserve one available top chunk per subquery before lower-ranked filling.
    for subquery_id in ordered_subqueries:
        if len(selected) >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
            break
        if subquery_id in _subquery_coverage(selected, subquery_ids=[subquery_id]):
            current = _subquery_coverage(selected, subquery_ids=[subquery_id])[subquery_id]
            if current > 0:
                continue

        candidate = next(
            (
                chunk
                for chunk in normalized_reranked_chunks
                if subquery_id in chunk.get("subquery_ids", [])
                and _normalize_text(chunk.get("chunk_id")) not in seen_chunk_ids
            ),
            None,
        )
        if candidate is None:
            continue
        try_add_chunk(candidate, allow_oversized_top=not selected)
        if not can_select_more():
            break

    # Fill remaining ranked chunks in stable rank order.
    if can_select_more():
        for chunk in normalized_reranked_chunks:
            if len(selected) >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
                break
            try_add_chunk(chunk, allow_oversized_top=not selected)
            if not can_select_more():
                break

    # Add requested boundary chunks after ranked chunks.
    if can_select_more():
        for boundary_chunk in _collect_boundary_chunks(
            normalized_reranked_chunks,
            settings=resolved_settings,
            supabase_client=supabase_client,
            retrieval_hints=retrieval_hints,
            document_ids=document_ids,
        ):
            if len(selected) >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
                break
            try_add_chunk(boundary_chunk)
            if not can_select_more():
                break

    # Collect and add neighbors with global same-section priority.
    if can_select_more():
        if context_mode == NEIGHBOR_CONTEXT_MODE:
            for chunk in normalized_reranked_chunks:
                if len(selected) >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
                    break
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
                    chunk["document_id"],
                    neighbor_indexes,
                    settings=resolved_settings,
                    supabase_client=supabase_client,
                )
                for neighbor_row in neighbor_rows:
                    try_add_chunk(
                        _normalize_context_chunk(
                            neighbor_row,
                            file_name_override=chunk.get("file_name"),
                            is_neighbor_context=True,
                        )
                    )
                    if not can_select_more():
                        break
                if not can_select_more():
                    break
        else:
            same_section_neighbors: list[dict[str, Any]] = []
            generic_neighbors: list[dict[str, Any]] = []
            section_window = resolved_settings.RETRIEVAL_SECTION_SIBLING_WINDOW
            context_window = resolved_settings.RETRIEVAL_CONTEXT_WINDOW

            for chunk in normalized_reranked_chunks:
                chunk_index = chunk.get("chunk_index")
                if chunk_index is None:
                    continue

                section_indexes = set(_neighbor_indexes(chunk_index, section_window))
                context_indexes = set(_neighbor_indexes(chunk_index, context_window))
                candidate_indexes = sorted(section_indexes | context_indexes)
                if not candidate_indexes:
                    continue

                candidate_rows = chunk_service.get_chunks_by_document_and_indexes(
                    chunk["document_id"],
                    candidate_indexes,
                    settings=resolved_settings,
                    supabase_client=supabase_client,
                )
                anchor_section_path = chunk["section_path"]
                for candidate_row in candidate_rows:
                    candidate_chunk = _normalize_context_chunk(
                        candidate_row,
                        file_name_override=chunk.get("file_name"),
                        is_neighbor_context=True,
                    )
                    candidate_index = candidate_chunk.get("chunk_index")
                    if candidate_index is None:
                        continue
                    if (
                        candidate_index in section_indexes
                        and candidate_chunk["section_path"] == anchor_section_path
                    ):
                        same_section_neighbors.append(candidate_chunk)
                    elif candidate_index in context_indexes:
                        generic_neighbors.append(candidate_chunk)

                if queued_neighbors_fill_context(
                    same_section_neighbors,
                    generic_neighbors,
                ):
                    break

            for neighbor_chunk in same_section_neighbors:
                if len(selected) >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
                    break
                try_add_chunk(neighbor_chunk)
                if not can_select_more():
                    break

            if can_select_more():
                for neighbor_chunk in generic_neighbors:
                    if len(selected) >= resolved_settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
                        break
                    try_add_chunk(neighbor_chunk)
                    if not can_select_more():
                        break

    retrieval_metrics = {
        "context_token_count": selected_token_count,
        "context_candidate_count": len(selected),
        "context_neighbor_count": sum(
            1 for chunk in selected if bool(chunk.get("is_neighbor_context"))
        ),
        "context_subquery_coverage": _subquery_coverage(
            selected,
            subquery_ids=ordered_subqueries,
        ),
    }
    return {
        "context_chunks": selected,
        "retrieval_metrics": retrieval_metrics,
    }


def expand_neighbor_context(
    reranked_chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
    retrieval_hints: Mapping[str, Any] | None = None,
    document_ids: Sequence[UUID | str] | None = None,
) -> list[dict[str, Any]]:
    return expand_neighbor_context_result(
        reranked_chunks,
        settings=settings,
        supabase_client=supabase_client,
        retrieval_hints=retrieval_hints,
        document_ids=document_ids,
    )["context_chunks"]
