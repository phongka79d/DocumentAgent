import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.prompts import (
    VERIFICATION_AGENT_OUTPUT_KEYS,
    VERIFICATION_AGENT_SYSTEM_PROMPT,
)
from app.agents.schemas import VerificationAgentOutput
from app.agents import verification_agent
from app.agents.verification_agent import VerificationAgentError, run_verification_agent
from app.services import agent_log_service


AGENT_RUN_ID = "11111111-1111-1111-1111-111111111111"
CANDIDATE_CHUNK_ID = "22222222-2222-2222-2222-222222222222"
CANDIDATE_DOCUMENT_ID = "33333333-3333-3333-3333-333333333333"
SECOND_CANDIDATE_CHUNK_ID = "44444444-4444-4444-4444-444444444444"


@pytest.fixture(autouse=True)
def _disable_verification_agent_log_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_log_service,
        "log_agent_step",
        Mock(return_value={"id": "step-id"}),
    )


def _verification_output_payload(confidence: float) -> dict[str, object]:
    return {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": confidence,
    }


def _candidate_payload() -> dict[str, object]:
    return {
        "chunk_id": CANDIDATE_CHUNK_ID,
        "document_id": CANDIDATE_DOCUMENT_ID,
        "file_name": "contract.pdf",
        "content": "Probation starts on June 1, 2026 and lasts two months.",
        "page_number": 3,
        "section_title": "Probation",
        "semantic_similarity": 0.88,
        "graph_relevance": 0.72,
        "keyword_overlap": 0.64,
        "metadata_match": 0.5,
        "recency_or_position_score": 0.4,
        "final_score": 0.91,
        "retrieval_reason": "Matched probation date terms.",
    }


def _second_candidate_payload() -> dict[str, object]:
    payload = _candidate_payload()
    payload["chunk_id"] = SECOND_CANDIDATE_CHUNK_ID
    payload["final_score"] = 0.89
    return payload


@pytest.mark.parametrize("confidence", [0.0, 0.42, 1.0])
def test_verification_agent_output_accepts_confidence_within_bounds(
    confidence: float,
) -> None:
    output = VerificationAgentOutput.model_validate(
        _verification_output_payload(confidence)
    )

    assert output.confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_verification_agent_output_rejects_out_of_range_confidence(
    confidence: float,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        VerificationAgentOutput.model_validate(_verification_output_payload(confidence))

    assert "confidence" in str(exc_info.value)


def test_verification_agent_returns_missing_information_without_llm_for_empty_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(side_effect=AssertionError("ShopAIKey must not be called"))

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": "11111111-1111-1111-1111-111111111111",
            "question": "When can I start?",
            "candidates": [],
        }
    )

    assert isinstance(output, VerificationAgentOutput)
    assert output.model_dump() == {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": True,
        "confidence": 0.0,
    }
    chat_completion.assert_not_called()


def test_verification_agent_logs_success_for_empty_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_agent_step = Mock(return_value={"id": "empty-step-id"})
    monkeypatch.setattr(
        agent_log_service,
        "log_agent_step",
        log_agent_step,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When can I start?",
            "candidates": [],
        }
    )

    assert output.model_dump() == {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": True,
        "confidence": 0.0,
    }
    log_agent_step.assert_called_once()
    log_call = log_agent_step.call_args.kwargs
    assert log_call["agent_run_id"] == AGENT_RUN_ID
    assert log_call["step_name"] == verification_agent.AGENT_2_VERIFICATION_STEP_NAME
    assert log_call["agent_name"] == verification_agent.VERIFICATION_AGENT_NAME
    assert log_call["status"] == "success"
    assert log_call["input_payload"].model_dump(mode="json") == {
        "agent_run_id": AGENT_RUN_ID,
        "question": "When can I start?",
        "candidates": [],
    }
    assert log_call["output_payload"].model_dump(mode="json") == {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": True,
        "confidence": 0.0,
    }


