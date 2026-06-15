import json
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.agents.answer_agent as answer_agent_module
from app.agents.answer_agent import (
    ANSWER_FAILURE_MESSAGE,
    ANSWER_OUTPUT_PUBLIC_KEYS,
    AnswerAgentError,
    AnswerEvidenceValidationError,
    READY_SELF_CHECK_REQUIRED_VALUES,
    DRAFT_SELF_CHECK_PLACEHOLDER,
    build_answer_generation_messages,
    build_answer_generation_payload,
    build_answer_self_check_messages,
    build_answer_evidence_lookup,
    enforce_answer_self_check,
    execute_answer_self_check,
    format_citation,
    normalize_answer_agent_input,
    normalize_answer_self_check,
    normalize_validated_draft_output,
    parse_and_validate_answer_self_check,
    parse_and_validate_draft_answer,
    run_answer_agent,
    validate_answer_evidence_contract,
)
from app.agents import AnswerAgentError as ExportedAnswerAgentError
from app.agents import run_answer_agent as exported_run_answer_agent
from app.agents.prompts import (
    ANSWER_GENERATION_OUTPUT_KEYS,
    ANSWER_GENERATION_SYSTEM_PROMPT,
    ANSWER_SELF_CHECK_SYSTEM_PROMPT,
    SELF_CHECK_OUTPUT_KEYS,
)
from app.agents.schemas import (
    AnswerAgentInput,
    AnswerAgentOutput,
    AnswerGroundingReview,
    AnswerSelfCheck,
    Citation,
    VerificationAgentOutput,
)


VERIFIED_CHUNK_ID = "22222222-2222-2222-2222-222222222222"
REJECTED_CHUNK_ID = "33333333-3333-3333-3333-333333333333"
DOCUMENT_ID = "44444444-4444-4444-4444-444444444444"
VERIFIED_QUOTE = "The probation period starts on 01/06/2026 and lasts 2 months."
REJECTED_QUOTE = "The probation period starts on 01/05/2026 and lasts 3 months."
EXPECTED_INSUFFICIENT_EVIDENCE_ANSWER = (
    "Tài liệu hiện tại chưa cung cấp đủ thông tin để xác định câu trả lời."
)


