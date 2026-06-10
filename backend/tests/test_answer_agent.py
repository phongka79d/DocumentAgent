import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.answer_agent import (
    AnswerEvidenceValidationError,
    READY_SELF_CHECK_REQUIRED_VALUES,
    enforce_answer_self_check,
    format_citation,
    normalize_answer_self_check,
    validate_answer_evidence_contract,
)
from app.agents.prompts import (
    ANSWER_GENERATION_OUTPUT_KEYS,
    ANSWER_GENERATION_SYSTEM_PROMPT,
    ANSWER_SELF_CHECK_SYSTEM_PROMPT,
    SELF_CHECK_OUTPUT_KEYS,
)
from app.agents.schemas import (
    AnswerAgentOutput,
    AnswerSelfCheck,
    Citation,
    VerificationAgentOutput,
)


VERIFIED_CHUNK_ID = "22222222-2222-2222-2222-222222222222"
REJECTED_CHUNK_ID = "33333333-3333-3333-3333-333333333333"
DOCUMENT_ID = "44444444-4444-4444-4444-444444444444"
VERIFIED_QUOTE = "The probation period starts on 01/06/2026 and lasts 2 months."
REJECTED_QUOTE = "The probation period starts on 01/05/2026 and lasts 3 months."


def _verification_output() -> VerificationAgentOutput:
    return VerificationAgentOutput.model_validate(
        {
            "verified_chunks": [
                {
                    "chunk_id": VERIFIED_CHUNK_ID,
                    "document_id": DOCUMENT_ID,
                    "file_name": "contract.pdf",
                    "quote": VERIFIED_QUOTE,
                    "page_number": 3,
                    "verification_reason": "Directly answers the probation period.",
                    "supports_simple_reasoning": True,
                }
            ],
            "rejected_chunks": [
                {
                    "chunk_id": REJECTED_CHUNK_ID,
                    "document_id": DOCUMENT_ID,
                    "file_name": "draft.pdf",
                    "quote": REJECTED_QUOTE,
                    "rejection_reason": "Contradicts verified evidence.",
                }
            ],
            "missing_information": False,
            "confidence": 0.82,
        }
    )


def _answer_output(
    *,
    final_answer: str = "Ban co the lam viec chinh thuc vao thang 8/2026.",
    citations: list[dict[str, str]] | None = None,
    self_check: dict[str, bool] | None = None,
) -> AnswerAgentOutput:
    return AnswerAgentOutput.model_validate(
        {
            "final_answer": final_answer,
            "citations": (
                [
                    {
                        "file_name": "contract.pdf",
                        "quote": VERIFIED_QUOTE,
                    }
                ]
                if citations is None
                else citations
            ),
            "reasoning_summary": "Start date plus two months gives 08/2026.",
            "confidence": 0.82,
            "self_check": self_check
            or {
                "uses_only_verified_chunks": True,
                "has_citation": True,
                "has_unsupported_claims": False,
                "is_ready": True,
            },
        }
    )


def test_citation_schema_normalizes_fields_and_formats_for_display() -> None:
    citation = Citation.model_validate(
        {
            "file_name": " contract.pdf ",
            "quote": f" {VERIFIED_QUOTE} ",
        }
    )

    assert citation.file_name == "contract.pdf"
    assert citation.quote == VERIFIED_QUOTE
    assert format_citation(citation) == f'contract.pdf: "{VERIFIED_QUOTE}"'


