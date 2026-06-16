from typing import Any

from app.agents.schemas import (
    AnswerAgentInput,
    AnswerAgentOutput,
    AnswerGroundingReview,
)


def build_answer_log_input(
    answer_input: AnswerAgentInput,
) -> dict[str, Any]:
    return {
        "agent_run_id": str(answer_input.agent_run_id),
        "question": answer_input.question,
        "missing_information": answer_input.verification.missing_information,
        "verification_confidence": answer_input.verification.confidence,
        "verified_chunk_count": len(answer_input.verification.verified_chunks),
        "rejected_chunk_count": len(answer_input.verification.rejected_chunks),
        "verified_chunk_ids": [
            str(chunk.chunk_id) for chunk in answer_input.verification.verified_chunks
        ],
        "rejected_chunk_ids": [
            str(chunk.chunk_id) for chunk in answer_input.verification.rejected_chunks
        ],
    }


def build_successful_answer_log_output(
    *,
    draft_output: AnswerAgentOutput,
    final_output: AnswerAgentOutput,
    grounding_review: AnswerGroundingReview,
) -> dict[str, Any]:
    return {
        "draft_answer": {
            "final_answer": draft_output.final_answer,
            "citations": [
                citation.model_dump(mode="json") for citation in draft_output.citations
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
    }


def build_insufficient_answer_log_output(
    *,
    output: AnswerAgentOutput,
    failure_type: str,
) -> dict[str, Any]:
    return {
        "final_answer": output.final_answer,
        "citations": [
            citation.model_dump(mode="json") for citation in output.citations
        ],
        "reasoning_summary": output.reasoning_summary,
        "confidence": output.confidence,
        "self_check_result": output.self_check.model_dump(mode="json"),
        "fallback_reason": failure_type,
        "errors": [],
    }


def build_safe_failed_answer_input(
    answer_input: AnswerAgentInput,
) -> dict[str, Any]:
    payload = build_answer_log_input(answer_input)
    payload.pop("missing_information")
    payload.pop("verification_confidence")
    return payload


def build_safe_failed_answer_output(
    *,
    failure_type: str,
    failure_message: str,
) -> dict[str, Any]:
    return {
        "error": {
            "type": failure_type,
            "message": failure_message,
        }
    }


__all__ = [
    "build_answer_log_input",
    "build_insufficient_answer_log_output",
    "build_safe_failed_answer_input",
    "build_safe_failed_answer_output",
    "build_successful_answer_log_output",
]
