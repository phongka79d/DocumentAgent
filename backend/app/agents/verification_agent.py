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
COVERAGE_FAILURE_CONFIDENCE_CAP = 0.4
CONTEXT_EXPANSION_CONFIDENCE_CAP = 0.65
ANSWERABLE_EVIDENCE_CONFIDENCE_FLOOR = 0.5
EVIDENCE_COVERAGE_RESPONSE_FORMAT = {"type": "json_object"}
COVERAGE_RETRY_INSTRUCTION = """
The previous response failed evidence coverage validation with category:
{failure_type}.
Return one corrected JSON object only.

The fields must be internally consistent:
- Split the question into every independently requested requirement.
- Every requirement must say whether it is satisfied and list exact source
  evidence or a non-empty missing_detail.
- answers_question may be true only when every requirement is satisfied.
- If selected_evidence is non-empty, answers_question must be true and
  missing_information must be false.
- If answers_question is false, missing_information must be true and
  selected_evidence must be an empty list.

Do not add evidence that is not an exact substring of the candidate content.
""".strip()
CORRECTABLE_COVERAGE_FAILURE_TYPES = frozenset(
    {
        "coverage_invalid_json",
        "coverage_validation_error",
        "coverage_unknown_chunk_id",
        "coverage_quote_validation_error",
    }
)
VERIFICATION_RETRY_INSTRUCTION = """
The previous verification response failed validation with category:
{failure_type}.
Return one corrected JSON object only.

Use only chunk_id and document_id values that appear in the compact evidence
payload. Do not invent IDs, documents, quotes, or metadata. Keep quotes copied
from candidate content, and keep the exact Agent 2 response schema.
""".strip()
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
_SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])(?P<closing_quote>['\"]?)\s+")
_ELLIPSIS_MARKER_PATTERN = re.compile(
    r"\s*(?:\[\s*(?:\.{3}|\u2026)\s*\]|\.{3}|\u2026)\s*"
)
_QUOTE_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
_ORDERED_QUOTE_MIN_TOKENS = 6
_ORDERED_QUOTE_MAX_EXTRA_TOKENS = 30
_ORDERED_QUOTE_MAX_SPAN_TOKEN_MULTIPLIER = 4
_ORDERED_QUOTE_MAX_SPAN_CHARS = 1200
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


def _build_verification_retry_messages(
    input_data: VerificationAgentInput,
    failure_type: str,
) -> list[dict[str, str]]:
    return [
        *_build_verification_messages(input_data),
        {
            "role": "user",
            "content": VERIFICATION_RETRY_INSTRUCTION.format(
                failure_type=failure_type
            ),
        },
    ]


def _build_coverage_messages(
    input_data: VerificationAgentInput,
) -> list[dict[str, str]]:
    payload = {
        "response_instruction": "Return only valid JSON.",
        "question": input_data.question,
        "candidates": [
            {
                "chunk_id": str(candidate.chunk_id),
                "file_name": candidate.file_name,
                "page_number": candidate.page_number,
                "content": candidate.content,
            }
            for candidate in input_data.candidates
        ],
    }
    return [
        {
            "role": "system",
            "content": EVIDENCE_COVERAGE_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        },
    ]


def _build_coverage_retry_messages(
    input_data: VerificationAgentInput,
    invalid_response: str,
    failure_type: str,
) -> list[dict[str, str]]:
    return [
        *_build_coverage_messages(input_data),
        {
            "role": "assistant",
            "content": invalid_response,
        },
        {
            "role": "user",
            "content": COVERAGE_RETRY_INSTRUCTION.format(
                failure_type=failure_type
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


def _source_span_for_ellipsized_quote(
    quote: str,
    content: str | None,
) -> str | None:
    normalized_quote = _normalize_quote_text(quote)
    if not _ELLIPSIS_MARKER_PATTERN.search(normalized_quote):
        return None

    fragments = [
        fragment.strip()
        for fragment in _ELLIPSIS_MARKER_PATTERN.split(normalized_quote)
        if fragment.strip()
    ]
    if len(fragments) < 2:
        return None

    normalized_content = _normalize_quote_text(content or "")
    span_start: int | None = None
    span_end: int | None = None
    search_start = 0
    for fragment in fragments:
        fragment_start = normalized_content.find(fragment, search_start)
        if fragment_start < 0:
            return None
        if span_start is None:
            span_start = fragment_start
        span_end = fragment_start + len(fragment)
        search_start = span_end

    if span_start is None or span_end is None:
        return None
    return normalized_content[span_start:span_end].strip()


def _source_span_for_token_sequence_quote(
    quote: str,
    content: str | None,
) -> str | None:
    normalized_quote = _normalize_quote_text(quote)
    normalized_content = _normalize_quote_text(content or "")
    quote_tokens = [
        match.group(0).casefold()
        for match in _QUOTE_TOKEN_PATTERN.finditer(normalized_quote)
    ]
    if len(quote_tokens) < 4:
        return None

    content_token_matches = list(_QUOTE_TOKEN_PATTERN.finditer(normalized_content))
    content_tokens = [match.group(0).casefold() for match in content_token_matches]
    matches: list[tuple[int, int]] = []
    window_size = len(quote_tokens)
    for start in range(0, len(content_tokens) - window_size + 1):
        if content_tokens[start : start + window_size] == quote_tokens:
            span_start = content_token_matches[start].start()
            span_end = content_token_matches[start + window_size - 1].end()
            matches.append((span_start, span_end))

    if len(matches) != 1:
        return None
    span_start, span_end = matches[0]
    return normalized_content[span_start:span_end].strip()


def _source_span_for_ordered_token_quote(
    quote: str,
    content: str | None,
) -> str | None:
    normalized_quote = _normalize_quote_text(quote)
    normalized_content = _normalize_quote_text(content or "")
    quote_tokens = [
        match.group(0).casefold()
        for match in _QUOTE_TOKEN_PATTERN.finditer(normalized_quote)
    ]
    if len(quote_tokens) < _ORDERED_QUOTE_MIN_TOKENS:
        return None

    content_token_matches = list(_QUOTE_TOKEN_PATTERN.finditer(normalized_content))
    content_tokens = [match.group(0).casefold() for match in content_token_matches]
    max_span_tokens = max(
        len(quote_tokens) + _ORDERED_QUOTE_MAX_EXTRA_TOKENS,
        len(quote_tokens) * _ORDERED_QUOTE_MAX_SPAN_TOKEN_MULTIPLIER,
    )
    spans: list[tuple[int, int, int]] = []

    for start_index, token in enumerate(content_tokens):
        if token != quote_tokens[0]:
            continue

        quote_index = 1
        end_index = start_index
        for content_index in range(start_index + 1, len(content_tokens)):
            if content_tokens[content_index] != quote_tokens[quote_index]:
                continue
            quote_index += 1
            end_index = content_index
            if quote_index == len(quote_tokens):
                break

        if quote_index != len(quote_tokens):
            continue

        span_token_count = end_index - start_index + 1
        span_start = content_token_matches[start_index].start()
        span_end = content_token_matches[end_index].end()
        if span_token_count > max_span_tokens:
            continue
        if span_end - span_start > _ORDERED_QUOTE_MAX_SPAN_CHARS:
            continue
        spans.append((span_token_count, span_start, span_end))

    if not spans:
        return None

    shortest_span_token_count = min(span[0] for span in spans)
    shortest_spans = {
        (span_start, span_end)
        for span_token_count, span_start, span_end in spans
        if span_token_count == shortest_span_token_count
    }
    if len(shortest_spans) != 1:
        return None

    span_start, span_end = next(iter(shortest_spans))
    return normalized_content[span_start:span_end].strip()


def _canonical_source_quote_for_candidate(
    quote: str,
    content: str | None,
) -> str | None:
    if _quote_matches_candidate_content(quote, content):
        return quote

    canonical_quote = _source_span_for_ellipsized_quote(quote, content)
    if canonical_quote is not None:
        return canonical_quote

    canonical_quote = _source_span_for_token_sequence_quote(quote, content)
    if canonical_quote is not None:
        return canonical_quote

    return _source_span_for_ordered_token_quote(quote, content)


def _normalize_quote_text(value: str) -> str:
    text = " ".join(value.split())
    # Normalize curly double quotes, curly single quotes, and straight double quotes to straight single quotes
    text = text.replace("“", "'").replace("”", "'").replace("„", "'").replace("‟", "'")
    text = text.replace("‘", "'").replace("’", "'").replace("‚", "'").replace("‛", "'")
    text = text.replace('"', "'")
    return text


def _quote_matches_candidate_content(quote: str, content: str | None) -> bool:
    normalized_quote = _normalize_quote_text(quote).lower()
    normalized_content = _normalize_quote_text(content or "").lower()
    if not normalized_quote:
        return False
    if normalized_quote in normalized_content:
        return True

    quote_without_terminal_punctuation = re.sub(
        r"[.,:;!?]+(?='?$)",
        "",
        normalized_quote,
    )
    return (
        quote_without_terminal_punctuation != normalized_quote
        and quote_without_terminal_punctuation in normalized_content
    )


def _question_needs_explanatory_context(question: str) -> bool:
    return bool(_EXPLANATORY_QUESTION_PATTERN.search(question))


def _expanded_quote_with_surrounding_context(
    quote: str,
    content: str | None,
) -> str | None:
    normalized_quote = _normalize_quote_text(quote)
    normalized_content = _normalize_quote_text(content or "")
    if not normalized_quote or normalized_quote not in normalized_content:
        return None

    quote_start = normalized_content.find(normalized_quote)
    quote_end = quote_start + len(normalized_quote)
    sentence_spans = _sentence_spans(normalized_content)

    overlapping_sentence_indexes = _overlapping_sentence_indexes(
        sentence_spans,
        quote_start,
        quote_end,
    )
    if not overlapping_sentence_indexes:
        return None

    start_index = max(0, overlapping_sentence_indexes[0] - 1)
    end_index = overlapping_sentence_indexes[-1] + 1
    expanded_quote = _normalize_quote_text(
        " ".join(
            sentence
            for _sentence_start, _sentence_end, sentence in sentence_spans[
                start_index:end_index
            ]
        )
    )
    if expanded_quote == normalized_quote:
        return None
    return expanded_quote


def _expanded_quotes_with_surrounding_context(
    quote: str,
    content: str | None,
) -> list[str] | None:
    normalized_quote = _normalize_quote_text(quote)
    normalized_content = _normalize_quote_text(content or "")
    if not normalized_quote or normalized_quote not in normalized_content:
        return None

    quote_start = normalized_content.find(normalized_quote)
    quote_end = quote_start + len(normalized_quote)
    sentence_spans = _sentence_spans(normalized_content)
    overlapping_sentence_indexes = _overlapping_sentence_indexes(
        sentence_spans,
        quote_start,
        quote_end,
    )
    if not overlapping_sentence_indexes:
        return None

    quotes: list[str] = []
    previous_index = overlapping_sentence_indexes[0] - 1
    if previous_index >= 0:
        context_quote = _trim_preceding_context_sentence(
            sentence_spans[previous_index][2]
        )
        if (
            context_quote
            and context_quote != normalized_quote
            and context_quote in normalized_content
        ):
            quotes.append(context_quote)

    if normalized_quote not in {_normalize_quote_text(value) for value in quotes}:
        quotes.append(normalized_quote)

    if len(quotes) <= 1:
        return None
    return quotes


def _sentence_spans(
    normalized_content: str,
) -> list[tuple[int, int, str]]:
    sentence_spans: list[tuple[int, int, str]] = []
    sentence_start = 0
    for boundary in _SENTENCE_BOUNDARY_PATTERN.finditer(normalized_content):
        sentence_end = boundary.start() + len(boundary.group("closing_quote"))
        raw_sentence = normalized_content[sentence_start:sentence_end]
        sentence = raw_sentence.strip()
        if sentence:
            leading_trim = len(raw_sentence) - len(raw_sentence.lstrip())
            trailing_trim = len(raw_sentence) - len(raw_sentence.rstrip())
            sentence_spans.append(
                (
                    sentence_start + leading_trim,
                    sentence_end - trailing_trim,
                    sentence,
                )
            )
        sentence_start = boundary.end()

    raw_sentence = normalized_content[sentence_start:]
    sentence = raw_sentence.strip()
    if sentence:
        leading_trim = len(raw_sentence) - len(raw_sentence.lstrip())
        trailing_trim = len(raw_sentence) - len(raw_sentence.rstrip())
        sentence_spans.append(
            (
                sentence_start + leading_trim,
                len(normalized_content) - trailing_trim,
                sentence,
            )
        )

    return sentence_spans


def _overlapping_sentence_indexes(
    sentence_spans: list[tuple[int, int, str]],
    quote_start: int,
    quote_end: int,
) -> list[int]:
    return [
        index
        for index, (sentence_start, sentence_end, _sentence) in enumerate(
            sentence_spans
        )
        if sentence_start < quote_end and quote_start < sentence_end
    ]


def _trim_preceding_context_sentence(sentence: str) -> str:
    leading_clause, separator, _remaining = sentence.partition(";")
    if separator and len(leading_clause.split()) >= 6:
        return f"{leading_clause.strip()};"
    return sentence


def _candidate_source_excerpt(content: str | None) -> str | None:
    excerpt = (content or "").strip()
    return excerpt or None


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
        return verified_chunk.model_copy(update={"quote": canonical_quote})

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
        validated_output = VerificationAgentOutput.model_validate(output_payload)
    except ValidationError as exc:
        logger.warning("Verification post-processing returned invalid output schema.")
        raise _VerificationAgentFailure("post_processing_validation_error") from exc

    if (
        validated_output.verified_chunks
        and not validated_output.missing_information
        and validated_output.confidence < ANSWERABLE_EVIDENCE_CONFIDENCE_FLOOR
    ):
        return validated_output.model_copy(
            update={"confidence": ANSWERABLE_EVIDENCE_CONFIDENCE_FLOOR}
        )

    return validated_output


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
    "ANSWERABLE_EVIDENCE_CONFIDENCE_FLOOR",
    "VerificationAgentError",
    "run_verification_agent",
]
