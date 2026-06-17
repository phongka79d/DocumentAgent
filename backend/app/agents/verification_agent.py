import json
from collections.abc import Mapping
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.agents.prompts import (
    EVIDENCE_COVERAGE_SYSTEM_PROMPT,
    VERIFICATION_AGENT_SYSTEM_PROMPT,
)
from app.agents.schemas import (
    EvidenceCoverageSelection,
    EvidenceCoverageReview,
    RejectedChunk,
    RetrievalCandidate,
    VerificationAgentInput,
    VerificationAgentOutput,
    VerifiedChunk,
)
from app.core.config import get_settings
from app.services import agent_log_service
from app.services import shopaikey_service
from app.services.evidence_quote_service import (
    canonical_source_quote_for_candidate as _canonical_source_quote_for_candidate,
)
from app.services.evidence_quote_service import (
    candidate_source_excerpt as _candidate_source_excerpt,
)
from app.services.evidence_quote_service import (
    expanded_quote_with_surrounding_context as _expanded_quote_with_surrounding_context,
)
from app.services.evidence_quote_service import (
    expanded_quotes_with_surrounding_context as _expanded_quotes_with_surrounding_context,
)
from app.services.evidence_quote_service import normalize_quote_text as _normalize_quote_text
from app.services.evidence_quote_service import (
    quote_matches_candidate_content as _quote_matches_candidate_content,
)
from app.services.verification_prompt_service import (
    COVERAGE_RETRY_INSTRUCTION,
    VERIFICATION_RETRY_INSTRUCTION,
    build_coverage_messages as _service_build_coverage_messages,
    build_coverage_retry_messages as _service_build_coverage_retry_messages,
    build_verification_messages as _service_build_verification_messages,
    build_verification_retry_messages as _service_build_verification_retry_messages,
)
from app.services.verification_log_service import (
    VERIFICATION_LOG_CONTENT_PREVIEW_CHARS,
    build_safe_failed_verification_input,
    build_safe_failed_verification_output,
    build_verification_log_input,
)
from app.services.verification_post_processor import (
    CONTRADICTION_CONFIDENCE_CAP,
    CONTRADICTION_VERIFICATION_REASON,
    NO_VERIFIED_CHUNKS_CONFIDENCE_CAP,
    apply_missing_information_adjustments as _apply_missing_information_adjustments,
)


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
OVERLAPPING_CONTENT_REJECTION_REASON = (
    "Overlapping verified content was removed in favor of a fuller source quote."
)
FINAL_VERIFICATION_OUTPUT_KEYS = (
    "verified_chunks",
    "rejected_chunks",
    "missing_information",
    "confidence",
)
COVERAGE_FAILURE_CONFIDENCE_CAP = 0.4
CONTEXT_EXPANSION_CONFIDENCE_CAP = 0.65
EVIDENCE_COVERAGE_RESPONSE_FORMAT = {"type": "json_object"}
CORRECTABLE_COVERAGE_FAILURE_TYPES = frozenset(
    {
        "coverage_invalid_json",
        "coverage_validation_error",
        "coverage_unknown_chunk_id",
        "coverage_quote_validation_error",
    }
)
CORRECTABLE_VERIFICATION_FAILURE_TYPES = frozenset(
    {
        "invalid_json",
        "schema_validation_error",
        "unknown_chunk_id",
    }
)
_EXPLANATORY_QUESTION_PATTERN = re.compile(
    r"^\s*(?:why|how|v[iì]\s+sao|t[aạ]i\s+sao)\b",
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


def _log_llm_payload_diagnostics(
    *,
    phase: str,
    messages: list[dict[str, str]],
    candidate_count: int,
    retry: bool,
) -> None:
    message_chars = shopaikey_service.estimate_chat_messages_chars(messages)
    logger.info(
        "LLM payload prepared. agent=%s phase=%s message_chars=%s candidate_count=%s retry=%s",
        VERIFICATION_AGENT_NAME,
        phase,
        message_chars,
        candidate_count,
        retry,
    )
    if message_chars >= get_settings().agent_llm_payload_warn_chars:
        logger.warning(
            "LLM payload exceeds warning threshold. agent=%s phase=%s message_chars=%s candidate_count=%s retry=%s",
            VERIFICATION_AGENT_NAME,
            phase,
            message_chars,
            candidate_count,
            retry,
        )


def _build_verification_messages(
    input_data: VerificationAgentInput,
) -> list[dict[str, str]]:
    settings = get_settings()
    return _service_build_verification_messages(
        input_data,
        max_candidates=settings.agent_verification_max_candidates,
        snippet_max_chars=settings.agent_evidence_snippet_max_chars,
        context_sentences=settings.agent_evidence_snippet_context_sentences,
    )


def _build_verification_retry_messages(
    input_data: VerificationAgentInput,
    failure_type: str,
) -> list[dict[str, str]]:
    settings = get_settings()
    return _service_build_verification_retry_messages(
        input_data,
        failure_type=failure_type,
        max_candidates=settings.agent_verification_max_candidates,
        snippet_max_chars=settings.agent_evidence_snippet_max_chars,
        context_sentences=settings.agent_evidence_snippet_context_sentences,
    )


def _build_coverage_messages(
    input_data: VerificationAgentInput,
) -> list[dict[str, str]]:
    settings = get_settings()
    return _service_build_coverage_messages(
        input_data,
        max_candidates=settings.agent_coverage_max_candidates,
        snippet_max_chars=settings.agent_evidence_snippet_max_chars,
        context_sentences=settings.agent_evidence_snippet_context_sentences,
    )


def _build_coverage_retry_messages(
    input_data: VerificationAgentInput,
    invalid_response: str,
    failure_type: str,
) -> list[dict[str, str]]:
    settings = get_settings()
    return _service_build_coverage_retry_messages(
        input_data,
        invalid_response=invalid_response,
        failure_type=failure_type,
        max_candidates=settings.agent_coverage_max_candidates,
        snippet_max_chars=settings.agent_evidence_snippet_max_chars,
        context_sentences=settings.agent_evidence_snippet_context_sentences,
    )


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


def _parse_coverage_review(response_content: str) -> EvidenceCoverageReview:
    try:
        response_payload = json.loads(response_content)
    except json.JSONDecodeError as exc:
        logger.warning("Evidence coverage reviewer returned invalid JSON.")
        raise _VerificationAgentFailure("coverage_invalid_json") from exc

    if (
        isinstance(response_payload, dict)
        and response_payload.get("answers_question") is False
        and response_payload.get("missing_information") is True
    ):
        response_payload = {
            "requirements": [
                {
                    "requirement": (
                        "Answer every independently requested part of the "
                        "question."
                    ),
                    "satisfied": False,
                    "evidence": [],
                    "missing_detail": (
                        "Candidate evidence does not cover every requested "
                        "requirement."
                    ),
                }
            ],
            "selected_evidence": [],
            "confidence": 0.0,
            **response_payload,
        }

    response_payload = _normalize_answerable_coverage_payload(response_payload)

    try:
        return EvidenceCoverageReview.model_validate(response_payload)
    except ValidationError as exc:
        logger.warning("Evidence coverage reviewer returned an invalid schema.")
        raise _VerificationAgentFailure("coverage_validation_error") from exc


def _parse_candidate_aware_coverage_review(
    input_data: VerificationAgentInput,
    response_content: str,
) -> EvidenceCoverageReview:
    try:
        response_payload = json.loads(response_content)
    except json.JSONDecodeError as exc:
        logger.warning("Evidence coverage reviewer returned invalid JSON.")
        raise _VerificationAgentFailure("coverage_invalid_json") from exc

    response_payload = _normalize_non_answerable_coverage_payload(response_payload)
    if (
        isinstance(response_payload, dict)
        and response_payload.get("answers_question") is True
    ):
        response_payload = _normalize_answerable_coverage_payload_with_candidates(
            input_data,
            response_payload,
        )

    try:
        return EvidenceCoverageReview.model_validate(response_payload)
    except ValidationError as exc:
        logger.warning("Evidence coverage reviewer returned an invalid schema.")
        raise _VerificationAgentFailure("coverage_validation_error") from exc


def _normalize_non_answerable_coverage_payload(response_payload: Any) -> Any:
    if (
        not isinstance(response_payload, dict)
        or response_payload.get("answers_question") is not False
        or response_payload.get("missing_information") is not True
    ):
        return response_payload

    return {
        "requirements": [
            {
                "requirement": (
                    "Answer every independently requested part of the question."
                ),
                "satisfied": False,
                "evidence": [],
                "missing_detail": (
                    "Candidate evidence does not cover every requested requirement."
                ),
            }
        ],
        "selected_evidence": [],
        "confidence": 0.0,
        **response_payload,
    }


def _normalize_answerable_coverage_payload(response_payload: Any) -> Any:
    if (
        not isinstance(response_payload, dict)
        or response_payload.get("answers_question") is not True
        or not isinstance(response_payload.get("selected_evidence"), list)
        or not isinstance(response_payload.get("requirements"), list)
    ):
        return response_payload

    selected_keys = {
        _coverage_mapping_key(selection)
        for selection in response_payload["selected_evidence"]
        if _coverage_mapping_key(selection) is not None
    }
    if not selected_keys:
        return response_payload

    changed = False
    requirements = []
    for requirement in response_payload["requirements"]:
        if not isinstance(requirement, dict):
            requirements.append(requirement)
            continue
        evidence = requirement.get("evidence")
        if requirement.get("satisfied") is not True or not isinstance(evidence, list):
            requirements.append(requirement)
            continue

        filtered_evidence = [
            selection
            for selection in evidence
            if _coverage_mapping_key(selection) in selected_keys
        ]
        if len(filtered_evidence) != len(evidence):
            changed = True
            requirement = {**requirement, "evidence": filtered_evidence}
        requirements.append(requirement)

    if not changed:
        return response_payload
    return {**response_payload, "requirements": requirements}


def _coverage_mapping_key(selection: Any) -> tuple[Any, Any] | None:
    if not isinstance(selection, dict):
        return None
    return selection.get("chunk_id"), selection.get("quote")


def _normalize_answerable_coverage_payload_with_candidates(
    input_data: VerificationAgentInput,
    response_payload: dict[str, Any],
) -> dict[str, Any]:
    requirements = response_payload.get("requirements")
    if not isinstance(requirements, list):
        return response_payload

    normalized_requirements = []
    selected_evidence: list[dict[str, Any]] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            normalized_requirements.append(requirement)
            continue
        if requirement.get("satisfied") is not True:
            normalized_requirements.append(requirement)
            continue

        raw_evidence = requirement.get("evidence")
        if not isinstance(raw_evidence, list):
            normalized_requirements.append(requirement)
            continue

        canonical_evidence = _canonicalize_coverage_evidence_payloads(
            input_data,
            raw_evidence,
        )
        normalized_requirement = {
            **requirement,
            "evidence": canonical_evidence,
        }
        normalized_requirements.append(normalized_requirement)
        for selection in canonical_evidence:
            if selection not in selected_evidence:
                selected_evidence.append(selection)

    return {
        **response_payload,
        "requirements": normalized_requirements,
        "selected_evidence": selected_evidence,
    }


def _canonicalize_coverage_evidence_payloads(
    input_data: VerificationAgentInput,
    raw_evidence: list[Any],
) -> list[dict[str, Any]]:
    canonical_evidence = []
    saw_known_invalid_quote = False
    for raw_selection in raw_evidence:
        try:
            selection = EvidenceCoverageSelection.model_validate(raw_selection)
        except ValidationError as exc:
            raise _VerificationAgentFailure("coverage_validation_error") from exc

        selected_candidate = _candidate_for_selection(input_data, selection)
        if selected_candidate is None:
            raise _VerificationAgentFailure("coverage_unknown_chunk_id")

        canonical_selection = _canonicalize_coverage_selection(input_data, selection)
        canonical_candidate = _candidate_for_selection(input_data, canonical_selection)
        if canonical_candidate is None:
            raise _VerificationAgentFailure("coverage_unknown_chunk_id")
        if not _quote_matches_candidate_content(
            canonical_selection.quote,
            canonical_candidate.content,
        ):
            saw_known_invalid_quote = True
            continue

        selection_payload = canonical_selection.model_dump(mode="json")
        if selection_payload not in canonical_evidence:
            canonical_evidence.append(selection_payload)

    if not canonical_evidence and saw_known_invalid_quote:
        raise _VerificationAgentFailure("coverage_quote_validation_error")
    return canonical_evidence


def _run_coverage_review(
    input_data: VerificationAgentInput,
    verification_output: VerificationAgentOutput,
) -> EvidenceCoverageReview:
    del verification_output
    messages = _build_coverage_messages(input_data)
    for attempt in range(2):
        try:
            _log_llm_payload_diagnostics(
                phase="coverage_review",
                messages=messages,
                candidate_count=len(input_data.candidates),
                retry=attempt > 0,
            )
            response_content = shopaikey_service.chat_completion(
                messages,
                response_format=EVIDENCE_COVERAGE_RESPONSE_FORMAT,
            )
        except shopaikey_service.ShopAIKeyServiceError as exc:
            raise _VerificationAgentFailure("coverage_provider_error") from exc

        try:
            review = _parse_candidate_aware_coverage_review(
                input_data,
                response_content,
            )
            review = _canonicalize_coverage_review_evidence(input_data, review)
            _validate_coverage_review_evidence(input_data, review)
            return review
        except _VerificationAgentFailure as exc:
            if (
                exc.failure_type not in CORRECTABLE_COVERAGE_FAILURE_TYPES
                or attempt == 1
            ):
                raise
            messages = _build_coverage_retry_messages(
                input_data,
                response_content,
                exc.failure_type,
            )

    raise _VerificationAgentFailure("coverage_validation_error")


def _run_initial_verification(
    input_data: VerificationAgentInput,
) -> VerificationAgentOutput:
    messages = _build_verification_messages(input_data)
    for attempt in range(2):
        try:
            _log_llm_payload_diagnostics(
                phase="initial_verification",
                messages=messages,
                candidate_count=len(input_data.candidates),
                retry=attempt > 0,
            )
            response_content = shopaikey_service.chat_completion(
                messages,
                response_format={"type": "json_object"},
            )
        except shopaikey_service.ShopAIKeyServiceError as exc:
            raise _VerificationAgentFailure("provider_error") from exc

        try:
            verification_output = _parse_verification_output(response_content)
            return _validate_candidate_membership(
                verification_output,
                input_data,
            )
        except _VerificationAgentFailure as exc:
            if (
                exc.failure_type not in CORRECTABLE_VERIFICATION_FAILURE_TYPES
                or attempt == 1
            ):
                raise
            messages = _build_verification_retry_messages(
                input_data,
                exc.failure_type,
            )

    raise _VerificationAgentFailure("schema_validation_error")


def _coverage_selections(
    coverage_review: EvidenceCoverageReview,
) -> list[EvidenceCoverageSelection]:
    selections = list(coverage_review.selected_evidence)
    for requirement in coverage_review.requirements:
        for selection in requirement.evidence:
            if selection not in selections:
                selections.append(selection)
    return selections


def _validate_coverage_review_evidence(
    input_data: VerificationAgentInput,
    coverage_review: EvidenceCoverageReview,
) -> None:
    candidates_by_chunk_id = {
        candidate.chunk_id: candidate for candidate in input_data.candidates
    }
    for selection in _coverage_selections(coverage_review):
        candidate = candidates_by_chunk_id.get(selection.chunk_id)
        if candidate is None:
            raise _VerificationAgentFailure("coverage_unknown_chunk_id")
        if not _quote_matches_candidate_content(selection.quote, candidate.content):
            raise _VerificationAgentFailure("coverage_quote_validation_error")


def _canonicalize_coverage_review_evidence(
    input_data: VerificationAgentInput,
    coverage_review: EvidenceCoverageReview,
) -> EvidenceCoverageReview:
    updated_requirements = [
        requirement.model_copy(
            update={
                "evidence": [
                    _canonicalize_coverage_selection(input_data, selection)
                    for selection in requirement.evidence
                ]
            }
        )
        for requirement in coverage_review.requirements
    ]
    updated_review = coverage_review.model_copy(
        update={
            "requirements": updated_requirements,
            "selected_evidence": [
                _canonicalize_coverage_selection(input_data, selection)
                for selection in coverage_review.selected_evidence
            ],
        }
    )
    return EvidenceCoverageReview.model_validate(
        updated_review.model_dump(mode="json")
    )


def _candidate_for_selection(
    input_data: VerificationAgentInput,
    selection: EvidenceCoverageSelection,
) -> RetrievalCandidate | None:
    for candidate in input_data.candidates:
        if candidate.chunk_id == selection.chunk_id:
            return candidate
    return None


def _canonicalize_coverage_selection(
    input_data: VerificationAgentInput,
    selection: EvidenceCoverageSelection,
) -> EvidenceCoverageSelection:
    selected_candidate = _candidate_for_selection(input_data, selection)
    if selected_candidate is None:
        return selection
    canonical_quote = _canonical_source_quote_for_candidate(
        selection.quote,
        selected_candidate.content,
    )
    if canonical_quote is not None:
        return selection.model_copy(update={"quote": canonical_quote})

    matching_evidence = []
    for candidate in input_data.candidates:
        canonical_quote = _canonical_source_quote_for_candidate(
            selection.quote,
            candidate.content,
        )
        if canonical_quote is not None:
            matching_evidence.append((candidate, canonical_quote))

    if len(matching_evidence) != 1:
        return selection

    matching_candidate, matching_quote = matching_evidence[0]
    return selection.model_copy(
        update={
            "chunk_id": matching_candidate.chunk_id,
            "quote": matching_quote,
        }
    )


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


def _question_needs_explanatory_context(question: str) -> bool:
    return bool(_EXPLANATORY_QUESTION_PATTERN.search(question))


def _canonicalize_verified_chunk_quote(
    input_data: VerificationAgentInput,
    verified_chunk: VerifiedChunk,
) -> VerifiedChunk | None:
    selected_candidate = next(
        (
            candidate
            for candidate in input_data.candidates
            if candidate.chunk_id == verified_chunk.chunk_id
        ),
        None,
    )
    if selected_candidate is None:
        return None

    canonical_quote = _canonical_source_quote_for_candidate(
        verified_chunk.quote,
        selected_candidate.content,
    )
    if canonical_quote is not None:
        return verified_chunk.model_copy(
            update={
                "quote": canonical_quote,
                "chunk_index": selected_candidate.chunk_index,
            }
        )

    matching_evidence: list[tuple[RetrievalCandidate, str]] = []
    for candidate in input_data.candidates:
        canonical_quote = _canonical_source_quote_for_candidate(
            verified_chunk.quote,
            candidate.content,
        )
        if canonical_quote is not None:
            matching_evidence.append((candidate, canonical_quote))

    if len(matching_evidence) != 1:
        return None

    matching_candidate, matching_quote = matching_evidence[0]
    return verified_chunk.model_copy(
        update={
            "chunk_id": matching_candidate.chunk_id,
            "document_id": matching_candidate.document_id,
            "file_name": matching_candidate.file_name,
            "quote": matching_quote,
            "page_number": matching_candidate.page_number,
            "chunk_index": matching_candidate.chunk_index,
        }
    )


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
        canonical_quote = _canonical_source_quote_for_candidate(
            rejected_chunk.quote,
            candidate.content,
        )
        if canonical_quote is not None:
            rejected_chunks.append(
                rejected_chunk.model_copy(update={"quote": canonical_quote})
            )
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
        canonical_verified_chunk = _canonicalize_verified_chunk_quote(
            input_data,
            verified_chunk,
        )
        if canonical_verified_chunk is not None:
            verified_chunks.append(canonical_verified_chunk)
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


def _filter_duplicate_verified_chunks(
    verification_output: VerificationAgentOutput,
) -> VerificationAgentOutput:
    verified_chunks = []
    rejected_chunks = list(verification_output.rejected_chunks)
    seen_evidence_keys = set()
    seen_quote_keys = set()

    for verified_chunk in verification_output.verified_chunks:
        quote_key = _normalize_quote_text(verified_chunk.quote)
        evidence_key = (verified_chunk.chunk_id, quote_key)

        overlapping_index = _overlapping_verified_chunk_index(
            verified_chunks,
            verified_chunk,
        )
        if overlapping_index is not None:
            existing_chunk = verified_chunks[overlapping_index]
            existing_quote_key = _coverage_quote_dedup_text(existing_chunk.quote)
            current_quote_key = _coverage_quote_dedup_text(verified_chunk.quote)
            if len(current_quote_key) > len(existing_quote_key):
                rejected_chunks.append(
                    _duplicate_rejection_from_verified(
                        existing_chunk,
                        OVERLAPPING_CONTENT_REJECTION_REASON,
                    )
                )
                verified_chunks[overlapping_index] = verified_chunk
                seen_evidence_keys.discard(
                    (existing_chunk.chunk_id, _normalize_quote_text(existing_chunk.quote))
                )
                seen_quote_keys.discard(_normalize_quote_text(existing_chunk.quote))
                seen_evidence_keys.add(evidence_key)
                seen_quote_keys.add(quote_key)
            else:
                rejected_chunks.append(
                    _duplicate_rejection_from_verified(
                        verified_chunk,
                        OVERLAPPING_CONTENT_REJECTION_REASON,
                    )
                )
            continue

        if evidence_key in seen_evidence_keys:
            rejected_chunks.append(
                _duplicate_rejection_from_verified(
                    verified_chunk,
                    DUPLICATE_CHUNK_ID_REJECTION_REASON,
                )
            )
            continue

        if quote_key in seen_quote_keys:
            rejected_chunks.append(
                _duplicate_rejection_from_verified(
                    verified_chunk,
                    DUPLICATE_CONTENT_REJECTION_REASON,
                )
            )
            seen_evidence_keys.add(evidence_key)
            continue

        verified_chunks.append(verified_chunk)
        seen_evidence_keys.add(evidence_key)
        seen_quote_keys.add(quote_key)

    return verification_output.model_copy(
        update={
            "verified_chunks": verified_chunks,
            "rejected_chunks": rejected_chunks,
        }
    )


def _overlapping_verified_chunk_index(
    verified_chunks: list[VerifiedChunk],
    candidate_chunk: VerifiedChunk,
) -> int | None:
    candidate_quote_key = _coverage_quote_dedup_text(candidate_chunk.quote).casefold()
    if not candidate_quote_key:
        return None
    for index, verified_chunk in enumerate(verified_chunks):
        if verified_chunk.chunk_id != candidate_chunk.chunk_id:
            continue
        verified_quote_key = _coverage_quote_dedup_text(verified_chunk.quote).casefold()
        if (
            candidate_quote_key in verified_quote_key
            or verified_quote_key in candidate_quote_key
        ):
            return index
    return None


def _apply_coverage_review(
    input_data: VerificationAgentInput,
    verification_output: VerificationAgentOutput,
    coverage_review: EvidenceCoverageReview,
) -> VerificationAgentOutput:
    if not coverage_review.answers_question:
        expanded_output = _expand_verified_context_for_explanatory_question(
            input_data,
            verification_output,
        )
        if expanded_output is not None:
            return expanded_output
        return verification_output.model_copy(
            update={
                "missing_information": True,
                "confidence": min(
                    verification_output.confidence,
                    coverage_review.confidence,
                    COVERAGE_FAILURE_CONFIDENCE_CAP,
                ),
            }
        )

    candidates_by_chunk_id = {
        candidate.chunk_id: candidate for candidate in input_data.candidates
    }
    selected_chunks = []
    for selection in coverage_review.selected_evidence:
        candidate = candidates_by_chunk_id.get(selection.chunk_id)
        if candidate is None:
            raise _VerificationAgentFailure("coverage_unknown_chunk_id")
        if not _quote_matches_candidate_content(selection.quote, candidate.content):
            raise _VerificationAgentFailure("coverage_quote_validation_error")
        selected_chunks.append(
            VerifiedChunk(
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                file_name=candidate.file_name,
                quote=selection.quote,
                page_number=candidate.page_number,
                chunk_index=candidate.chunk_index,
                verification_reason=selection.purpose,
                supports_simple_reasoning=selection.supports_simple_reasoning,
            )
        )

    selected_keys = {
        _verified_chunk_dedup_key(chunk)
        for chunk in selected_chunks
    }
    verified_chunks = list(selected_chunks)
    for chunk in verification_output.verified_chunks:
        chunk_key = _verified_chunk_dedup_key(chunk)
        if chunk_key in selected_keys:
            continue
        verified_chunks.append(chunk)
        selected_keys.add(chunk_key)

    remaining_rejected_chunks = [
        chunk
        for chunk in verification_output.rejected_chunks
        if (chunk.chunk_id, _coverage_quote_dedup_text(chunk.quote)) not in selected_keys
    ]
    covered_output = verification_output.model_copy(
        update={
            "verified_chunks": verified_chunks,
            "rejected_chunks": remaining_rejected_chunks,
            "missing_information": False,
            "confidence": min(
                verification_output.confidence,
                coverage_review.confidence,
            ),
        }
    )
    return _filter_duplicate_verified_chunks(covered_output)


def _verified_chunk_dedup_key(chunk: VerifiedChunk) -> tuple[Any, str]:
    return chunk.chunk_id, _coverage_quote_dedup_text(chunk.quote)


def _coverage_quote_dedup_text(quote: str) -> str:
    normalized_quote = _normalize_quote_text(quote)
    return re.sub(r"[.,:;!?]+(?='?$)", "", normalized_quote)


def _expand_verified_context_for_explanatory_question(
    input_data: VerificationAgentInput,
    verification_output: VerificationAgentOutput,
) -> VerificationAgentOutput | None:
    if (
        not _question_needs_explanatory_context(input_data.question)
        or not verification_output.verified_chunks
    ):
        return None

    candidates_by_chunk_id = {
        candidate.chunk_id: candidate for candidate in input_data.candidates
    }
    expanded_chunks = []
    expanded_any = False
    for verified_chunk in verification_output.verified_chunks:
        candidate = candidates_by_chunk_id.get(verified_chunk.chunk_id)
        if candidate is None:
            continue
        expanded_quotes = _expanded_quotes_with_surrounding_context(
            verified_chunk.quote,
            candidate.content,
        )
        if expanded_quotes is None:
            expanded_chunks.append(verified_chunk)
            continue
        expanded_any = True
        for expanded_quote in expanded_quotes:
            expanded_chunks.append(
                verified_chunk.model_copy(
                    update={
                        "quote": expanded_quote,
                        "verification_reason": (
                            f"{verified_chunk.verification_reason} "
                            "Expanded with surrounding source context for the "
                            "explanatory question."
                        ),
                        "supports_simple_reasoning": True,
                    }
                )
            )

    if not expanded_any:
        return None

    return _filter_duplicate_verified_chunks(
        verification_output.model_copy(
            update={
                "verified_chunks": expanded_chunks,
                "missing_information": False,
                "confidence": min(
                    verification_output.confidence,
                    CONTEXT_EXPANSION_CONFIDENCE_CAP,
                ),
            }
        )
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
        validated_output = VerificationAgentOutput.model_validate(output_payload)
    except ValidationError as exc:
        logger.warning("Verification post-processing returned invalid output schema.")
        raise _VerificationAgentFailure("post_processing_validation_error") from exc

    return validated_output


def _log_successful_verification(
    validated_input: VerificationAgentInput,
    validated_output: VerificationAgentOutput,
) -> None:
    log_attempt = agent_log_service.try_log_agent_step(
        agent_run_id=str(validated_input.agent_run_id),
        step_name=AGENT_2_VERIFICATION_STEP_NAME,
        agent_name=VERIFICATION_AGENT_NAME,
        input_payload=build_verification_log_input(validated_input),
        output_payload=validated_output,
        status="success",
    )
    _warn_if_agent_2_log_failed(log_attempt)


def _safe_failed_verification_input(
    validated_input: VerificationAgentInput,
) -> dict[str, Any]:
    return build_safe_failed_verification_input(validated_input)


def _safe_failed_verification_output(failure_type: str) -> dict[str, Any]:
    return build_safe_failed_verification_output(
        failure_type=failure_type,
        failure_message=VERIFICATION_FAILURE_MESSAGE,
    )


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

    try:
        candidate_bound_output = _run_initial_verification(validated_input)
        quote_validated_output = _validate_candidate_quotes(
            candidate_bound_output,
            validated_input,
        )
        duplicate_filtered_output = _filter_duplicate_verified_chunks(
            quote_validated_output,
        )
        coverage_review = _run_coverage_review(
            validated_input,
            duplicate_filtered_output,
        )
        coverage_checked_output = _apply_coverage_review(
            validated_input,
            duplicate_filtered_output,
            coverage_review,
        )
        post_processed_output = _apply_missing_information_adjustments(
            coverage_checked_output
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
    "VERIFICATION_LOG_CONTENT_PREVIEW_CHARS",
    "VerificationAgentError",
    "run_verification_agent",
]
