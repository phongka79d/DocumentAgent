import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.schemas import RetrievalCandidate
from app.services.evidence_payload_optimizer import optimize_candidates_for_verification


CHUNK_ID = UUID("11111111-1111-4111-8111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")


def _candidate(
    *,
    content: str | None,
    chunk_id: UUID = CHUNK_ID,
    document_id: UUID = DOCUMENT_ID,
    file_name: str | None = "policy.pdf",
    page_number: int | None = 3,
    section_title: str | None = "Returns",
    chunk_index: int | None = 4,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name=file_name,
        content=content,
        page_number=page_number,
        section_title=section_title,
        chunk_index=chunk_index,
        semantic_similarity=0.8,
        graph_relevance=0.2,
        keyword_overlap=0.1,
        metadata_match=0.3,
        recency_or_position_score=0.4,
        final_score=0.7,
        retrieval_reason="semantic match",
    )


def test_optimize_candidates_keeps_relevant_sentence_window_without_inventing_text() -> None:
    candidate = _candidate(
        content=(
            "The document starts with unrelated background. "
            "The refund period lasts 30 days after purchase. "
            "Customers must provide the original receipt. "
            "The final paragraph is unrelated."
        )
    )

    optimized = optimize_candidates_for_verification(
        question="What is the refund period and what proof is required?",
        candidates=[candidate],
        max_candidates=8,
        snippet_max_chars=140,
        context_sentences=1,
    )

    assert len(optimized) == 1
    assert optimized[0].chunk_id == candidate.chunk_id
    assert optimized[0].document_id == candidate.document_id
    assert optimized[0].file_name == candidate.file_name
    assert optimized[0].page_number == candidate.page_number
    assert optimized[0].section_title == candidate.section_title
    assert optimized[0].chunk_index == candidate.chunk_index
    assert "refund period lasts 30 days" in optimized[0].content
    assert "original receipt" in optimized[0].content
    assert optimized[0].content in candidate.content


def test_optimize_candidates_limits_candidate_count_without_reordering() -> None:
    candidates = [
        _candidate(
            chunk_id=UUID(f"11111111-1111-4111-8111-{index:012d}"),
            content=f"Candidate {index} includes payment policy evidence.",
        )
        for index in range(5)
    ]

    optimized = optimize_candidates_for_verification(
        question="payment policy",
        candidates=candidates,
        max_candidates=3,
        snippet_max_chars=120,
        context_sentences=0,
    )

    assert [candidate.chunk_id for candidate in optimized] == [
        candidate.chunk_id for candidate in candidates[:3]
    ]


def test_optimize_candidates_caps_snippet_length_and_keeps_source_substring() -> None:
    candidate = _candidate(
        content=(
            "Noise sentence before the useful part. "
            "Warranty coverage includes replacement parts and labor for two years after purchase. "
            "Noise sentence after the useful part."
        )
    )

    optimized = optimize_candidates_for_verification(
        question="How long does warranty coverage last?",
        candidates=[candidate],
        max_candidates=8,
        snippet_max_chars=70,
        context_sentences=1,
    )

    assert optimized[0].content in candidate.content
    assert len(optimized[0].content) <= 70
    assert "Warranty coverage" in optimized[0].content


def test_optimize_candidates_uses_generic_terms_not_fixture_specific_strings() -> None:
    candidate = _candidate(
        content=(
            "General introduction. "
            "Renewal notices are sent ten business days before expiration. "
            "Closing note."
        )
    )

    optimized = optimize_candidates_for_verification(
        question="When are renewal notices sent?",
        candidates=[candidate],
        max_candidates=8,
        snippet_max_chars=80,
        context_sentences=0,
    )

    assert optimized[0].content == (
        "Renewal notices are sent ten business days before expiration."
    )
