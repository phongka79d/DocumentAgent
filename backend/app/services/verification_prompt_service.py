import json
from typing import Any

from app.agents.prompts import (
    EVIDENCE_COVERAGE_SYSTEM_PROMPT,
    VERIFICATION_AGENT_SYSTEM_PROMPT,
)
from app.agents.schemas import RetrievalCandidate, VerificationAgentInput
from app.services.evidence_payload_optimizer import optimize_candidates_for_verification


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
VERIFICATION_RETRY_INSTRUCTION = """
The previous verification response failed validation with category:
{failure_type}.
Return one corrected JSON object only.

Use only chunk_id and document_id values that appear in the compact evidence
payload. Do not invent IDs, documents, quotes, or metadata. Keep quotes copied
from candidate content, and keep the exact Agent 2 response schema.
""".strip()
INVALID_RESPONSE_RETRY_PREVIEW_CHARS = 2000


def build_compact_evidence_payload(
    input_data: VerificationAgentInput,
    candidates: list[RetrievalCandidate] | None = None,
) -> dict[str, Any]:
    payload_candidates = candidates if candidates is not None else input_data.candidates
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
            for candidate in payload_candidates
        ],
    }


def compact_candidates_for_llm(
    *,
    question: str,
    candidates: list[RetrievalCandidate],
    max_candidates: int,
    snippet_max_chars: int,
    context_sentences: int,
) -> list[RetrievalCandidate]:
    return optimize_candidates_for_verification(
        question=question,
        candidates=candidates,
        max_candidates=max_candidates,
        snippet_max_chars=snippet_max_chars,
        context_sentences=context_sentences,
    )


def build_verification_messages(
    input_data: VerificationAgentInput,
    *,
    max_candidates: int,
    snippet_max_chars: int,
    context_sentences: int,
) -> list[dict[str, str]]:
    compact_candidates = compact_candidates_for_llm(
        question=input_data.question,
        candidates=input_data.candidates,
        max_candidates=max_candidates,
        snippet_max_chars=snippet_max_chars,
        context_sentences=context_sentences,
    )
    compact_payload = build_compact_evidence_payload(input_data, compact_candidates)
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
                f"{json.dumps(compact_payload, ensure_ascii=False, separators=(',', ':'))}"
            ),
        },
    ]


def build_verification_retry_messages(
    input_data: VerificationAgentInput,
    *,
    failure_type: str,
    max_candidates: int,
    snippet_max_chars: int,
    context_sentences: int,
) -> list[dict[str, str]]:
    return [
        *build_verification_messages(
            input_data,
            max_candidates=max_candidates,
            snippet_max_chars=snippet_max_chars,
            context_sentences=context_sentences,
        ),
        {
            "role": "user",
            "content": VERIFICATION_RETRY_INSTRUCTION.format(
                failure_type=failure_type
            ),
        },
    ]


def build_coverage_messages(
    input_data: VerificationAgentInput,
    *,
    max_candidates: int,
    snippet_max_chars: int,
    context_sentences: int,
) -> list[dict[str, str]]:
    compact_candidates = compact_candidates_for_llm(
        question=input_data.question,
        candidates=input_data.candidates,
        max_candidates=max_candidates,
        snippet_max_chars=snippet_max_chars,
        context_sentences=context_sentences,
    )
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
            for candidate in compact_candidates
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


def build_coverage_retry_messages(
    input_data: VerificationAgentInput,
    *,
    invalid_response: str,
    failure_type: str,
    max_candidates: int,
    snippet_max_chars: int,
    context_sentences: int,
) -> list[dict[str, str]]:
    return [
        *build_coverage_messages(
            input_data,
            max_candidates=max_candidates,
            snippet_max_chars=snippet_max_chars,
            context_sentences=context_sentences,
        ),
        {
            "role": "assistant",
            "content": compact_invalid_response_for_retry(invalid_response),
        },
        {
            "role": "user",
            "content": COVERAGE_RETRY_INSTRUCTION.format(
                failure_type=failure_type
            ),
        },
    ]


def compact_invalid_response_for_retry(invalid_response: str) -> str:
    if len(invalid_response) <= INVALID_RESPONSE_RETRY_PREVIEW_CHARS:
        return invalid_response

    omitted_chars = len(invalid_response) - INVALID_RESPONSE_RETRY_PREVIEW_CHARS
    return (
        invalid_response[:INVALID_RESPONSE_RETRY_PREVIEW_CHARS].rstrip()
        + f"\n[truncated invalid response: {omitted_chars} chars omitted]"
    )


__all__ = [
    "COVERAGE_RETRY_INSTRUCTION",
    "INVALID_RESPONSE_RETRY_PREVIEW_CHARS",
    "VERIFICATION_RETRY_INSTRUCTION",
    "build_compact_evidence_payload",
    "build_coverage_messages",
    "build_coverage_retry_messages",
    "build_verification_messages",
    "build_verification_retry_messages",
    "compact_candidates_for_llm",
    "compact_invalid_response_for_retry",
]
