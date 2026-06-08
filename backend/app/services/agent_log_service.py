from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import logging
from typing import Any

from pydantic import BaseModel, TypeAdapter

from app.services.supabase_service import insert_agent_step_log

logger = logging.getLogger(__name__)


AGENT_1_RETRIEVAL_STEP_NAME = "agent_1_retrieval"
RETRIEVAL_AGENT_NAME = "retrieval_agent"
VALID_AGENT_STEP_STATUSES = frozenset({"success", "failed"})


class AgentLogValidationError(ValueError):
    """Raised when an agent step log request is invalid."""


class AgentLogPersistenceError(RuntimeError):
    """Raised when agent step persistence fails."""

    def __init__(
        self,
        *,
        step_name: str,
        agent_name: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        self.step_name = step_name
        self.agent_name = agent_name
        self.status = status
        self.error_message = error_message
        super().__init__(
            f"failed to persist agent step log for {agent_name}::{step_name} [{status}]"
        )


@dataclass(frozen=True)
class AgentStepLogAttempt:
    """Non-fatal result for callers that must preserve retrieval outcomes."""

    persisted: bool
    row: dict | None = None
    persistence_error: AgentLogPersistenceError | None = None


def log_agent_step(
    agent_run_id: str,
    step_name: str,
    agent_name: str,
    input_payload: BaseModel | Mapping[str, Any],
    output_payload: BaseModel | Mapping[str, Any],
    status: str,
    error_message: str | None = None,
) -> dict:
    if status not in VALID_AGENT_STEP_STATUSES:
        allowed_statuses = ", ".join(sorted(VALID_AGENT_STEP_STATUSES))
        raise AgentLogValidationError(
            f"agent step status must be one of: {allowed_statuses}"
        )

    serialized_input = _json_compatible_dict(input_payload, "input_payload")
    serialized_output = _json_compatible_dict(output_payload, "output_payload")

    try:
        return insert_agent_step_log(
            agent_run_id=str(agent_run_id),
            step_name=step_name,
            agent_name=agent_name,
            input_payload=serialized_input,
            output_payload=serialized_output,
            status=status,
            error_message=error_message,
        )
    except Exception as exc:
        logger.exception(
            "Agent step log persistence failed for %s::%s [%s]",
            agent_name,
            step_name,
            status,
        )
        raise AgentLogPersistenceError(
            step_name=step_name,
            agent_name=agent_name,
            status=status,
            error_message=error_message,
        ) from exc


def try_log_agent_step(
    agent_run_id: str,
    step_name: str,
    agent_name: str,
    input_payload: BaseModel | Mapping[str, Any],
    output_payload: BaseModel | Mapping[str, Any],
    status: str,
    error_message: str | None = None,
) -> AgentStepLogAttempt:
    """Persist a step log without letting insert failure replace retrieval outcome.

    Retrieval callers should inspect the returned attempt. A failed attempt has
    already been logged by `log_agent_step`; successful retrieval output or the
    original retrieval exception should continue to be returned or raised.
    """

    try:
        row = log_agent_step(
            agent_run_id=agent_run_id,
            step_name=step_name,
            agent_name=agent_name,
            input_payload=input_payload,
            output_payload=output_payload,
            status=status,
            error_message=error_message,
        )
    except AgentLogPersistenceError as exc:
        return AgentStepLogAttempt(
            persisted=False,
            row=None,
            persistence_error=exc,
        )

    return AgentStepLogAttempt(
        persisted=True,
        row=row,
        persistence_error=None,
    )


def _json_compatible_dict(
    payload: BaseModel | Mapping[str, Any],
    field_name: str,
) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        payload_data = payload.model_dump(mode="json")
    elif isinstance(payload, Mapping):
        payload_data = deepcopy(dict(payload))
    else:
        raise AgentLogValidationError(
            f"{field_name} must be a dictionary or Pydantic model"
        )

    serialized_payload = TypeAdapter(dict[str, Any]).dump_python(
        payload_data,
        mode="json",
    )
    if not isinstance(serialized_payload, dict):
        raise AgentLogValidationError(f"{field_name} must serialize to a dictionary")

    return serialized_payload


__all__ = [
    "AGENT_1_RETRIEVAL_STEP_NAME",
    "AgentLogValidationError",
    "AgentLogPersistenceError",
    "AgentStepLogAttempt",
    "RETRIEVAL_AGENT_NAME",
    "log_agent_step",
    "try_log_agent_step",
]
