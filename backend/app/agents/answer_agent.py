import re
import json
from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

from pydantic import ValidationError

from app.agents.prompts import ANSWER_GENERATION_SYSTEM_PROMPT
from app.agents.schemas import (
    AnswerAgentInput,
    AnswerAgentOutput,
    AnswerSelfCheck,
    Citation,
    RejectedChunk,
    VerificationAgentOutput,
    VerifiedChunk,
)
from app.services import shopaikey_service


logger = logging.getLogger(__name__)

ANSWER_AGENT_NAME = "answer_agent"
ANSWER_FAILURE_MESSAGE = "Answer generation failed. Please try again later."
INSUFFICIENT_EVIDENCE_ANSWER = (
    "T\u00e0i li\u1ec7u hi\u1ec7n t\u1ea1i ch\u01b0a cung c\u1ea5p "
    "\u0111\u1ee7 th\u00f4ng tin \u0111\u1ec3 x\u00e1c \u0111\u1ecbnh "
    "c\u00e2u tr\u1ea3 l\u1eddi."
)


class AnswerAgentError(RuntimeError):
    """Raised when Agent 3 answer generation fails in a controlled way."""


class _AnswerAgentFailure(AnswerAgentError):
    def __init__(self, failure_type: str) -> None:
        self.failure_type = failure_type
        super().__init__(ANSWER_FAILURE_MESSAGE)


class AnswerEvidenceValidationError(ValueError):
    """Raised when visible answer evidence violates the Agent 3 contract."""


@dataclass(frozen=True)
class AnswerEvidenceLookup:
    """Immutable lookup sets derived from Agent 2 verification output."""

    verified_quotes: frozenset[str]
    verified_file_names: frozenset[str]
    verified_citation_pairs: frozenset[tuple[str, str]]
    verified_chunk_ids: frozenset[str]
    rejected_quotes: frozenset[str]
    rejected_file_names: frozenset[str]
    rejected_citation_pairs: frozenset[tuple[str, str]]
    rejected_chunk_ids: frozenset[str]


READY_SELF_CHECK_REQUIRED_VALUES = {
    "uses_only_verified_chunks": True,
    "has_citation": True,
    "has_unsupported_claims": False,
    "is_ready": True,
}

_CHUNK_ID_LABEL_PATTERN = re.compile(r"\bchunk[\s_-]*id\b", re.IGNORECASE)
ANSWER_GENERATION_RESPONSE_FORMAT = {"type": "json_object"}


def format_citation(citation: Citation) -> str:
    """Render a structured citation in the normal-user display format."""
    return f'{citation.file_name}: "{citation.quote}"'


