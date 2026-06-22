from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.models.schemas import CitationValidationResult

_VALID_MARKER_RE = re.compile(r"\[S([1-9]\d*)\]")
_SOURCE_LIKE_BRACKET_RE = re.compile(r"\[([^\]]*[sS]\d*[^\]]*)\]")
_NO_RELEVANT_INFORMATION_MESSAGE = "No relevant information found in indexed documents."
_SAFE_INSUFFICIENT_PHRASE = "indexed documents do not contain enough information"


@dataclass(frozen=True)
class CitationValidationOutput:
    validation: CitationValidationResult
    sources: list[dict[str, Any]]


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def assign_citation_keys(context_chunks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    keyed_chunks: list[dict[str, Any]] = []
    for index, chunk in enumerate(context_chunks, start=1):
        normalized = dict(chunk)
        normalized["citation_key"] = f"S{index}"
        keyed_chunks.append(normalized)
    return keyed_chunks


def _safe_insufficient_answer(answer: str) -> bool:
    normalized = answer.strip().lower()
    return (
        normalized == _NO_RELEVANT_INFORMATION_MESSAGE.lower()
        or _SAFE_INSUFFICIENT_PHRASE in normalized
    )


def _context_by_key(
    context_chunks: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    keyed_chunks = assign_citation_keys(context_chunks)
    return {
        str(chunk["citation_key"]): chunk
        for chunk in keyed_chunks
        if _normalize_text(chunk.get("chunk_id") or chunk.get("id")) is not None
    }


def _extract_invalid_source_like_markers(answer: str, valid_markers: set[str]) -> list[str]:
    invalid: list[str] = []
    for match in _SOURCE_LIKE_BRACKET_RE.finditer(answer):
        marker = match.group(1).strip()
        if marker in valid_markers:
            continue
        if marker not in invalid:
            invalid.append(marker)
    return invalid


def validate_answer_citations(
    answer: str | None,
    context_chunks: Sequence[Mapping[str, Any]],
) -> CitationValidationOutput:
    from app.graphs.query_formatting import build_source_citations

    text = _normalize_text(answer)
    context = _context_by_key(context_chunks)

    if text is None:
        validation = CitationValidationResult(valid=True)
        return CitationValidationOutput(validation=validation, sources=[])

    if _safe_insufficient_answer(text):
        validation = CitationValidationResult(valid=True)
        return CitationValidationOutput(validation=validation, sources=[])

    cited_keys: list[str] = []
    cited_chunk_ids: list[str] = []
    cited_chunks: list[dict[str, Any]] = []
    invalid_keys: list[str] = []
    valid_markers: set[str] = set()

    for match in _VALID_MARKER_RE.finditer(text):
        key = f"S{match.group(1)}"
        valid_markers.add(key)
        chunk = context.get(key)
        if chunk is None:
            if key not in invalid_keys:
                invalid_keys.append(key)
            continue
        chunk_id = _normalize_text(chunk.get("chunk_id") or chunk.get("id"))
        if chunk_id is None or key in cited_keys:
            continue
        cited_keys.append(key)
        cited_chunk_ids.append(chunk_id)
        cited_chunks.append(chunk)

    for marker in _extract_invalid_source_like_markers(text, valid_markers):
        if marker not in invalid_keys:
            invalid_keys.append(marker)

    missing_citations = bool(text and not cited_keys)
    validation = CitationValidationResult(
        valid=not invalid_keys and not missing_citations,
        cited_keys=cited_keys,
        cited_chunk_ids=cited_chunk_ids,
        invalid_keys=invalid_keys,
        missing_citations=missing_citations,
    )
    return CitationValidationOutput(
        validation=validation,
        sources=build_source_citations(cited_chunks),
    )


__all__ = [
    "CitationValidationOutput",
    "assign_citation_keys",
    "validate_answer_citations",
]
