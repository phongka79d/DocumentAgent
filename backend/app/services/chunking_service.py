import re
from dataclasses import dataclass
from collections.abc import Iterable

from app.schemas.parsing import ChunkDraft, ParsedSection


_TOKEN_PATTERN = re.compile(r"\S+")
_SENTENCE_BOUNDARY_CHARS = (".", "!", "?", ";")


@dataclass(frozen=True)
class _TokenSpan:
    start: int
    end: int
    value: str


def estimate_token_count(text: str) -> int:
    """Estimate tokens with the same word-based approximation everywhere."""
    return len(_TOKEN_PATTERN.findall(text or ""))


def _tokenize(text: str) -> list[_TokenSpan]:
    return [
        _TokenSpan(start=match.start(), end=match.end(), value=match.group(0))
        for match in _TOKEN_PATTERN.finditer(text)
    ]


def _is_boundary_after_token(
    *,
    text: str,
    tokens: list[_TokenSpan],
    token_index: int,
) -> bool:
    token = tokens[token_index]
    next_token = tokens[token_index + 1] if token_index + 1 < len(tokens) else None
    separator = text[token.end : next_token.start] if next_token else ""

    return "\n" in separator or token.value.rstrip().endswith(_SENTENCE_BOUNDARY_CHARS)


def _choose_chunk_end(
    *,
    text: str,
    tokens: list[_TokenSpan],
    start_index: int,
    max_end_index: int,
) -> int:
    if max_end_index >= len(tokens):
        return len(tokens)

    minimum_end_index = start_index + max(1, (max_end_index - start_index) // 2)
    for end_index in range(max_end_index, minimum_end_index, -1):
        if _is_boundary_after_token(
            text=text,
            tokens=tokens,
            token_index=end_index - 1,
        ):
            return end_index

    return max_end_index


def _split_section_text(
    text: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> Iterable[str]:
    stripped_text = text.strip()
    if not stripped_text:
        return

    tokens = _tokenize(stripped_text)
    start_index = 0

    while start_index < len(tokens):
        max_end_index = min(start_index + chunk_size, len(tokens))
        end_index = _choose_chunk_end(
            text=stripped_text,
            tokens=tokens,
            start_index=start_index,
            max_end_index=max_end_index,
        )

        chunk_text = stripped_text[tokens[start_index].start : tokens[end_index - 1].end].strip()
        if chunk_text:
            yield chunk_text

        if end_index >= len(tokens):
            break

        start_index = max(end_index - chunk_overlap, start_index + 1)


def _validate_chunk_settings(chunk_size: int, chunk_overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be greater than or equal to 0.")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be less than chunk_size.")


def _has_usable_text(section: ParsedSection) -> bool:
    return bool(section.text.strip())


def _build_chunk_draft(
    *,
    section: ParsedSection,
    content: str,
    chunk_index: int,
) -> ChunkDraft:
    metadata = dict(section.metadata)
    return ChunkDraft(
        content=content,
        chunk_index=chunk_index,
        token_count=estimate_token_count(content),
        document_id=metadata.get("document_id"),
        user_id=metadata.get("user_id"),
        page_number=section.page_number,
        section_title=section.section_title,
        file_name=section.file_name,
        metadata=metadata,
    )


def chunk_sections(
    sections: list[ParsedSection],
    chunk_size: int,
    chunk_overlap: int,
) -> list[ChunkDraft]:
    """Split parsed sections into deterministic chunk drafts."""
    _validate_chunk_settings(chunk_size, chunk_overlap)

    chunks: list[ChunkDraft] = []
    for section in sections:
        if not _has_usable_text(section):
            continue

        for chunk_text in _split_section_text(
            section.text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ):
            chunks.append(
                _build_chunk_draft(
                    section=section,
                    content=chunk_text,
                    chunk_index=len(chunks),
                )
            )

    return chunks


__all__ = ["chunk_sections", "estimate_token_count"]
