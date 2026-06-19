from __future__ import annotations

from app.chunking.section_chunker import SmartSectionChunker
from app.chunking.token_chunker import (
    ChunkingError,
    EmptyChunkingTextError,
    FixedTokenChunker,
)
from app.core.config import Settings
from app.parsing.structure import (
    build_heading_block,
    build_paragraph_block,
    build_table_block,
)
from app.services.hashing import compute_sha256


class CharacterTokenizer:
    def encode(self, text: str) -> list[int]:
        return [ord(character) for character in text]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)

    def decode_single_token_bytes(self, token: int) -> bytes:
        return chr(token).encode("utf-8")


def _build_parsed_document(text: str) -> dict:
    return {
        "text": text,
        "pages": [
            {
                "page_number": 1,
                "text": text,
            }
        ],
        "metadata": {
            "parser_name": "text",
            "parser_version": "1.0.0",
        },
    }


def _build_structured_document(blocks: list[dict]) -> dict:
    text = "\n\n".join(block["text"] for block in blocks if block["text"].strip())
    pages = []
    for index, block in enumerate(blocks, start=1):
        block_text = block["text"]
        if not isinstance(block_text, str) or not block_text.strip():
            continue

        page_number = block.get("page_number")
        pages.append(
            {
                "page_number": page_number if page_number is not None else index,
                "text": block_text,
            }
        )

    return {
        "text": text,
        "pages": pages or [{"page_number": 1, "text": text}],
        "metadata": {
            "parser_name": "structured-test",
            "parser_version": "1.0.0",
        },
        "blocks": blocks,
    }


def test_fixed_token_chunker_uses_settings_defaults_and_emits_metadata(monkeypatch):
    settings = Settings(
        _env_file=None,
        CHUNK_SIZE_TOKENS=500,
        CHUNK_OVERLAP_TOKENS=150,
    )
    monkeypatch.setattr(
        "app.chunking.token_chunker.get_settings",
        lambda: settings,
    )

    chunker = FixedTokenChunker(tokenizer=CharacterTokenizer())
    text = "".join(str(index % 10) for index in range(1200))

    chunks = chunker.chunk(_build_parsed_document(text))

    assert chunker.chunk_size_tokens == 500
    assert chunker.chunk_overlap_tokens == 150
    assert chunker.chunk_step_tokens == 350
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1, 2]
    assert [chunk["token_start"] for chunk in chunks] == [0, 350, 700]
    assert [chunk["token_end"] for chunk in chunks] == [500, 850, 1200]

    first_chunk = chunks[0]
    assert first_chunk["chunk_type"] == "fixed"
    assert first_chunk["heading"] is None
    assert first_chunk["section_path"] == []
    assert first_chunk["page_start"] == 1
    assert first_chunk["page_end"] == 1
    assert first_chunk["token_count"] == 500
    assert first_chunk["content_hash"] == compute_sha256(
        first_chunk["content"].encode("utf-8")
    )


def test_fixed_token_chunker_uses_150_token_overlap_for_multiple_chunks():
    chunker = FixedTokenChunker(
        tokenizer=CharacterTokenizer(),
        chunk_size_tokens=500,
        chunk_overlap_tokens=150,
    )
    text = "".join(chr(65 + (index % 26)) for index in range(1200))

    chunks = chunker.chunk(_build_parsed_document(text))

    assert len(chunks) == 3
    assert chunks[0]["content"][-150:] == chunks[1]["content"][:150]
    assert chunks[1]["content"][-150:] == chunks[2]["content"][:150]
    assert chunks[0]["token_end"] - chunks[1]["token_start"] == 150
    assert chunks[1]["token_end"] - chunks[2]["token_start"] == 150


def test_fixed_token_chunker_rejects_empty_text():
    chunker = FixedTokenChunker(tokenizer=CharacterTokenizer())

    for empty_text in ("", "   \n\t"):
        try:
            chunker.chunk(_build_parsed_document(empty_text))
        except EmptyChunkingTextError as exc:
            assert "non-empty text" in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected EmptyChunkingTextError")


def test_base_chunker_rejects_invalid_chunk_windows():
    try:
        FixedTokenChunker(
            tokenizer=CharacterTokenizer(),
            chunk_size_tokens=100,
            chunk_overlap_tokens=100,
        )
    except ChunkingError as exc:
        assert "Chunk step" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ChunkingError")


def test_smart_section_chunker_uses_settings_defaults_and_falls_back_when_blocks_are_missing(monkeypatch):
    default_settings = Settings(_env_file=None)
    assert default_settings.CHUNKING_STRATEGY == "smart_section"
    assert default_settings.HEADER_SCORE_THRESHOLD == 4
    assert default_settings.TABLE_CHUNK_MAX_TOKENS == 500

    settings = Settings(
        _env_file=None,
        CHUNK_SIZE_TOKENS=20,
        CHUNK_OVERLAP_TOKENS=5,
        TABLE_CHUNK_MAX_TOKENS=30,
    )
    monkeypatch.setattr(
        "app.chunking.section_chunker.get_settings",
        lambda: settings,
    )

    smart_chunker = SmartSectionChunker(tokenizer=CharacterTokenizer())
    fixed_chunker = FixedTokenChunker(settings=settings, tokenizer=CharacterTokenizer())
    text = "".join(str(index % 10) for index in range(120))
    parsed_document = _build_parsed_document(text)

    assert smart_chunker.chunk_size_tokens == 20
    assert smart_chunker.chunk_overlap_tokens == 5
    assert smart_chunker.table_chunk_max_tokens == 30
    assert smart_chunker.header_score_threshold == 4
    assert smart_chunker.chunk(parsed_document) == fixed_chunker.chunk(parsed_document)


