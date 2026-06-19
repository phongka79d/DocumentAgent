from __future__ import annotations

import re

from app.services.validation import MARKDOWN_MIME_TYPES

from .base import BaseParser, PARSER_VERSION, ParsedDocument, normalize_text
from .structure import (
    build_heading_block,
    build_paragraph_block,
    build_table_block,
    flatten_table_to_markdown,
)
from .text import _decode_text

_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+\s*)?$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|(?:\d+[.)]))\s+")


def _split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]

    cells = [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", stripped)]
    return cells


def _is_table_separator_row(line: str) -> bool:
    cells = _split_markdown_table_row(line)
    if not cells:
        return False

    for cell in cells:
        compact = cell.replace(" ", "")
        if not compact:
            return False
        if re.fullmatch(r":?-{3,}:?", compact) is None:
            return False

    return True


def _is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False

    current_line = lines[index]
    next_line = lines[index + 1]
    return "|" in current_line and _is_table_separator_row(next_line)


def _is_heading_line(line: str) -> bool:
    return _ATX_HEADING_RE.match(line) is not None


def _parse_heading_line(line: str) -> tuple[int, str]:
    match = _ATX_HEADING_RE.match(line)
    if match is None:  # pragma: no cover - guarded by caller
        raise ValueError(f"Not an ATX heading line: {line!r}")

    return len(match.group(1)), match.group(2).strip()


def _is_list_item_line(line: str) -> bool:
    return _LIST_ITEM_RE.match(line) is not None


def _consume_table_block(lines: list[str], start_index: int) -> tuple[str, int]:
    table_lines = [lines[start_index]]
    index = start_index + 2

    while index < len(lines):
        line = lines[index]
        if not line.strip() or "|" not in line:
            break
        table_lines.append(line)
        index += 1

    rows = [_split_markdown_table_row(line) for line in table_lines]
    table_text = flatten_table_to_markdown(rows)
    return table_text, index


def _consume_paragraph_block(lines: list[str], start_index: int) -> tuple[str, int]:
    paragraph_lines = [lines[start_index]]
    index = start_index + 1

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            break
        if _is_heading_line(line) or _is_list_item_line(line) or _is_table_start(lines, index):
            break
        paragraph_lines.append(line)
        index += 1

    return "\n".join(paragraph_lines), index


def _consume_list_group(lines: list[str], start_index: int) -> tuple[str, int]:
    list_lines = [lines[start_index]]
    index = start_index + 1

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            break
        if _is_heading_line(line) or _is_table_start(lines, index) or _is_list_item_line(line):
            if _is_list_item_line(line):
                list_lines.append(line)
                index += 1
                continue
            break
        if line.startswith(" ") or line.startswith("\t"):
            list_lines.append(line)
            index += 1
            continue
        break

    return "\n".join(list_lines), index


class MarkdownParser(BaseParser):
    parser_name = "markdown"
    parser_version = PARSER_VERSION
    supported_extensions = frozenset({".md", ".markdown"})
    supported_mime_types = frozenset(MARKDOWN_MIME_TYPES)

    def parse(
        self,
        file_bytes: bytes,
        *,
        file_name: str | None = None,
        mime_type: str | None = None,
    ) -> ParsedDocument:
        text = _decode_text(file_bytes)
        normalized_text = normalize_text(text)
        lines = normalized_text.split("\n")
        blocks = []
        index = 0

        while index < len(lines):
            line = lines[index]
            if not line.strip():
                index += 1
                continue

            if _is_heading_line(line):
                heading_level, heading_text = _parse_heading_line(line)
                blocks.append(
                    build_heading_block(
                        heading_text,
                        heading_level=heading_level,
                        page_number=None,
                        metadata=None,
                    )
                )
                index += 1
                continue

            if _is_table_start(lines, index):
                table_text, next_index = _consume_table_block(lines, index)
                blocks.append(
                    build_table_block(
                        table_text,
                        page_number=None,
                        metadata=None,
                    )
                )
                index = next_index
                continue

            if _is_list_item_line(line):
                list_text, next_index = _consume_list_group(lines, index)
                blocks.append(build_paragraph_block(list_text, page_number=None))
                index = next_index
                continue

            paragraph_text, next_index = _consume_paragraph_block(lines, index)
            blocks.append(build_paragraph_block(paragraph_text, page_number=None))
            index = next_index

        return self.build_document(text=text, blocks=blocks)
