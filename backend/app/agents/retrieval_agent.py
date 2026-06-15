from collections.abc import Mapping
import logging
from typing import Any

from app.agents.schemas import RetrievalAgentInput, RetrievalAgentOutput, RetrievalCandidate
from app.core.config import get_settings
from app.schemas.retrieval import HybridRetrievalCandidate
from app.services import (
    agent_log_service,
    hybrid_retrieval_service,
    retrieval_context_service,
)


logger = logging.getLogger(__name__)

AGENT_1_RETRIEVAL_STEP_NAME = "agent_1_retrieval"
RETRIEVAL_AGENT_NAME = "retrieval_agent"
RETRIEVAL_FAILURE_MESSAGE = "Retrieval failed. Please try again later."


class RetrievalAgentError(RuntimeError):
    """Raised when Agent 1 retrieval fails in a controlled way."""


def run_retrieval_agent(
    input_data: RetrievalAgentInput | Mapping[str, Any],
) -> RetrievalAgentOutput:
    """Validate Agent 1 input, call hybrid retrieval, and log success."""

    validated_input = RetrievalAgentInput.model_validate(input_data)
    settings = get_settings()
    try:
        hybrid_response = hybrid_retrieval_service.retrieve_hybrid(
            validated_input.question,
            validated_input.document_ids,
            settings.retrieval_final_top_k,
        )
        expanded_candidates = retrieval_context_service.expand_retrieval_context(
            validated_input.question,
            hybrid_response.candidates,
            context_window=settings.retrieval_context_window,
            max_context_candidates=settings.retrieval_context_max_candidates,
        )
    except Exception:
        _log_failed_retrieval(validated_input)
        raise RetrievalAgentError(RETRIEVAL_FAILURE_MESSAGE) from None

    validated_output = RetrievalAgentOutput.model_validate(
        {
            "question": hybrid_response.question,
            "candidates": [
                _to_agent_candidate(candidate) for candidate in expanded_candidates
            ],
        }
    )

    agent_log_service.log_agent_step(
        agent_run_id=str(validated_input.agent_run_id),
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        input_payload=validated_input,
        output_payload=validated_output,
        status="success",
    )

    return validated_output


def _log_failed_retrieval(validated_input: RetrievalAgentInput) -> None:
    log_attempt = agent_log_service.try_log_agent_step(
        agent_run_id=str(validated_input.agent_run_id),
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        input_payload=validated_input,
        output_payload={},
        status="failed",
        error_message=RETRIEVAL_FAILURE_MESSAGE,
    )

    if not log_attempt.persisted:
        logger.error(
            "Failed to persist retrieval failure agent step log for %s::%s",
            RETRIEVAL_AGENT_NAME,
            AGENT_1_RETRIEVAL_STEP_NAME,
        )


def _to_agent_candidate(candidate: HybridRetrievalCandidate) -> RetrievalCandidate:
    return RetrievalCandidate.model_validate(
        candidate.model_dump(include=RetrievalCandidate.model_fields.keys())
    )


__all__ = [
    "AGENT_1_RETRIEVAL_STEP_NAME",
    "RETRIEVAL_AGENT_NAME",
    "RETRIEVAL_FAILURE_MESSAGE",
    "RetrievalAgentError",
    "run_retrieval_agent",
]
