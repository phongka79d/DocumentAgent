from __future__ import annotations

from app.services.validation import PDF_MIME_TYPE

from .base import BaseParser, PARSER_VERSION, ParseError, ParsedDocument, normalize_text


def _load_fitz():
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - dependency should be installed
        raise ParseError("PyMuPDF is required to parse PDF documents") from exc

    return fitz


class PdfParser(BaseParser):
    parser_name = "pymupdf"
    parser_version = PARSER_VERSION
    supported_extensions = frozenset({".pdf"})
    supported_mime_types = frozenset({PDF_MIME_TYPE})

    def parse(
        self,
        file_bytes: bytes,
        *,
        file_name: str | None = None,
        mime_type: str | None = None,
    ) -> ParsedDocument:
        fitz = _load_fitz()
        document = None

        try:
            document = fitz.open(stream=file_bytes, filetype="pdf")
            page_texts: list[str] = []
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                page_texts.append(normalize_text(page.get_text("text")).rstrip("\n"))

            full_text = "\n\n".join(page_texts)
            return self.build_document(text=full_text, page_texts=page_texts)
        except ParseError:
            raise
        except Exception as exc:  # pragma: no cover - exercised via parser boundary tests
            raise ParseError(f"Failed to parse PDF document: {exc}") from exc
        finally:
            if document is not None:
                document.close()
