from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Sequence, TypedDict

PARSER_VERSION = "1.0.0"


class ParsedPage(TypedDict):
    page_number: int
    text: str


class ParsedMetadata(TypedDict):
    parser_name: str
    parser_version: str


class ParsedDocument(TypedDict):
    text: str
    pages: list[ParsedPage]
    metadata: ParsedMetadata


class ParseError(ValueError):
    """Base error raised by parser implementations."""


class EmptyExtractedTextError(ParseError):
    def __init__(self, *, parser_name: str):
        super().__init__(f"Extracted text is empty for parser {parser_name}")


class UnsupportedDocumentTypeError(ParseError):
    def __init__(
        self,
        *,
        extension: str | None = None,
        mime_type: str | None = None,
    ):
        details: list[str] = []
        if extension is not None:
            details.append(f"extension={extension!r}")
        if mime_type is not None:
            details.append(f"mime_type={mime_type!r}")
        detail_text = ", ".join(details) if details else "no extension or MIME type"
        super().__init__(f"Unsupported document type: {detail_text}")


def normalize_mime_type(mime_type: str | None) -> str | None:
    if mime_type is None:
        return None

    normalized = mime_type.split(";", 1)[0].strip().lower()
    return normalized or None


def normalize_extension(file_name: str | Path | None) -> str | None:
    if file_name is None:
        return None

    normalized_name = Path(file_name).name.strip()
    if not normalized_name:
        return None

    extension = Path(normalized_name).suffix.lower()
    return extension or None


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n")


def build_parsed_document(
    *,
    text: str,
    parser_name: str,
    parser_version: str = PARSER_VERSION,
    page_texts: Sequence[str] | None = None,
) -> ParsedDocument:
    normalized_text = normalize_text(text)
    if not normalized_text.strip():
        raise EmptyExtractedTextError(parser_name=parser_name)

    if page_texts is None:
        normalized_page_texts = [normalized_text]
    else:
        normalized_page_texts = [normalize_text(page_text) for page_text in page_texts]
        if not normalized_page_texts:
            normalized_page_texts = [normalized_text]

    pages: list[ParsedPage] = [
        {"page_number": page_number, "text": page_text}
        for page_number, page_text in enumerate(normalized_page_texts, start=1)
    ]

    return {
        "text": normalized_text,
        "pages": pages,
        "metadata": {
            "parser_name": parser_name,
            "parser_version": parser_version,
        },
    }


class BaseParser(ABC):
    parser_name: ClassVar[str]
    parser_version: ClassVar[str] = PARSER_VERSION
    supported_extensions: ClassVar[frozenset[str]] = frozenset()
    supported_mime_types: ClassVar[frozenset[str]] = frozenset()

    @property
    def extensions(self) -> frozenset[str]:
        return self.supported_extensions

    @property
    def mime_types(self) -> frozenset[str]:
        return self.supported_mime_types

    @abstractmethod
    def parse(
        self,
        file_bytes: bytes,
        *,
        file_name: str | None = None,
        mime_type: str | None = None,
    ) -> ParsedDocument:
        raise NotImplementedError

    def build_document(
        self,
        *,
        text: str,
        page_texts: Sequence[str] | None = None,
    ) -> ParsedDocument:
        return build_parsed_document(
            text=text,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            page_texts=page_texts,
        )
