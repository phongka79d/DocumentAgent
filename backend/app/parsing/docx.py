from __future__ import annotations

import re
from io import BytesIO

from app.services.validation import DOCX_MIME_TYPE

from .base import BaseParser, PARSER_VERSION, ParseError, ParsedDocument
from .structure import (
    build_heading_block,
    build_paragraph_block,
    build_table_block,
    flatten_table_to_markdown,
)

_HEADING_STYLE_RE = re.compile(r"^Heading\s+([1-6])$")


def _load_document_class():
    try:
        from docx import Document  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - dependency should be installed
        raise ParseError("python-docx is required to parse DOCX documents") from exc

    return Document


def _iter_block_items(document):
    from docx.table import Table  # type: ignore[import-not-found]
    from docx.text.paragraph import Paragraph  # type: ignore[import-not-found]

    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield Table(child, document)


def _heading_level_from_paragraph(paragraph) -> int | None:
    style = getattr(paragraph, "style", None)
    style_name = getattr(style, "name", "") or ""
    match = _HEADING_STYLE_RE.match(style_name)
    if match is None:
        return None

    return int(match.group(1))


def _table_to_markdown(table) -> str:
    rows = [[cell.text for cell in row.cells] for row in table.rows]
    return flatten_table_to_markdown(rows)


class DocxParser(BaseParser):
    parser_name = "python-docx"
    parser_version = PARSER_VERSION
    supported_extensions = frozenset({".docx"})
    supported_mime_types = frozenset({DOCX_MIME_TYPE})

    def parse(
        self,
        file_bytes: bytes,
        *,
        file_name: str | None = None,
        mime_type: str | None = None,
    ) -> ParsedDocument:
        document_class = _load_document_class()

        try:
            document = document_class(BytesIO(file_bytes))
        except ParseError:
            raise
        except Exception as exc:  # pragma: no cover - exercised via parser boundary tests
            raise ParseError(f"Failed to parse DOCX document: {exc}") from exc

        blocks = []
        text_parts: list[str] = []

        for item in _iter_block_items(document):
            if hasattr(item, "text"):
                item_text = item.text.strip()
                if not item_text:
                    continue

                heading_level = _heading_level_from_paragraph(item)
                if heading_level is None:
                    block = build_paragraph_block(item_text, page_number=None)
                else:
                    block = build_heading_block(
                        item_text,
                        heading_level=heading_level,
                        page_number=None,
                        metadata=None,
                    )

                blocks.append(block)
                text_parts.append(block["text"])
                continue

            table_text = _table_to_markdown(item)
            if not table_text.strip():
                continue

            block = build_table_block(table_text, page_number=None, metadata=None)
            blocks.append(block)
            text_parts.append(block["text"])

        full_text = "\n\n".join(text_parts)
        return self.build_document(text=full_text, page_texts=[full_text], blocks=blocks)
