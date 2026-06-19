from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.parsing.base import normalize_text

_MARKDOWN_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S")
_NUMBERED_HEADING_RE = re.compile(r"^\s*(?:\d+[.)]|\d+(?:\.\d+)+)\s+\S")
_TOC_METADATA_KEYS = (
    "is_toc_entry",
    "toc_entry",
    "table_of_contents_entry",
    "is_table_of_contents_entry",
    "toc",
    "table_of_contents",
)
_SENTENCE_ENDINGS = (".", "?", "!")


def _block_text(block: Mapping[str, Any] | None) -> str:
    if block is None:
        return ""

    text = block.get("text")
    if not isinstance(text, str):
        return ""

    return normalize_text(text).strip()


def _block_type(block: Mapping[str, Any] | None) -> str:
    if block is None:
        return ""

    block_type = block.get("type")
    if not isinstance(block_type, str):
        return ""

    return block_type.strip().lower()


def _block_metadata(block: Mapping[str, Any] | None) -> dict[str, Any]:
    if block is None:
        return {}

    metadata = block.get("metadata")
    if isinstance(metadata, Mapping):
        return dict(metadata)

    return {}


def _word_count(text: str) -> int:
    if not text:
        return 0

    return len([token for token in text.split() if token])


def _ends_with_sentence_punctuation(text: str) -> bool:
    stripped_text = text.rstrip()
    return bool(stripped_text) and stripped_text.endswith(_SENTENCE_ENDINGS)


def _starts_with_markdown_heading_marker(text: str) -> bool:
    return _MARKDOWN_HEADING_RE.match(text) is not None


def _matches_numbered_heading_pattern(text: str) -> bool:
    return _NUMBERED_HEADING_RE.match(text) is not None


def _is_uppercase_text(text: str) -> bool:
    letters = [character for character in text if character.isalpha()]
    return len(letters) >= 2 and all(character.isupper() for character in letters)


def _has_toc_metadata(metadata: Mapping[str, Any]) -> bool:
    return any(bool(metadata.get(key)) for key in _TOC_METADATA_KEYS)


def _font_size_value(block: Mapping[str, Any] | None) -> float | None:
    metadata = _block_metadata(block)
    font_size = metadata.get("font_size")
    if font_size is None:
        return None

    try:
        return float(font_size)
    except (TypeError, ValueError):
        return None


def _neighbor_body_font_sizes(
    previous_block: Mapping[str, Any] | None,
    next_block: Mapping[str, Any] | None,
) -> list[float]:
    sizes: list[float] = []

    for nearby_block in (previous_block, next_block):
        if _block_type(nearby_block) == "heading":
            continue

        font_size = _font_size_value(nearby_block)
        if font_size is not None:
            sizes.append(font_size)

    return sizes


def _has_larger_font_size(
    block: Mapping[str, Any] | None,
    previous_block: Mapping[str, Any] | None,
    next_block: Mapping[str, Any] | None,
) -> bool:
    block_font_size = _font_size_value(block)
    if block_font_size is None:
        return False

    nearby_body_font_sizes = _neighbor_body_font_sizes(previous_block, next_block)
    if not nearby_body_font_sizes:
        return False

    return block_font_size > max(nearby_body_font_sizes)


def score_heading_candidate(
    block: Mapping[str, Any] | None,
    previous_block: Mapping[str, Any] | None,
    next_block: Mapping[str, Any] | None,
) -> int:
    text = _block_text(block)
    metadata = _block_metadata(block)
    score = 0
    word_count = _word_count(text)

    if _block_type(block) == "heading":
        score += 5

    if _starts_with_markdown_heading_marker(text):
        score += 4

    if _matches_numbered_heading_pattern(text):
        score += 3

    if _has_toc_metadata(metadata):
        score += 2

    if word_count <= 12 and not _ends_with_sentence_punctuation(text):
        score += 1

    if _is_uppercase_text(text):
        score += 1

    if bool(metadata.get("is_bold")):
        score += 1

    if _has_larger_font_size(block, previous_block, next_block):
        score += 1

    if _ends_with_sentence_punctuation(text):
        score -= 2

    if word_count > 18:
        score -= 3

    return score


def is_heading_candidate(
    block: Mapping[str, Any] | None,
    threshold: int = 4,
) -> bool:
    return score_heading_candidate(block, None, None) >= threshold
