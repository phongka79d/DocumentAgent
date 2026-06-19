from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any

from app.chunking.heading_detection import score_heading_candidate
from app.chunking.token_chunker import (
    BaseChunker,
    ChunkRecord,
    ChunkingError,
    FixedTokenChunker,
)
from app.core.config import Settings, get_settings
from app.parsing.base import ParsedDocument, normalize_text

SMART_SECTION_CHUNK_TYPE = "smart_section"
TABLE_CHUNK_TYPE = "table"
DEFAULT_PARSER_NAME = "smart_section"
DEFAULT_PARSER_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class _PageGroup:
    page_number: int | None
    text: str


def _block_text(block: Mapping[str, Any] | None) -> str:
    if block is None:
        return ""

    text = block.get("text")
    if not isinstance(text, str):
        return ""

    return normalize_text(text).strip()


def _block_type(block: Mapping[str, Any] | None) -> str:
    if block is None:
        return ""

    block_type = block.get("type")
    if not isinstance(block_type, str):
        return ""

    return block_type.strip().lower()


def _block_page_number(block: Mapping[str, Any] | None) -> int | None:
    if block is None:
        return None

    page_number = block.get("page_number")
    if page_number is None:
        return None

    try:
        value = int(page_number)
    except (TypeError, ValueError):
        return None

    return value if value > 0 else None


def _block_heading_level(block: Mapping[str, Any] | None) -> int | None:
    if block is None:
        return None

    heading_level = block.get("heading_level")
    if heading_level is None:
        return None

    try:
        value = int(heading_level)
    except (TypeError, ValueError):
        return None

    return value if value > 0 else None


def _normalize_blocks(blocks: Any) -> list[dict[str, Any]] | None:
    if not isinstance(blocks, Sequence) or isinstance(blocks, (str, bytes)):
        return None

    normalized_blocks: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, Mapping):
            return None
        normalized_blocks.append(dict(block))

    return normalized_blocks


def _is_table_block(block: Mapping[str, Any] | None) -> bool:
    return _block_type(block) == "table"


def _is_heading_candidate(
    block: Mapping[str, Any] | None,
    previous_block: Mapping[str, Any] | None,
    next_block: Mapping[str, Any] | None,
    *,
    threshold: int,
) -> bool:
    if _is_table_block(block):
        return False

    if _block_type(block) == "heading":
        return bool(_block_text(block))

    return score_heading_candidate(block, previous_block, next_block) >= threshold


def _group_blocks_by_page(blocks: Sequence[Mapping[str, Any]]) -> list[_PageGroup]:
    page_groups: list[_PageGroup] = []
    current_page_number: int | None = None
    current_texts: list[str] = []

    for block in blocks:
        text = _block_text(block)
        if not text:
            continue

        page_number = _block_page_number(block)
        if not current_texts:
            current_page_number = page_number
            current_texts = [text]
            continue

        if page_number is None:
            current_texts.append(text)
            continue

        if current_page_number is None:
            current_page_number = page_number
            current_texts.append(text)
            continue

        if page_number == current_page_number:
            current_texts.append(text)
            continue

        page_groups.append(
            _PageGroup(page_number=current_page_number, text="\n\n".join(current_texts))
        )
        current_page_number = page_number
        current_texts = [text]

    if current_texts:
        page_groups.append(
            _PageGroup(page_number=current_page_number, text="\n\n".join(current_texts))
        )

    return page_groups


def _build_temp_document(blocks: Sequence[Mapping[str, Any]]) -> ParsedDocument:
    page_groups = _group_blocks_by_page(blocks)
    page_texts = [group.text for group in page_groups]
    full_text = normalize_text("\n\n".join(page_texts))
    pages = [
        {
            "page_number": group.page_number if group.page_number is not None else index,
            "text": group.text,
        }
        for index, group in enumerate(page_groups, start=1)
    ]

    if not pages:
        pages = [{"page_number": 1, "text": full_text}]

    return {
        "text": full_text,
        "pages": pages,
        "metadata": {
            "parser_name": DEFAULT_PARSER_NAME,
            "parser_version": DEFAULT_PARSER_VERSION,
        },
    }


