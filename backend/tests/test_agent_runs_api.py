import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.agent_runs import (
    AgentRunEvidenceResponse,
    AgentRunLogsResponse,
    AgentRunLogStepResponse,
)
from app.services import agent_run_service


AGENT_RUN_ID = UUID("11111111-1111-1111-1111-111111111111")
CHUNK_ID = UUID("22222222-2222-2222-2222-222222222222")
DOCUMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
CREATED_AT = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)


def test_agent_run_service_error_taxonomy_exposes_safe_public_messages() -> None:
    errors = [
        agent_run_service.AgentRunNotFoundError(),
        agent_run_service.AgentRunStepNotFoundError("agent_2_verification"),
        agent_run_service.AgentRunStepDataError(),
        agent_run_service.AgentRunDependencyError(),
        agent_run_service.AgentRunWorkflowError(RuntimeError("raw provider failure")),
    ]

    assert [error.public_message for error in errors] == [
        "Agent run not found.",
        "Agent step not found.",
        "Agent run step data is invalid.",
        "Agent run persistence is temporarily unavailable.",
        "Agent run failed. Please try again later.",
    ]
    assert "provider" not in str(errors[-1]).lower()


def test_agent_run_evidence_response_reuses_agent_2_chunk_shapes() -> None:
    response = AgentRunEvidenceResponse.model_validate(
        {
            "verified_chunks": [
                {
                    "chunk_id": str(CHUNK_ID),
                    "document_id": str(DOCUMENT_ID),
                    "file_name": "contract.pdf",
                    "quote": "Probation starts on June 1, 2026.",
                    "page_number": 3,
                    "verification_reason": "The chunk directly states the date.",
                    "supports_simple_reasoning": True,
                }
            ],
            "rejected_chunks": [
                {
                    "chunk_id": str(CHUNK_ID),
                    "document_id": str(DOCUMENT_ID),
                    "file_name": "contract.pdf",
                    "quote": "The office closes on Fridays.",
                    "rejection_reason": "This does not answer the question.",
                }
            ],
        }
    )

    assert response.model_dump(mode="json") == {
        "verified_chunks": [
            {
                "chunk_id": str(CHUNK_ID),
                "document_id": str(DOCUMENT_ID),
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026.",
                "page_number": 3,
                "verification_reason": "The chunk directly states the date.",
                "supports_simple_reasoning": True,
            }
        ],
        "rejected_chunks": [
            {
                "chunk_id": str(CHUNK_ID),
                "document_id": str(DOCUMENT_ID),
                "file_name": "contract.pdf",
                "quote": "The office closes on Fridays.",
                "rejection_reason": "This does not answer the question.",
            }
        ],
    }


def test_agent_run_evidence_response_requires_verified_and_rejected_chunks() -> None:
    with pytest.raises(ValidationError):
        AgentRunEvidenceResponse.model_validate({"verified_chunks": []})


def test_agent_run_logs_response_matches_plan_12_field_names_and_order() -> None:
    response = AgentRunLogsResponse(
        agent_run_id=AGENT_RUN_ID,
        steps=[
            AgentRunLogStepResponse(
                agent_name="retrieval_agent",
                input={"question": "When does probation start?"},
                output={"candidate_count": 2},
                status="success",
                created_at=CREATED_AT,
            ),
            AgentRunLogStepResponse(
                agent_name="verification_agent",
                input={"candidate_count": 2},
                output={"verified_chunks": [], "rejected_chunks": []},
                status="failed",
                created_at=CREATED_AT,
            ),
        ],
    )

    assert response.model_dump(mode="json") == {
        "agent_run_id": str(AGENT_RUN_ID),
        "steps": [
            {
                "agent_name": "retrieval_agent",
                "input": {"question": "When does probation start?"},
                "output": {"candidate_count": 2},
                "status": "success",
                "created_at": "2026-06-01T10:00:00Z",
            },
            {
                "agent_name": "verification_agent",
                "input": {"candidate_count": 2},
                "output": {"verified_chunks": [], "rejected_chunks": []},
                "status": "failed",
                "created_at": "2026-06-01T10:00:00Z",
            },
        ],
    }


def test_agent_run_log_step_response_rejects_unserializable_payloads() -> None:
    with pytest.raises(ValidationError):
        AgentRunLogStepResponse(
            agent_name="retrieval_agent",
            input={"client": object()},
            output={},
            status="success",
            created_at=CREATED_AT,
        )


def test_agent_run_log_step_response_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        AgentRunLogStepResponse(
            agent_name="retrieval_agent",
            input={},
            output={},
            status="running",
            created_at=CREATED_AT,
        )


def test_agent_run_service_creates_running_run_with_string_document_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_agent_run = Mock(return_value={"id": str(AGENT_RUN_ID), "status": "running"})
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "create_agent_run",
        create_agent_run,
    )

    result = agent_run_service.create_running_agent_run(
        session_id=UUID("44444444-4444-4444-4444-444444444444"),
        question="When does probation start?",
        document_ids=[DOCUMENT_ID],
    )

    assert result == {"id": str(AGENT_RUN_ID), "status": "running"}
    create_agent_run.assert_called_once_with(
        session_id="44444444-4444-4444-4444-444444444444",
        question="When does probation start?",
        selected_document_ids=[str(DOCUMENT_ID)],
    )


