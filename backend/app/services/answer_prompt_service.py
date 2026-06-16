import json
from typing import Any

from app.agents.prompts import (
    ANSWER_GENERATION_SYSTEM_PROMPT,
    ANSWER_GROUNDING_SYSTEM_PROMPT,
)
from app.agents.schemas import (
    AnswerAgentInput,
    AnswerAgentOutput,
    VerificationAgentOutput,
)


REJECTED_SELF_CHECK_MAX_CHUNKS = 3


def build_answer_generation_payload(
    answer_input: AnswerAgentInput,
    retry_instruction: str | None = None,
) -> dict[str, Any]:
    """Build the compact provider payload from verified evidence only."""
    payload = {
        "response_instruction": "Return only valid JSON.",
        "question": answer_input.question,
        "verified_chunks": answer_evidence_payload(answer_input.verification),
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
        "verified_chunks": answer_evidence_payload(verification),
        "rejected_chunks": rejected_evidence_payload(verification, output),
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


def answer_evidence_payload(
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


def rejected_evidence_payload(
    verification: VerificationAgentOutput,
    output: AnswerAgentOutput | None = None,
) -> list[dict[str, Any]]:
    if output is None:
        rejected_chunks = verification.rejected_chunks
    else:
        draft_text = _normalized_draft_visible_text(output)
        rejected_chunks = [
            chunk
            for chunk in verification.rejected_chunks
            if _normalize_text(chunk.quote) in draft_text
            or _normalize_text(f"{chunk.file_name or ''} {chunk.quote}") in draft_text
        ][:REJECTED_SELF_CHECK_MAX_CHUNKS]

    return [
        {
            "file_name": chunk.file_name,
            "quote": chunk.quote,
        }
        for chunk in rejected_chunks
    ]


def _normalized_draft_visible_text(output: AnswerAgentOutput) -> str:
    citation_text = " ".join(
        f"{citation.file_name} {citation.quote}" for citation in output.citations
    )
    return _normalize_text(
        " ".join(
            [
                output.final_answer,
                output.reasoning_summary,
                citation_text,
            ]
        )
    )


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


__all__ = [
    "answer_evidence_payload",
    "build_answer_generation_messages",
    "build_answer_generation_payload",
    "build_answer_self_check_messages",
    "build_answer_self_check_payload",
    "REJECTED_SELF_CHECK_MAX_CHUNKS",
    "rejected_evidence_payload",
]