def test_answer_grounding_review_requires_both_visible_answer_fields() -> None:
    with pytest.raises(ValidationError):
        AnswerGroundingReview.model_validate(
            {
                "answers_question": True,
                "field_reviews": [
                    {
                        "field_name": "final_answer",
                        "text": "Grounded answer.",
                        "claims": [
                            {
                                "claim": "Grounded answer.",
                                "supported": True,
                                "supporting_citations": [
                                    {
                                        "file_name": "source.txt",
                                        "quote": "Grounded source text.",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "confidence": 0.8,
            }
        )


def _verification_output(
    *,
    missing_information: bool = False,
    verified_chunks: list[dict[str, object]] | None = None,
) -> VerificationAgentOutput:
    return VerificationAgentOutput.model_validate(
        {
            "verified_chunks": (
                [
                    {
                        "chunk_id": VERIFIED_CHUNK_ID,
                        "document_id": DOCUMENT_ID,
                        "file_name": "contract.pdf",
                        "quote": VERIFIED_QUOTE,
                        "page_number": 3,
                        "verification_reason": "Directly answers the probation period.",
                        "supports_simple_reasoning": True,
                    }
                ]
                if verified_chunks is None
                else verified_chunks
            ),
            "rejected_chunks": [
                {
                    "chunk_id": REJECTED_CHUNK_ID,
                    "document_id": DOCUMENT_ID,
                    "file_name": "draft.pdf",
                    "quote": REJECTED_QUOTE,
                    "rejection_reason": "Contradicts verified evidence.",
                }
            ],
            "missing_information": missing_information,
            "confidence": 0.82,
        }
    )


def _answer_output(
    *,
    final_answer: str = "Ban co the lam viec chinh thuc vao thang 8/2026.",
    citations: list[dict[str, str]] | None = None,
    self_check: dict[str, bool] | None = None,
) -> AnswerAgentOutput:
    return AnswerAgentOutput.model_validate(
        {
            "final_answer": final_answer,
            "citations": (
                [
                    {
                        "file_name": "contract.pdf",
                        "quote": VERIFIED_QUOTE,
                    }
                ]
                if citations is None
                else citations
            ),
            "reasoning_summary": "Start date plus two months gives 08/2026.",
            "confidence": 0.82,
            "self_check": self_check
            or {
                "uses_only_verified_chunks": True,
                "has_citation": True,
                "has_unsupported_claims": False,
                "is_ready": True,
            },
        }
    )


def _answer_input_payload() -> dict[str, object]:
    return {
        "agent_run_id": "11111111-1111-1111-1111-111111111111",
        "question": " When can I start official work? ",
        "verification": _verification_output().model_dump(mode="json"),
    }


def _draft_answer_payload(
    *,
    self_check: dict[str, bool] | None = None,
    confidence: float = 0.82,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "final_answer": "Ban co the lam viec chinh thuc vao thang 8/2026.",
        "citations": [
            {
                "file_name": "contract.pdf",
                "quote": VERIFIED_QUOTE,
            }
        ],
        "reasoning_summary": "Start date plus two months gives 08/2026.",
        "confidence": confidence,
    }
    if self_check is not None:
        payload["self_check"] = self_check
    return payload


def _ready_self_check_payload() -> dict[str, bool]:
    return {
        "uses_only_verified_chunks": True,
        "has_citation": True,
        "has_unsupported_claims": False,
        "is_ready": True,
    }


def _unsupported_self_check_payload() -> dict[str, bool]:
    return {
        "uses_only_verified_chunks": True,
        "has_citation": True,
        "has_unsupported_claims": True,
        "is_ready": False,
    }


def _unverified_self_check_payload() -> dict[str, bool]:
    return {
        "uses_only_verified_chunks": False,
        "has_citation": True,
        "has_unsupported_claims": True,
        "is_ready": False,
    }


def _not_ready_self_check_payload() -> dict[str, bool]:
    return {
        "uses_only_verified_chunks": True,
        "has_citation": True,
        "has_unsupported_claims": False,
        "is_ready": False,
    }


@pytest.fixture(autouse=True)
def _mock_answer_agent_log_service(monkeypatch: pytest.MonkeyPatch) -> Mock:
    log_agent_step = Mock(return_value={"id": "step-1"})
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "log_agent_step",
        log_agent_step,
    )
    return log_agent_step


def _assert_insufficient_evidence_output(output: AnswerAgentOutput) -> None:
    assert (
        answer_agent_module.INSUFFICIENT_EVIDENCE_ANSWER
        == EXPECTED_INSUFFICIENT_EVIDENCE_ANSWER
    )
    assert output.final_answer == EXPECTED_INSUFFICIENT_EVIDENCE_ANSWER
    assert output.citations == []
    assert output.reasoning_summary == "Insufficient verified evidence."
    assert output.confidence == 0.0
    assert output.self_check == AnswerSelfCheck(
        uses_only_verified_chunks=True,
        has_citation=False,
        has_unsupported_claims=False,
        is_ready=False,
    )


def test_answer_agent_exports_internal_callable_and_error() -> None:
    assert exported_run_answer_agent is run_answer_agent
    assert ExportedAnswerAgentError is AnswerAgentError


def test_run_answer_agent_accepts_answer_agent_input_for_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_ready_self_check_payload()),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    input_model = AnswerAgentInput.model_validate(_answer_input_payload())

    output = run_answer_agent(input_model)

    assert isinstance(output, AnswerAgentOutput)
    assert output.final_answer == _draft_answer_payload()["final_answer"]
    assert chat_completion.call_count == 2


def test_run_answer_agent_accepts_mapping_for_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_ready_self_check_payload()),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    assert isinstance(output, AnswerAgentOutput)
    assert output.citations == [Citation(file_name="contract.pdf", quote=VERIFIED_QUOTE)]
    assert output.self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES
    assert chat_completion.call_count == 2


def test_run_answer_agent_logs_successful_answer_and_self_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_ready_self_check_payload()),
        ]
    )
    log_agent_step = Mock(return_value={"id": "step-1"})
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "log_agent_step",
        log_agent_step,
    )

    output = run_answer_agent(_answer_input_payload())

    assert output.self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES
    log_agent_step.assert_called_once()
    log_kwargs = log_agent_step.call_args.kwargs
    assert log_kwargs["agent_run_id"] == _answer_input_payload()["agent_run_id"]
    assert log_kwargs["step_name"] == "agent_3_answer_self_check"
    assert log_kwargs["agent_name"] == answer_agent_module.ANSWER_AGENT_NAME
    assert log_kwargs["status"] == "success"
    assert log_kwargs["error_message"] is None
    assert log_kwargs["input_payload"]["question"] == "When can I start official work?"
    assert "verified_chunks" in log_kwargs["input_payload"]["verification"]
    assert log_kwargs["output_payload"]["draft_answer"]["final_answer"] == (
        _draft_answer_payload()["final_answer"]
    )
    assert log_kwargs["output_payload"]["self_check_result"] == (
        READY_SELF_CHECK_REQUIRED_VALUES
    )
    assert log_kwargs["output_payload"]["final_answer"] == output.final_answer
    assert log_kwargs["output_payload"]["confidence"] == output.confidence
    assert log_kwargs["output_payload"]["errors"] == []


def test_run_answer_agent_preserves_success_when_success_log_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_ready_self_check_payload()),
        ]
    )
    persistence_error = answer_agent_module.agent_log_service.AgentLogPersistenceError(
        step_name="agent_3_answer_self_check",
        agent_name=answer_agent_module.ANSWER_AGENT_NAME,
        status="success",
    )
    log_attempt = answer_agent_module.agent_log_service.AgentStepLogAttempt(
        persisted=False,
        row=None,
        persistence_error=persistence_error,
    )
    try_log_agent_step = Mock(return_value=log_attempt)
    logger_warning = Mock()
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    monkeypatch.setattr(answer_agent_module.logger, "warning", logger_warning)

    output = run_answer_agent(_answer_input_payload())

    assert output.final_answer == _draft_answer_payload()["final_answer"]
    assert output.self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "success"
    assert log_call["error_message"] is None
    assert log_call["output_payload"]["final_answer"] == output.final_answer
    logger_warning.assert_called_once_with(
        "Agent 3 step log persistence failed for %s::%s [%s].",
        answer_agent_module.ANSWER_AGENT_NAME,
        "agent_3_answer_self_check",
        "success",
    )
    warning_text = str(logger_warning.call_args)
    assert _draft_answer_payload()["final_answer"] not in warning_text
    assert VERIFIED_QUOTE not in warning_text
    assert REJECTED_QUOTE not in warning_text


