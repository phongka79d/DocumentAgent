from __future__ import annotations

from app.core.config import Settings
from app.core.contracts import ContextMode


DOC_A = "00000000-0000-0000-0000-000000000001"


def _settings(
    *,
    context_mode: ContextMode = ContextMode.NEIGHBOR,
    context_window: int = 1,
    section_sibling_window: int = 1,
) -> Settings:
    return Settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SHOPAIKEY_API_KEY="shop",
        JINA_API_KEY="jina",
        RETRIEVAL_CONTEXT_MODE=context_mode,
        RETRIEVAL_CONTEXT_WINDOW=context_window,
        RETRIEVAL_SECTION_SIBLING_WINDOW=section_sibling_window,
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
