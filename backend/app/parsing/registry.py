from __future__ import annotations

from collections.abc import Iterable

from .base import (
    BaseParser,
    UnsupportedDocumentTypeError,
    normalize_extension,
    normalize_mime_type,
)
from .docx import DocxParser
from .html import HtmlParser
from .markdown import MarkdownParser
from .pdf import PdfParser
from .text import TextParser


class ParserRegistry:
    def __init__(self, parsers: Iterable[BaseParser] | None = None):
        self._parsers_by_extension: dict[str, BaseParser] = {}
        self._parsers_by_mime_type: dict[str, BaseParser] = {}

        if parsers is not None:
            for parser in parsers:
                self.register(parser)

    def register(self, parser: BaseParser) -> None:
        for extension in parser.supported_extensions:
            existing = self._parsers_by_extension.get(extension)
            if existing is not None and existing is not parser:
                raise ValueError(f"Parser extension already registered: {extension}")
            self._parsers_by_extension[extension] = parser

        for mime_type in parser.supported_mime_types:
            existing = self._parsers_by_mime_type.get(mime_type)
            if existing is not None and existing is not parser:
                raise ValueError(f"Parser MIME type already registered: {mime_type}")
            self._parsers_by_mime_type[mime_type] = parser

    def get_by_extension(self, extension: str) -> BaseParser:
        normalized_extension = extension.lower().strip()
        if normalized_extension and not normalized_extension.startswith("."):
            normalized_extension = f".{normalized_extension}"
        parser = self._parsers_by_extension.get(normalized_extension)
        if parser is None:
            raise UnsupportedDocumentTypeError(extension=normalized_extension)
        return parser

    def get_by_mime_type(self, mime_type: str) -> BaseParser:
        normalized_mime_type = normalize_mime_type(mime_type)
        parser = self._parsers_by_mime_type.get(normalized_mime_type or "")
        if parser is None:
            raise UnsupportedDocumentTypeError(mime_type=normalized_mime_type)
        return parser

    def resolve(
        self,
        *,
        file_name: str | None = None,
        mime_type: str | None = None,
    ) -> BaseParser:
        extension = normalize_extension(file_name)
        normalized_mime_type = normalize_mime_type(mime_type)

        if extension is not None:
            parser = self._parsers_by_extension.get(extension)
            if parser is not None:
                return parser

        if normalized_mime_type is not None:
            parser = self._parsers_by_mime_type.get(normalized_mime_type)
            if parser is not None:
                return parser

        raise UnsupportedDocumentTypeError(extension=extension, mime_type=normalized_mime_type)

    def get_parser(
        self,
        *,
        file_name: str | None = None,
        mime_type: str | None = None,
    ) -> BaseParser:
        return self.resolve(file_name=file_name, mime_type=mime_type)

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset(self._parsers_by_extension)

    @property
    def supported_mime_types(self) -> frozenset[str]:
        return frozenset(self._parsers_by_mime_type)


PARSER_REGISTRY = ParserRegistry(
    (
        PdfParser(),
        DocxParser(),
        TextParser(),
        MarkdownParser(),
        HtmlParser(),
    )
)

SUPPORTED_EXTENSIONS = PARSER_REGISTRY.supported_extensions
SUPPORTED_MIME_TYPES = PARSER_REGISTRY.supported_mime_types


def get_parser_for_file(
    file_name: str,
    *,
    mime_type: str | None = None,
) -> BaseParser:
    return PARSER_REGISTRY.resolve(file_name=file_name, mime_type=mime_type)


def get_parser_for_extension(extension: str) -> BaseParser:
    return PARSER_REGISTRY.get_by_extension(extension)


def get_parser_for_mime_type(mime_type: str) -> BaseParser:
    return PARSER_REGISTRY.get_by_mime_type(mime_type)
