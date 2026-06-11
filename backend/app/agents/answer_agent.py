import re
import json
from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

from pydantic import ValidationError

from app.agents.prompts import (
    ANSWER_GENERATION_SYSTEM_PROMPT,
    ANSWER_SELF_CHECK_SYSTEM_PROMPT,
)
from app.agents.schemas import (
    AnswerAgentInput,
    AnswerAgentOutput,
    AnswerSelfCheck,
    Citation,
    RejectedChunk,
    VerificationAgentOutput,
    VerifiedChunk,
)
from app.services import agent_log_service, shopaikey_service


logger = logging.getLogger(__name__)

ANSWER_AGENT_NAME = "answer_agent"
ANSWER_AGENT_SUCCESS_STEP_NAME = "agent_3_answer_self_check"
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
DRAFT_SELF_CHECK_PLACEHOLDER = {
    "uses_only_verified_chunks": False,
    "has_citation": False,
    "has_unsupported_claims": True,
    "is_ready": False,
}
ANSWER_OUTPUT_PUBLIC_KEYS = (
    "final_answer",
    "citations",
    "reasoning_summary",
    "confidence",
    "self_check",
)

_CHUNK_ID_LABEL_PATTERN = re.compile(r"\bchunk[\s_-]*id\b", re.IGNORECASE)
ANSWER_GENERATION_RESPONSE_FORMAT = {"type": "json_object"}
ANSWER_SELF_CHECK_RESPONSE_FORMAT = {"type": "json_object"}


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


