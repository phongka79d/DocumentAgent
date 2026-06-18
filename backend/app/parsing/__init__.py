"""Document parser package."""

from .base import (
    BaseParser,
    EmptyExtractedTextError,
    ParseError,
    ParsedDocument,
    ParsedMetadata,
    ParsedPage,
    PARSER_VERSION,
    UnsupportedDocumentTypeError,
)
from .docx import DocxParser
from .markdown import MarkdownParser
from .pdf import PdfParser
from .registry import (
    PARSER_REGISTRY,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_MIME_TYPES,
    ParserRegistry,
    get_parser_for_extension,
    get_parser_for_file,
    get_parser_for_mime_type,
)
from .text import TextParser

__all__ = [
    "BaseParser",
    "DocxParser",
    "EmptyExtractedTextError",
    "MarkdownParser",
    "PARSER_REGISTRY",
    "PARSER_VERSION",
    "ParseError",
    "ParsedDocument",
    "ParsedMetadata",
    "ParsedPage",
    "ParserRegistry",
    "PdfParser",
    "SUPPORTED_EXTENSIONS",
    "SUPPORTED_MIME_TYPES",
    "TextParser",
    "UnsupportedDocumentTypeError",
    "get_parser_for_extension",
    "get_parser_for_file",
    "get_parser_for_mime_type",
]
