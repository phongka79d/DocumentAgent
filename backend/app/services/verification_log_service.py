from typing import Any

from app.agents.schemas import RetrievalCandidate, VerificationAgentInput


VERIFICATION_LOG_CONTENT_PREVIEW_CHARS = 500


def build_verification_log_input(
    validated_input: VerificationAgentInput,
) -> dict[str, Any]:
    return {
        "agent_run_id": str(validated_input.agent_run_id),
        "question": validated_input.question,
        "candidates": [
            build_verification_log_candidate(candidate)
            for candidate in validated_input.candidates
        ],
    }


def build_verification_log_candidate(
    candidate: RetrievalCandidate,
) -> dict[str, Any]:
    payload = candidate.model_dump(mode="json", exclude={"content"})
    content = candidate.content or ""
    payload["content_preview"] = content[:VERIFICATION_LOG_CONTENT_PREVIEW_CHARS] or None
    payload["content_char_count"] = len(content)
    payload["content_omitted"] = len(content) > VERIFICATION_LOG_CONTENT_PREVIEW_CHARS
    return payload


def build_safe_failed_verification_input(
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


def build_safe_failed_verification_output(
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
    "VERIFICATION_LOG_CONTENT_PREVIEW_CHARS",
    "build_safe_failed_verification_input",
    "build_safe_failed_verification_output",
    "build_verification_log_candidate",
    "build_verification_log_input",
]