def test_agent_run_service_marks_success_and_failure_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update_success = Mock(return_value={"id": str(AGENT_RUN_ID), "status": "success"})
    update_failure = Mock(return_value={"id": str(AGENT_RUN_ID), "status": "failed"})
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "update_agent_run_success",
        update_success,
    )
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "update_agent_run_failure",
        update_failure,
    )

    success = agent_run_service.mark_agent_run_success(
        AGENT_RUN_ID,
        final_answer="Probation starts on June 1, 2026.",
        confidence=0.87,
    )
    failure = agent_run_service.mark_agent_run_failed(
        AGENT_RUN_ID,
        error=RuntimeError("provider secret stack trace"),
    )

    assert success["status"] == "success"
    assert failure["status"] == "failed"
    update_success.assert_called_once_with(
        str(AGENT_RUN_ID),
        final_answer="Probation starts on June 1, 2026.",
        confidence=0.87,
    )
    update_failure.assert_called_once_with(
        str(AGENT_RUN_ID),
        error_message=agent_run_service.SAFE_AGENT_RUN_FAILURE_MESSAGE,
    )


def test_agent_run_service_fetches_agent_2_evidence_from_persisted_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "get_agent_run",
        Mock(return_value={"id": str(AGENT_RUN_ID)}),
    )
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "list_agent_steps_for_run",
        Mock(
            return_value=[
                {
                    "step_name": "agent_1_retrieval",
                    "agent_name": "retrieval_agent",
                    "input_payload": {},
                    "output_payload": {"candidates": [{"quote": "unverified"}]},
                    "status": "success",
                    "created_at": CREATED_AT,
                },
                {
                    "step_name": "agent_2_verification",
                    "agent_name": "verification_agent",
                    "input_payload": {"candidate_count": 1},
                    "output_payload": {
                        "verified_chunks": [
                            {
                                "chunk_id": str(CHUNK_ID),
                                "document_id": str(DOCUMENT_ID),
                                "file_name": "contract.pdf",
                                "quote": "Probation starts on June 1, 2026.",
                                "page_number": 3,
                                "verification_reason": "Direct support.",
                                "supports_simple_reasoning": True,
                            }
                        ],
                        "rejected_chunks": [],
                        "missing_information": False,
                        "confidence": 0.86,
                    },
                    "status": "success",
                    "created_at": CREATED_AT,
                },
            ]
        ),
    )

    evidence = agent_run_service.get_agent_run_evidence(AGENT_RUN_ID)

    assert isinstance(evidence, AgentRunEvidenceResponse)
    assert evidence.model_dump(mode="json") == {
        "verified_chunks": [
            {
                "chunk_id": str(CHUNK_ID),
                "document_id": str(DOCUMENT_ID),
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026.",
                "page_number": 3,
                "verification_reason": "Direct support.",
                "supports_simple_reasoning": True,
            }
        ],
        "rejected_chunks": [],
    }


def test_agent_run_service_fetches_ordered_logs_for_owned_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "get_agent_run",
        Mock(return_value={"id": str(AGENT_RUN_ID)}),
    )
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "list_agent_steps_for_run",
        Mock(
            return_value=[
                {
                    "step_name": "agent_1_retrieval",
                    "agent_name": "retrieval_agent",
                    "input_payload": {"question": "When does probation start?"},
                    "output_payload": {"candidate_count": 1},
                    "status": "success",
                    "created_at": CREATED_AT,
                }
            ]
        ),
    )

    logs = agent_run_service.get_agent_run_logs(AGENT_RUN_ID)

    assert isinstance(logs, AgentRunLogsResponse)
    assert logs.model_dump(mode="json") == {
        "agent_run_id": str(AGENT_RUN_ID),
        "steps": [
            {
                "agent_name": "retrieval_agent",
                "input": {"question": "When does probation start?"},
                "output": {"candidate_count": 1},
                "status": "success",
                "created_at": "2026-06-01T10:00:00Z",
            }
        ],
    }


def test_agent_run_service_raises_controlled_errors_for_lookup_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "get_agent_run",
        Mock(return_value=None),
    )

    with pytest.raises(agent_run_service.AgentRunNotFoundError):
        agent_run_service.get_agent_run_logs(AGENT_RUN_ID)


def test_agent_run_service_wraps_log_query_failure_with_safe_public_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "get_agent_run",
        Mock(return_value={"id": str(AGENT_RUN_ID)}),
    )
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "list_agent_steps_for_run",
        Mock(side_effect=RuntimeError("raw supabase service role key leaked")),
    )

    with pytest.raises(agent_run_service.AgentRunDependencyError) as exc_info:
        agent_run_service.get_agent_run_logs(AGENT_RUN_ID)

    assert (
        exc_info.value.public_message
        == "Agent run logs are temporarily unavailable."
    )
    assert str(exc_info.value) == "Agent run logs are temporarily unavailable."
    assert "service role key" not in str(exc_info.value).lower()


def test_agent_run_service_rejects_invalid_agent_2_step_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "get_agent_run",
        Mock(return_value={"id": str(AGENT_RUN_ID)}),
    )
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "list_agent_steps_for_run",
        Mock(
            return_value=[
                {
                    "step_name": "agent_2_verification",
                    "agent_name": "verification_agent",
                    "input_payload": {},
                    "output_payload": {"verified_chunks": []},
                    "status": "success",
                    "created_at": CREATED_AT,
                }
            ]
        ),
    )

    with pytest.raises(agent_run_service.AgentRunStepDataError):
        agent_run_service.get_agent_run_evidence(AGENT_RUN_ID)


def test_agent_run_service_wraps_persistence_dependency_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_run_service.supabase_service,
        "get_agent_run",
        Mock(side_effect=RuntimeError("database unavailable")),
    )

    with pytest.raises(agent_run_service.AgentRunDependencyError) as exc_info:
        agent_run_service.get_agent_run_logs(AGENT_RUN_ID)

    assert str(exc_info.value) == "Agent run logs are temporarily unavailable."
    assert (
        exc_info.value.public_message
        == "Agent run logs are temporarily unavailable."
    )
