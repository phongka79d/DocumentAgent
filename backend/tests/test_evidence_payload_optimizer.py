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


def test_optimize_candidates_preserves_multi_part_answer_evidence() -> None:
    candidate = _candidate(
        file_name="alice.txt",
        content=(
            "Alice was beginning to get very tired of sitting by her sister on the bank. "
            "Down, down, down. Would the fall never come to an end? "
            "There were cupboards and bookshelves here and there; she saw maps and pictures hung upon pegs. "
            "She took down a jar from one of the shelves as she passed; it was labelled 'ORANGE MARMALADE', "
            "but to her great disappointment it was empty. "
            "She did not like to drop the jar for fear of killing somebody, so managed to put it into one of the cupboards."
        ),
    )

    optimized = optimize_candidates_for_verification(
        question=(
            "What was the label on the jar that Alice took from the shelf "
            "while falling down the well, and what did it contain?"
        ),
        candidates=[candidate],
        max_candidates=8,
        snippet_max_chars=170,
        context_sentences=0,
    )

    assert optimized[0].content in candidate.content
    assert len(optimized[0].content) <= 170
    assert "ORANGE MARMALADE" in optimized[0].content
    assert "it was empty" in optimized[0].content


def test_optimize_candidates_finds_answer_sentence_after_long_front_matter() -> None:
    candidate = _candidate(
        file_name="alice.txt",
        content=(
            "Project Gutenberg's Alice's Adventures in Wonderland, by Lewis Carroll\r\n\r\n"
            "This eBook is for the use of anyone anywhere at no cost and with "
            "almost no restrictions whatsoever. "
            "Alice was beginning to get very tired of sitting by her sister on the bank, "
            "and of having nothing to do: once or twice she had peeped into the book "
            "her sister was reading, but it had no pictures or conversations in it, "
            "'and what is the use of a book,' thought Alice 'without pictures or conversation?' "
            "There was nothing so very remarkable in that; nor did Alice think it so very "
            "much out of the way to hear the Rabbit say to itself, 'Oh dear! Oh dear!' "
            + "Unrelated public domain and story setup text. " * 70
            + "Down, down, down. "
            "Alice looked at the sides of the well, and noticed that they were filled with "
            "cupboards and book-shelves; here and there she saw maps and pictures hung upon pegs. "
            "She took down a jar from one of the shelves as she passed; it was labelled "
            "'ORANGE MARMALADE', but to her great disappointment it was empty: she did not "
            "like to drop the jar for fear of killing somebody."
        ),
    )

    optimized = optimize_candidates_for_verification(
        question=(
            "What was the label on the jar that Alice took from the shelf "
            "while falling down the well, and what did it contain?"
        ),
        candidates=[candidate],
        max_candidates=8,
        snippet_max_chars=1800,
        context_sentences=1,
    )

    snippet = optimized[0].content

    assert snippet is not None
    assert "ORANGE MARMALADE" in snippet
    assert "it was empty" in snippet
    assert len(snippet) <= 1800
    assert snippet in candidate.content


def test_indirect_when_question_snippet_keeps_date_and_duration_evidence() -> None:
    candidate = _candidate(
        file_name="contract.pdf",
        section_title="Probation",
        content=(
            "The employee began trial employment on 01/06/2026. "
            "Trial employment lasts 2 months. "
            "After completion, official work status may be considered. "
            + "General workplace policy sentence. " * 80
        ),
    )

    optimized = optimize_candidates_for_verification(
        question="When can I start official work?",
        candidates=[candidate],
        max_candidates=1,
        snippet_max_chars=150,
        context_sentences=0,
    )

    snippet = optimized[0].content

    assert snippet is not None
    assert "01/06/2026" in snippet
    assert "2 months" in snippet
    assert "official work status" in snippet
    assert len(snippet) <= 150


def test_vietnamese_official_work_question_keeps_date_duration_and_condition() -> None:
    candidate = _candidate(
        file_name="hop-dong.txt",
        section_title="Thoi gian thu viec",
        content=(
            "Nguoi lao dong bat dau thu viec tu ngay 01/06/2026. "
            "Thoi gian thu viec keo dai 2 thang. "
            "Sau khi hoan thanh thu viec, nguoi lao dong co the duoc xet lam viec chinh thuc. "
            + "Noi quy chung cua cong ty. " * 80
        ),
    )

    optimized = optimize_candidates_for_verification(
        question="Toi co the lam viec chinh thuc vao thang may?",
        candidates=[candidate],
        max_candidates=1,
        snippet_max_chars=230,
        context_sentences=0,
    )

    snippet = optimized[0].content

    assert snippet is not None
    assert "01/06/2026" in snippet
    assert "2 thang" in snippet
    assert "lam viec chinh thuc" in snippet
    assert len(snippet) <= 230


def test_vietnamese_when_question_prioritizes_date_and_duration_under_tight_budget() -> None:
    candidate = _candidate(
        file_name="hop-dong.txt",
        section_title="Thoi gian thu viec",
        content=(
            "Nguoi lao dong bat dau thu viec tu ngay 01/06/2026. "
            "Thoi gian thu viec keo dai 2 thang. "
            "Sau khi hoan thanh thu viec, nguoi lao dong co the duoc xet lam viec chinh thuc. "
            + "Noi quy chung cua cong ty. " * 80
        ),
    )

    optimized = optimize_candidates_for_verification(
        question="Bao gio toi duoc xet chinh thuc?",
        candidates=[candidate],
        max_candidates=1,
        snippet_max_chars=95,
        context_sentences=0,
    )

    snippet = optimized[0].content

    assert snippet is not None
    assert "01/06/2026" in snippet
    assert "2 thang" in snippet
    assert len(snippet) <= 95


def test_accented_vietnamese_month_question_prioritizes_date_and_duration() -> None:
    candidate = _candidate(
        file_name="hop-dong.txt",
        section_title="Thời gian thử việc",
        content=(
            "Người lao động bắt đầu thử việc từ ngày 01/06/2026. "
            "Thời gian thử việc kéo dài 2 tháng. "
            "Sau khi hoàn thành thử việc, người lao động có thể được xét làm việc chính thức. "
            + "Nội quy chung của công ty. " * 80
        ),
    )

    optimized = optimize_candidates_for_verification(
        question="Tôi có thể làm việc chính thức vào tháng mấy?",
        candidates=[candidate],
        max_candidates=1,
        snippet_max_chars=95,
        context_sentences=0,
    )

    snippet = optimized[0].content

    assert snippet is not None
    assert "01/06/2026" in snippet
    assert "2 tháng" in snippet
    assert len(snippet) <= 95