def test_verification_agent_calls_shopaikey_with_compact_evidence_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_messages = []
    captured_response_format = None

    def fake_chat_completion(messages, response_format=None):
        nonlocal captured_messages, captured_response_format
        captured_messages = messages
        captured_response_format = response_format
        return '{"verified_chunks":[],"rejected_chunks":[],"missing_information":true,"confidence":0.0}'

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert output == VerificationAgentOutput(
        verified_chunks=[],
        rejected_chunks=[],
        missing_information=True,
        confidence=0.0,
    )

    assert captured_response_format == {"type": "json_object"}
    assert [message["role"] for message in captured_messages] == ["system", "user"]
    assert captured_messages[0]["content"] == VERIFICATION_AGENT_SYSTEM_PROMPT

    user_payload = captured_messages[1]["content"]
    assert "When does probation start?" in user_payload
    assert CANDIDATE_CHUNK_ID in user_payload
    assert CANDIDATE_DOCUMENT_ID not in user_payload
    assert "contract.pdf" in user_payload
    assert '"page_number": 3' in user_payload
    assert '"section_title": "Probation"' in user_payload
    assert '"score": 0.91' in user_payload
    assert "Probation starts on June 1, 2026 and lasts two months." in user_payload
    assert "semantic_similarity" not in user_payload
    assert "retrieval_reason" not in user_payload


def test_verification_agent_returns_validated_llm_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start and duration.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert isinstance(output, VerificationAgentOutput)
    assert output.confidence == 0.82
    assert output.missing_information is False
    assert output.verified_chunks[0].chunk_id.hex == CANDIDATE_CHUNK_ID.replace("-", "")


def test_verification_agent_accepts_direct_answer_and_rejects_weak_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct_candidate = _candidate_payload()
    direct_candidate["content"] = (
        "The official work start date is August 1, 2026 after the employee "
        "completes a two-month probation period."
    )
    weak_candidate = _second_candidate_payload()
    weak_candidate["content"] = (
        "Employees should follow office etiquette and keep their work area tidy."
    )

    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "The official work start date is August 1, 2026 after the employee completes a two-month probation period.",
              "page_number": 3,
              "verification_reason": "This chunk directly states the official work start date and the probation period.",
              "supports_simple_reasoning": false
            }
          ],
          "rejected_chunks": [
            {
              "chunk_id": "44444444-4444-4444-4444-444444444444",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Employees should follow office etiquette and keep their work area tidy.",
              "rejection_reason": "This chunk is only loosely related to employment and does not mention the official work start date or probation duration."
            }
          ],
          "missing_information": false,
          "confidence": 0.86
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does official work start after probation?",
            "candidates": [direct_candidate, weak_candidate],
        }
    )

    output_payload = output.model_dump(mode="json")
    assert output_payload == {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": (
                    "The official work start date is August 1, 2026 after "
                    "the employee completes a two-month probation period."
                ),
                "page_number": 3,
                "verification_reason": (
                    "This chunk directly states the official work start date "
                    "and the probation period."
                ),
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [
            {
                "chunk_id": SECOND_CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": (
                    "Employees should follow office etiquette and keep their "
                    "work area tidy."
                ),
                "rejection_reason": (
                    "This chunk is only loosely related to employment and "
                    "does not mention the official work start date or "
                    "probation duration."
                ),
            }
        ],
        "missing_information": False,
        "confidence": 0.86,
    }
    assert SECOND_CANDIDATE_CHUNK_ID not in {
        chunk["chunk_id"] for chunk in output_payload["verified_chunks"]
    }


