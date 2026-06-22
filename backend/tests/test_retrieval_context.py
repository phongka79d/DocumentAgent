from __future__ import annotations

from app.core.config import Settings
from app.core.contracts import ContextMode


DOC_A = "00000000-0000-0000-0000-000000000001"


def _settings(
    *,
    context_mode: ContextMode = ContextMode.NEIGHBOR,
    context_window: int = 1,
    section_sibling_window: int = 1,
    context_max_candidates: int = 8,
    context_max_tokens: int = 4000,
) -> Settings:
    return Settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SHOPAIKEY_API_KEY="shop",
        JINA_API_KEY="jina",
        RETRIEVAL_CONTEXT_MODE=context_mode,
        RETRIEVAL_CONTEXT_WINDOW=context_window,
        RETRIEVAL_SECTION_SIBLING_WINDOW=section_sibling_window,
        RETRIEVAL_CONTEXT_MAX_CANDIDATES=context_max_candidates,
        RETRIEVAL_CONTEXT_MAX_TOKENS=context_max_tokens,
    )


def test_expand_neighbor_context_adds_neighbor_chunks(monkeypatch):
    from app.services import retrieval_context

    def fake_get_chunks_by_document_and_indexes(
        document_id,
        chunk_indexes,
        *,
        settings,
        supabase_client=None,
    ):
        assert document_id == DOC_A
        assert list(chunk_indexes) == [1, 3]
        return [
            {
                "id": "chunk-1",
                "document_id": DOC_A,
                "chunk_index": 1,
                "content": "previous",
            },
            {
                "id": "chunk-3",
                "document_id": DOC_A,
                "chunk_index": 3,
                "content": "next",
            },
        ]

    monkeypatch.setattr(
        retrieval_context.chunk_service,
        "get_chunks_by_document_and_indexes",
        fake_get_chunks_by_document_and_indexes,
    )

    chunks = retrieval_context.expand_neighbor_context(
        [
            {
                "chunk_id": "chunk-2",
                "document_id": DOC_A,
                "file_name": "doc.pdf",
                "chunk_index": 2,
                "content": "anchor",
            }
        ],
        settings=_settings(context_mode=ContextMode.NEIGHBOR),
    )

    assert [chunk["chunk_id"] for chunk in chunks] == [
        "chunk-2",
        "chunk-1",
        "chunk-3",
    ]
    assert chunks[1]["is_neighbor_context"] is True
    assert chunks[2]["is_neighbor_context"] is True


def test_expand_neighbor_context_section_aware_prioritizes_same_section(monkeypatch):
    from app.services import retrieval_context

    def fake_get_chunks_by_document_and_indexes(
        document_id,
        chunk_indexes,
        *,
        settings,
        supabase_client=None,
    ):
        assert document_id == DOC_A
        assert list(chunk_indexes) == [0, 1, 3, 4]
        return [
            {
                "id": "chunk-0",
                "document_id": DOC_A,
                "chunk_index": 0,
                "content": "generic previous",
                "section_path": ["Intro"],
            },
            {
                "id": "chunk-1",
                "document_id": DOC_A,
                "chunk_index": 1,
                "content": "same previous",
                "section_path": ["Pricing"],
            },
            {
                "id": "chunk-3",
                "document_id": DOC_A,
                "chunk_index": 3,
                "content": "same next",
                "section_path": ["Pricing"],
            },
            {
                "id": "chunk-4",
                "document_id": DOC_A,
                "chunk_index": 4,
                "content": "generic next",
                "section_path": ["Appendix"],
            },
        ]

    monkeypatch.setattr(
        retrieval_context.chunk_service,
        "get_chunks_by_document_and_indexes",
        fake_get_chunks_by_document_and_indexes,
    )

    chunks = retrieval_context.expand_neighbor_context(
        [
            {
                "chunk_id": "chunk-2",
                "document_id": DOC_A,
                "file_name": "doc.pdf",
                "chunk_index": 2,
                "section_path": ["Pricing"],
                "content": "anchor",
            }
        ],
        settings=_settings(
            context_mode=ContextMode.SECTION_AWARE,
            context_window=2,
            section_sibling_window=1,
        ),
    )

    assert [chunk["chunk_id"] for chunk in chunks] == [
        "chunk-2",
        "chunk-1",
        "chunk-3",
        "chunk-0",
        "chunk-4",
    ]


def test_expand_neighbor_context_result_reserves_multi_subquery_coverage_before_lower_ranked_fill():
    from app.services import retrieval_context

    result = retrieval_context.expand_neighbor_context_result(
        [
            {
                "chunk_id": "shared",
                "document_id": DOC_A,
                "file_name": "doc.pdf",
                "chunk_index": 0,
                "content": "shared",
                "token_count": 1,
                "subquery_ids": ["left", "right"],
            },
            {
                "chunk_id": "left-extra",
                "document_id": DOC_A,
                "file_name": "doc.pdf",
                "chunk_index": 1,
                "content": "left extra",
                "token_count": 1,
                "subquery_ids": ["left"],
            },
            {
                "chunk_id": "third-coverage",
                "document_id": DOC_A,
                "file_name": "doc.pdf",
                "chunk_index": 2,
                "content": "third",
                "token_count": 1,
                "subquery_ids": ["third"],
            },
        ],
        settings=_settings(
            context_mode=ContextMode.NEIGHBOR,
            context_max_candidates=2,
        ),
    )

    assert [chunk["chunk_id"] for chunk in result["context_chunks"]] == [
        "shared",
        "third-coverage",
    ]
    assert result["retrieval_metrics"]["context_subquery_coverage"] == {
        "left": 1,
        "right": 1,
        "third": 1,
    }


