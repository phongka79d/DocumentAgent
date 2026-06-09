import json
from collections.abc import Mapping
import logging
from typing import Any

from pydantic import ValidationError

from app.agents.prompts import VERIFICATION_AGENT_SYSTEM_PROMPT
from app.agents.schemas import VerificationAgentInput, VerificationAgentOutput
from app.services import shopaikey_service


logger = logging.getLogger(__name__)

AGENT_2_VERIFICATION_STEP_NAME = "agent_2_verification"
VERIFICATION_AGENT_NAME = "verification_agent"
VERIFICATION_FAILURE_MESSAGE = "Verification failed. Please try again later."


class VerificationAgentError(RuntimeError):
    """Raised when Agent 2 verification fails in a controlled way."""


def _build_compact_evidence_payload(
    input_data: VerificationAgentInput,
) -> dict[str, Any]:
    return {
        "question": input_data.question,
        "evidence": [
            {
                "chunk_id": str(candidate.chunk_id),
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
        raise VerificationAgentError(VERIFICATION_FAILURE_MESSAGE) from exc

    try:
        return VerificationAgentOutput.model_validate(response_payload)
    except ValidationError as exc:
        logger.warning("Verification LLM returned invalid output schema.")
        raise VerificationAgentError(VERIFICATION_FAILURE_MESSAGE) from exc


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
        return VerificationAgentOutput(
            verified_chunks=[],
            rejected_chunks=[],
            missing_information=True,
            confidence=0.0,
        )

    messages = _build_verification_messages(validated_input)
    try:
        response_content = shopaikey_service.chat_completion(
            messages,
            response_format={"type": "json_object"},
        )
    except shopaikey_service.ShopAIKeyServiceError as exc:
        raise VerificationAgentError(VERIFICATION_FAILURE_MESSAGE) from exc

    return _parse_verification_output(response_content)


__all__ = [
    "AGENT_2_VERIFICATION_STEP_NAME",
    "VERIFICATION_AGENT_NAME",
    "VERIFICATION_FAILURE_MESSAGE",
    "VerificationAgentError",
    "run_verification_agent",
]