def execute_answer_self_check(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> AnswerSelfCheck:
    """Run Agent 3 self-check and normalize the provider result into the schema."""
    validate_answer_evidence_contract(output, verification)
    try:
        provider_content = shopaikey_service.chat_completion(
            build_answer_self_check_messages(output, verification),
            response_format=ANSWER_SELF_CHECK_RESPONSE_FORMAT,
        )
    except shopaikey_service.ShopAIKeyServiceError as exc:
        raise _AnswerAgentFailure("self_check_provider_error") from exc

    executed_self_check = parse_and_validate_answer_self_check(provider_content)
    checked_output = output.model_copy(
        update={"self_check": executed_self_check},
    )
    return enforce_answer_self_check(checked_output, verification)


def normalize_answer_agent_input(
    input_data: AnswerAgentInput | Mapping[str, Any],
) -> AnswerAgentInput:
    """Validate and normalize Agent 3 input without mutating caller data."""
    try:
        return AnswerAgentInput.model_validate(input_data)
    except ValidationError as exc:
        logger.warning("Answer agent input failed schema validation.")
        raise _AnswerAgentFailure("input_validation_error") from exc


def parse_and_validate_draft_answer(provider_content: str) -> AnswerAgentOutput:
    """Parse provider JSON and validate the draft answer shape."""
    try:
        draft_payload = json.loads(provider_content)
    except json.JSONDecodeError as exc:
        logger.warning("Answer agent provider response contained invalid JSON.")
        raise _AnswerAgentFailure("invalid_json_response") from exc

    if isinstance(draft_payload, dict) and "self_check" not in draft_payload:
        draft_payload = {
            **draft_payload,
            "self_check": DRAFT_SELF_CHECK_PLACEHOLDER,
        }

    try:
        draft_output = AnswerAgentOutput.model_validate(draft_payload)
    except ValidationError as exc:
        logger.warning("Answer agent draft response failed schema validation.")
        raise _AnswerAgentFailure("draft_validation_error") from exc

    try:
        _validate_citation_presence(draft_output.citations)
    except AnswerEvidenceValidationError as exc:
        logger.warning("Answer agent draft response omitted required citations.")
        raise _AnswerAgentFailure("citation_validation_error") from exc

    return draft_output


def parse_and_validate_answer_self_check(provider_content: str) -> AnswerSelfCheck:
    """Parse provider JSON and validate the self-check shape."""
    try:
        self_check_payload = json.loads(provider_content)
    except json.JSONDecodeError as exc:
        logger.warning("Answer agent self-check response contained invalid JSON.")
        raise _AnswerAgentFailure("invalid_self_check_json_response") from exc

    try:
        return normalize_answer_self_check(self_check_payload)
    except ValidationError as exc:
        logger.warning("Answer agent self-check response failed schema validation.")
        raise _AnswerAgentFailure("self_check_validation_error") from exc


def validate_draft_citation_quotes_against_verified_evidence(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> None:
    """Validate that every draft citation quote exactly matches verified evidence."""
    evidence_lookup = build_answer_evidence_lookup(verification)
    for citation in output.citations:
        if citation.quote not in evidence_lookup.verified_quotes:
            raise AnswerEvidenceValidationError(
                f"Citation quote is not present in verified evidence: "
                f"{format_citation(citation)}"
            )


def validate_draft_answer_against_evidence(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> None:
    """Validate draft citations and visible text before returning an answer."""
    validate_answer_evidence_contract(output, verification)


def normalize_validated_draft_output(
    output: AnswerAgentOutput | Mapping[str, Any],
) -> AnswerAgentOutput:
    """Keep validated drafts in the public Agent 3 output shape."""
    validated_output = AnswerAgentOutput.model_validate(output)
    public_payload = validated_output.model_dump(mode="json")
    if tuple(public_payload.keys()) != ANSWER_OUTPUT_PUBLIC_KEYS:
        raise _AnswerAgentFailure("draft_output_shape_error")
    return AnswerAgentOutput.model_validate(public_payload)


def build_answer_generation_payload(
    answer_input: AnswerAgentInput,
) -> dict[str, Any]:
    """Build the compact provider payload from verified evidence only."""
    return {
        "response_instruction": "Return only valid JSON.",
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


def build_answer_self_check_payload(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> dict[str, Any]:
    """Build the self-check payload with full draft content and evidence context."""
    return {
        "response_instruction": "Return only valid JSON.",
        "draft_answer": {
            "final_answer": output.final_answer,
            "citations": [
                citation.model_dump(mode="json") for citation in output.citations
            ],
            "reasoning_summary": output.reasoning_summary,
            "confidence": output.confidence,
        },
        "verified_chunks": [
            {
                "file_name": chunk.file_name,
                "quote": chunk.quote,
                "page_number": chunk.page_number,
                "verification_reason": chunk.verification_reason,
                "supports_simple_reasoning": chunk.supports_simple_reasoning,
            }
            for chunk in verification.verified_chunks
        ],
        "rejected_chunks": [
            {
                "file_name": chunk.file_name,
                "quote": chunk.quote,
                "rejection_reason": chunk.rejection_reason,
            }
            for chunk in verification.rejected_chunks
        ],
    }


def build_answer_self_check_messages(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> list[dict[str, str]]:
    """Build ShopAIKey messages for full-content answer self-check."""
    payload = build_answer_self_check_payload(output, verification)
    return [
        {
            "role": "system",
            "content": ANSWER_SELF_CHECK_SYSTEM_PROMPT,
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

    try:
        messages = build_answer_generation_messages(answer_input)
        provider_content = shopaikey_service.chat_completion(
            messages,
            response_format=ANSWER_GENERATION_RESPONSE_FORMAT,
        )
    except shopaikey_service.ShopAIKeyServiceError as exc:
        failure = _AnswerAgentFailure("provider_error")
        _log_failed_answer_self_check(answer_input, failure.failure_type)
        raise failure from exc

    try:
        draft_output = parse_and_validate_draft_answer(provider_content)
        validate_draft_citation_quotes_against_verified_evidence(
            draft_output,
            answer_input.verification,
        )
        validate_draft_answer_against_evidence(
            draft_output,
            answer_input.verification,
        )
    except _AnswerAgentFailure as exc:
        _log_failed_answer_self_check(answer_input, exc.failure_type)
        raise
    except AnswerEvidenceValidationError as exc:
        logger.warning("Answer agent draft failed evidence validation.")
        failure = _AnswerAgentFailure(_evidence_validation_failure_type(exc))
        _log_failed_answer_self_check(answer_input, failure.failure_type)
        raise failure from exc

    try:
        self_check = execute_answer_self_check(
            draft_output,
            answer_input.verification,
        )
    except _AnswerAgentFailure as exc:
        _log_failed_answer_self_check(answer_input, exc.failure_type)
        raise
    except AnswerEvidenceValidationError as exc:
        logger.warning("Answer agent self-check failed readiness validation.")
        failure = _AnswerAgentFailure("self_check_failed")
        _log_failed_answer_self_check(answer_input, failure.failure_type)
        raise failure from exc

    try:
        checked_output = draft_output.model_copy(update={"self_check": self_check})
        final_output = normalize_validated_draft_output(checked_output)
    except _AnswerAgentFailure as exc:
        _log_failed_answer_self_check(answer_input, exc.failure_type)
        raise
    _log_successful_answer_self_check(answer_input, draft_output, final_output)
    return final_output


def _log_successful_answer_self_check(
    answer_input: AnswerAgentInput,
    draft_output: AnswerAgentOutput,
    final_output: AnswerAgentOutput,
) -> None:
    log_attempt = agent_log_service.try_log_agent_step(
        agent_run_id=str(answer_input.agent_run_id),
        step_name=ANSWER_AGENT_SUCCESS_STEP_NAME,
        agent_name=ANSWER_AGENT_NAME,
        input_payload=answer_input.model_dump(mode="json"),
        output_payload={
            "draft_answer": {
                "final_answer": draft_output.final_answer,
                "citations": [
                    citation.model_dump(mode="json")
                    for citation in draft_output.citations
                ],
                "reasoning_summary": draft_output.reasoning_summary,
                "confidence": draft_output.confidence,
            },
            "self_check_result": final_output.self_check.model_dump(mode="json"),
            "final_answer": final_output.final_answer,
            "citations": [
                citation.model_dump(mode="json") for citation in final_output.citations
            ],
            "reasoning_summary": final_output.reasoning_summary,
            "confidence": final_output.confidence,
            "errors": [],
        },
        status="success",
        error_message=None,
    )
    _warn_if_agent_3_log_failed(log_attempt)


def _safe_failed_answer_input(answer_input: AnswerAgentInput) -> dict[str, Any]:
    return {
        "agent_run_id": str(answer_input.agent_run_id),
        "question": answer_input.question,
        "verified_chunk_count": len(answer_input.verification.verified_chunks),
        "rejected_chunk_count": len(answer_input.verification.rejected_chunks),
        "verified_chunk_ids": [
            str(chunk.chunk_id) for chunk in answer_input.verification.verified_chunks
        ],
        "rejected_chunk_ids": [
            str(chunk.chunk_id) for chunk in answer_input.verification.rejected_chunks
        ],
    }


def _safe_failed_answer_output(failure_type: str) -> dict[str, Any]:
    return {
        "error": {
            "type": failure_type,
            "message": ANSWER_FAILURE_MESSAGE,
        }
    }


def _log_failed_answer_self_check(
    answer_input: AnswerAgentInput,
    failure_type: str,
) -> None:
    try:
        log_attempt = agent_log_service.try_log_agent_step(
            agent_run_id=str(answer_input.agent_run_id),
            step_name=ANSWER_AGENT_SUCCESS_STEP_NAME,
            agent_name=ANSWER_AGENT_NAME,
            input_payload=_safe_failed_answer_input(answer_input),
            output_payload=_safe_failed_answer_output(failure_type),
            status="failed",
            error_message=ANSWER_FAILURE_MESSAGE,
        )
        _warn_if_agent_3_log_failed(log_attempt)
    except Exception:
        logger.exception(
            "Failed to record Agent 3 failed-step log for %s.",
            answer_input.agent_run_id,
        )


def _warn_if_agent_3_log_failed(
    log_attempt: agent_log_service.AgentStepLogAttempt | None,
) -> None:
    if (
        log_attempt is None
        or log_attempt.persisted
        or log_attempt.persistence_error is None
    ):
        return

    logger.warning(
        "Agent 3 step log persistence failed for %s::%s [%s].",
        log_attempt.persistence_error.agent_name,
        log_attempt.persistence_error.step_name,
        log_attempt.persistence_error.status,
    )


def _evidence_validation_failure_type(exc: AnswerEvidenceValidationError) -> str:
    if "rejected evidence" in str(exc):
        return "rejected_evidence_error"
    return "citation_validation_error"


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
    "ANSWER_AGENT_SUCCESS_STEP_NAME",
    "ANSWER_FAILURE_MESSAGE",
    "ANSWER_GENERATION_RESPONSE_FORMAT",
    "ANSWER_SELF_CHECK_RESPONSE_FORMAT",
    "ANSWER_OUTPUT_PUBLIC_KEYS",
    "AnswerEvidenceLookup",
    "AnswerAgentError",
    "AnswerEvidenceValidationError",
    "DRAFT_SELF_CHECK_PLACEHOLDER",
    "INSUFFICIENT_EVIDENCE_ANSWER",
    "READY_SELF_CHECK_REQUIRED_VALUES",
    "build_answer_generation_messages",
    "build_answer_generation_payload",
    "build_answer_self_check_messages",
    "build_answer_self_check_payload",
    "build_answer_evidence_lookup",
    "enforce_answer_self_check",
    "execute_answer_self_check",
    "format_citation",
    "normalize_answer_self_check",
    "normalize_answer_agent_input",
    "normalize_validated_draft_output",
    "parse_and_validate_draft_answer",
    "parse_and_validate_answer_self_check",
    "run_answer_agent",
    "validate_draft_answer_against_evidence",
    "validate_draft_citation_quotes_against_verified_evidence",
    "validate_answer_evidence_contract",
]
