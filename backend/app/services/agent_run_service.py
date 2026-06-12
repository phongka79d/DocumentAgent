from collections.abc import Sequence
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.agents.schemas import VerificationAgentOutput
from app.agents.verification_agent import (
    AGENT_2_VERIFICATION_STEP_NAME,
    VERIFICATION_AGENT_NAME,
)
from app.schemas.agent_runs import (
    AgentRunEvidenceResponse,
    AgentRunLogsResponse,
    AgentRunLogStepResponse,
)
from app.services import supabase_service


SAFE_AGENT_RUN_FAILURE_MESSAGE = "Agent run failed. Please try again later."
SAFE_AGENT_RUN_PERSISTENCE_MESSAGE = "Agent run persistence is temporarily unavailable."
SAFE_AGENT_RUN_EVIDENCE_MESSAGE = "Agent run evidence is temporarily unavailable."
SAFE_AGENT_RUN_LOGS_MESSAGE = "Agent run logs are temporarily unavailable."


class AgentRunServiceError(RuntimeError):
    """Base class for controlled agent run service failures."""

    def __init__(self, public_message: str) -> None:
        self.public_message = public_message
        super().__init__(public_message)


class AgentRunNotFoundError(AgentRunServiceError, LookupError):
    """Raised when an agent run is not owned by the configured user."""

    def __init__(self) -> None:
        super().__init__("Agent run not found.")


class AgentRunSessionNotFoundError(AgentRunServiceError, LookupError):
    """Raised when a run session is not owned by the configured user."""

    def __init__(self) -> None:
        super().__init__("Chat session not found.")


class AgentRunStepNotFoundError(AgentRunServiceError, LookupError):
    """Raised when the required persisted agent step is missing."""

    def __init__(self, step_name: str) -> None:
        super().__init__("Agent step not found.")


class AgentRunStepDataError(AgentRunServiceError, ValueError):
    """Raised when persisted agent step data cannot satisfy the API contract."""

    def __init__(self, message: str = "Agent run step data is invalid.") -> None:
        super().__init__(message)


class AgentRunDependencyError(AgentRunServiceError):
    """Raised when persistence dependencies fail behind a safe service boundary."""

    def __init__(self, public_message: str = SAFE_AGENT_RUN_PERSISTENCE_MESSAGE) -> None:
        super().__init__(public_message)


class AgentRunWorkflowError(AgentRunServiceError):
    """Raised when the workflow fails behind a safe service boundary."""

    def __init__(self, error: BaseException | str | None = None) -> None:
        super().__init__(SAFE_AGENT_RUN_FAILURE_MESSAGE)


def _stringify_uuid(value: UUID | str) -> str:
    return str(value)


def _stringify_uuid_list(values: Sequence[UUID | str]) -> list[str]:
    return [_stringify_uuid(value) for value in values]


def _dependency_failure(
    exc: Exception,
    *,
    public_message: str = SAFE_AGENT_RUN_PERSISTENCE_MESSAGE,
) -> AgentRunDependencyError:
    return AgentRunDependencyError(public_message)


def _safe_error_message(error: BaseException | str | None) -> str:
    return SAFE_AGENT_RUN_FAILURE_MESSAGE


def create_running_agent_run(
    *,
    session_id: UUID | str | None,
    question: str,
    document_ids: Sequence[UUID | str],
) -> dict[str, Any]:
    resolved_session_id = None if session_id is None else str(session_id)
    try:
        if resolved_session_id is not None:
            session = supabase_service.get_chat_session(resolved_session_id)
            if session is None:
                raise AgentRunSessionNotFoundError()
        return supabase_service.create_agent_run(
            session_id=resolved_session_id,
            question=question,
            selected_document_ids=_stringify_uuid_list(document_ids),
        )
    except AgentRunSessionNotFoundError:
        raise
    except Exception as exc:
        raise _dependency_failure(exc) from exc


def mark_agent_run_success(
    agent_run_id: UUID | str,
    *,
    final_answer: str,
    confidence: float,
) -> dict[str, Any]:
    try:
        return supabase_service.update_agent_run_success(
            str(agent_run_id),
            final_answer=final_answer,
            confidence=confidence,
        )
    except Exception as exc:
        raise _dependency_failure(exc) from exc