def test_verification_agent_logs_success_with_final_verification_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_agent_step = Mock(return_value={"id": "step-id"})
    monkeypatch.setattr(
        agent_log_service,
        "log_agent_step",
        log_agent_step,
    )

    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start and duration.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [
            {
              "chunk_id": "44444444-4444-4444-4444-444444444444",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "rejection_reason": "Duplicate evidence."
            }
          ],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload(), _second_candidate_payload()],
        }
    )

    assert len(output.verified_chunks) == 1
    assert len(output.rejected_chunks) == 1
    log_agent_step.assert_called_once()
    log_call = log_agent_step.call_args.kwargs
    assert log_call["agent_run_id"] == AGENT_RUN_ID
    assert log_call["step_name"] == verification_agent.AGENT_2_VERIFICATION_STEP_NAME
    assert log_call["agent_name"] == verification_agent.VERIFICATION_AGENT_NAME
    assert log_call["status"] == "success"
    assert log_call["input_payload"].model_dump(mode="json") == {
        "agent_run_id": AGENT_RUN_ID,
        "question": "When does probation start?",
        "candidates": [
            _candidate_payload(),
            _second_candidate_payload(),
        ],
    }
    assert log_call["output_payload"].model_dump(mode="json") == {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026 and lasts two months.",
                "page_number": 3,
                "verification_reason": (
                    "This chunk states the probation start and duration."
                ),
                "supports_simple_reasoning": True,
            }
        ],
        "rejected_chunks": [
            {
                "chunk_id": SECOND_CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026 and lasts two months.",
                "rejection_reason": "Duplicate evidence.",
            }
        ],
        "missing_information": False,
        "confidence": 0.82,
    }


def test_verification_agent_warns_when_success_log_insert_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_attempt = agent_log_service.AgentStepLogAttempt(
        persisted=False,
        row=None,
        persistence_error=agent_log_service.AgentLogPersistenceError(
            step_name=verification_agent.AGENT_2_VERIFICATION_STEP_NAME,
            agent_name=verification_agent.VERIFICATION_AGENT_NAME,
            status="success",
        ),
    )
    try_log_agent_step = Mock(return_value=log_attempt)
    logger_warning = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    monkeypatch.setattr(verification_agent.logger, "warning", logger_warning)

    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start and duration.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert isinstance(output, VerificationAgentOutput)
    assert output.confidence == 0.82
    try_log_agent_step.assert_called_once()
    logger_warning.assert_called_once_with(
        "Agent 2 step log persistence failed for %s::%s [%s].",
        verification_agent.VERIFICATION_AGENT_NAME,
        verification_agent.AGENT_2_VERIFICATION_STEP_NAME,
        "success",
    )
    assert "Probation starts on June 1, 2026" not in str(logger_warning.call_args)


def test_verification_agent_rejects_invalid_llm_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    def fake_chat_completion(messages, response_format=None):
        return "Here is the JSON: {\"verified_chunks\": []}"

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    with pytest.raises(VerificationAgentError):
        run_verification_agent(
            {
                "agent_run_id": AGENT_RUN_ID,
                "question": "When does probation start?",
                "candidates": [_candidate_payload()],
            }
        )

    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["agent_run_id"] == AGENT_RUN_ID
    assert log_call["step_name"] == verification_agent.AGENT_2_VERIFICATION_STEP_NAME
    assert log_call["agent_name"] == verification_agent.VERIFICATION_AGENT_NAME
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == verification_agent.VERIFICATION_FAILURE_MESSAGE
    assert log_call["input_payload"] == {
        "agent_run_id": AGENT_RUN_ID,
        "question": "When does probation start?",
        "candidate_count": 1,
        "candidate_chunk_ids": [CANDIDATE_CHUNK_ID],
    }
    assert log_call["output_payload"] == {
        "error": {
            "type": "invalid_json",
            "message": verification_agent.VERIFICATION_FAILURE_MESSAGE,
        }
    }
    assert "Here is the JSON" not in str(log_call)
    assert "Probation starts on June 1, 2026" not in str(log_call)


