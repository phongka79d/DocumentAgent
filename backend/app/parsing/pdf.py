from __future__ import annotations

from typing import Any, Mapping

from app.services.validation import PDF_MIME_TYPE

from .base import BaseParser, PARSER_VERSION, ParseError, ParsedDocument, normalize_text
from .structure import build_paragraph_block


def _load_fitz():
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - dependency should be installed
        raise ParseError("PyMuPDF is required to parse PDF documents") from exc

    return fitz


def _span_is_bold(span: Mapping[str, Any]) -> bool:
    font_name = str(span.get("font", ""))
    if "bold" in font_name.lower():
        return True

    flags = span.get("flags")
    return isinstance(flags, int) and bool(flags & 16)


def _build_pdf_paragraph_block(
    *,
    text: str,
    page_number: int,
    font_size: float | None,
    is_bold: bool | None,
    bbox: list[float] | None,
) -> dict[str, Any]:
    block = build_paragraph_block(text, page_number=page_number)
    metadata: dict[str, Any] = {}

    if font_size is not None:
        metadata["font_size"] = font_size
    if is_bold is not None:
        metadata["is_bold"] = is_bold
    if bbox is not None:
        metadata["bbox"] = bbox

    block["metadata"] = metadata
    return block


def _extract_page_blocks(page: Any, page_number: int) -> list[dict[str, Any]]:
    page_dict = page.get_text("dict")
    blocks: list[dict[str, Any]] = []

    for raw_block in page_dict.get("blocks", []):
        if raw_block.get("type") != 0:
            continue

        raw_lines = raw_block.get("lines", [])
        line_texts: list[str] = []
        font_sizes: list[float] = []
        bold_states: list[bool] = []

        for raw_line in raw_lines:
            span_texts: list[str] = []
            for span in raw_line.get("spans", []):
                span_text = str(span.get("text", ""))
                if span_text:
                    span_texts.append(span_text)
                size = span.get("size")
                if isinstance(size, (int, float)):
                    font_sizes.append(float(size))
                bold_states.append(_span_is_bold(span))

            line_text = "".join(span_texts).strip()
            if line_text:
                line_texts.append(line_text)

        block_text = "\n".join(line_texts).strip()
        if not block_text:
            continue

        bbox_value = raw_block.get("bbox")
        bbox = list(bbox_value) if bbox_value is not None else None
        font_size = max(font_sizes) if font_sizes else None
        is_bold = any(bold_states) if bold_states else None
        blocks.append(
            _build_pdf_paragraph_block(
                text=block_text,
                page_number=page_number,
                font_size=font_size,
                is_bold=is_bold,
                bbox=bbox,
            )
        )

    return blocks


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
            blocks: list[dict[str, Any]] = []
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                page_texts.append(normalize_text(page.get_text("text")).rstrip("\n"))
                blocks.extend(_extract_page_blocks(page, page_number=page_index + 1))

            full_text = "\n\n".join(page_texts)
            return self.build_document(text=full_text, page_texts=page_texts, blocks=blocks)
        except ParseError:
            raise
        except Exception as exc:  # pragma: no cover - exercised via parser boundary tests
            raise ParseError(f"Failed to parse PDF document: {exc}") from exc
        finally:
            if document is not None:
                document.close()