def test_run_answer_agent_logs_failed_step_for_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    def fake_chat_completion(messages, response_format=None):
        raise answer_agent_module.shopaikey_service.ShopAIKeyServiceError(
            "provider raw secret detail"
        )

    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        run_answer_agent(_answer_input_payload())

    assert exc_info.value.failure_type == "provider_error"
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["agent_run_id"] == _answer_input_payload()["agent_run_id"]
    assert log_call["step_name"] == "agent_3_answer_self_check"
    assert log_call["agent_name"] == answer_agent_module.ANSWER_AGENT_NAME
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == ANSWER_FAILURE_MESSAGE
    assert log_call["input_payload"] == {
        "agent_run_id": _answer_input_payload()["agent_run_id"],
        "question": "When can I start official work?",
        "verified_chunk_count": 1,
        "rejected_chunk_count": 1,
        "verified_chunk_ids": [VERIFIED_CHUNK_ID],
        "rejected_chunk_ids": [REJECTED_CHUNK_ID],
    }
    assert log_call["output_payload"] == {
        "error": {
            "type": "provider_error",
            "message": ANSWER_FAILURE_MESSAGE,
        }
    }
    assert "provider raw secret detail" not in str(log_call)
    assert VERIFIED_QUOTE not in str(log_call)
    assert REJECTED_QUOTE not in str(log_call)


def test_run_answer_agent_logs_failed_step_for_self_check_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_unsupported_self_check_payload()),
        ]
    )
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        run_answer_agent(_answer_input_payload())

    assert exc_info.value.failure_type == "self_check_failed"
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == ANSWER_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": "self_check_failed",
            "message": ANSWER_FAILURE_MESSAGE,
        }
    }
    assert VERIFIED_QUOTE not in str(log_call)
    assert REJECTED_QUOTE not in str(log_call)


@pytest.mark.parametrize(
    ("provider_content", "expected_failure_type"),
    [
        ("not-json", "invalid_json_response"),
        (
            json.dumps(_draft_answer_payload(confidence=1.5)),
            "draft_validation_error",
        ),
        (
            json.dumps(_draft_answer_payload() | {"citations": []}),
            "citation_validation_error",
        ),
    ],
)
def test_run_answer_agent_logs_failed_step_for_invalid_draft_response(
    monkeypatch: pytest.MonkeyPatch,
    provider_content: str,
    expected_failure_type: str,
) -> None:
    chat_completion = Mock(return_value=provider_content)
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        run_answer_agent(_answer_input_payload())

    assert exc_info.value.failure_type == expected_failure_type
    chat_completion.assert_called_once()
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == ANSWER_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": expected_failure_type,
            "message": ANSWER_FAILURE_MESSAGE,
        }
    }
    assert "final_answer" not in log_call["output_payload"]
    assert "is_ready" not in json.dumps(log_call["output_payload"])
    assert provider_content not in str(log_call)


@pytest.mark.parametrize(
    ("self_check_content", "expected_failure_type"),
    [
        ("not-json", "invalid_self_check_json_response"),
        (
            json.dumps(
                {
                    "uses_only_verified_chunks": True,
                    "has_citation": True,
                    "has_unsupported_claims": False,
                }
            ),
            "self_check_validation_error",
        ),
    ],
)
def test_run_answer_agent_logs_failed_step_for_invalid_self_check_response(
    monkeypatch: pytest.MonkeyPatch,
    self_check_content: str,
    expected_failure_type: str,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            self_check_content,
        ]
    )
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        run_answer_agent(_answer_input_payload())

    assert exc_info.value.failure_type == expected_failure_type
    assert chat_completion.call_count == 2
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == ANSWER_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": expected_failure_type,
            "message": ANSWER_FAILURE_MESSAGE,
        }
    }
    assert "final_answer" not in log_call["output_payload"]
    assert "is_ready" not in json.dumps(log_call["output_payload"])


def test_run_answer_agent_preserves_provider_failure_when_failure_log_insert_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=answer_agent_module.shopaikey_service.ShopAIKeyServiceError(
            "provider raw secret detail"
        )
    )
    persistence_error = answer_agent_module.agent_log_service.AgentLogPersistenceError(
        step_name="agent_3_answer_self_check",
        agent_name=answer_agent_module.ANSWER_AGENT_NAME,
        status="failed",
        error_message=ANSWER_FAILURE_MESSAGE,
    )
    log_attempt = answer_agent_module.agent_log_service.AgentStepLogAttempt(
        persisted=False,
        row=None,
        persistence_error=persistence_error,
    )
    try_log_agent_step = Mock(return_value=log_attempt)
    logger_warning = Mock()
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    monkeypatch.setattr(answer_agent_module.logger, "warning", logger_warning)

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        run_answer_agent(_answer_input_payload())

    assert exc_info.value.failure_type == "provider_error"
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == ANSWER_FAILURE_MESSAGE
    logger_warning.assert_called_once_with(
        "Agent 3 step log persistence failed for %s::%s [%s].",
        answer_agent_module.ANSWER_AGENT_NAME,
        "agent_3_answer_self_check",
        "failed",
    )
    warning_text = str(logger_warning.call_args)
    assert "provider raw secret detail" not in warning_text
    assert VERIFIED_QUOTE not in warning_text
    assert REJECTED_QUOTE not in warning_text


def test_run_answer_agent_preserves_provider_failure_when_failure_log_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=answer_agent_module.shopaikey_service.ShopAIKeyServiceError(
            "provider raw secret detail"
        )
    )
    try_log_agent_step = Mock(side_effect=RuntimeError("database unavailable"))
    logger_exception = Mock()
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    monkeypatch.setattr(answer_agent_module.logger, "exception", logger_exception)

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        run_answer_agent(_answer_input_payload())

    assert exc_info.value.failure_type == "provider_error"
    try_log_agent_step.assert_called_once()
    logger_exception.assert_called_once()
    assert logger_exception.call_args.args[0] == (
        "Failed to record Agent 3 failed-step log for %s."
    )
    assert str(logger_exception.call_args.args[1]) == _answer_input_payload()[
        "agent_run_id"
    ]
    exception_text = str(logger_exception.call_args)
    assert "provider raw secret detail" not in exception_text
    assert VERIFIED_QUOTE not in exception_text
    assert REJECTED_QUOTE not in exception_text