def test_smart_section_chunker_keeps_small_tables_intact_and_tracks_section_path():
    settings = Settings(
        _env_file=None,
        CHUNK_SIZE_TOKENS=20,
        CHUNK_OVERLAP_TOKENS=5,
        TABLE_CHUNK_MAX_TOKENS=80,
    )
    chunker = SmartSectionChunker(
        settings=settings,
        tokenizer=CharacterTokenizer(),
    )
    small_table_text = (
        "| Name | Value |\n"
        "| --- | --- |\n"
        "| Alpha | Beta |"
    )

    blocks = [
        build_heading_block("Overview", heading_level=1, page_number=1, metadata=None),
        build_paragraph_block("Intro text", page_number=1),
        build_table_block(small_table_text, page_number=1, metadata=None),
        build_heading_block("Details", heading_level=2, page_number=2, metadata=None),
        build_paragraph_block("More details", page_number=2),
    ]

    chunks = chunker.chunk(_build_structured_document(blocks))

    assert [chunk["chunk_type"] for chunk in chunks] == ["smart_section", "table", "smart_section"]
    assert chunks[0]["heading"] == "Overview"
    assert chunks[0]["section_path"] == ["Overview"]
    assert chunks[0]["content"] == "Intro text"
    assert chunks[1]["heading"] == "Overview"
    assert chunks[1]["section_path"] == ["Overview"]
    assert chunks[1]["content"] == small_table_text
    assert chunks[1]["token_count"] == len(small_table_text)
    assert chunks[1]["page_start"] == 1
    assert chunks[1]["page_end"] == 1
    assert chunks[2]["heading"] == "Details"
    assert chunks[2]["section_path"] == ["Overview", "Details"]
    assert chunks[2]["content"] == "More details"


def test_smart_section_chunker_splits_oversized_table_and_preserves_heading_metadata():
    settings = Settings(
        _env_file=None,
        CHUNK_SIZE_TOKENS=20,
        CHUNK_OVERLAP_TOKENS=5,
        TABLE_CHUNK_MAX_TOKENS=30,
    )
    chunker = SmartSectionChunker(
        settings=settings,
        tokenizer=CharacterTokenizer(),
    )
    large_table_text = (
        "| Name | Value |\n"
        "| --- | --- |\n"
        "| Alpha | Beta |\n"
        "| Gamma | Delta |\n"
        "| Epsilon | Zeta |"
    )

    blocks = [
        build_heading_block("Data", heading_level=1, page_number=1, metadata=None),
        build_table_block(large_table_text, page_number=1, metadata=None),
    ]

    chunks = chunker.chunk(_build_structured_document(blocks))

    assert len(chunks) > 1
    assert all(chunk["chunk_type"] == "table" for chunk in chunks)
    assert all(chunk["heading"] == "Data" for chunk in chunks)
    assert all(chunk["section_path"] == ["Data"] for chunk in chunks)
    assert chunks[0]["token_start"] == 0
    assert chunks[0]["page_start"] == 1
    assert chunks[0]["page_end"] == 1


def test_smart_section_chunker_detects_scored_heading_and_splits_oversized_section():
    settings = Settings(
        _env_file=None,
        CHUNK_SIZE_TOKENS=20,
        CHUNK_OVERLAP_TOKENS=5,
        TABLE_CHUNK_MAX_TOKENS=80,
    )
    chunker = SmartSectionChunker(
        settings=settings,
        tokenizer=CharacterTokenizer(),
    )
    previous_body = build_paragraph_block("Body copy", page_number=1)
    previous_body["metadata"]["font_size"] = 12
    heading_candidate = build_paragraph_block("2.3 Pricing", page_number=1)
    heading_candidate["metadata"]["is_bold"] = True
    heading_candidate["metadata"]["font_size"] = 18
    next_body = build_paragraph_block("More body", page_number=1)
    next_body["metadata"]["font_size"] = 11
    long_body = build_paragraph_block("A" * 60, page_number=1)

    blocks = [previous_body, heading_candidate, next_body, long_body]

    chunks = chunker.chunk(_build_structured_document(blocks))

    assert len(chunks) >= 3
    assert chunks[0]["heading"] is None
    assert chunks[0]["section_path"] == []
    assert chunks[0]["content"] == "Body copy"
    assert all(chunk["chunk_type"] == "smart_section" for chunk in chunks[1:])
    assert all(chunk["heading"] == "2.3 Pricing" for chunk in chunks[1:])
    assert all(chunk["section_path"] == ["2.3 Pricing"] for chunk in chunks[1:])
    assert all("2.3 Pricing" not in chunk["content"] for chunk in chunks)
    assert chunks[1]["token_start"] == 0
    assert chunks[1]["page_start"] == 1
    assert chunks[1]["page_end"] == 1
