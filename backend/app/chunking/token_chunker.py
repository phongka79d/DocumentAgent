from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Protocol, Sequence, TypedDict

from app.core.config import Settings, get_settings
from app.parsing.base import ParsedDocument, normalize_text
from app.services.hashing import compute_sha256

try:  # pragma: no cover - dependency is expected to be installed
    import tiktoken
except ImportError:  # pragma: no cover - handled at runtime
    tiktoken = None

DEFAULT_ENCODING_NAME = "cl100k_base"
DEFAULT_CHUNK_TYPE = "fixed"


class TokenizerProtocol(Protocol):
    def encode(self, text: str) -> list[int]: ...

    def decode(self, tokens: Sequence[int]) -> str: ...

    def decode_single_token_bytes(self, token: int) -> bytes: ...


class ChunkingError(ValueError):
    """Base error raised by chunker implementations."""


class EmptyChunkingTextError(ChunkingError):
    def __init__(self) -> None:
        super().__init__("Chunking requires non-empty text")


class ChunkRecord(TypedDict):
    chunk_index: int
    content: str
    content_hash: str
    token_count: int
    chunk_type: str
    heading: str | None
    section_path: list[str]
    page_start: int | None
    page_end: int | None
    token_start: int
    token_end: int


@dataclass(frozen=True, slots=True)
class _PageSpan:
    page_number: int
    byte_start: int
    byte_end: int


def _load_default_tokenizer(encoding_name: str) -> TokenizerProtocol:
    if tiktoken is None:
        raise ChunkingError("tiktoken is required for fixed token chunking")

    return tiktoken.get_encoding(encoding_name)