def test_run_answer_agent_executes_self_check_for_grounded_draft_without_provider_self_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_ready_self_check_payload()),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    assert output.self_check == AnswerSelfCheck(
        uses_only_verified_chunks=True,
        has_citation=True,
        has_unsupported_claims=False,
        is_ready=True,
    )
    assert chat_completion.call_count == 2


def test_run_answer_agent_uses_verification_confidence_for_ready_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload(confidence=0.0)),
            json.dumps(_ready_self_check_payload()),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    assert output.confidence == 0.82


def test_execute_answer_self_check_marks_reasoning_ready_when_grounded_in_verified_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(return_value=json.dumps(_ready_self_check_payload()))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    draft_output = _answer_output(
        final_answer="Ban co the lam viec chinh thuc vao thang 8/2026."
    )

    self_check = execute_answer_self_check(draft_output, _verification_output())

    assert self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES
    chat_completion.assert_called_once()


def test_execute_answer_self_check_rejects_unsupported_numeric_claim_with_valid_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(return_value=json.dumps(_unsupported_self_check_payload()))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    draft_output = _answer_output(
        final_answer=(
            "Ban co the lam viec chinh thuc vao thang 8/2026 "
            "voi muc luong 1000 USD."
        ),
        self_check=DRAFT_SELF_CHECK_PLACEHOLDER,
    )

    with pytest.raises(AnswerEvidenceValidationError, match="has_unsupported_claims"):
        execute_answer_self_check(draft_output, _verification_output())
    chat_completion.assert_called_once()


def test_execute_answer_self_check_rejects_unsupported_semantic_claim_with_valid_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(return_value=json.dumps(_unsupported_self_check_payload()))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    draft_output = _answer_output(
        final_answer=(
            "Ban co the lam viec chinh thuc vao thang 8/2026 va duoc lam viec tu xa."
        ),
        self_check=DRAFT_SELF_CHECK_PLACEHOLDER,
    )

    with pytest.raises(AnswerEvidenceValidationError, match="has_unsupported_claims"):
        execute_answer_self_check(draft_output, _verification_output())
    chat_completion.assert_called_once()


def test_execute_answer_self_check_derives_uses_only_verified_chunks_from_self_check_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(return_value=json.dumps(_unverified_self_check_payload()))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    draft_output = _answer_output(
        final_answer=(
            "Ban co the lam viec chinh thuc vao thang 8/2026 va theo chinh sach noi bo."
        ),
        self_check=DRAFT_SELF_CHECK_PLACEHOLDER,
    )

    with pytest.raises(AnswerEvidenceValidationError, match="uses_only_verified_chunks"):
        execute_answer_self_check(draft_output, _verification_output())
    chat_completion.assert_called_once()