def test_verification_agent_preserves_failure_when_failed_log_insert_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_attempt = agent_log_service.AgentStepLogAttempt(
        persisted=False,
        row=None,
        persistence_error=agent_log_service.AgentLogPersistenceError(
            step_name=verification_agent.AGENT_2_VERIFICATION_STEP_NAME,
            agent_name=verification_agent.VERIFICATION_AGENT_NAME,
            status="failed",
            error_message=verification_agent.VERIFICATION_FAILURE_MESSAGE,
        ),
    )
    try_log_agent_step = Mock(return_value=log_attempt)
    logger_warning = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    monkeypatch.setattr(verification_agent.logger, "warning", logger_warning)

    def fake_chat_completion(messages, response_format=None):
        return "raw invalid JSON with provider internal detail"

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    with pytest.raises(VerificationAgentError):
        run_verification_agent(
            {
                "agent_run_id": AGENT_RUN_ID,
                "question": "When does probation start?",
                "candidates": [_candidate_payload()],
            }
        )

    try_log_agent_step.assert_called_once()
    assert (
        (
            "Agent 2 step log persistence failed for %s::%s [%s].",
            verification_agent.VERIFICATION_AGENT_NAME,
            verification_agent.AGENT_2_VERIFICATION_STEP_NAME,
            "failed",
        ),
        {},
    ) in logger_warning.call_args_list
    assert "raw invalid JSON" not in str(logger_warning.call_args)
    assert "Probation starts on June 1, 2026" not in str(logger_warning.call_args)


def test_verification_agent_logs_failed_step_for_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    def fake_chat_completion(messages, response_format=None):
        raise verification_agent.shopaikey_service.ShopAIKeyServiceError(
            "provider raw secret detail"
        )

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    with pytest.raises(VerificationAgentError):
        run_verification_agent(
            {
                "agent_run_id": AGENT_RUN_ID,
                "question": "When does probation start?",
                "candidates": [_candidate_payload()],
            }
        )

    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == verification_agent.VERIFICATION_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": "provider_error",
            "message": verification_agent.VERIFICATION_FAILURE_MESSAGE,
        }
    }
    assert "provider raw secret detail" not in str(log_call)
    assert "Probation starts on June 1, 2026" not in str(log_call)


def test_verification_agent_rejects_llm_schema_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    def fake_chat_completion(messages, response_format=None):
        return '{"verified_chunks":[],"rejected_chunks":[],"confidence":0.5}'

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    with pytest.raises(VerificationAgentError):
        run_verification_agent(
            {
                "agent_run_id": AGENT_RUN_ID,
                "question": "When does probation start?",
                "candidates": [_candidate_payload()],
            }
        )

    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == verification_agent.VERIFICATION_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": "schema_validation_error",
            "message": verification_agent.VERIFICATION_FAILURE_MESSAGE,
        }
    }
    assert "missing_information" not in str(log_call)
    assert "Probation starts on June 1, 2026" not in str(log_call)


def test_verification_agent_rejects_out_of_range_llm_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    def fake_chat_completion(messages, response_format=None):
        return '{"verified_chunks":[],"rejected_chunks":[],"missing_information":false,"confidence":1.5}'

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    with pytest.raises(VerificationAgentError):
        run_verification_agent(
            {
                "agent_run_id": AGENT_RUN_ID,
                "question": "When does probation start?",
                "candidates": [_candidate_payload()],
            }
        )

    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == verification_agent.VERIFICATION_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": "schema_validation_error",
            "message": verification_agent.VERIFICATION_FAILURE_MESSAGE,
        }
    }
    assert "1.5" not in str(log_call)
    assert "Probation starts on June 1, 2026" not in str(log_call)


