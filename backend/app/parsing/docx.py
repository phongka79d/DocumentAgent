from __future__ import annotations

from io import BytesIO

from app.services.validation import DOCX_MIME_TYPE

from .base import BaseParser, PARSER_VERSION, ParseError, ParsedDocument


def _load_document_class():
    try:
        from docx import Document  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - dependency should be installed
        raise ParseError("python-docx is required to parse DOCX documents") from exc

    return Document


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

        paragraph_texts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        full_text = "\n".join(paragraph_texts)
        return self.build_document(text=full_text, page_texts=[full_text])
