import json
from collections.abc import Mapping
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.agents.prompts import VERIFICATION_AGENT_SYSTEM_PROMPT
from app.agents.schemas import (
    RejectedChunk,
    VerificationAgentInput,
    VerificationAgentOutput,
    VerifiedChunk,
)
from app.services import agent_log_service
from app.services import shopaikey_service


logger = logging.getLogger(__name__)

AGENT_2_VERIFICATION_STEP_NAME = "agent_2_verification"
VERIFICATION_AGENT_NAME = "verification_agent"
VERIFICATION_FAILURE_MESSAGE = "Verification failed. Please try again later."
UNSUPPORTED_QUOTE_REJECTION_REASON = "Quote was not found in source candidate content."
DUPLICATE_CHUNK_ID_REJECTION_REASON = (
    "Duplicate verified chunk_id was removed from verified evidence."
)
DUPLICATE_CONTENT_REJECTION_REASON = (
    "Duplicate verified content was removed from verified evidence."
)
CONTRADICTION_VERIFICATION_REASON = (
    "Potential contradiction detected: verified chunks contain unresolved "
    "conflicting evidence."
)
FINAL_VERIFICATION_OUTPUT_KEYS = (
    "verified_chunks",
    "rejected_chunks",
    "missing_information",
    "confidence",
)
NO_VERIFIED_CHUNKS_CONFIDENCE_CAP = 0.2
CONTRADICTION_CONFIDENCE_CAP = 0.4
_MONTH_BY_NAME = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}
_DATE_PATTERN = re.compile(
    r"\b(?P<iso>\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"
    r"|\b(?P<numeric>\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b"
    r"|\b(?P<month>"
    r"january|february|march|april|may|june|july|august|september|october|"
    r"november|december"
    r")\s+(?P<day>\d{1,2}),?\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)
_NEGATION_PATTERN = re.compile(
    r"\b(?:not|no|never|cannot|can't|does\s+not|do\s+not|did\s+not|"
    r"is\s+not|are\s+not|was\s+not|were\s+not|khong|không|chua|chưa)\b",
    re.IGNORECASE,
)
_CLAIM_HELPER_VERB_PATTERN = re.compile(
    r"\b(?:is|are|was|were|be|being|been|does|do|did|can|may|must|will|"
    r"should)\b",
    re.IGNORECASE,
)


class VerificationAgentError(RuntimeError):
    """Raised when Agent 2 verification fails in a controlled way."""


class _VerificationAgentFailure(VerificationAgentError):
    def __init__(self, failure_type: str) -> None:
        self.failure_type = failure_type
        super().__init__(VERIFICATION_FAILURE_MESSAGE)


def _build_compact_evidence_payload(
    input_data: VerificationAgentInput,
) -> dict[str, Any]:
    return {
        "question": input_data.question,
        "evidence": [
            {
                "chunk_id": str(candidate.chunk_id),
                "document_id": str(candidate.document_id),
                "file_name": candidate.file_name,
                "page_number": candidate.page_number,
                "section_title": candidate.section_title,
                "score": candidate.final_score,
                "content": candidate.content,
            }
            for candidate in input_data.candidates
        ],
    }


def _build_verification_messages(
    input_data: VerificationAgentInput,
) -> list[dict[str, str]]:
    compact_payload = _build_compact_evidence_payload(input_data)
    return [
        {
            "role": "system",
            "content": VERIFICATION_AGENT_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                "Verify the candidate evidence for this question using only the "
                "compact JSON payload below.\n"
                f"{json.dumps(compact_payload, ensure_ascii=False, indent=2)}"
            ),
        },
    ]


def _parse_verification_output(response_content: str) -> VerificationAgentOutput:
    try:
        response_payload = json.loads(response_content)
    except json.JSONDecodeError as exc:
        logger.warning("Verification LLM returned invalid JSON.")
        raise _VerificationAgentFailure("invalid_json") from exc

    try:
        return VerificationAgentOutput.model_validate(response_payload)
    except ValidationError as exc:
        logger.warning("Verification LLM returned invalid output schema.")
        raise _VerificationAgentFailure("schema_validation_error") from exc


def _validate_candidate_membership(
    verification_output: VerificationAgentOutput,
    input_data: VerificationAgentInput,
) -> VerificationAgentOutput:
    candidates_by_chunk_id = {
        candidate.chunk_id: candidate for candidate in input_data.candidates
    }

    for chunk in [
        *verification_output.verified_chunks,
        *verification_output.rejected_chunks,
    ]:
        if chunk.chunk_id not in candidates_by_chunk_id:
            logger.warning(
                "Verification LLM returned unknown chunk_id %s.",
                chunk.chunk_id,
            )
            raise _VerificationAgentFailure("unknown_chunk_id")

    return verification_output


