from __future__ import annotations

from .base import BaseParser, PARSER_VERSION, ParsedDocument


def _decode_text(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")


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
        return self.build_document(text=text)
