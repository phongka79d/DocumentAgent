from collections.abc import Callable
from io import BytesIO

from docx import Document
from pypdf import PdfReader

from app.schemas.parsing import ParsedSection
from app.utils.file_validation import SUPPORTED_DOCUMENT_TYPES


class DocumentParserError(RuntimeError):
    """Raised when document parsing fails with a safe public message."""


class EmptyDocumentError(DocumentParserError):
    """Raised when parsing produces no usable text."""


class UnsupportedDocumentTypeError(DocumentParserError):
    """Raised when a document type has no parser implementation."""


class UnreadableDocumentError(DocumentParserError):
    """Raised when a document cannot be read by its parser."""


class DocumentDecodingError(DocumentParserError):
    """Raised when document bytes cannot be decoded safely."""


Parser = Callable[[bytes, str], list[ParsedSection]]


def _parser_not_ready(file_type: str) -> Parser:
    def _parse(_file_bytes: bytes, _file_name: str) -> list[ParsedSection]:
        raise UnreadableDocumentError(
            f"{file_type.upper()} parser implementation is not available yet."
        )

    return _parse


_PARSERS: dict[str, Parser] = {
    file_type: _parser_not_ready(file_type)
    for file_type in sorted(SUPPORTED_DOCUMENT_TYPES)
}


def _normalize_file_type(file_type: str) -> str:
    return (file_type or "").strip().lower().removeprefix(".")


def _ensure_document_bytes(file_bytes: bytes) -> None:
    if not isinstance(file_bytes, bytes):
        raise UnreadableDocumentError("Document content must be bytes.")


def _ensure_non_empty(sections: list[ParsedSection]) -> None:
    parsed_text = "\n".join(section.text for section in sections)
    if not parsed_text.strip():
        raise EmptyDocumentError("Parsed document is empty.")


def _build_section(
    *,
    text: str,
    file_name: str,
    source_type: str,
    page_number: int | None = None,
    section_title: str | None = None,
    metadata: dict[str, object] | None = None,
) -> ParsedSection:
    section_metadata = {"source_type": source_type}
    if metadata:
        section_metadata.update(metadata)

    return ParsedSection(
        text=text,
        page_number=page_number,
        section_title=section_title,
        file_name=file_name,
        metadata=section_metadata,
    )


def _parse_pdf(file_bytes: bytes, file_name: str) -> list[ParsedSection]:
    reader = PdfReader(BytesIO(file_bytes))
    sections: list[ParsedSection] = []

    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            sections.append(
                _build_section(
                    text=text,
                    file_name=file_name,
                    source_type="pdf",
                    page_number=page_index,
                )
            )

    return sections


def _is_heading_style(style_name: str | None) -> bool:
    normalized_style = (style_name or "").strip().lower()
    return normalized_style.startswith("heading")


def _parse_docx(file_bytes: bytes, file_name: str) -> list[ParsedSection]:
    document = Document(BytesIO(file_bytes))
    sections: list[ParsedSection] = []
    current_section_title: str | None = None

    for paragraph_index, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph.text.strip()
        if not text:
            continue

        style_name = paragraph.style.name if paragraph.style else None
        is_heading = _is_heading_style(style_name)
        if is_heading:
            current_section_title = text

        sections.append(
            _build_section(
                text=text,
                file_name=file_name,
                source_type="docx",
                section_title=current_section_title,
                metadata={
                    "paragraph_index": paragraph_index,
                    "style_name": style_name,
                    "is_heading": is_heading,
                },
            )
        )

    return sections


def _parse_txt(file_bytes: bytes, file_name: str) -> list[ParsedSection]:
    encoding_used = "utf-8"
    try:
        text = file_bytes.decode(encoding_used)
    except UnicodeDecodeError:
        encoding_used = "latin-1"
        text = file_bytes.decode(encoding_used)

    return [
        _build_section(
            text=text,
            file_name=file_name,
            source_type="txt",
            metadata={"encoding": encoding_used},
        )
    ]


_PARSERS.update(
    {
        "docx": _parse_docx,
        "pdf": _parse_pdf,
        "txt": _parse_txt,
    }
)


def parse_document(
    file_bytes: bytes,
    file_type: str,
    file_name: str,
) -> list[ParsedSection]:
    """Dispatch supported document bytes to the parser for their file type."""
    _ensure_document_bytes(file_bytes)

    normalized_file_type = _normalize_file_type(file_type)
    parser = _PARSERS.get(normalized_file_type)
    if parser is None:
        raise UnsupportedDocumentTypeError(
            f"Unsupported document type: {normalized_file_type or 'unknown'}."
        )

    try:
        sections = parser(file_bytes, file_name)
    except UnicodeDecodeError as exc:
        raise DocumentDecodingError(
            f"Could not decode {normalized_file_type.upper()} document."
        ) from exc
    except DocumentParserError:
        raise
    except Exception as exc:
        raise UnreadableDocumentError(
            f"Could not read {normalized_file_type.upper()} document."
        ) from exc

    _ensure_non_empty(sections)
    return sections


__all__ = [
    "DocumentDecodingError",
    "DocumentParserError",
    "EmptyDocumentError",
    "UnsupportedDocumentTypeError",
    "UnreadableDocumentError",
    "parse_document",
]