def mark_agent_run_failed(
    agent_run_id: UUID | str,
    *,
    error: BaseException | str | None = None,
) -> dict[str, Any]:
    try:
        return supabase_service.update_agent_run_failure(
            str(agent_run_id),
            error_message=_safe_error_message(error),
        )
    except Exception as exc:
        raise _dependency_failure(exc) from exc


def _get_owned_agent_run(
    agent_run_id: UUID | str,
    *,
    dependency_message: str = SAFE_AGENT_RUN_PERSISTENCE_MESSAGE,
) -> dict[str, Any]:
    try:
        agent_run = supabase_service.get_agent_run(str(agent_run_id))
    except Exception as exc:
        raise _dependency_failure(exc, public_message=dependency_message) from exc

    if agent_run is None:
        raise AgentRunNotFoundError()

    return agent_run


def _list_steps_for_owned_run(
    agent_run_id: UUID | str,
    *,
    dependency_message: str,
) -> list[dict[str, Any]]:
    _get_owned_agent_run(agent_run_id, dependency_message=dependency_message)
    try:
        return supabase_service.list_agent_steps_for_run(str(agent_run_id))
    except Exception as exc:
        raise _dependency_failure(exc, public_message=dependency_message) from exc


def _is_agent_2_verification_step(step: dict[str, Any]) -> bool:
    return (
        step.get("step_name") == AGENT_2_VERIFICATION_STEP_NAME
        or step.get("agent_name") == VERIFICATION_AGENT_NAME
    )


def _agent_2_output_payload(step: dict[str, Any]) -> dict[str, Any]:
    output_payload = step.get("output_payload")
    if not isinstance(output_payload, dict):
        raise AgentRunStepDataError("Agent 2 output payload is invalid.")
    return output_payload


def get_agent_run_evidence(agent_run_id: UUID | str) -> AgentRunEvidenceResponse:
    steps = _list_steps_for_owned_run(
        agent_run_id,
        dependency_message=SAFE_AGENT_RUN_EVIDENCE_MESSAGE,
    )
    agent_2_step = next(
        (step for step in steps if _is_agent_2_verification_step(step)),
        None,
    )
    if agent_2_step is None:
        raise AgentRunStepNotFoundError(AGENT_2_VERIFICATION_STEP_NAME)

    try:
        verification_output = VerificationAgentOutput.model_validate(
            _agent_2_output_payload(agent_2_step)
        )
        return AgentRunEvidenceResponse(
            verified_chunks=verification_output.verified_chunks,
            rejected_chunks=verification_output.rejected_chunks,
        )
    except (ValidationError, ValueError) as exc:
        raise AgentRunStepDataError("Agent 2 output payload is invalid.") from exc


def _log_step_response(step: dict[str, Any]) -> AgentRunLogStepResponse:
    try:
        return AgentRunLogStepResponse(
            agent_name=step["agent_name"],
            input=step.get("input") or {},
            output=step.get("output") or {},
            status=step["status"],
            created_at=step["created_at"],
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise AgentRunStepDataError("Agent step log payload is invalid.") from exc


def get_agent_run_logs(agent_run_id: UUID | str) -> AgentRunLogsResponse:
    steps = _list_steps_for_owned_run(
        agent_run_id,
        dependency_message=SAFE_AGENT_RUN_LOGS_MESSAGE,
    )
    return AgentRunLogsResponse(
        agent_run_id=agent_run_id,
        steps=[_log_step_response(step) for step in steps],
    )


__all__ = [
    "SAFE_AGENT_RUN_FAILURE_MESSAGE",
    "SAFE_AGENT_RUN_EVIDENCE_MESSAGE",
    "SAFE_AGENT_RUN_LOGS_MESSAGE",
    "SAFE_AGENT_RUN_PERSISTENCE_MESSAGE",
    "AgentRunDependencyError",
    "AgentRunNotFoundError",
    "AgentRunSessionNotFoundError",
    "AgentRunServiceError",
    "AgentRunStepDataError",
    "AgentRunStepNotFoundError",
    "AgentRunWorkflowError",
    "create_running_agent_run",
    "get_agent_run_evidence",
    "get_agent_run_logs",
    "mark_agent_run_failed",
    "mark_agent_run_success",
]
