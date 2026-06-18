from __future__ import annotations

from app.chunking.token_chunker import (
    ChunkingError,
    EmptyChunkingTextError,
    FixedTokenChunker,
)
from app.core.config import Settings
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
