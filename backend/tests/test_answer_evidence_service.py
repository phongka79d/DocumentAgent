import sys
from pathlib import Path
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.schemas import Citation, VerificationAgentOutput
from app.services.answer_evidence_service import (
    AnswerEvidenceValidationError,
    build_answer_evidence_lookup,
    canonicalize_answer_citations,
    format_citation,
    validate_answer_evidence_contract,
)


VERIFIED_CHUNK_ID = UUID("11111111-1111-1111-1111-111111111111")
REJECTED_CHUNK_ID = UUID("22222222-2222-2222-2222-222222222222")
DOCUMENT_ID = UUID("33333333-3333-3333-3333-333333333333")


def _verification_output() -> VerificationAgentOutput:
    return VerificationAgentOutput.model_validate(
        {
            "verified_chunks": [
                {
                    "chunk_id": str(VERIFIED_CHUNK_ID),
                    "document_id": str(DOCUMENT_ID),
                    "file_name": "policy.txt",
                    "quote": "The refund period lasts 30 days after purchase.",
                    "page_number": 1,
                    "verification_reason": "Direct refund evidence.",
                    "supports_simple_reasoning": False,
                }
            ],
            "rejected_chunks": [
                {
                    "chunk_id": str(REJECTED_CHUNK_ID),
                    "document_id": str(DOCUMENT_ID),
                    "file_name": "policy.txt",
                    "quote": "Refunds are always unlimited.",
                    "rejection_reason": "Contradicted by stronger evidence.",
                }
            ],
            "missing_information": False,
            "confidence": 0.8,
        }
    )


def _answer_output(*, quote: str = "The refund period lasts 30 days after purchase."):
    from app.agents.schemas import AnswerAgentOutput, AnswerSelfCheck

    return AnswerAgentOutput(
        final_answer="The refund period lasts 30 days after purchase.",
        citations=[Citation(file_name="policy.txt", quote=quote)],
        reasoning_summary="The verified quote states the refund period.",
        confidence=0.8,
        self_check=AnswerSelfCheck(
            uses_only_verified_chunks=True,
            has_citation=True,
            has_unsupported_claims=False,
            is_ready=True,
        ),
    )


def test_answer_evidence_service_builds_lookup_and_formats_citations() -> None:
    lookup = build_answer_evidence_lookup(_verification_output())

    assert lookup.verified_citation_pairs == frozenset(
        {("policy.txt", "The refund period lasts 30 days after purchase.")}
    )
    assert lookup.rejected_quotes == frozenset({"Refunds are always unlimited."})
    assert format_citation(
        Citation(
            file_name="policy.txt",
            quote="The refund period lasts 30 days after purchase.",
        )
    ) == 'policy.txt: "The refund period lasts 30 days after purchase."'


def test_answer_evidence_service_canonicalizes_unique_verified_subquote() -> None:
    output = _answer_output(quote="refund period lasts 30 days")

    canonical_output = canonicalize_answer_citations(
        output,
        _verification_output(),
    )

    assert canonical_output.citations == [
        Citation(
            file_name="policy.txt",
            quote="The refund period lasts 30 days after purchase.",
        )
    ]


def test_answer_evidence_service_rejects_rejected_visible_quote() -> None:
    output = _answer_output()
    output = output.model_copy(
        update={
            "final_answer": (
                "The refund period lasts 30 days after purchase. "
                "Refunds are always unlimited."
            )
        }
    )

    with pytest.raises(AnswerEvidenceValidationError, match="rejected evidence"):
        validate_answer_evidence_contract(output, _verification_output())


def test_answer_evidence_service_rejects_rejected_visible_quote_variation() -> None:
    output = _answer_output()
    output = output.model_copy(
        update={
            "final_answer": (
                "The refund period lasts 30 days after purchase, "
                "not because refunds are always unlimited"
            )
        }
    )

    with pytest.raises(AnswerEvidenceValidationError, match="rejected evidence"):
        validate_answer_evidence_contract(output, _verification_output())