def _normalize_quote_text(value: str) -> str:
    return " ".join(value.split())


def _quote_matches_candidate_content(quote: str, content: str | None) -> bool:
    normalized_quote = _normalize_quote_text(quote)
    normalized_content = _normalize_quote_text(content or "")
    return bool(normalized_quote) and normalized_quote in normalized_content


def _candidate_source_excerpt(content: str | None) -> str | None:
    excerpt = (content or "").strip()
    return excerpt or None


def _validate_candidate_quotes(
    verification_output: VerificationAgentOutput,
    input_data: VerificationAgentInput,
) -> VerificationAgentOutput:
    candidates_by_chunk_id = {
        candidate.chunk_id: candidate for candidate in input_data.candidates
    }
    rejected_chunks = []

    for rejected_chunk in verification_output.rejected_chunks:
        candidate = candidates_by_chunk_id[rejected_chunk.chunk_id]
        if _quote_matches_candidate_content(rejected_chunk.quote, candidate.content):
            rejected_chunks.append(rejected_chunk)
            continue

        source_excerpt = _candidate_source_excerpt(candidate.content)
        if source_excerpt is not None:
            rejected_chunks.append(
                rejected_chunk.model_copy(update={"quote": source_excerpt})
            )

    rejected_chunk_ids = {chunk.chunk_id for chunk in rejected_chunks}
    verified_chunks = []

    for verified_chunk in verification_output.verified_chunks:
        candidate = candidates_by_chunk_id[verified_chunk.chunk_id]
        if _quote_matches_candidate_content(verified_chunk.quote, candidate.content):
            verified_chunks.append(verified_chunk)
            continue

        source_excerpt = _candidate_source_excerpt(candidate.content)
        if (
            source_excerpt is not None
            and verified_chunk.chunk_id not in rejected_chunk_ids
        ):
            rejected_chunks.append(
                RejectedChunk(
                    chunk_id=verified_chunk.chunk_id,
                    document_id=verified_chunk.document_id,
                    file_name=verified_chunk.file_name,
                    quote=source_excerpt,
                    rejection_reason=UNSUPPORTED_QUOTE_REJECTION_REASON,
                )
            )
            rejected_chunk_ids.add(verified_chunk.chunk_id)

    return verification_output.model_copy(
        update={
            "verified_chunks": verified_chunks,
            "rejected_chunks": rejected_chunks,
        }
    )


def _duplicate_rejection_from_verified(
    verified_chunk: VerifiedChunk,
    rejection_reason: str,
) -> RejectedChunk:
    return RejectedChunk(
        chunk_id=verified_chunk.chunk_id,
        document_id=verified_chunk.document_id,
        file_name=verified_chunk.file_name,
        quote=verified_chunk.quote,
        rejection_reason=rejection_reason,
    )


def _duplicate_content_key(
    verified_chunk: VerifiedChunk,
    input_data: VerificationAgentInput,
) -> str:
    candidates_by_chunk_id = {
        candidate.chunk_id: candidate for candidate in input_data.candidates
    }
    candidate = candidates_by_chunk_id[verified_chunk.chunk_id]
    normalized_content = _normalize_quote_text(candidate.content or "")
    if normalized_content:
        return normalized_content
    return _normalize_quote_text(verified_chunk.quote)


def _filter_duplicate_verified_chunks(
    verification_output: VerificationAgentOutput,
    input_data: VerificationAgentInput,
) -> VerificationAgentOutput:
    verified_chunks = []
    rejected_chunks = list(verification_output.rejected_chunks)
    seen_chunk_ids = set()
    seen_content_keys = set()

    for verified_chunk in verification_output.verified_chunks:
        if verified_chunk.chunk_id in seen_chunk_ids:
            rejected_chunks.append(
                _duplicate_rejection_from_verified(
                    verified_chunk,
                    DUPLICATE_CHUNK_ID_REJECTION_REASON,
                )
            )
            continue

        content_key = _duplicate_content_key(verified_chunk, input_data)
        if content_key and content_key in seen_content_keys:
            rejected_chunks.append(
                _duplicate_rejection_from_verified(
                    verified_chunk,
                    DUPLICATE_CONTENT_REJECTION_REASON,
                )
            )
            seen_chunk_ids.add(verified_chunk.chunk_id)
            continue

        verified_chunks.append(verified_chunk)
        seen_chunk_ids.add(verified_chunk.chunk_id)
        if content_key:
            seen_content_keys.add(content_key)

    return verification_output.model_copy(
        update={
            "verified_chunks": verified_chunks,
            "rejected_chunks": rejected_chunks,
        }
    )