@pytest.mark.parametrize(
    "payload",
    [
        {"file_name": "", "quote": VERIFIED_QUOTE},
        {"file_name": "contract.pdf", "quote": "   "},
        {
            "file_name": "contract.pdf",
            "quote": VERIFIED_QUOTE,
            "chunk_id": VERIFIED_CHUNK_ID,
        },
    ],
)
def test_citation_schema_rejects_malformed_or_internal_fields(
    payload: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        Citation.model_validate(payload)


def test_answer_evidence_contract_accepts_verified_citations() -> None:
    validate_answer_evidence_contract(_answer_output(), _verification_output())


def test_answer_self_check_schema_normalizes_and_forbids_extra_fields() -> None:
    self_check = normalize_answer_self_check(
        {
            "uses_only_verified_chunks": True,
            "has_citation": True,
            "has_unsupported_claims": False,
            "is_ready": True,
        }
    )

    assert isinstance(self_check, AnswerSelfCheck)
    assert self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES

    with pytest.raises(ValidationError):
        normalize_answer_self_check(
            {
                "uses_only_verified_chunks": True,
                "has_citation": True,
                "has_unsupported_claims": False,
                "is_ready": True,
                "ignored": True,
            }
        )


def test_enforce_answer_self_check_accepts_ready_verified_answer() -> None:
    self_check = enforce_answer_self_check(_answer_output(), _verification_output())

    assert self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES


@pytest.mark.parametrize(
    ("self_check", "message"),
    [
        (
            {
                "uses_only_verified_chunks": False,
                "has_citation": True,
                "has_unsupported_claims": False,
                "is_ready": True,
            },
            "uses_only_verified_chunks",
        ),
        (
            {
                "uses_only_verified_chunks": True,
                "has_citation": False,
                "has_unsupported_claims": False,
                "is_ready": True,
            },
            "has_citation",
        ),
        (
            {
                "uses_only_verified_chunks": True,
                "has_citation": True,
                "has_unsupported_claims": True,
                "is_ready": True,
            },
            "has_unsupported_claims",
        ),
        (
            {
                "uses_only_verified_chunks": True,
                "has_citation": True,
                "has_unsupported_claims": False,
                "is_ready": False,
            },
            "is_ready",
        ),
    ],
)
def test_enforce_answer_self_check_rejects_non_ready_fields(
    self_check: dict[str, bool],
    message: str,
) -> None:
    with pytest.raises(AnswerEvidenceValidationError, match=message):
        enforce_answer_self_check(
            _answer_output(self_check=self_check),
            _verification_output(),
        )


def test_answer_evidence_contract_requires_at_least_one_citation() -> None:
    with pytest.raises(AnswerEvidenceValidationError, match="at least one citation"):
        validate_answer_evidence_contract(
            _answer_output(citations=[]),
            _verification_output(),
        )


def test_answer_evidence_contract_rejects_citation_not_in_verified_quotes() -> None:
    with pytest.raises(AnswerEvidenceValidationError, match="verified evidence"):
        validate_answer_evidence_contract(
            _answer_output(
                citations=[
                    {
                        "file_name": "contract.pdf",
                        "quote": "This quote does not appear in verified evidence.",
                    }
                ]
            ),
            _verification_output(),
        )


def test_answer_evidence_contract_rejects_citation_from_rejected_chunks() -> None:
    with pytest.raises(AnswerEvidenceValidationError, match="rejected evidence"):
        validate_answer_evidence_contract(
            _answer_output(
                citations=[
                    {
                        "file_name": "draft.pdf",
                        "quote": REJECTED_QUOTE,
                    }
                ]
            ),
            _verification_output(),
        )


def test_answer_evidence_contract_rejects_internal_chunk_ids_in_answer() -> None:
    with pytest.raises(AnswerEvidenceValidationError, match="internal chunk ID"):
        validate_answer_evidence_contract(
            _answer_output(
                final_answer=(
                    "Evidence chunk "
                    f"{VERIFIED_CHUNK_ID} says probation lasts two months."
                )
            ),
            _verification_output(),
        )


def test_answer_generation_prompt_contains_required_grounding_rules() -> None:
    prompt = ANSWER_GENERATION_SYSTEM_PROMPT.lower()

    assert "verified chunks only" in prompt
    assert "never use rejected chunks" in prompt
    assert "outside knowledge" in prompt
    assert "include citations" in prompt
    assert "vietnamese by default" in prompt
    assert "simple reasoning only when the verified evidence clearly supports it" in prompt
    assert "return only valid json" in prompt


def test_answer_generation_prompt_requires_json_output_fields() -> None:
    assert ANSWER_GENERATION_OUTPUT_KEYS == (
        "final_answer",
        "citations",
        "reasoning_summary",
        "confidence",
    )

    for output_key in ANSWER_GENERATION_OUTPUT_KEYS:
        assert f'"{output_key}"' in ANSWER_GENERATION_SYSTEM_PROMPT

    assert '"file_name"' in ANSWER_GENERATION_SYSTEM_PROMPT
    assert '"quote"' in ANSWER_GENERATION_SYSTEM_PROMPT


def test_answer_self_check_prompt_contains_required_rules() -> None:
    prompt = ANSWER_SELF_CHECK_SYSTEM_PROMPT.lower()

    assert "uses only verified chunks" in prompt
    assert "avoids rejected chunks" in prompt
    assert "includes citations" in prompt
    assert "reasoning that follows clearly from the evidence" in prompt
    assert "has no unsupported claims" in prompt
    assert "understandable to the user" in prompt
    assert "return only valid json" in prompt


def test_answer_self_check_prompt_requires_schema_output_fields() -> None:
    assert SELF_CHECK_OUTPUT_KEYS == (
        "uses_only_verified_chunks",
        "has_citation",
        "has_unsupported_claims",
        "is_ready",
    )

    for output_key in SELF_CHECK_OUTPUT_KEYS:
        assert f'"{output_key}"' in ANSWER_SELF_CHECK_SYSTEM_PROMPT
