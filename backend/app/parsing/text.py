from __future__ import annotations

import re

from .base import BaseParser, PARSER_VERSION, ParsedDocument, normalize_text
from .structure import build_paragraph_block


_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")


def _decode_text(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")


def _split_paragraphs(text: str) -> list[str]:
    normalized_text = normalize_text(text)
    normalized_text = _PARAGRAPH_SPLIT_RE.split(normalized_text)
    return [paragraph.strip() for paragraph in normalized_text if paragraph.strip()]


class TextParser(BaseParser):
    parser_name = "text"
    parser_version = PARSER_VERSION
    supported_extensions = frozenset({".txt"})
    supported_mime_types = frozenset({"text/plain"})

    def parse(
        self,
        file_bytes: bytes,
        *,
        file_name: str | None = None,
        mime_type: str | None = None,
    ) -> ParsedDocument:
        text = _decode_text(file_bytes)
        paragraph_blocks = [
            build_paragraph_block(paragraph_text, page_number=None)
            for paragraph_text in _split_paragraphs(text)
        ]
        return self.build_document(text=text, blocks=paragraph_blocks)