def _normalize_date_match(match: re.Match[str]) -> str:
    if match.group("iso"):
        year, month, day = re.split(r"[-/]", match.group("iso"))
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    if match.group("numeric"):
        first, second, third = re.split(r"[-/]", match.group("numeric"))
        if len(third) == 2:
            third = f"20{third}"
        return f"{int(third):04d}-{int(second):02d}-{int(first):02d}"

    month = _MONTH_BY_NAME[match.group("month").lower()]
    return f"{int(match.group('year')):04d}-{month}-{int(match.group('day')):02d}"


def _date_conflict_key(text: str) -> tuple[str, tuple[str, ...]] | None:
    dates = tuple(_normalize_date_match(match) for match in _DATE_PATTERN.finditer(text))
    if not dates:
        return None

    without_dates = _DATE_PATTERN.sub(" <date> ", text.lower())
    key = _normalize_quote_text(re.sub(r"[^a-z0-9<>\s]", " ", without_dates))
    return key, dates


def _has_clear_date_conflict(verified_chunks: list[VerifiedChunk]) -> bool:
    dates_by_statement_key: dict[str, tuple[str, ...]] = {}

    for verified_chunk in verified_chunks:
        conflict_key = _date_conflict_key(verified_chunk.quote)
        if conflict_key is None:
            continue

        statement_key, dates = conflict_key
        existing_dates = dates_by_statement_key.get(statement_key)
        if existing_dates is not None and existing_dates != dates:
            return True
        dates_by_statement_key[statement_key] = dates

    return False


def _claim_conflict_key(text: str) -> tuple[str, bool] | None:
    normalized_text = _normalize_quote_text(text.lower())
    if len(normalized_text) > 180:
        return None

    has_negation = bool(_NEGATION_PATTERN.search(normalized_text))
    without_negation = _NEGATION_PATTERN.sub(" ", normalized_text)
    without_helper_verbs = _CLAIM_HELPER_VERB_PATTERN.sub(" ", without_negation)
    key = _normalize_quote_text(re.sub(r"[^a-z0-9\s]", " ", without_helper_verbs))
    return (key, has_negation) if key else None


def _has_clear_short_claim_conflict(verified_chunks: list[VerifiedChunk]) -> bool:
    polarity_by_claim_key: dict[str, bool] = {}

    for verified_chunk in verified_chunks:
        conflict_key = _claim_conflict_key(verified_chunk.quote)
        if conflict_key is None:
            continue

        claim_key, has_negation = conflict_key
        existing_negation = polarity_by_claim_key.get(claim_key)
        if existing_negation is not None and existing_negation != has_negation:
            return True
        polarity_by_claim_key[claim_key] = has_negation

    return False


def _append_contradiction_reason(verified_chunk: VerifiedChunk) -> VerifiedChunk:
    if "contradict" in verified_chunk.verification_reason.lower():
        return verified_chunk

    return verified_chunk.model_copy(
        update={
            "verification_reason": (
                f"{verified_chunk.verification_reason} "
                f"{CONTRADICTION_VERIFICATION_REASON}"
            )
        }
    )


def _apply_missing_information_adjustments(
    verification_output: VerificationAgentOutput,
) -> VerificationAgentOutput:
    if not verification_output.verified_chunks:
        return verification_output.model_copy(
            update={
                "missing_information": True,
                "confidence": min(
                    verification_output.confidence,
                    NO_VERIFIED_CHUNKS_CONFIDENCE_CAP,
                ),
            }
        )

    has_conflict = _has_clear_date_conflict(
        verification_output.verified_chunks
    ) or _has_clear_short_claim_conflict(verification_output.verified_chunks)
    if not has_conflict:
        return verification_output

    return verification_output.model_copy(
        update={
            "verified_chunks": [
                _append_contradiction_reason(chunk)
                for chunk in verification_output.verified_chunks
            ],
            "missing_information": True,
            "confidence": min(
                verification_output.confidence,
                CONTRADICTION_CONFIDENCE_CAP,
            ),
        }
    )


def _finalize_verification_output(
    verification_output: VerificationAgentOutput | Mapping[str, Any],
) -> VerificationAgentOutput:
    if isinstance(verification_output, VerificationAgentOutput):
        output_payload = verification_output.model_dump()
    else:
        output_payload = {
            key: verification_output[key]
            for key in FINAL_VERIFICATION_OUTPUT_KEYS
            if key in verification_output
        }

    try:
        return VerificationAgentOutput.model_validate(output_payload)
    except ValidationError as exc:
        logger.warning("Verification post-processing returned invalid output schema.")
        raise _VerificationAgentFailure("post_processing_validation_error") from exc