@pytest.mark.parametrize("chunk_list_name", ["verified_chunks", "rejected_chunks"])
def test_verification_agent_rejects_unknown_returned_chunk_ids(
    monkeypatch: pytest.MonkeyPatch,
    chunk_list_name: str,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    unknown_chunk_id = "44444444-4444-4444-4444-444444444444"
    response_payload: dict[str, object] = {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.5,
    }
    if chunk_list_name == "verified_chunks":
        response_payload[chunk_list_name] = [
            {
                "chunk_id": unknown_chunk_id,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026.",
                "page_number": 3,
                "verification_reason": "States the requested date.",
                "supports_simple_reasoning": False,
            }
        ]
    else:
        response_payload[chunk_list_name] = [
            {
                "chunk_id": unknown_chunk_id,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "This chunk is unrelated.",
                "rejection_reason": "Does not answer the question.",
            }
        ]

    def fake_chat_completion(messages, response_format=None):
        return json.dumps(response_payload)

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    with pytest.raises(VerificationAgentError):
        run_verification_agent(
            {
                "agent_run_id": AGENT_RUN_ID,
                "question": "When does probation start?",
                "candidates": [_candidate_payload()],
            }
        )

    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == verification_agent.VERIFICATION_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": "unknown_chunk_id",
            "message": verification_agent.VERIFICATION_FAILURE_MESSAGE,
        }
    }
    assert unknown_chunk_id not in str(log_call)
    assert "Probation starts on June 1, 2026" not in str(log_call)


def test_verification_agent_keeps_verified_quote_found_in_candidate_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start and duration.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert len(output.verified_chunks) == 1
    assert output.verified_chunks[0].quote == (
        "Probation starts on June 1, 2026 and lasts two months."
    )
    assert output.rejected_chunks == []


def test_verification_agent_accepts_quote_with_whitespace_variation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026\\n   and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start and duration.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert len(output.verified_chunks) == 1
    assert output.verified_chunks[0].quote == (
        "Probation starts on June 1, 2026\n   and lasts two months."
    )
    assert output.rejected_chunks == []


def test_verification_agent_moves_fabricated_verified_quote_to_rejected_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on May 1, 2026 and lasts six months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start and duration.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert output.verified_chunks == []
    assert len(output.rejected_chunks) == 1
    assert output.rejected_chunks[0].chunk_id.hex == CANDIDATE_CHUNK_ID.replace("-", "")
    assert output.rejected_chunks[0].quote == (
        "Probation starts on June 1, 2026 and lasts two months."
    )
    assert (
        "Quote was not found in source candidate content."
        in output.rejected_chunks[0].rejection_reason
    )


def test_verification_agent_corrects_fabricated_rejected_quote_to_source_excerpt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [],
          "rejected_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "The office closes on Fridays.",
              "rejection_reason": "Does not answer the probation question."
            }
          ],
          "missing_information": true,
          "confidence": 0.1
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert output.verified_chunks == []
    assert len(output.rejected_chunks) == 1
    assert output.rejected_chunks[0].quote == (
        "Probation starts on June 1, 2026 and lasts two months."
    )
    assert output.rejected_chunks[0].rejection_reason == (
        "Does not answer the probation question."
    )


def test_verification_agent_marks_missing_information_when_no_verified_chunks_remain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on May 1, 2026 and lasts six months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start and duration.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert output.verified_chunks == []
    assert len(output.rejected_chunks) == 1
    assert output.missing_information is True
    assert output.confidence == verification_agent.NO_VERIFIED_CHUNKS_CONFIDENCE_CAP


def test_verification_agent_filters_duplicate_verified_chunk_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start and duration.",
              "supports_simple_reasoning": true
            },
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This is a repeated verified copy.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert len(output.verified_chunks) == 1
    assert output.verified_chunks[0].chunk_id.hex == CANDIDATE_CHUNK_ID.replace("-", "")
    assert len(output.rejected_chunks) == 1
    assert output.rejected_chunks[0].chunk_id.hex == CANDIDATE_CHUNK_ID.replace("-", "")
    assert "Duplicate verified chunk_id" in output.rejected_chunks[0].rejection_reason


