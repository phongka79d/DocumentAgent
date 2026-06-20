from __future__ import annotations

from uuid import uuid4

from app.core.config import Settings
from app.core.contracts import RetrievalBoundary


def _settings(*, start_count: int = 2, end_count: int = 2) -> Settings:
    return Settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SHOPAIKEY_API_KEY="shop",
        JINA_API_KEY="jina",
        RETRIEVAL_BOUNDARY_START_CHUNKS=start_count,
        RETRIEVAL_BOUNDARY_END_CHUNKS=end_count,
    )


def test_resolve_boundary_chunks_fetches_configured_beginning_indexes(monkeypatch):
    from app.services import retrieval_boundaries

    document_id = uuid4()
    calls: list[list[int]] = []

    def fake_get_chunks_by_document_and_indexes(
        requested_document_id,
        chunk_indexes,
        *,
        settings,
        supabase_client=None,
    ):
        assert requested_document_id == document_id
        calls.append(list(chunk_indexes))
        return [{"id": f"chunk-{index}", "chunk_index": index} for index in chunk_indexes]

    monkeypatch.setattr(
        retrieval_boundaries.chunk_service,
        "get_chunks_by_document_and_indexes",
        fake_get_chunks_by_document_and_indexes,
    )

    chunks = retrieval_boundaries.resolve_boundary_chunks(
        document_id,
        [RetrievalBoundary.BEGINNING],
        settings=_settings(start_count=3),
    )

    assert calls == [[0, 1, 2]]
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1, 2]


def test_resolve_boundary_chunks_fetches_configured_end_indexes(monkeypatch):
    from app.services import retrieval_boundaries

    document_id = uuid4()
    calls: list[list[int]] = []

    def fake_get_last_chunk_by_document(
        requested_document_id,
        *,
        settings,
        supabase_client=None,
    ):
        assert requested_document_id == document_id
        return {"id": "chunk-9", "chunk_index": 9}

    def fake_get_chunks_by_document_and_indexes(
        requested_document_id,
        chunk_indexes,
        *,
        settings,
        supabase_client=None,
    ):
        assert requested_document_id == document_id
        calls.append(list(chunk_indexes))
        return [{"id": f"chunk-{index}", "chunk_index": index} for index in chunk_indexes]

    monkeypatch.setattr(
        retrieval_boundaries.chunk_service,
        "get_last_chunk_by_document",
        fake_get_last_chunk_by_document,
    )
    monkeypatch.setattr(
        retrieval_boundaries.chunk_service,
        "get_chunks_by_document_and_indexes",
        fake_get_chunks_by_document_and_indexes,
    )

    chunks = retrieval_boundaries.resolve_boundary_chunks(
        document_id,
        [RetrievalBoundary.END],
        settings=_settings(end_count=3),
    )

    assert calls == [[7, 8, 9]]
    assert [chunk["chunk_index"] for chunk in chunks] == [7, 8, 9]


def test_resolve_boundary_chunks_skips_non_positive_counts(monkeypatch):
    from app.services import retrieval_boundaries

    def fail_get_chunks(*args, **kwargs):
        raise AssertionError("should not fetch chunks when counts are non-positive")

    def fail_get_last(*args, **kwargs):
        raise AssertionError("should not fetch last chunk when end count is non-positive")

    monkeypatch.setattr(
        retrieval_boundaries.chunk_service,
        "get_chunks_by_document_and_indexes",
        fail_get_chunks,
    )
    monkeypatch.setattr(
        retrieval_boundaries.chunk_service,
        "get_last_chunk_by_document",
        fail_get_last,
    )

    chunks = retrieval_boundaries.resolve_boundary_chunks(
        uuid4(),
        [RetrievalBoundary.BEGINNING, RetrievalBoundary.END],
        settings=_settings(start_count=0, end_count=-1),
    )

    assert chunks == []


def test_resolve_boundary_chunks_deduplicates_overlapping_boundaries(monkeypatch):
    from app.services import retrieval_boundaries

    document_id = uuid4()

    def fake_get_last_chunk_by_document(
        requested_document_id,
        *,
        settings,
        supabase_client=None,
    ):
        assert requested_document_id == document_id
        return {"id": "chunk-1", "chunk_index": 1}

    def fake_get_chunks_by_document_and_indexes(
        requested_document_id,
        chunk_indexes,
        *,
        settings,
        supabase_client=None,
    ):
        assert requested_document_id == document_id
        return [{"id": f"chunk-{index}", "chunk_index": index} for index in chunk_indexes]

    monkeypatch.setattr(
        retrieval_boundaries.chunk_service,
        "get_last_chunk_by_document",
        fake_get_last_chunk_by_document,
    )
    monkeypatch.setattr(
        retrieval_boundaries.chunk_service,
        "get_chunks_by_document_and_indexes",
        fake_get_chunks_by_document_and_indexes,
    )

    chunks = retrieval_boundaries.resolve_boundary_chunks(
        document_id,
        [RetrievalBoundary.BEGINNING, RetrievalBoundary.END],
        settings=_settings(start_count=2, end_count=2),
    )

    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1]