class SmartSectionChunker(BaseChunker):
    chunk_type = SMART_SECTION_CHUNK_TYPE

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        chunk_size_tokens: int | None = None,
        chunk_overlap_tokens: int | None = None,
        tokenizer: Any | None = None,
        header_score_threshold: int | None = None,
        table_chunk_max_tokens: int | None = None,
    ) -> None:
        resolved_settings = settings if settings is not None else get_settings()
        super().__init__(
            settings=resolved_settings,
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            tokenizer=tokenizer,
        )
        self.header_score_threshold = (
            header_score_threshold
            if header_score_threshold is not None
            else resolved_settings.HEADER_SCORE_THRESHOLD
        )
        self.table_chunk_max_tokens = (
            table_chunk_max_tokens
            if table_chunk_max_tokens is not None
            else resolved_settings.TABLE_CHUNK_MAX_TOKENS
        )
        if self.table_chunk_max_tokens <= 0:
            raise ChunkingError("Table chunk max tokens must be greater than zero")

        self._fixed_chunker = FixedTokenChunker(
            settings=resolved_settings,
            chunk_size_tokens=self.chunk_size_tokens,
            chunk_overlap_tokens=self.chunk_overlap_tokens,
            tokenizer=self.tokenizer,
        )

    def _current_heading_metadata(
        self,
        heading_stack: Sequence[tuple[int, str]],
    ) -> tuple[str | None, list[str]]:
        section_path = [heading_text for _, heading_text in heading_stack]
        heading = section_path[-1] if section_path else None
        return heading, section_path

    def _append_fixed_chunks(
        self,
        *,
        chunks: list[ChunkRecord],
        chunk_index: int,
        fixed_chunks: list[ChunkRecord],
        chunk_type: str,
        heading: str | None,
        section_path: list[str],
    ) -> int:
        for chunk in fixed_chunks:
            chunk["chunk_index"] = chunk_index
            chunk["chunk_type"] = chunk_type
            chunk["heading"] = heading
            chunk["section_path"] = list(section_path)
            chunks.append(chunk)
            chunk_index += 1

        return chunk_index

    def _build_section_chunks(
        self,
        *,
        blocks: list[dict[str, Any]],
        chunks: list[ChunkRecord],
        chunk_index: int,
        heading_stack: Sequence[tuple[int, str]],
    ) -> int:
        heading, section_path = self._current_heading_metadata(heading_stack)
        temp_document = _build_temp_document(blocks)
        fixed_chunks = self._fixed_chunker.chunk(temp_document)
        return self._append_fixed_chunks(
            chunks=chunks,
            chunk_index=chunk_index,
            fixed_chunks=fixed_chunks,
            chunk_type=SMART_SECTION_CHUNK_TYPE,
            heading=heading,
            section_path=section_path,
        )

    def _build_table_chunks(
        self,
        *,
        block: dict[str, Any],
        chunks: list[ChunkRecord],
        chunk_index: int,
        heading_stack: Sequence[tuple[int, str]],
    ) -> int:
        heading, section_path = self._current_heading_metadata(heading_stack)
        table_text = _block_text(block)
        if not table_text:
            return chunk_index

        page_groups = _group_blocks_by_page([block])
        page_start = page_groups[0].page_number if page_groups else 1
        page_end = page_groups[-1].page_number if page_groups else 1
        token_count = len(self._encode_text(table_text))

        if token_count <= self.table_chunk_max_tokens:
            chunk = self._build_chunk_record(
                content=table_text,
                chunk_index=chunk_index,
                token_start=0,
                token_end=token_count,
                page_start=page_start if page_start is not None else 1,
                page_end=page_end if page_end is not None else 1,
            )
            chunk["chunk_type"] = TABLE_CHUNK_TYPE
            chunk["heading"] = heading
            chunk["section_path"] = list(section_path)
            chunks.append(chunk)
            return chunk_index + 1

        temp_document = _build_temp_document([block])
        fixed_chunks = self._fixed_chunker.chunk(temp_document)
        return self._append_fixed_chunks(
            chunks=chunks,
            chunk_index=chunk_index,
            fixed_chunks=fixed_chunks,
            chunk_type=TABLE_CHUNK_TYPE,
            heading=heading,
            section_path=section_path,
        )

    def chunk(self, parsed_document: ParsedDocument) -> list[ChunkRecord]:
        blocks = _normalize_blocks(parsed_document.get("blocks"))
        if not blocks:
            return self._fixed_chunker.chunk(parsed_document)

        chunks: list[ChunkRecord] = []
        heading_stack: list[tuple[int, str]] = []
        pending_section_blocks: list[dict[str, Any]] = []
        chunk_index = 0

        def flush_section() -> None:
            nonlocal chunk_index
            if not pending_section_blocks:
                return

            section_blocks = list(pending_section_blocks)
            pending_section_blocks.clear()
            section_text = "\n\n".join(
                _block_text(block) for block in section_blocks if _block_text(block)
            )
            if not section_text.strip():
                return

            chunk_index = self._build_section_chunks(
                blocks=section_blocks,
                chunks=chunks,
                chunk_index=chunk_index,
                heading_stack=heading_stack,
            )

        for index, block in enumerate(blocks):
            previous_block = blocks[index - 1] if index > 0 else None
            next_block = blocks[index + 1] if index + 1 < len(blocks) else None
            block_type = _block_type(block)

            if _is_heading_candidate(
                block,
                previous_block,
                next_block,
                threshold=self.header_score_threshold,
            ):
                flush_section()
                heading_text = _block_text(block)
                if not heading_text:
                    continue

                heading_level = _block_heading_level(block) or 1
                while heading_stack and heading_stack[-1][0] >= heading_level:
                    heading_stack.pop()
                heading_stack.append((heading_level, heading_text))
                continue

            if block_type == "table":
                flush_section()
                chunk_index = self._build_table_chunks(
                    block=block,
                    chunks=chunks,
                    chunk_index=chunk_index,
                    heading_stack=heading_stack,
                )
                continue

            block_text = _block_text(block)
            if block_text:
                pending_section_blocks.append(block)

        flush_section()

        if not chunks:
            return self._fixed_chunker.chunk(parsed_document)

        return chunks


__all__ = ["SmartSectionChunker"]