def validate_answer_evidence_contract(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> None:
    """Validate citation and visible-evidence rules that require Agent 2 output."""
    evidence_lookup = build_answer_evidence_lookup(verification)
    _validate_citation_presence(output.citations)
    _validate_citations_against_evidence(output.citations, evidence_lookup)
    _validate_visible_text(
        text=output.final_answer,
        evidence_lookup=evidence_lookup,
        field_name="final_answer",
    )
    _validate_visible_text(
        text=output.reasoning_summary,
        evidence_lookup=evidence_lookup,
        field_name="reasoning_summary",
    )


def normalize_answer_self_check(
    self_check: AnswerSelfCheck | dict[str, bool],
) -> AnswerSelfCheck:
    """Normalize provider or deterministic self-check data into the schema."""
    if isinstance(self_check, AnswerSelfCheck):
        return self_check
    return AnswerSelfCheck.model_validate(self_check)


def enforce_answer_self_check(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> AnswerSelfCheck:
    """Fail closed unless the answer and self-check both satisfy readiness."""
    validate_answer_evidence_contract(output, verification)
    self_check = normalize_answer_self_check(output.self_check)

    for field_name, required_value in READY_SELF_CHECK_REQUIRED_VALUES.items():
        actual_value = getattr(self_check, field_name)
        if actual_value is not required_value:
            raise AnswerEvidenceValidationError(
                f"Self-check failed: {field_name} must be {required_value}."
            )

    if bool(output.citations) is not self_check.has_citation:
        raise AnswerEvidenceValidationError(
            "Self-check failed: has_citation does not match answer citations."
        )

    return self_check


def normalize_answer_agent_input(
    input_data: AnswerAgentInput | Mapping[str, Any],
) -> AnswerAgentInput:
    """Validate and normalize Agent 3 input without mutating caller data."""
    try:
        return AnswerAgentInput.model_validate(input_data)
    except ValidationError as exc:
        logger.warning("Answer agent input failed schema validation.")
        raise _AnswerAgentFailure("input_validation_error") from exc


def build_answer_generation_payload(
    answer_input: AnswerAgentInput,
) -> dict[str, Any]:
    """Build the compact provider payload from verified evidence only."""
    return {
        "question": answer_input.question,
        "verified_chunks": [
            {
                "file_name": chunk.file_name,
                "quote": chunk.quote,
                "page_number": chunk.page_number,
                "verification_reason": chunk.verification_reason,
                "supports_simple_reasoning": chunk.supports_simple_reasoning,
            }
            for chunk in answer_input.verification.verified_chunks
        ],
    }


def build_answer_generation_messages(
    answer_input: AnswerAgentInput,
) -> list[dict[str, str]]:
    """Build ShopAIKey chat messages without rejected chunks as evidence."""
    payload = build_answer_generation_payload(answer_input)
    return [
        {
            "role": "system",
            "content": ANSWER_GENERATION_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def build_answer_evidence_lookup(
    verification: VerificationAgentOutput,
) -> AnswerEvidenceLookup:
    """Build immutable verified/rejected evidence sets for Agent 3 checks."""
    return AnswerEvidenceLookup(
        verified_quotes=frozenset(chunk.quote for chunk in verification.verified_chunks),
        verified_file_names=frozenset(
            chunk.file_name
            for chunk in verification.verified_chunks
            if chunk.file_name is not None
        ),
        verified_citation_pairs=_evidence_citation_pairs(verification.verified_chunks),
        verified_chunk_ids=frozenset(
            str(chunk.chunk_id) for chunk in verification.verified_chunks
        ),
        rejected_quotes=frozenset(chunk.quote for chunk in verification.rejected_chunks),
        rejected_file_names=frozenset(
            chunk.file_name
            for chunk in verification.rejected_chunks
            if chunk.file_name is not None
        ),
        rejected_citation_pairs=_evidence_citation_pairs(verification.rejected_chunks),
        rejected_chunk_ids=frozenset(
            str(chunk.chunk_id) for chunk in verification.rejected_chunks
        ),
    )


def run_answer_agent(
    input_data: AnswerAgentInput | Mapping[str, Any],
) -> AnswerAgentOutput:
    """Validate Agent 3 input and return safe deterministic answers when required."""

    answer_input = normalize_answer_agent_input(input_data)
    build_answer_evidence_lookup(answer_input.verification)
    if _has_insufficient_evidence(answer_input.verification):
        return _build_insufficient_evidence_output()

    messages = build_answer_generation_messages(answer_input)
    try:
        shopaikey_service.chat_completion(
            messages,
            response_format=ANSWER_GENERATION_RESPONSE_FORMAT,
        )
    except shopaikey_service.ShopAIKeyServiceError as exc:
        raise _AnswerAgentFailure("provider_error") from exc

    raise _AnswerAgentFailure("answer_generation_not_implemented")


def _has_insufficient_evidence(verification: VerificationAgentOutput) -> bool:
    return verification.missing_information or not verification.verified_chunks


def _build_insufficient_evidence_output() -> AnswerAgentOutput:
    return AnswerAgentOutput(
        final_answer=INSUFFICIENT_EVIDENCE_ANSWER,
        citations=[],
        reasoning_summary="Insufficient verified evidence.",
        confidence=0.0,
        self_check=AnswerSelfCheck(
            uses_only_verified_chunks=True,
            has_citation=False,
            has_unsupported_claims=False,
            is_ready=False,
        ),
    )


def _validate_citation_presence(citations: list[Citation]) -> None:
    if not citations:
        raise AnswerEvidenceValidationError(
            "Grounded answer output must include at least one citation."
        )


def _validate_citations_against_evidence(
    citations: list[Citation],
    evidence_lookup: AnswerEvidenceLookup,
) -> None:
    for citation in citations:
        citation_pair = (citation.file_name, citation.quote)
        if (
            citation_pair in evidence_lookup.rejected_citation_pairs
            or citation.quote in evidence_lookup.rejected_quotes
        ):
            raise AnswerEvidenceValidationError(
                f"Citation uses rejected evidence: {format_citation(citation)}"
            )
        if citation.quote not in evidence_lookup.verified_quotes:
            raise AnswerEvidenceValidationError(
                f"Citation quote is not present in verified evidence: "
                f"{format_citation(citation)}"
            )
        if citation_pair not in evidence_lookup.verified_citation_pairs:
            raise AnswerEvidenceValidationError(
                f"Citation file_name and quote do not match verified evidence: "
                f"{format_citation(citation)}"
            )


def _validate_visible_text(
    *,
    text: str,
    evidence_lookup: AnswerEvidenceLookup,
    field_name: str,
) -> None:
    if _CHUNK_ID_LABEL_PATTERN.search(text):
        raise AnswerEvidenceValidationError(
            f"{field_name} must not expose internal chunk ID fields."
        )

    for chunk_id in [
        *evidence_lookup.verified_chunk_ids,
        *evidence_lookup.rejected_chunk_ids,
    ]:
        if chunk_id in text:
            raise AnswerEvidenceValidationError(
                f"{field_name} must not expose internal chunk ID values."
            )

    for rejected_quote in evidence_lookup.rejected_quotes:
        if rejected_quote in text:
            raise AnswerEvidenceValidationError(
                f"{field_name} must not copy rejected evidence into normal output."
            )


def _evidence_citation_pairs(
    chunks: list[VerifiedChunk] | list[RejectedChunk],
) -> frozenset[tuple[str, str]]:
    return frozenset(
        (chunk.file_name, chunk.quote)
        for chunk in chunks
        if chunk.file_name is not None
    )


__all__ = [
    "ANSWER_AGENT_NAME",
    "ANSWER_FAILURE_MESSAGE",
    "ANSWER_GENERATION_RESPONSE_FORMAT",
    "AnswerEvidenceLookup",
    "AnswerAgentError",
    "AnswerEvidenceValidationError",
    "INSUFFICIENT_EVIDENCE_ANSWER",
    "READY_SELF_CHECK_REQUIRED_VALUES",
    "build_answer_generation_messages",
    "build_answer_generation_payload",
    "build_answer_evidence_lookup",
    "enforce_answer_self_check",
    "format_citation",
    "normalize_answer_self_check",
    "normalize_answer_agent_input",
    "run_answer_agent",
    "validate_answer_evidence_contract",
]
