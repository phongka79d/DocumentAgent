import sys
from pathlib import Path
from uuid import UUID
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.schemas import RetrievalAgentInput, RetrievalAgentOutput
from app.services import agent_log_service
from app.services.agent_log_service import (
    AGENT_1_RETRIEVAL_STEP_NAME,
    RETRIEVAL_AGENT_NAME,
    AgentStepLogAttempt,
    AgentLogValidationError,
    AgentLogPersistenceError,
)


def test_log_agent_step_writes_success_row_from_pydantic_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_agent_step_log = Mock(return_value={"id": "step-id"})
    monkeypatch.setattr(
        agent_log_service,
        "insert_agent_step_log",
        insert_agent_step_log,
    )

    agent_input = RetrievalAgentInput(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        question="  When can I start?  ",
        document_ids=["22222222-2222-2222-2222-222222222222"],
    )
    agent_output = RetrievalAgentOutput(
        question="When can I start?",
        candidates=[],
    )

    result = agent_log_service.log_agent_step(
        agent_run_id=str(agent_input.agent_run_id),
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        input_payload=agent_input,
        output_payload=agent_output,
        status="success",
    )

    assert result == {"id": "step-id"}
    insert_agent_step_log.assert_called_once_with(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        step_name="agent_1_retrieval",
        agent_name="retrieval_agent",
        input_payload={
            "agent_run_id": "11111111-1111-1111-1111-111111111111",
            "question": "When can I start?",
            "document_ids": ["22222222-2222-2222-2222-222222222222"],
        },
        output_payload={
            "question": "When can I start?",
            "candidates": [],
        },
        status="success",
        error_message=None,
    )


def test_log_agent_step_writes_failed_row_from_dict_payloads_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_agent_step_log = Mock(return_value={"id": "failed-step-id"})
    monkeypatch.setattr(
        agent_log_service,
        "insert_agent_step_log",
        insert_agent_step_log,
    )
    input_payload = {
        "question": "When can I start?",
        "document_ids": [UUID("22222222-2222-2222-2222-222222222222")],
    }
    output_payload = {"candidates": []}

    result = agent_log_service.log_agent_step(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        input_payload=input_payload,
        output_payload=output_payload,
        status="failed",
        error_message="Hybrid retrieval failed.",
    )

    assert result == {"id": "failed-step-id"}
    assert input_payload["document_ids"] == [
        UUID("22222222-2222-2222-2222-222222222222")
    ]
    insert_agent_step_log.assert_called_once_with(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        step_name="agent_1_retrieval",
        agent_name="retrieval_agent",
        input_payload={
            "question": "When can I start?",
            "document_ids": ["22222222-2222-2222-2222-222222222222"],
        },
        output_payload={"candidates": []},
        status="failed",
        error_message="Hybrid retrieval failed.",
    )


def test_log_agent_step_rejects_unknown_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_agent_step_log = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "insert_agent_step_log",
        insert_agent_step_log,
    )

    with pytest.raises(AgentLogValidationError) as exc_info:
        agent_log_service.log_agent_step(
            agent_run_id="11111111-1111-1111-1111-111111111111",
            step_name=AGENT_1_RETRIEVAL_STEP_NAME,
            agent_name=RETRIEVAL_AGENT_NAME,
            input_payload={},
            output_payload={},
            status="running",
        )

    assert "success" in str(exc_info.value)
    assert "failed" in str(exc_info.value)
    insert_agent_step_log.assert_not_called()


def test_log_agent_step_rejects_non_mapping_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_agent_step_log = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "insert_agent_step_log",
        insert_agent_step_log,
    )

    with pytest.raises(AgentLogValidationError):
        agent_log_service.log_agent_step(
            agent_run_id="11111111-1111-1111-1111-111111111111",
            step_name=AGENT_1_RETRIEVAL_STEP_NAME,
            agent_name=RETRIEVAL_AGENT_NAME,
            input_payload=[],
            output_payload={},
            status="success",
        )

    insert_agent_step_log.assert_not_called()


def test_log_agent_step_raises_persistence_error_when_insert_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_agent_step_log = Mock(side_effect=RuntimeError("insert failed"))
    logger_mock = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "insert_agent_step_log",
        insert_agent_step_log,
    )
    monkeypatch.setattr(agent_log_service.logger, "exception", logger_mock)

    with pytest.raises(AgentLogPersistenceError) as exc_info:
        agent_log_service.log_agent_step(
            agent_run_id="11111111-1111-1111-1111-111111111111",
            step_name=AGENT_1_RETRIEVAL_STEP_NAME,
            agent_name=RETRIEVAL_AGENT_NAME,
            input_payload={},
            output_payload={},
            status="failed",
            error_message="Hybrid retrieval failed.",
        )

    assert "agent_1_retrieval" in str(exc_info.value)
    assert exc_info.value.step_name == AGENT_1_RETRIEVAL_STEP_NAME
    assert exc_info.value.agent_name == RETRIEVAL_AGENT_NAME
    assert exc_info.value.status == "failed"
    assert exc_info.value.error_message == "Hybrid retrieval failed."
    logger_mock.assert_called_once()
    insert_agent_step_log.assert_called_once()


def test_try_log_agent_step_returns_persisted_attempt_when_insert_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_agent_step_log = Mock(return_value={"id": "step-id"})
    monkeypatch.setattr(
        agent_log_service,
        "insert_agent_step_log",
        insert_agent_step_log,
    )

    result = agent_log_service.try_log_agent_step(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        input_payload={"question": "When can I start?"},
        output_payload={"candidates": []},
        status="success",
    )

    assert result == AgentStepLogAttempt(
        persisted=True,
        row={"id": "step-id"},
        persistence_error=None,
    )


def test_try_log_agent_step_preserves_success_when_insert_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_agent_step_log = Mock(side_effect=RuntimeError("insert failed"))
    logger_mock = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "insert_agent_step_log",
        insert_agent_step_log,
    )
    monkeypatch.setattr(agent_log_service.logger, "exception", logger_mock)

    result = agent_log_service.try_log_agent_step(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        input_payload={"question": "When can I start?"},
        output_payload={"candidates": []},
        status="success",
    )

    assert result.persisted is False
    assert result.row is None
    assert isinstance(result.persistence_error, AgentLogPersistenceError)
    assert result.persistence_error.status == "success"
    assert result.persistence_error.error_message is None
    logger_mock.assert_called_once()


def test_try_log_agent_step_preserves_original_retrieval_error_when_failed_log_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_agent_step_log = Mock(side_effect=RuntimeError("insert failed"))
    logger_mock = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "insert_agent_step_log",
        insert_agent_step_log,
    )
    monkeypatch.setattr(agent_log_service.logger, "exception", logger_mock)

    result = agent_log_service.try_log_agent_step(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        input_payload={"question": "When can I start?"},
        output_payload={},
        status="failed",
        error_message="Hybrid retrieval failed.",
    )

    assert result.persisted is False
    assert result.row is None
    assert isinstance(result.persistence_error, AgentLogPersistenceError)
    assert result.persistence_error.status == "failed"
    assert result.persistence_error.error_message == "Hybrid retrieval failed."
    assert result.persistence_error.__cause__ is not None
    logger_mock.assert_called_once()
