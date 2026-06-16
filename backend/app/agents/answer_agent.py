import re
import json
from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

from pydantic import ValidationError

from app.agents.prompts import (
    ANSWER_GROUNDING_SYSTEM_PROMPT,
    ANSWER_GENERATION_SYSTEM_PROMPT,
)
from app.agents.schemas import (
    AnswerAgentInput,
    AnswerAgentOutput,
    AnswerGroundingReview,
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


@dataclass(frozen=True)
class ExecutedAnswerGrounding:
    """Validated grounding review and its derived public self-check."""

    self_check: AnswerSelfCheck
    confidence: float
    review: AnswerGroundingReview


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
ANSWER_GENERATION_RETRY_INSTRUCTION = (
    "The previous draft failed claim grounding. Rewrite the answer more "
    "narrowly using only facts, causes, reasons, or context explicitly stated "
    "in verified quotes. Preserve literal labels, names, titles, identifiers, "
    "codes, and numeric values exactly. Remove unsupported interpretations, "
    "broad labels, examples, and side events unless the question asks for them."
)
_EXPLANATORY_QUESTION_PATTERN = re.compile(
    r"^\s*(?:why|how|v[iì]\s+sao|t[aạ]i\s+sao)\b",
    re.IGNORECASE,
)


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
    question: str,
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> ExecutedAnswerGrounding:
    """Run claim grounding and derive the public Agent 3 self-check."""
    validate_answer_evidence_contract(output, verification)
    try:
        provider_content = shopaikey_service.chat_completion(
            build_answer_self_check_messages(question, output, verification),
            response_format=ANSWER_SELF_CHECK_RESPONSE_FORMAT,
        )
    except shopaikey_service.ShopAIKeyServiceError as exc:
        raise _AnswerAgentFailure("self_check_provider_error") from exc

    review = parse_and_validate_answer_grounding(provider_content)
    review = canonicalize_grounding_review_citations(review, verification)
    executed_self_check = _derive_answer_self_check(
        output,
        verification,
        review,
    )
    checked_output = output.model_copy(
        update={"self_check": executed_self_check},
    )
    enforce_answer_self_check(checked_output, verification)
    return ExecutedAnswerGrounding(
        self_check=executed_self_check,
        confidence=review.confidence,
        review=review,
    )


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


def parse_and_validate_answer_grounding(
    provider_content: str,
) -> AnswerGroundingReview:
    """Parse provider JSON and validate the claim-grounding shape."""
    try:
        grounding_payload = json.loads(provider_content)
    except json.JSONDecodeError as exc:
        logger.warning("Answer grounding response contained invalid JSON.")
        raise _AnswerAgentFailure("invalid_grounding_json_response") from exc

    try:
        return AnswerGroundingReview.model_validate(grounding_payload)
    except ValidationError as exc:
        logger.warning("Answer grounding response failed schema validation.")
        raise _AnswerAgentFailure("grounding_validation_error") from exc


def _normalize_visible_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _derive_answer_self_check(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
    review: AnswerGroundingReview,
) -> AnswerSelfCheck:
    evidence_lookup = build_answer_evidence_lookup(verification)
    expected_text = {
        "final_answer": output.final_answer,
        "reasoning_summary": output.reasoning_summary,
    }
    all_claims_supported = True

    for field_review in review.field_reviews:
        if field_review.text != expected_text[field_review.field_name]:
            raise AnswerEvidenceValidationError(
                f"Grounding review text does not match {field_review.field_name}."
            )
        normalized_field_text = _normalize_visible_text(field_review.text)
        for claim in field_review.claims:
            if _normalize_visible_text(claim.claim) not in normalized_field_text:
                raise AnswerEvidenceValidationError(
                    "Grounding review claim is not present in the reviewed field."
                )
            if not claim.supported or not claim.supporting_citations:
                all_claims_supported = False
            for citation in claim.supporting_citations:
                citation_pair = (citation.file_name, citation.quote)
                if (
                    citation_pair in evidence_lookup.rejected_citation_pairs
                    or citation.quote in evidence_lookup.rejected_quotes
                ):
                    raise AnswerEvidenceValidationError(
                        "Grounding review references rejected evidence."
                    )
                if citation_pair not in evidence_lookup.verified_citation_pairs:
                    raise AnswerEvidenceValidationError(
                        "Grounding review references non-verified evidence."
                    )

    has_citation = bool(output.citations)
    has_unsupported_claims = (
        not review.answers_question or not all_claims_supported
    )
    return AnswerSelfCheck(
        uses_only_verified_chunks=all_claims_supported,
        has_citation=has_citation,
        has_unsupported_claims=has_unsupported_claims,
        is_ready=(
            review.answers_question
            and all_claims_supported
            and has_citation
        ),
    )


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


def canonicalize_answer_citations(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> AnswerAgentOutput:
    """Replace source subquote citations with their unique verified quote."""
    canonical_citations = [
        _canonicalize_citation(citation, verification)
        for citation in output.citations
    ]
    if canonical_citations == output.citations:
        return output
    return output.model_copy(update={"citations": canonical_citations})


def canonicalize_grounding_review_citations(
    review: AnswerGroundingReview,
    verification: VerificationAgentOutput,
) -> AnswerGroundingReview:
    """Replace grounding subquote support with its unique verified quote."""
    field_reviews = []
    for field_review in review.field_reviews:
        claims = []
        for claim in field_review.claims:
            claims.append(
                claim.model_copy(
                    update={
                        "supporting_citations": [
                            _canonicalize_citation(citation, verification)
                            for citation in claim.supporting_citations
                        ]
                    }
                )
            )
        field_reviews.append(field_review.model_copy(update={"claims": claims}))
    return review.model_copy(update={"field_reviews": field_reviews})


def _canonicalize_citation(
    citation: Citation,
    verification: VerificationAgentOutput,
) -> Citation:
    normalized_citation_quote = _normalize_evidence_quote(citation.quote)
    for rejected_chunk in verification.rejected_chunks:
        if (
            rejected_chunk.file_name == citation.file_name
            and _normalize_evidence_quote(rejected_chunk.quote)
            == normalized_citation_quote
        ):
            return citation

    exact_matches = [
        chunk
        for chunk in verification.verified_chunks
        if chunk.file_name == citation.file_name and chunk.quote == citation.quote
    ]
    if len(exact_matches) == 1:
        return citation

    verified_substring_matches = [
        chunk
        for chunk in verification.verified_chunks
        if (
            chunk.file_name == citation.file_name
            and normalized_citation_quote
            and normalized_citation_quote in _normalize_evidence_quote(chunk.quote)
        )
    ]
    if len(verified_substring_matches) == 1:
        matched_chunk = verified_substring_matches[0]
        return Citation(file_name=matched_chunk.file_name, quote=matched_chunk.quote)
    if len(verified_substring_matches) > 1:
        raise AnswerEvidenceValidationError(
            f"Citation quote matches multiple verified evidence quotes: "
            f"{format_citation(citation)}"
        )
    return citation


def _normalize_evidence_quote(value: str) -> str:
    return " ".join(value.split())


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
    retry_instruction: str | None = None,
) -> dict[str, Any]:
    """Build the compact provider payload from verified evidence only."""
    payload = {
        "response_instruction": "Return only valid JSON.",
        "question": answer_input.question,
        "verified_chunks": _answer_evidence_payload(answer_input.verification),
    }
    if retry_instruction is not None:
        payload["retry_instruction"] = retry_instruction
    return payload


def build_answer_generation_messages(
    answer_input: AnswerAgentInput,
    retry_instruction: str | None = None,
) -> list[dict[str, str]]:
    """Build ShopAIKey chat messages without rejected chunks as evidence."""
    payload = build_answer_generation_payload(answer_input, retry_instruction)
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
    question: str,
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> dict[str, Any]:
    """Build the self-check payload with full draft content and evidence context."""
    return {
        "response_instruction": "Return only valid JSON.",
        "question": question,
        "draft_answer": {
            "final_answer": output.final_answer,
            "citations": [
                citation.model_dump(mode="json") for citation in output.citations
            ],
            "reasoning_summary": output.reasoning_summary,
            "confidence": output.confidence,
        },
        "verified_chunks": _answer_evidence_payload(verification),
        "rejected_chunks": _rejected_evidence_payload(verification),
    }


def build_answer_self_check_messages(
    question: str,
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> list[dict[str, str]]:
    """Build ShopAIKey messages for full-content answer self-check."""
    payload = build_answer_self_check_payload(question, output, verification)
    return [
        {
            "role": "system",
            "content": ANSWER_GROUNDING_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def _answer_evidence_payload(
    verification: VerificationAgentOutput,
) -> list[dict[str, Any]]:
    return [
        {
            "file_name": chunk.file_name,
            "quote": chunk.quote,
            "page_number": chunk.page_number,
        }
        for chunk in verification.verified_chunks
    ]


def _rejected_evidence_payload(
    verification: VerificationAgentOutput,
) -> list[dict[str, Any]]:
    return [
        {
            "file_name": chunk.file_name,
            "quote": chunk.quote,
        }
        for chunk in verification.rejected_chunks
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
        insufficient_output = _build_insufficient_evidence_output()
        _log_insufficient_answer(
            answer_input,
            failure_type="insufficient_evidence",
            output=insufficient_output,
        )
        return insufficient_output

    try:
        draft_output = _generate_validated_draft_answer(answer_input)
    except _AnswerAgentFailure as exc:
        _log_failed_answer_self_check(answer_input, exc.failure_type)
        raise
    except AnswerEvidenceValidationError as exc:
        logger.warning("Answer agent draft failed evidence validation.")
        failure = _AnswerAgentFailure(_evidence_validation_failure_type(exc))
        _log_failed_answer_self_check(answer_input, failure.failure_type)
        raise failure from exc

    try:
        executed_grounding = execute_answer_self_check(
            answer_input.question,
            draft_output,
            answer_input.verification,
        )
    except _AnswerAgentFailure as exc:
        _log_failed_answer_self_check(answer_input, exc.failure_type)
        raise
    except AnswerEvidenceValidationError as exc:
        logger.warning("Answer agent self-check failed readiness validation.")
        if not _should_retry_answer_generation_after_self_check_failure(answer_input):
            failure = _AnswerAgentFailure("self_check_failed")
            _log_failed_answer_self_check(answer_input, failure.failure_type)
            raise failure from exc
        try:
            draft_output = _generate_validated_draft_answer(
                answer_input,
                retry_instruction=ANSWER_GENERATION_RETRY_INSTRUCTION,
            )
            executed_grounding = execute_answer_self_check(
                answer_input.question,
                draft_output,
                answer_input.verification,
            )
        except _AnswerAgentFailure as retry_exc:
            _log_failed_answer_self_check(answer_input, retry_exc.failure_type)
            raise
        except AnswerEvidenceValidationError as retry_exc:
            logger.warning("Answer agent self-check retry failed readiness validation.")
            insufficient_output = _build_insufficient_evidence_output()
            _log_insufficient_answer(
                answer_input,
                failure_type="self_check_failed",
                output=insufficient_output,
            )
            return insufficient_output

    try:
        checked_output = draft_output.model_copy(
            update={
                "self_check": executed_grounding.self_check,
                "confidence": min(
                    draft_output.confidence,
                    answer_input.verification.confidence,
                    executed_grounding.confidence,
                ),
            }
        )
        final_output = normalize_validated_draft_output(checked_output)
    except _AnswerAgentFailure as exc:
        _log_failed_answer_self_check(answer_input, exc.failure_type)
        raise
    _log_successful_answer_self_check(
        answer_input,
        draft_output,
        final_output,
        executed_grounding.review,
    )
    return final_output


def _generate_validated_draft_answer(
    answer_input: AnswerAgentInput,
    retry_instruction: str | None = None,
) -> AnswerAgentOutput:
    try:
        messages = build_answer_generation_messages(answer_input, retry_instruction)
        provider_content = shopaikey_service.chat_completion(
            messages,
            response_format=ANSWER_GENERATION_RESPONSE_FORMAT,
        )
    except shopaikey_service.ShopAIKeyServiceError as exc:
        raise _AnswerAgentFailure("provider_error") from exc

    draft_output = parse_and_validate_draft_answer(provider_content)
    draft_output = canonicalize_answer_citations(
        draft_output,
        answer_input.verification,
    )
    validate_draft_citation_quotes_against_verified_evidence(
        draft_output,
        answer_input.verification,
    )
    validate_draft_answer_against_evidence(
        draft_output,
        answer_input.verification,
    )
    return draft_output


def _should_retry_answer_generation_after_self_check_failure(
    answer_input: AnswerAgentInput,
) -> bool:
    return bool(answer_input.verification.verified_chunks)


def _log_successful_answer_self_check(
    answer_input: AnswerAgentInput,
    draft_output: AnswerAgentOutput,
    final_output: AnswerAgentOutput,
    grounding_review: AnswerGroundingReview,
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
            "grounding_review": grounding_review.model_dump(mode="json"),
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


def _log_insufficient_answer(
    answer_input: AnswerAgentInput,
    *,
    failure_type: str,
    output: AnswerAgentOutput,
) -> None:
    log_attempt = agent_log_service.try_log_agent_step(
        agent_run_id=str(answer_input.agent_run_id),
        step_name=ANSWER_AGENT_SUCCESS_STEP_NAME,
        agent_name=ANSWER_AGENT_NAME,
        input_payload=answer_input.model_dump(mode="json"),
        output_payload={
            "final_answer": output.final_answer,
            "citations": [
                citation.model_dump(mode="json") for citation in output.citations
            ],
            "reasoning_summary": output.reasoning_summary,
            "confidence": output.confidence,
            "self_check_result": output.self_check.model_dump(mode="json"),
            "fallback_reason": failure_type,
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
    "ExecutedAnswerGrounding",
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
    "parse_and_validate_answer_grounding",
    "run_answer_agent",
    "validate_draft_answer_against_evidence",
    "validate_draft_citation_quotes_against_verified_evidence",
    "validate_answer_evidence_contract",
]
