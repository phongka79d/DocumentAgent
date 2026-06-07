from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
import math
import re
from typing import Any


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PAGE_RE = re.compile(r"\b(?:page|p)\s*#?\s*(\d+)\b", re.IGNORECASE)
_IMPORTANT_SECTION_TERMS = {
    "abstract",
    "executive",
    "introduction",
    "overview",
    "policy",
    "summary",
    "title",
}
_DATE_METADATA_KEYS = {
    "created_at",
    "date",
    "document_date",
    "effective_date",
    "modified_at",
    "published_at",
    "updated_at",
}
FINAL_SCORE_WEIGHTS: dict[str, float] = {
    "semantic_similarity": 0.45,
    "graph_relevance": 0.25,
    "keyword_overlap": 0.15,
    "metadata_match": 0.10,
    "recency_or_position_score": 0.05,
}


def clamp_score(value: Any) -> float:
    """Return a finite score normalized to the inclusive 0.0 to 1.0 range."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0

    if not math.isfinite(score):
        return 0.0

    return min(1.0, max(0.0, score))


def keyword_overlap_score(question: str | None, chunk_content: str | None) -> float:
    """Score unique question-token coverage in the candidate chunk content."""
    question_tokens = set(_tokenize(question))
    if not question_tokens:
        return 0.0

    chunk_tokens = set(_tokenize(chunk_content))
    if not chunk_tokens:
        return 0.0

    return clamp_score(len(question_tokens & chunk_tokens) / len(question_tokens))


def metadata_match_score(
    question: str | None,
    candidate: Any,
    selected_document_ids: Iterable[Any] | None = None,
) -> float:
    """Score deterministic matches against selected document and chunk metadata."""
    question_tokens = set(_tokenize(question))
    if not question_tokens and not selected_document_ids:
        return 0.0

    score = 0.0
    document_id = _candidate_value(candidate, "document_id")
    if selected_document_ids and document_id is not None:
        selected_ids = {str(item) for item in selected_document_ids}
        if str(document_id) in selected_ids:
            score += 0.4

    page_number = _as_int(_candidate_value(candidate, "page_number"))
    if page_number is not None and page_number in _page_numbers_from_question(question):
        score += 0.2

    section_title = _candidate_value(candidate, "section_title")
    score += 0.2 * _token_match_ratio(question_tokens, _tokenize(section_title))

    file_name = _candidate_value(candidate, "file_name")
    if file_name:
        file_stem = Path(str(file_name)).stem
        score += 0.2 * _token_match_ratio(question_tokens, _tokenize(file_stem))

    return clamp_score(score)


def position_score(candidate: Any) -> float:
    """Score early chunks, important sections, and explicit date metadata."""
    score = 0.0

    chunk_index = _as_int(_candidate_value(candidate, "chunk_index"))
    if chunk_index is not None:
        if chunk_index <= 0:
            score += 0.5
        elif chunk_index <= 2:
            score += 0.4
        elif chunk_index <= 4:
            score += 0.25

    page_number = _as_int(_candidate_value(candidate, "page_number"))
    if chunk_index is None and page_number is not None:
        if page_number <= 1:
            score += 0.35
        elif page_number <= 3:
            score += 0.2

    section_tokens = set(_tokenize(_candidate_value(candidate, "section_title")))
    if section_tokens & _IMPORTANT_SECTION_TERMS:
        score += 0.35

    if _has_explicit_date_metadata(candidate):
        score += 0.15

    return clamp_score(score)


def recency_or_position_score(candidate: Any) -> float:
    """Alias for the Plan 8 score component name."""
    return position_score(candidate)


def final_score(components: Any) -> float:
    """Calculate the exact Plan 8 weighted final score from normalized components."""
    return sum(
        weight * clamp_score(_component_value(components, component_name))
        for component_name, weight in FINAL_SCORE_WEIGHTS.items()
    )


def _component_value(components: Any, key: str) -> Any:
    if isinstance(components, Mapping):
        return components.get(key, 0.0)

    return getattr(components, key, 0.0)


def _tokenize(value: Any) -> list[str]:
    if value is None:
        return []

    return _TOKEN_RE.findall(str(value).lower())


def _candidate_value(candidate: Any, key: str) -> Any:
    if isinstance(candidate, Mapping):
        value = candidate.get(key)
        metadata = candidate.get("metadata")
    else:
        value = getattr(candidate, key, None)
        metadata = getattr(candidate, "metadata", None)

    if value is not None:
        return value

    if isinstance(metadata, Mapping):
        return metadata.get(key)

    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _page_numbers_from_question(question: str | None) -> set[int]:
    if not question:
        return set()

    return {int(match.group(1)) for match in _PAGE_RE.finditer(question)}


def _token_match_ratio(question_tokens: set[str], metadata_tokens: list[str]) -> float:
    metadata_token_set = set(metadata_tokens)
    if not question_tokens or not metadata_token_set:
        return 0.0

    return clamp_score(len(question_tokens & metadata_token_set) / len(metadata_token_set))


def _has_explicit_date_metadata(candidate: Any) -> bool:
    if isinstance(candidate, Mapping):
        metadata = candidate.get("metadata")
        values = candidate
    else:
        metadata = getattr(candidate, "metadata", None)
        values = {
            key: getattr(candidate, key, None)
            for key in _DATE_METADATA_KEYS
            if hasattr(candidate, key)
        }

    for key in _DATE_METADATA_KEYS:
        if values.get(key) not in (None, ""):
            return True

    if isinstance(metadata, Mapping):
        for key in _DATE_METADATA_KEYS:
            if metadata.get(key) not in (None, ""):
                return True

    return False


__all__ = [
    "FINAL_SCORE_WEIGHTS",
    "clamp_score",
    "final_score",
    "keyword_overlap_score",
    "metadata_match_score",
    "position_score",
    "recency_or_position_score",
]