def test_run_answer_agent_rejects_incorrect_simple_reasoning_with_valid_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_payload = _draft_answer_payload()
    provider_payload["final_answer"] = (
        "Ban co the lam viec chinh thuc vao thang 9/2026."
    )
    provider_payload["reasoning_summary"] = (
        "Start date plus three months gives 09/2026."
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(provider_payload),
            json.dumps(_unsupported_self_check_payload()),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        run_answer_agent(_answer_input_payload())

    assert chat_completion.call_count == 2


@pytest.mark.parametrize(
    "failed_self_check",
    [
        _unsupported_self_check_payload(),
        _not_ready_self_check_payload(),
        {
            "uses_only_verified_chunks": True,
            "has_citation": False,
            "has_unsupported_claims": False,
            "is_ready": True,
        },
        _unverified_self_check_payload(),
    ],
)
def test_run_answer_agent_raises_self_check_failure_without_returning_ready_answer(
    monkeypatch: pytest.MonkeyPatch,
    failed_self_check: dict[str, bool],
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(failed_self_check),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        run_answer_agent(_answer_input_payload())

    assert exc_info.value.failure_type == "self_check_failed"
    assert chat_completion.call_count == 2


def test_run_answer_agent_wraps_input_validation_failures_safely() -> None:
    invalid_payload = _answer_input_payload()
    invalid_payload["question"] = "   "

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        run_answer_agent(invalid_payload)


def test_normalize_answer_agent_input_accepts_agent_2_verification_payload_without_mutation() -> None:
    payload = _answer_input_payload()
    original_payload = deepcopy(payload)

    normalized = normalize_answer_agent_input(payload)

    assert str(normalized.agent_run_id) == original_payload["agent_run_id"]
    assert normalized.question == "When can I start official work?"
    assert normalized.verification == _verification_output()
    assert payload == original_payload


@pytest.mark.parametrize(
    "invalid_update",
    [
        {"agent_run_id": "not-a-uuid"},
        {"verification": {"verified_chunks": [], "rejected_chunks": []}},
        {"verification": {"missing_information": False, "confidence": 0.5}},
        {"verification": _verification_output().model_dump(mode="json") | {"confidence": 1.5}},
    ],
)
def test_normalize_answer_agent_input_rejects_invalid_pydantic_cases(
    invalid_update: dict[str, object],
) -> None:
    payload = _answer_input_payload()
    payload.update(invalid_update)

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        normalize_answer_agent_input(payload)


def test_build_answer_evidence_lookup_maps_verified_and_rejected_evidence() -> None:
    verification = _verification_output()

    evidence_lookup = build_answer_evidence_lookup(verification)

    assert evidence_lookup.verified_quotes == frozenset({VERIFIED_QUOTE})
    assert evidence_lookup.verified_file_names == frozenset({"contract.pdf"})
    assert evidence_lookup.verified_citation_pairs == frozenset(
        {("contract.pdf", VERIFIED_QUOTE)}
    )
    assert evidence_lookup.verified_chunk_ids == frozenset({VERIFIED_CHUNK_ID})
    assert evidence_lookup.rejected_quotes == frozenset({REJECTED_QUOTE})
    assert evidence_lookup.rejected_file_names == frozenset({"draft.pdf"})
    assert evidence_lookup.rejected_citation_pairs == frozenset(
        {("draft.pdf", REJECTED_QUOTE)}
    )
    assert evidence_lookup.rejected_chunk_ids == frozenset({REJECTED_CHUNK_ID})


def test_build_answer_generation_payload_contains_question_and_verified_evidence_only() -> None:
    answer_input = AnswerAgentInput.model_validate(_answer_input_payload())

    payload = build_answer_generation_payload(answer_input)

    assert payload == {
        "response_instruction": "Return only valid JSON.",
        "question": "When can I start official work?",
        "verified_chunks": [
            {
                "file_name": "contract.pdf",
                "quote": VERIFIED_QUOTE,
                "page_number": 3,
                "verification_reason": "Directly answers the probation period.",
                "supports_simple_reasoning": True,
            }
        ],
    }
    payload_json = json.dumps(payload)
    assert "rejected_chunks" not in payload
    assert "chunk_id" not in payload_json
    assert "document_id" not in payload_json
    assert REJECTED_QUOTE not in payload_json
    assert REJECTED_CHUNK_ID not in payload_json
    assert "rejection_reason" not in payload_json


def test_build_answer_generation_messages_exclude_rejected_chunks_from_user_evidence() -> None:
    answer_input = AnswerAgentInput.model_validate(_answer_input_payload())

    messages = build_answer_generation_messages(answer_input)

    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == ANSWER_GENERATION_SYSTEM_PROMPT
    assert messages[1]["role"] == "user"

    provider_payload = json.loads(messages[1]["content"])
    assert "json" in messages[1]["content"].lower()
    assert provider_payload["question"] == "When can I start official work?"
    assert provider_payload["verified_chunks"][0]["quote"] == VERIFIED_QUOTE
    assert "rejected_chunks" not in provider_payload
    assert REJECTED_QUOTE not in messages[1]["content"]
    assert REJECTED_CHUNK_ID not in messages[1]["content"]


def test_build_answer_self_check_messages_include_json_instruction_for_json_mode() -> None:
    messages = build_answer_self_check_messages(_answer_output(), _verification_output())

    assert messages[1]["role"] == "user"
    provider_payload = json.loads(messages[1]["content"])
    assert "json" in messages[1]["content"].lower()
    assert provider_payload["draft_answer"]["final_answer"] == (
        "Ban co the lam viec chinh thuc vao thang 8/2026."
    )
    assert provider_payload["verified_chunks"][0]["quote"] == VERIFIED_QUOTE


def test_run_answer_agent_sends_verified_evidence_only_to_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_ready_self_check_payload()),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    assert isinstance(output, AnswerAgentOutput)
    assert chat_completion.call_count == 2
    messages = chat_completion.call_args_list[0].args[0]
    assert chat_completion.call_args_list[0].kwargs == {
        "response_format": answer_agent_module.ANSWER_GENERATION_RESPONSE_FORMAT
    }
    user_payload = json.loads(messages[1]["content"])
    assert user_payload["question"] == "When can I start official work?"
    assert user_payload["verified_chunks"] == [
        {
            "file_name": "contract.pdf",
            "quote": VERIFIED_QUOTE,
            "page_number": 3,
            "verification_reason": "Directly answers the probation period.",
            "supports_simple_reasoning": True,
        }
    ]
    assert "rejected_chunks" not in user_payload
    assert REJECTED_QUOTE not in messages[1]["content"]
    assert REJECTED_CHUNK_ID not in messages[1]["content"]


def test_run_answer_agent_returns_grounded_simple_reasoning_answer_from_verified_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_date_chunk_id = "55555555-5555-5555-5555-555555555555"
    duration_chunk_id = "66666666-6666-6666-6666-666666666666"
    start_date_quote = "The employee starts probation on 01/06/2026."
    duration_quote = "The probation period lasts 2 months."
    payload = _answer_input_payload()
    payload["question"] = "Which month can I start official work?"
    payload["verification"] = _verification_output(
        verified_chunks=[
            {
                "chunk_id": start_date_chunk_id,
                "document_id": DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": start_date_quote,
                "page_number": 1,
                "verification_reason": "Provides the probation start date.",
                "supports_simple_reasoning": True,
            },
            {
                "chunk_id": duration_chunk_id,
                "document_id": DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": duration_quote,
                "page_number": 1,
                "verification_reason": "Provides the probation duration.",
                "supports_simple_reasoning": True,
            },
        ],
    ).model_dump(mode="json")
    provider_payload = {
        "final_answer": "You can be considered for official work in August 2026.",
        "citations": [
            {"file_name": "contract.pdf", "quote": start_date_quote},
            {"file_name": "contract.pdf", "quote": duration_quote},
        ],
        "reasoning_summary": (
            "The verified start date is 01/06/2026 and probation lasts 2 months, "
            "so the official work month is August 2026."
        ),
        "confidence": 0.82,
    }
    chat_completion = Mock(
        side_effect=[
            json.dumps(provider_payload),
            json.dumps(_ready_self_check_payload()),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(payload)

    assert output.final_answer == provider_payload["final_answer"]
    assert output.citations == [
        Citation(file_name="contract.pdf", quote=start_date_quote),
        Citation(file_name="contract.pdf", quote=duration_quote),
    ]
    assert output.reasoning_summary == provider_payload["reasoning_summary"]
    assert output.confidence == 0.82
    assert output.self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES

    public_output_json = json.dumps(output.model_dump(mode="json"))
    assert "August 2026" in public_output_json
    assert start_date_chunk_id not in public_output_json
    assert duration_chunk_id not in public_output_json
    assert VERIFIED_CHUNK_ID not in public_output_json
    assert "chunk_id" not in public_output_json
    assert "document_id" not in public_output_json

    answer_generation_messages = chat_completion.call_args_list[0].args[0]
    answer_generation_payload = json.loads(answer_generation_messages[1]["content"])
    assert answer_generation_payload["verified_chunks"] == [
        {
            "file_name": "contract.pdf",
            "quote": start_date_quote,
            "page_number": 1,
            "verification_reason": "Provides the probation start date.",
            "supports_simple_reasoning": True,
        },
        {
            "file_name": "contract.pdf",
            "quote": duration_quote,
            "page_number": 1,
            "verification_reason": "Provides the probation duration.",
            "supports_simple_reasoning": True,
        },
    ]
    assert "rejected_chunks" not in answer_generation_payload
    assert start_date_chunk_id not in answer_generation_messages[1]["content"]
    assert duration_chunk_id not in answer_generation_messages[1]["content"]
    assert REJECTED_QUOTE not in answer_generation_messages[1]["content"]
    assert chat_completion.call_count == 2


def test_parse_and_validate_draft_answer_rejects_invalid_json_safely() -> None:
    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        parse_and_validate_draft_answer("not-json")


def test_parse_and_validate_draft_answer_rejects_missing_required_fields_safely() -> None:
    payload = _draft_answer_payload()
    payload.pop("final_answer")

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        parse_and_validate_draft_answer(json.dumps(payload))


def test_parse_and_validate_draft_answer_rejects_missing_citations_safely() -> None:
    payload = _draft_answer_payload()
    payload.pop("citations")

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        parse_and_validate_draft_answer(json.dumps(payload))


def test_parse_and_validate_draft_answer_rejects_empty_citations_safely() -> None:
    payload = _draft_answer_payload()
    payload["citations"] = []

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        parse_and_validate_draft_answer(json.dumps(payload))


def test_parse_and_validate_draft_answer_rejects_invalid_confidence_safely() -> None:
    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        parse_and_validate_draft_answer(json.dumps(_draft_answer_payload(confidence=1.5)))


def test_parse_and_validate_answer_self_check_rejects_invalid_json_safely() -> None:
    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        parse_and_validate_answer_self_check("not-json")

    assert exc_info.value.failure_type == "invalid_self_check_json_response"


def test_parse_and_validate_answer_self_check_rejects_schema_invalid_payload_safely() -> None:
    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        parse_and_validate_answer_self_check(
            json.dumps(
                {
                    "uses_only_verified_chunks": True,
                    "has_citation": True,
                    "has_unsupported_claims": False,
                }
            )
        )

    assert exc_info.value.failure_type == "self_check_validation_error"


def test_parse_and_validate_draft_answer_accepts_valid_draft_without_self_check() -> None:
    output = parse_and_validate_draft_answer(json.dumps(_draft_answer_payload()))

    assert output == AnswerAgentOutput.model_validate(
        _draft_answer_payload(self_check=DRAFT_SELF_CHECK_PLACEHOLDER)
    )


def test_parse_and_validate_draft_answer_accepts_valid_draft_with_self_check() -> None:
    self_check = {
        "uses_only_verified_chunks": True,
        "has_citation": True,
        "has_unsupported_claims": False,
        "is_ready": True,
    }

    output = parse_and_validate_draft_answer(
        json.dumps(_draft_answer_payload(self_check=self_check))
    )

    assert output.self_check == AnswerSelfCheck.model_validate(self_check)


def test_parse_and_validate_draft_answer_preserves_valid_citation_shape() -> None:
    output = parse_and_validate_draft_answer(json.dumps(_draft_answer_payload()))

    assert output.citations == [Citation(file_name="contract.pdf", quote=VERIFIED_QUOTE)]
    assert format_citation(output.citations[0]) == f'contract.pdf: "{VERIFIED_QUOTE}"'


def test_normalize_validated_draft_output_preserves_exact_public_output_shape() -> None:
    output = parse_and_validate_draft_answer(json.dumps(_draft_answer_payload()))
    validate_answer_evidence_contract(output, _verification_output())

    normalized = normalize_validated_draft_output(output)
    normalized_payload = normalized.model_dump(mode="json")

    assert isinstance(normalized, AnswerAgentOutput)
    assert tuple(normalized_payload.keys()) == ANSWER_OUTPUT_PUBLIC_KEYS
    assert tuple(normalized_payload["citations"][0].keys()) == ("file_name", "quote")
    assert tuple(normalized_payload["self_check"].keys()) == (
        "uses_only_verified_chunks",
        "has_citation",
        "has_unsupported_claims",
        "is_ready",
    )
    assert "chunk_id" not in json.dumps(normalized_payload)
    json.dumps(normalized_payload)


def test_run_answer_agent_rejects_sufficient_evidence_draft_without_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_payload = _draft_answer_payload()
    provider_payload["citations"] = []
    chat_completion = Mock(return_value=json.dumps(provider_payload))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        run_answer_agent(_answer_input_payload())

    chat_completion.assert_called_once()


def test_run_answer_agent_rejects_sufficient_evidence_draft_missing_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_payload = _draft_answer_payload()
    provider_payload.pop("citations")
    chat_completion = Mock(return_value=json.dumps(provider_payload))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        run_answer_agent(_answer_input_payload())

    chat_completion.assert_called_once()


def test_run_answer_agent_rejects_draft_citation_quote_not_in_verified_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_payload = _draft_answer_payload()
    provider_payload["citations"] = [
        {
            "file_name": "contract.pdf",
            "quote": "The probation term is similar but this quote was fabricated.",
        }
    ]
    chat_completion = Mock(return_value=json.dumps(provider_payload))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        run_answer_agent(_answer_input_payload())

    chat_completion.assert_called_once()


def test_run_answer_agent_accepts_verified_citation_and_renders_required_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_ready_self_check_payload()),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    assert output.citations == [Citation(file_name="contract.pdf", quote=VERIFIED_QUOTE)]
    assert [format_citation(citation) for citation in output.citations] == [
        f'contract.pdf: "{VERIFIED_QUOTE}"'
    ]
    assert chat_completion.call_count == 2


def test_run_answer_agent_rejects_draft_citation_from_rejected_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_payload = _draft_answer_payload()
    provider_payload["citations"] = [
        {
            "file_name": "draft.pdf",
            "quote": REJECTED_QUOTE,
        }
    ]
    chat_completion = Mock(return_value=json.dumps(provider_payload))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        run_answer_agent(_answer_input_payload())

    chat_completion.assert_called_once()


@pytest.mark.parametrize(
    ("payload_update", "expected_failure_type"),
    [
        (
            {
                "citations": [
                    {
                        "file_name": "draft.pdf",
                        "quote": REJECTED_QUOTE,
                    }
                ],
            },
            "citation_validation_error",
        ),
        (
            {
                "final_answer": (
                    "Ban co the lam viec chinh thuc vao thang 8/2026. "
                    f"{REJECTED_QUOTE}"
                ),
            },
            "rejected_evidence_error",
        ),
    ],
)
def test_run_answer_agent_rejected_chunk_usage_fails_closed_without_ready_output(
    monkeypatch: pytest.MonkeyPatch,
    payload_update: dict[str, object],
    expected_failure_type: str,
) -> None:
    provider_payload = _draft_answer_payload()
    provider_payload.update(payload_update)
    chat_completion = Mock(return_value=json.dumps(provider_payload))
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        run_answer_agent(_answer_input_payload())

    assert exc_info.value.failure_type == expected_failure_type
    chat_completion.assert_called_once()
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == ANSWER_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": expected_failure_type,
            "message": ANSWER_FAILURE_MESSAGE,
        }
    }
    assert "is_ready" not in json.dumps(log_call["output_payload"])