def test_expand_neighbor_context_result_keeps_all_same_section_neighbors_before_any_generic_neighbor(
    monkeypatch,
):
    from app.services import retrieval_context

    def fake_get_chunks_by_document_and_indexes(
        document_id,
        chunk_indexes,
        *,
        settings,
        supabase_client=None,
    ):
        assert document_id == DOC_A
        lookup = {
            (0, 2): [
                {
                    "id": "generic-a",
                    "document_id": DOC_A,
                    "chunk_index": 0,
                    "content": "generic a",
                    "token_count": 1,
                    "section_path": ["Other"],
                },
                {
                    "id": "same-a",
                    "document_id": DOC_A,
                    "chunk_index": 2,
                    "content": "same a",
                    "token_count": 1,
                    "section_path": ["Pricing"],
                },
            ],
            (3, 5): [
                {
                    "id": "same-b",
                    "document_id": DOC_A,
                    "chunk_index": 3,
                    "content": "same b",
                    "token_count": 1,
                    "section_path": ["Security"],
                },
                {
                    "id": "generic-b",
                    "document_id": DOC_A,
                    "chunk_index": 5,
                    "content": "generic b",
                    "token_count": 1,
                    "section_path": ["Appendix"],
                },
            ],
        }
        return lookup[tuple(chunk_indexes)]

    monkeypatch.setattr(
        retrieval_context.chunk_service,
        "get_chunks_by_document_and_indexes",
        fake_get_chunks_by_document_and_indexes,
    )

    result = retrieval_context.expand_neighbor_context_result(
        [
            {
                "chunk_id": "anchor-a",
                "document_id": DOC_A,
                "file_name": "doc.pdf",
                "chunk_index": 1,
                "section_path": ["Pricing"],
                "content": "anchor a",
                "token_count": 1,
                "subquery_ids": ["left"],
            },
            {
                "chunk_id": "anchor-b",
                "document_id": DOC_A,
                "file_name": "doc.pdf",
                "chunk_index": 4,
                "section_path": ["Security"],
                "content": "anchor b",
                "token_count": 1,
                "subquery_ids": ["right"],
            },
        ],
        settings=_settings(
            context_mode=ContextMode.SECTION_AWARE,
            context_window=1,
            section_sibling_window=1,
        ),
    )

    assert [chunk["chunk_id"] for chunk in result["context_chunks"]] == [
        "anchor-a",
        "anchor-b",
        "same-a",
        "same-b",
        "generic-a",
        "generic-b",
    ]
    assert result["retrieval_metrics"]["context_neighbor_count"] == 4


def test_expand_neighbor_context_result_truncates_only_prompt_copy_for_oversized_top_chunk(
    monkeypatch,
):
    from app.services import retrieval_context

    full_content = "alpha beta gamma delta epsilon"

    monkeypatch.setattr(
        retrieval_context,
        "_count_text_tokens",
        lambda text: 5 if text == full_content else 2,
    )
    monkeypatch.setattr(
        retrieval_context,
        "_truncate_prompt_text_to_tokens",
        lambda text, max_tokens: f"TRUNCATED:{max_tokens}:{text}",
    )

    result = retrieval_context.expand_neighbor_context_result(
        [
            {
                "chunk_id": "oversized",
                "document_id": DOC_A,
                "file_name": "doc.pdf",
                "chunk_index": 0,
                "content": full_content,
                "subquery_ids": ["q1"],
            }
        ],
        settings=_settings(
            context_mode=ContextMode.NEIGHBOR,
            context_max_tokens=3,
        ),
    )

    assert result["context_chunks"][0]["content"] == full_content
    assert result["context_chunks"][0]["prompt_content"] == (
        f"TRUNCATED:3:{full_content}"
    )
    assert result["context_chunks"][0]["context_truncated"] is True
    assert result["context_chunks"][0]["token_count"] is None
    assert result["retrieval_metrics"]["context_token_count"] == 3


def test_expand_neighbor_context_result_uses_chunking_tokenizer_fallback_when_token_count_missing(
    monkeypatch,
):
    from app.services import retrieval_context

    token_counts = {
        "anchor": 3,
        "neighbor": 2,
    }

    monkeypatch.setattr(
        retrieval_context,
        "_count_text_tokens",
        lambda text: token_counts[text],
    )

    def fake_get_chunks_by_document_and_indexes(
        document_id,
        chunk_indexes,
        *,
        settings,
        supabase_client=None,
    ):
        assert list(chunk_indexes) == [1, 3]
        return [
            {
                "id": "neighbor",
                "document_id": DOC_A,
                "chunk_index": 1,
                "content": "neighbor",
            },
            {
                "id": "too-large",
                "document_id": DOC_A,
                "chunk_index": 3,
                "content": "neighbor",
                "token_count": 3,
            },
        ]

    monkeypatch.setattr(
        retrieval_context.chunk_service,
        "get_chunks_by_document_and_indexes",
        fake_get_chunks_by_document_and_indexes,
    )

    result = retrieval_context.expand_neighbor_context_result(
        [
            {
                "chunk_id": "anchor-chunk",
                "document_id": DOC_A,
                "file_name": "doc.pdf",
                "chunk_index": 2,
                "content": "anchor",
            }
        ],
        settings=_settings(
            context_mode=ContextMode.NEIGHBOR,
            context_max_tokens=5,
        ),
    )

    assert [chunk["chunk_id"] for chunk in result["context_chunks"]] == [
        "anchor-chunk",
        "neighbor",
    ]
    assert result["retrieval_metrics"]["context_token_count"] == 5
