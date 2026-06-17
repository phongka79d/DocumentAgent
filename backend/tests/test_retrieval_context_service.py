from collections.abc import Callable
import sys
from pathlib import Path
from unittest.mock import Mock, call
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.retrieval import HybridRetrievalCandidate
from app.services import retrieval_context_service


DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SECOND_DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")
ANCHOR_ID = UUID("33333333-3333-3333-3333-333333333333")
SECOND_ANCHOR_ID = UUID("44444444-4444-4444-4444-444444444444")
PREVIOUS_ID = UUID("55555555-5555-5555-5555-555555555555")
NEXT_ID = UUID("66666666-6666-6666-6666-666666666666")


def _candidate(
    *,
    chunk_id: UUID,
    document_id: UUID = DOCUMENT_ID,
    chunk_index: int | None = 5,
    final_score: float = 0.9,
) -> HybridRetrievalCandidate:
    return HybridRetrievalCandidate(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name=f"{document_id}.txt",
        file_type="text/plain",
        content="The event was organized in a circle.",
        content_preview=None,
        page_number=1,
        section_title="Event",
        chunk_index=chunk_index,
        semantic_similarity=0.9,
        metadata=None,
        graph_relevance=0.5,
        keyword_overlap=0.4,
        metadata_match=0.3,
        recency_or_position_score=0.2,
        final_score=final_score,
        retrieval_reason="Semantic anchor.",
    )


def _row(
    *,
    chunk_id: UUID,
    document_id: UUID = DOCUMENT_ID,
    chunk_index: int,
    content: str,
) -> dict[str, object]:
    return {
        "id": str(chunk_id),
        "document_id": str(document_id),
        "chunk_index": chunk_index,
        "content": content,
        "page_number": 2,
        "section_title": "Continuation",
    }


def test_expand_retrieval_context_returns_anchors_when_disabled() -> None:
    anchors = [_candidate(chunk_id=ANCHOR_ID)]
    chunk_lookup = Mock()

    assert retrieval_context_service.expand_retrieval_context(
        "What happened?",
        anchors,
        context_window=0,
        max_context_candidates=2,
        chunk_lookup=chunk_lookup,
    ) == anchors
    assert retrieval_context_service.expand_retrieval_context(
        "What happened?",
        anchors,
        context_window=1,
        max_context_candidates=0,
        chunk_lookup=chunk_lookup,
    ) == anchors
    chunk_lookup.assert_not_called()


def test_expand_retrieval_context_skips_weak_anchor_below_min_parent_score() -> None:
    anchor = _candidate(chunk_id=ANCHOR_ID, chunk_index=5, final_score=0.1)
    chunk_lookup = Mock(
        return_value=[
            _row(
                chunk_id=NEXT_ID,
                chunk_index=6,
                content="Adjacent context that should not be pulled in.",
            )
        ]
    )

    expanded = retrieval_context_service.expand_retrieval_context(
        "What happened?",
        [anchor],
        context_window=1,
        max_context_candidates=2,
        min_parent_score=0.2,
        chunk_lookup=chunk_lookup,
    )

    assert expanded == [anchor]
    chunk_lookup.assert_not_called()


def test_expand_retrieval_context_adds_adjacent_chunks_once_per_document() -> None:
    anchors = [
        _candidate(chunk_id=ANCHOR_ID, chunk_index=5),
        _candidate(chunk_id=SECOND_ANCHOR_ID, chunk_index=7, final_score=0.8),
    ]
    chunk_lookup = Mock(
        return_value=[
            _row(
                chunk_id=PREVIOUS_ID,
                chunk_index=4,
                content="The participants gathered before the event.",
            ),
            _row(
                chunk_id=NEXT_ID,
                chunk_index=6,
                content="Every participant received the requested result.",
            ),
        ]
    )

    expanded = retrieval_context_service.expand_retrieval_context(
        "How was the event organized and what did participants receive?",
        anchors,
        context_window=1,
        max_context_candidates=4,
        chunk_lookup=chunk_lookup,
    )

    chunk_lookup.assert_called_once_with(str(DOCUMENT_ID), [4, 6, 8])
    assert {candidate.chunk_id for candidate in expanded} == {
        ANCHOR_ID,
        SECOND_ANCHOR_ID,
        PREVIOUS_ID,
        NEXT_ID,
    }
    next_candidate = next(
        candidate for candidate in expanded if candidate.chunk_id == NEXT_ID
    )
    assert next_candidate.chunk_index == 6
    assert next_candidate.file_name == f"{DOCUMENT_ID}.txt"
    assert next_candidate.retrieval_reason == (
        "Adjacent source context for retrieved chunk index 5."
    )
    assert next_candidate.final_score > 0.0
    assert [candidate.final_score for candidate in expanded] == sorted(
        [candidate.final_score for candidate in expanded],
        reverse=True,
    )


def test_expand_retrieval_context_scopes_documents_and_deduplicates_anchors() -> None:
    anchors = [
        _candidate(chunk_id=ANCHOR_ID, document_id=DOCUMENT_ID, chunk_index=5),
        _candidate(
            chunk_id=SECOND_ANCHOR_ID,
            document_id=SECOND_DOCUMENT_ID,
            chunk_index=2,
            final_score=0.8,
        ),
    ]

    def chunk_lookup(document_id: str, indexes: list[int]) -> list[dict[str, object]]:
        if document_id == str(DOCUMENT_ID):
            return [
                _row(
                    chunk_id=ANCHOR_ID,
                    document_id=DOCUMENT_ID,
                    chunk_index=5,
                    content="Duplicate anchor row.",
                ),
                _row(
                    chunk_id=NEXT_ID,
                    document_id=DOCUMENT_ID,
                    chunk_index=6,
                    content="First document continuation.",
                ),
            ]
        return [
            _row(
                chunk_id=PREVIOUS_ID,
                document_id=SECOND_DOCUMENT_ID,
                chunk_index=1,
                content="Second document context.",
            )
        ]

    lookup: Callable[[str, list[int]], list[dict[str, object]]] = Mock(
        side_effect=chunk_lookup
    )
    expanded = retrieval_context_service.expand_retrieval_context(
        "What context applies?",
        anchors,
        context_window=1,
        max_context_candidates=3,
        chunk_lookup=lookup,
    )

    assert lookup.call_args_list == [
        call(str(DOCUMENT_ID), [4, 6]),
        call(str(SECOND_DOCUMENT_ID), [1, 3]),
    ]
    assert [candidate.chunk_id for candidate in expanded].count(ANCHOR_ID) == 1
    assert {candidate.chunk_id for candidate in expanded} == {
        ANCHOR_ID,
        SECOND_ANCHOR_ID,
        NEXT_ID,
        PREVIOUS_ID,
    }


def test_expand_retrieval_context_respects_global_context_limit() -> None:
    anchors = [_candidate(chunk_id=ANCHOR_ID, chunk_index=5)]
    chunk_lookup = Mock(
        return_value=[
            _row(
                chunk_id=PREVIOUS_ID,
                chunk_index=4,
                content="Previous context.",
            ),
            _row(
                chunk_id=NEXT_ID,
                chunk_index=6,
                content="Next context.",
            ),
        ]
    )

    expanded = retrieval_context_service.expand_retrieval_context(
        "What happened?",
        anchors,
        context_window=1,
        max_context_candidates=1,
        chunk_lookup=chunk_lookup,
    )

    assert len(expanded) == 2
    assert ANCHOR_ID in {candidate.chunk_id for candidate in expanded}