class BaseChunker(ABC):
    chunk_type: ClassVar[str] = DEFAULT_CHUNK_TYPE
    encoding_name: ClassVar[str] = DEFAULT_ENCODING_NAME

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        chunk_size_tokens: int | None = None,
        chunk_overlap_tokens: int | None = None,
        tokenizer: TokenizerProtocol | None = None,
    ) -> None:
        resolved_settings = settings if settings is not None else get_settings()
        self.settings = resolved_settings
        self.chunk_size_tokens = (
            chunk_size_tokens
            if chunk_size_tokens is not None
            else resolved_settings.CHUNK_SIZE_TOKENS
        )
        self.chunk_overlap_tokens = (
            chunk_overlap_tokens
            if chunk_overlap_tokens is not None
            else resolved_settings.CHUNK_OVERLAP_TOKENS
        )
        self.chunk_step_tokens = self.chunk_size_tokens - self.chunk_overlap_tokens

        if self.chunk_size_tokens <= 0:
            raise ChunkingError("Chunk size must be greater than zero")
        if self.chunk_overlap_tokens < 0:
            raise ChunkingError("Chunk overlap cannot be negative")
        if self.chunk_step_tokens <= 0:
            raise ChunkingError("Chunk step must be greater than zero")

        self.tokenizer = tokenizer if tokenizer is not None else _load_default_tokenizer(
            self.encoding_name
        )

    @abstractmethod
    def chunk(self, parsed_document: ParsedDocument) -> list[ChunkRecord]:
        raise NotImplementedError

    def _require_text(self, parsed_document: ParsedDocument) -> str:
        text = parsed_document.get("text")
        if not isinstance(text, str) or not text.strip():
            raise EmptyChunkingTextError()
        return normalize_text(text)

    def _encode_text(self, text: str) -> list[int]:
        tokens = self.tokenizer.encode(text)
        if not tokens:
            raise EmptyChunkingTextError()
        return tokens

    def _token_byte_offsets(self, tokens: Sequence[int]) -> list[int]:
        byte_offsets = [0]
        running_total = 0
        for token in tokens:
            token_bytes = self.tokenizer.decode_single_token_bytes(token)
            running_total += len(token_bytes)
            byte_offsets.append(running_total)
        return byte_offsets

    def _build_page_spans(self, parsed_document: ParsedDocument) -> list[_PageSpan]:
        pages = parsed_document.get("pages") or []
        normalized_text = self._require_text(parsed_document)
        full_text_bytes = normalized_text.encode("utf-8")

        if not pages:
            return [_PageSpan(page_number=1, byte_start=0, byte_end=len(full_text_bytes))]

        spans: list[_PageSpan] = []
        cursor = 0
        separator_size = len("\n\n".encode("utf-8"))

        for page_position, page in enumerate(pages, start=1):
            page_number = int(page.get("page_number") or page_position)
            page_text = normalize_text(str(page.get("text") or ""))
            page_bytes = page_text.encode("utf-8")
            start = cursor
            end = start + len(page_bytes)
            spans.append(_PageSpan(page_number=page_number, byte_start=start, byte_end=end))
            cursor = end
            if page_position < len(pages):
                cursor += separator_size

        if spans and spans[-1].byte_end > len(full_text_bytes):
            # Keep the metadata bounded by the actual text when a parser supplied
            # page text that slightly exceeds the normalized full text.
            last_span = spans[-1]
            spans[-1] = _PageSpan(
                page_number=last_span.page_number,
                byte_start=last_span.byte_start,
                byte_end=len(full_text_bytes),
            )

        return spans

    def _resolve_page_range(
        self,
        page_spans: Sequence[_PageSpan],
        *,
        chunk_byte_start: int,
        chunk_byte_end: int,
    ) -> tuple[int | None, int | None]:
        overlapping_pages = [
            span.page_number
            for span in page_spans
            if span.byte_end > chunk_byte_start and span.byte_start < chunk_byte_end
        ]
        if overlapping_pages:
            return overlapping_pages[0], overlapping_pages[-1]

        if not page_spans:
            return None, None

        preceding = None
        for span in page_spans:
            if span.byte_start <= chunk_byte_start:
                preceding = span
            else:
                break

        following = None
        for span in page_spans:
            if span.byte_start >= chunk_byte_end:
                following = span
                break

        if preceding is not None and following is not None:
            return preceding.page_number, following.page_number

        if preceding is not None:
            return preceding.page_number, preceding.page_number

        return page_spans[0].page_number, page_spans[0].page_number

    def _build_chunk_record(
        self,
        *,
        content: str,
        chunk_index: int,
        token_start: int,
        token_end: int,
        page_start: int | None,
        page_end: int | None,
    ) -> ChunkRecord:
        return {
            "chunk_index": chunk_index,
            "content": content,
            "content_hash": compute_sha256(content.encode("utf-8")),
            "token_count": token_end - token_start,
            "chunk_type": self.chunk_type,
            "heading": None,
            "section_path": [],
            "page_start": page_start,
            "page_end": page_end,
            "token_start": token_start,
            "token_end": token_end,
        }


class FixedTokenChunker(BaseChunker):
    chunk_type = DEFAULT_CHUNK_TYPE

    def chunk(self, parsed_document: ParsedDocument) -> list[ChunkRecord]:
        text = self._require_text(parsed_document)
        tokens = self._encode_text(text)
        byte_offsets = self._token_byte_offsets(tokens)
        page_spans = self._build_page_spans(parsed_document)
        text_bytes = text.encode("utf-8")

        chunks: list[ChunkRecord] = []
        token_start = 0
        chunk_index = 0

        while token_start < len(tokens):
            token_end = min(token_start + self.chunk_size_tokens, len(tokens))
            byte_start = byte_offsets[token_start]
            byte_end = byte_offsets[token_end]
            chunk_bytes = text_bytes[byte_start:byte_end]

            try:
                content = chunk_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:  # pragma: no cover - defensive
                raise ChunkingError("Chunk content could not be decoded as UTF-8") from exc

            page_start, page_end = self._resolve_page_range(
                page_spans,
                chunk_byte_start=byte_start,
                chunk_byte_end=byte_end,
            )
            chunks.append(
                self._build_chunk_record(
                    content=content,
                    chunk_index=chunk_index,
                    token_start=token_start,
                    token_end=token_end,
                    page_start=page_start,
                    page_end=page_end,
                )
            )

            if token_end >= len(tokens):
                break

            token_start += self.chunk_step_tokens
            chunk_index += 1

        return chunks