def test_run_answer_agent_rejects_draft_copying_rejected_quote_in_final_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_payload = _draft_answer_payload()
    provider_payload["final_answer"] = (
        "Ban co the lam viec chinh thuc vao thang 8/2026. "
        f"{REJECTED_QUOTE}"
    )
    chat_completion = Mock(return_value=json.dumps(provider_payload))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        run_answer_agent(_answer_input_payload())

    chat_completion.assert_called_once()


def test_run_answer_agent_rejects_draft_copying_rejected_quote_in_reasoning_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_payload = _draft_answer_payload()
    provider_payload["reasoning_summary"] = (
        "This reasoning copied rejected evidence: "
        f"{REJECTED_QUOTE}"
    )
    chat_completion = Mock(return_value=json.dumps(provider_payload))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE):
        run_answer_agent(_answer_input_payload())

    chat_completion.assert_called_once()


def test_run_answer_agent_unsupported_self_check_claims_fail_without_ready_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_unsupported_self_check_payload()),
        ]
    )
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        run_answer_agent(_answer_input_payload())

    assert exc_info.value.failure_type == "self_check_failed"
    assert chat_completion.call_count == 2
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == ANSWER_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": "self_check_failed",
            "message": ANSWER_FAILURE_MESSAGE,
        }
    }
    assert "final_answer" not in log_call["output_payload"]
    assert "is_ready" not in json.dumps(log_call["output_payload"])


