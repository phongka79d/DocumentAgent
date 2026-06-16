import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.schemas import VerificationAgentOutput, VerifiedChunk
from app.services.verification_post_processor import (
    CONTRADICTION_CONFIDENCE_CAP,
    NO_VERIFIED_CHUNKS_CONFIDENCE_CAP,
    apply_missing_information_adjustments,
)


CHUNK_ID = UUID("22222222-2222-2222-2222-222222222222")
SECOND_CHUNK_ID = UUID("44444444-4444-4444-4444-444444444444")
DOCUMENT_ID = UUID("33333333-3333-3333-3333-333333333333")


def _verified_chunk(chunk_id: UUID, quote: str) -> VerifiedChunk:
    return VerifiedChunk(
        chunk_id=chunk_id,
        document_id=DOCUMENT_ID,
        file_name="contract.pdf",
        quote=quote,
        page_number=3,
        verification_reason="This chunk states the relevant fact.",
        supports_simple_reasoning=True,
    )


def test_apply_missing_information_adjustments_caps_output_without_verified_chunks() -> None:
    output = VerificationAgentOutput(
        verified_chunks=[],
        rejected_chunks=[],
        missing_information=False,
        confidence=0.82,
    )

    adjusted = apply_missing_information_adjustments(output)

    assert adjusted.missing_information is True
    assert adjusted.confidence == NO_VERIFIED_CHUNKS_CONFIDENCE_CAP


def test_apply_missing_information_adjustments_marks_conflicting_dates() -> None:
    output = VerificationAgentOutput(
        verified_chunks=[
            _verified_chunk(CHUNK_ID, "Probation starts on June 1, 2026."),
            _verified_chunk(SECOND_CHUNK_ID, "Probation starts on July 1, 2026."),
        ],
        rejected_chunks=[],
        missing_information=False,
        confidence=0.82,
    )

    adjusted = apply_missing_information_adjustments(output)

    assert adjusted.missing_information is True
    assert adjusted.confidence == CONTRADICTION_CONFIDENCE_CAP
    assert all("contradict" in chunk.verification_reason for chunk in adjusted.verified_chunks)


def test_apply_missing_information_adjustments_marks_accented_vietnamese_negation_conflict() -> None:
    output = VerificationAgentOutput(
        verified_chunks=[
            _verified_chunk(CHUNK_ID, "Người lao động đủ điều kiện làm việc chính thức."),
            _verified_chunk(
                SECOND_CHUNK_ID,
                "Người lao động không đủ điều kiện làm việc chính thức.",
            ),
        ],
        rejected_chunks=[],
        missing_information=False,
        confidence=0.82,
    )

    adjusted = apply_missing_information_adjustments(output)

    assert adjusted.missing_information is True
    assert adjusted.confidence == CONTRADICTION_CONFIDENCE_CAP