def _log_successful_verification(
    validated_input: VerificationAgentInput,
    validated_output: VerificationAgentOutput,
) -> None:
    log_attempt = agent_log_service.try_log_agent_step(
        agent_run_id=str(validated_input.agent_run_id),
        step_name=AGENT_2_VERIFICATION_STEP_NAME,
        agent_name=VERIFICATION_AGENT_NAME,
        input_payload=validated_input,
        output_payload=validated_output,
        status="success",
    )
    _warn_if_agent_2_log_failed(log_attempt)


def _safe_failed_verification_input(
    validated_input: VerificationAgentInput,
) -> dict[str, Any]:
    return {
        "agent_run_id": str(validated_input.agent_run_id),
        "question": validated_input.question,
        "candidate_count": len(validated_input.candidates),
        "candidate_chunk_ids": [
            str(candidate.chunk_id) for candidate in validated_input.candidates
        ],
    }


def _safe_failed_verification_output(failure_type: str) -> dict[str, Any]:
    return {
        "error": {
            "type": failure_type,
            "message": VERIFICATION_FAILURE_MESSAGE,
        }
    }


def _log_failed_verification(
    validated_input: VerificationAgentInput,
    failure_type: str,
) -> None:
    try:
        log_attempt = agent_log_service.try_log_agent_step(
            agent_run_id=str(validated_input.agent_run_id),
            step_name=AGENT_2_VERIFICATION_STEP_NAME,
            agent_name=VERIFICATION_AGENT_NAME,
            input_payload=_safe_failed_verification_input(validated_input),
            output_payload=_safe_failed_verification_output(failure_type),
            status="failed",
            error_message=VERIFICATION_FAILURE_MESSAGE,
        )
        _warn_if_agent_2_log_failed(log_attempt)
    except Exception:
        logger.exception(
            "Failed to record Agent 2 failed-step log for %s.",
            validated_input.agent_run_id,
        )


def _warn_if_agent_2_log_failed(
    log_attempt: agent_log_service.AgentStepLogAttempt,
) -> None:
    if log_attempt.persisted or log_attempt.persistence_error is None:
        return

    logger.warning(
        "Agent 2 step log persistence failed for %s::%s [%s].",
        log_attempt.persistence_error.agent_name,
        log_attempt.persistence_error.step_name,
        log_attempt.persistence_error.status,
    )


def run_verification_agent(
    input_data: VerificationAgentInput | Mapping[str, Any],
) -> VerificationAgentOutput:
    """Validate Agent 2 input and return structured verification output."""

    validated_input = VerificationAgentInput.model_validate(input_data)

    if not validated_input.candidates:
        logger.info(
            "Verification skipped for %s because Agent 1 returned no candidates.",
            validated_input.agent_run_id,
        )
        empty_output = VerificationAgentOutput(
            verified_chunks=[],
            rejected_chunks=[],
            missing_information=True,
            confidence=0.0,
        )
        _log_successful_verification(validated_input, empty_output)
        return empty_output

    messages = _build_verification_messages(validated_input)
    try:
        response_content = shopaikey_service.chat_completion(
            messages,
            response_format={"type": "json_object"},
        )
    except shopaikey_service.ShopAIKeyServiceError as exc:
        failure = _VerificationAgentFailure("provider_error")
        _log_failed_verification(validated_input, failure.failure_type)
        raise failure from exc

    try:
        verification_output = _parse_verification_output(response_content)
        candidate_bound_output = _validate_candidate_membership(
            verification_output,
            validated_input,
        )
        quote_validated_output = _validate_candidate_quotes(
            candidate_bound_output,
            validated_input,
        )
        duplicate_filtered_output = _filter_duplicate_verified_chunks(
            quote_validated_output,
            validated_input,
        )
        post_processed_output = _apply_missing_information_adjustments(
            duplicate_filtered_output
        )
        finalized_output = _finalize_verification_output(post_processed_output)
    except _VerificationAgentFailure as exc:
        _log_failed_verification(validated_input, exc.failure_type)
        raise
    except VerificationAgentError:
        _log_failed_verification(validated_input, "verification_error")
        raise

    _log_successful_verification(validated_input, finalized_output)
    return finalized_output


__all__ = [
    "AGENT_2_VERIFICATION_STEP_NAME",
    "VERIFICATION_AGENT_NAME",
    "VERIFICATION_FAILURE_MESSAGE",
    "VerificationAgentError",
    "run_verification_agent",
]
