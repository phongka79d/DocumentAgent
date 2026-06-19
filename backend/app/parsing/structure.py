from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence, TypedDict

from .base import normalize_text

ParsedBlockType = Literal["paragraph", "heading", "table"]


class ParsedBlock(TypedDict):
    type: ParsedBlockType
    text: str
    page_number: int | None
    heading_level: int | None
    section_path: list[str]
    metadata: dict[str, Any]


def normalize_block_text(text: str) -> str:
    return normalize_text(text).strip()


def _normalize_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(metadata or {})


def _build_block(
    *,
    block_type: ParsedBlockType,
    text: str,
    page_number: int | None,
    heading_level: int | None,
    metadata: Mapping[str, Any] | None = None,
) -> ParsedBlock:
    return {
        "type": block_type,
        "text": normalize_block_text(text),
        "page_number": page_number,
        "heading_level": heading_level,
        "section_path": [],
        "metadata": _normalize_metadata(metadata),
    }


def build_paragraph_block(text: str, page_number: int | None) -> ParsedBlock:
    return _build_block(
        block_type="paragraph",
        text=text,
        page_number=page_number,
        heading_level=None,
    )


def build_heading_block(
    text: str,
    heading_level: int | None,
    page_number: int | None,
    metadata: Mapping[str, Any] | None,
) -> ParsedBlock:
    return _build_block(
        block_type="heading",
        text=text,
        page_number=page_number,
        heading_level=heading_level,
        metadata=metadata,
    )


def build_table_block(
    text: str,
    page_number: int | None,
    metadata: Mapping[str, Any] | None,
) -> ParsedBlock:
    return _build_block(
        block_type="table",
        text=text,
        page_number=page_number,
        heading_level=None,
        metadata=metadata,
    )


def _normalize_table_cell_text(value: Any) -> str:
    if value is None:
        return ""

    normalized = normalize_block_text(str(value))
    if not normalized:
        return ""

    collapsed = " ".join(line.strip() for line in normalized.splitlines() if line.strip())
    return collapsed.replace("|", r"\|")


def _format_markdown_row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def flatten_table_to_markdown(rows: Sequence[Sequence[Any]]) -> str:
    normalized_rows = [
        [_normalize_table_cell_text(cell) for cell in row]
        for row in rows
    ]

    if not normalized_rows:
        return ""

    column_count = max((len(row) for row in normalized_rows), default=0)
    if column_count == 0:
        return ""

    padded_rows = [row + [""] * (column_count - len(row)) for row in normalized_rows]
    header_row = padded_rows[0]
    separator_row = ["---"] * column_count

    markdown_rows = [
        _format_markdown_row(header_row),
        _format_markdown_row(separator_row),
    ]
    markdown_rows.extend(_format_markdown_row(row) for row in padded_rows[1:])
    return "\n".join(markdown_rows)
