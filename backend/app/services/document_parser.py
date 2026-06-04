from collections.abc import Callable

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
