import re

from app.agents.schemas import (
    AnswerAgentOutput,
    AnswerSelfCheck,
    Citation,
    RejectedChunk,
    VerificationAgentOutput,
    VerifiedChunk,
)


class AnswerEvidenceValidationError(ValueError):
    """Raised when visible answer evidence violates the Agent 3 contract."""


READY_SELF_CHECK_REQUIRED_VALUES = {
    "uses_only_verified_chunks": True,
    "has_citation": True,
    "has_unsupported_claims": False,
    "is_ready": True,
}

_CHUNK_ID_LABEL_PATTERN = re.compile(r"\bchunk[\s_-]*id\b", re.IGNORECASE)


def format_citation(citation: Citation) -> str:
    """Render a structured citation in the normal-user display format."""
    return f'{citation.file_name}: "{citation.quote}"'


def validate_answer_evidence_contract(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> None:
    """Validate citation and visible-evidence rules that require Agent 2 output."""
    _validate_citation_presence(output.citations)
    _validate_citations_against_evidence(output.citations, verification)
    _validate_visible_text(
        text=output.final_answer,
        verification=verification,
        field_name="final_answer",
    )
    _validate_visible_text(
        text=output.reasoning_summary,
        verification=verification,
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


def _validate_citation_presence(citations: list[Citation]) -> None:
    if not citations:
        raise AnswerEvidenceValidationError(
            "Grounded answer output must include at least one citation."
        )


def _validate_citations_against_evidence(
    citations: list[Citation],
    verification: VerificationAgentOutput,
) -> None:
    verified_citations = _evidence_citation_pairs(verification.verified_chunks)
    verified_quotes = _evidence_quotes(verification.verified_chunks)
    rejected_citations = _evidence_citation_pairs(verification.rejected_chunks)
    rejected_quotes = _evidence_quotes(verification.rejected_chunks)

    for citation in citations:
        citation_pair = (citation.file_name, citation.quote)
        if citation_pair in rejected_citations or citation.quote in rejected_quotes:
            raise AnswerEvidenceValidationError(
                f"Citation uses rejected evidence: {format_citation(citation)}"
            )
        if citation.quote not in verified_quotes:
            raise AnswerEvidenceValidationError(
                f"Citation quote is not present in verified evidence: "
                f"{format_citation(citation)}"
            )
        if citation_pair not in verified_citations:
            raise AnswerEvidenceValidationError(
                f"Citation file_name and quote do not match verified evidence: "
                f"{format_citation(citation)}"
            )


def _validate_visible_text(
    *,
    text: str,
    verification: VerificationAgentOutput,
    field_name: str,
) -> None:
    if _CHUNK_ID_LABEL_PATTERN.search(text):
        raise AnswerEvidenceValidationError(
            f"{field_name} must not expose internal chunk ID fields."
        )

    for chunk_id in _evidence_chunk_ids(verification):
        if chunk_id in text:
            raise AnswerEvidenceValidationError(
                f"{field_name} must not expose internal chunk ID values."
            )

    for rejected_quote in _evidence_quotes(verification.rejected_chunks):
        if rejected_quote in text:
            raise AnswerEvidenceValidationError(
                f"{field_name} must not copy rejected evidence into normal output."
            )


def _evidence_citation_pairs(
    chunks: list[VerifiedChunk] | list[RejectedChunk],
) -> set[tuple[str, str]]:
    return {
        (chunk.file_name, chunk.quote)
        for chunk in chunks
        if chunk.file_name is not None
    }


def _evidence_quotes(chunks: list[VerifiedChunk] | list[RejectedChunk]) -> set[str]:
    return {chunk.quote for chunk in chunks}


def _evidence_chunk_ids(verification: VerificationAgentOutput) -> set[str]:
    return {
        str(chunk.chunk_id)
        for chunk in [
            *verification.verified_chunks,
            *verification.rejected_chunks,
        ]
    }


__all__ = [
    "AnswerEvidenceValidationError",
    "READY_SELF_CHECK_REQUIRED_VALUES",
    "enforce_answer_self_check",
    "format_citation",
    "normalize_answer_self_check",
    "validate_answer_evidence_contract",
]