def test_verification_agent_filters_duplicate_verified_content_across_chunk_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start and duration.",
              "supports_simple_reasoning": true
            },
            {
              "chunk_id": "44444444-4444-4444-4444-444444444444",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This duplicate content states the same facts.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload(), _second_candidate_payload()],
        }
    )

    assert [chunk.chunk_id.hex for chunk in output.verified_chunks] == [
        CANDIDATE_CHUNK_ID.replace("-", "")
    ]
    assert len(output.rejected_chunks) == 1
    assert output.rejected_chunks[0].chunk_id.hex == SECOND_CANDIDATE_CHUNK_ID.replace(
        "-",
        "",
    )
    assert (
        "Duplicate verified content"
        in output.rejected_chunks[0].rejection_reason
    )


def test_verification_agent_marks_missing_information_for_conflicting_verified_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_candidate = _second_candidate_payload()
    second_candidate["content"] = (
        "Probation starts on July 1, 2026 and lasts two months."
    )

    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start date.",
              "supports_simple_reasoning": true
            },
            {
              "chunk_id": "44444444-4444-4444-4444-444444444444",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on July 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states a different probation start date.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload(), second_candidate],
        }
    )

    assert len(output.verified_chunks) == 2
    assert output.missing_information is True
    assert output.confidence < 0.82
    assert 0.0 <= output.confidence <= 1.0
    assert any(
        "contradict" in chunk.verification_reason.lower()
        for chunk in output.verified_chunks
    )


def test_verification_agent_marks_missing_information_for_incompatible_short_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_candidate = _candidate_payload()
    first_candidate["content"] = "The employee is eligible for official work."
    second_candidate = _second_candidate_payload()
    second_candidate["content"] = "The employee is not eligible for official work."

    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "The employee is eligible for official work.",
              "page_number": 3,
              "verification_reason": "This chunk states eligibility.",
              "supports_simple_reasoning": false
            },
            {
              "chunk_id": "44444444-4444-4444-4444-444444444444",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "The employee is not eligible for official work.",
              "page_number": 3,
              "verification_reason": "This chunk states ineligibility.",
              "supports_simple_reasoning": false
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "Is the employee eligible for official work?",
            "candidates": [first_candidate, second_candidate],
        }
    )

    assert output.missing_information is True
    assert output.confidence < 0.82
    assert any(
        "contradict" in chunk.verification_reason.lower()
        for chunk in output.verified_chunks
    )


def test_verification_agent_final_output_serializes_with_exact_top_level_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states the probation start and duration.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.82
        }
        """

    def add_internal_helper_metadata(output):
        payload = output.model_dump()
        payload["internal_reasons"] = ["post-processing diagnostic metadata"]
        return payload

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_apply_missing_information_adjustments",
        add_internal_helper_metadata,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert isinstance(output, VerificationAgentOutput)
    assert list(output.model_dump().keys()) == [
        "verified_chunks",
        "rejected_chunks",
        "missing_information",
        "confidence",
    ]


def test_verification_prompt_contains_required_output_shape() -> None:
    prompt = VERIFICATION_AGENT_SYSTEM_PROMPT

    assert "Return only valid JSON" in prompt
    assert "exactly these top-level keys" in prompt
    for key in VERIFICATION_AGENT_OUTPUT_KEYS:
        assert f'"{key}"' in prompt


def test_verification_prompt_contains_accept_reject_and_missing_rules() -> None:
    prompt = VERIFICATION_AGENT_SYSTEM_PROMPT.lower()

    for phrase in [
        "directly answers",
        "date",
        "period",
        "condition",
        "definition",
        "ambiguity",
        "simple reasoning",
        "loosely related",
        "duplicated",
        "contradicted",
        "unclear",
        "wrong document",
        "missing_information",
        "guessing beyond the document",
    ]:
        assert phrase in prompt


def test_verification_prompt_limits_agent_scope() -> None:
    prompt = VERIFICATION_AGENT_SYSTEM_PROMPT.lower()

    assert "evaluate only the provided agent 1 candidate chunks" in prompt
    assert "do not retrieve more chunks" in prompt
    assert "generate a final answer" in prompt
    assert "user-facing citations" in prompt