def test_run_answer_agent_returns_insufficient_evidence_without_provider_for_missing_information(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(side_effect=AssertionError("ShopAIKey must not be called"))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    payload = _answer_input_payload()
    payload["verification"] = _verification_output(
        missing_information=True
    ).model_dump(mode="json")

    output = run_answer_agent(payload)

    _assert_insufficient_evidence_output(output)
    chat_completion.assert_not_called()


def test_run_answer_agent_returns_insufficient_evidence_without_provider_for_empty_verified_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(side_effect=AssertionError("ShopAIKey must not be called"))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    payload = _answer_input_payload()
    payload["verification"] = _verification_output(
        verified_chunks=[]
    ).model_dump(mode="json")

    output = run_answer_agent(payload)

    _assert_insufficient_evidence_output(output)
    chat_completion.assert_not_called()


def test_citation_schema_normalizes_fields_and_formats_for_display() -> None:
    citation = Citation.model_validate(
        {
            "file_name": " contract.pdf ",
            "quote": f" {VERIFIED_QUOTE} ",
        }
    )

    assert citation.file_name == "contract.pdf"
    assert citation.quote == VERIFIED_QUOTE
    assert format_citation(citation) == f'contract.pdf: "{VERIFIED_QUOTE}"'


@pytest.mark.parametrize(
    "payload",
    [
        {"file_name": "", "quote": VERIFIED_QUOTE},
        {"file_name": "contract.pdf", "quote": "   "},
        {
            "file_name": "contract.pdf",
            "quote": VERIFIED_QUOTE,
            "chunk_id": VERIFIED_CHUNK_ID,
        },
    ],
)
def test_citation_schema_rejects_malformed_or_internal_fields(
    payload: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        Citation.model_validate(payload)


def test_answer_evidence_contract_accepts_verified_citations() -> None:
    validate_answer_evidence_contract(_answer_output(), _verification_output())


def test_answer_self_check_schema_normalizes_and_forbids_extra_fields() -> None:
    self_check = normalize_answer_self_check(
        {
            "uses_only_verified_chunks": True,
            "has_citation": True,
            "has_unsupported_claims": False,
            "is_ready": True,
        }
    )

    assert isinstance(self_check, AnswerSelfCheck)
    assert self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES

    with pytest.raises(ValidationError):
        normalize_answer_self_check(
            {
                "uses_only_verified_chunks": True,
                "has_citation": True,
                "has_unsupported_claims": False,
                "is_ready": True,
                "ignored": True,
            }
        )


def test_enforce_answer_self_check_accepts_ready_verified_answer() -> None:
    self_check = enforce_answer_self_check(_answer_output(), _verification_output())

    assert self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES


@pytest.mark.parametrize(
    ("self_check", "message"),
    [
        (
            {
                "uses_only_verified_chunks": False,
                "has_citation": True,
                "has_unsupported_claims": False,
                "is_ready": True,
            },
            "uses_only_verified_chunks",
        ),
        (
            {
                "uses_only_verified_chunks": True,
                "has_citation": False,
                "has_unsupported_claims": False,
                "is_ready": True,
            },
            "has_citation",
        ),
        (
            {
                "uses_only_verified_chunks": True,
                "has_citation": True,
                "has_unsupported_claims": True,
                "is_ready": True,
            },
            "has_unsupported_claims",
        ),
        (
            {
                "uses_only_verified_chunks": True,
                "has_citation": True,
                "has_unsupported_claims": False,
                "is_ready": False,
            },
            "is_ready",
        ),
    ],
)
def test_enforce_answer_self_check_rejects_non_ready_fields(
    self_check: dict[str, bool],
    message: str,
) -> None:
    with pytest.raises(AnswerEvidenceValidationError, match=message):
        enforce_answer_self_check(
            _answer_output(self_check=self_check),
            _verification_output(),
        )


def test_answer_evidence_contract_requires_at_least_one_citation() -> None:
    with pytest.raises(AnswerEvidenceValidationError, match="at least one citation"):
        validate_answer_evidence_contract(
            _answer_output(citations=[]),
            _verification_output(),
        )


def test_answer_evidence_contract_rejects_citation_not_in_verified_quotes() -> None:
    with pytest.raises(AnswerEvidenceValidationError, match="verified evidence"):
        validate_answer_evidence_contract(
            _answer_output(
                citations=[
                    {
                        "file_name": "contract.pdf",
                        "quote": "This quote does not appear in verified evidence.",
                    }
                ]
            ),
            _verification_output(),
        )


def test_answer_evidence_contract_rejects_citation_from_rejected_chunks() -> None:
    with pytest.raises(AnswerEvidenceValidationError, match="rejected evidence"):
        validate_answer_evidence_contract(
            _answer_output(
                citations=[
                    {
                        "file_name": "draft.pdf",
                        "quote": REJECTED_QUOTE,
                    }
                ]
            ),
            _verification_output(),
        )


def test_answer_evidence_contract_rejects_internal_chunk_ids_in_answer() -> None:
    with pytest.raises(AnswerEvidenceValidationError, match="internal chunk ID"):
        validate_answer_evidence_contract(
            _answer_output(
                final_answer=(
                    "Evidence chunk "
                    f"{VERIFIED_CHUNK_ID} says probation lasts two months."
                )
            ),
            _verification_output(),
        )


def test_answer_generation_prompt_contains_required_grounding_rules() -> None:
    prompt = ANSWER_GENERATION_SYSTEM_PROMPT.lower()

    assert "verified chunks only" in prompt
    assert "never use rejected chunks" in prompt
    assert "outside knowledge" in prompt
    assert "include citations" in prompt
    assert "vietnamese by default" in prompt
    assert "simple reasoning only when the verified evidence clearly supports it" in prompt
    assert "return only valid json" in prompt


def test_answer_generation_prompt_requires_json_output_fields() -> None:
    assert ANSWER_GENERATION_OUTPUT_KEYS == (
        "final_answer",
        "citations",
        "reasoning_summary",
        "confidence",
    )

    for output_key in ANSWER_GENERATION_OUTPUT_KEYS:
        assert f'"{output_key}"' in ANSWER_GENERATION_SYSTEM_PROMPT

    assert '"file_name"' in ANSWER_GENERATION_SYSTEM_PROMPT
    assert '"quote"' in ANSWER_GENERATION_SYSTEM_PROMPT


def test_answer_self_check_prompt_contains_required_rules() -> None:
    prompt = ANSWER_SELF_CHECK_SYSTEM_PROMPT.lower()

    assert "uses only verified chunks" in prompt
    assert "avoids rejected chunks" in prompt
    assert "includes citations" in prompt
    assert "reasoning that follows clearly from the evidence" in prompt
    assert "has no unsupported claims" in prompt
    assert "understandable to the user" in prompt
    assert "return only valid json" in prompt


def test_answer_self_check_prompt_requires_schema_output_fields() -> None:
    assert SELF_CHECK_OUTPUT_KEYS == (
        "uses_only_verified_chunks",
        "has_citation",
        "has_unsupported_claims",
        "is_ready",
    )

    for output_key in SELF_CHECK_OUTPUT_KEYS:
        assert f'"{output_key}"' in ANSWER_SELF_CHECK_SYSTEM_PROMPT
