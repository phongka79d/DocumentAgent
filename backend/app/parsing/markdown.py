from __future__ import annotations

from app.services.validation import MARKDOWN_MIME_TYPES

from .base import BaseParser, PARSER_VERSION, ParsedDocument
from .text import _decode_text


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
        return self.build_document(text=text)
