import json
import logging
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
    build_answer_self_check_payload,
    build_answer_evidence_lookup,
    enforce_answer_self_check,
    execute_answer_self_check,
    format_citation,
    normalize_answer_agent_input,
    normalize_answer_self_check,
    normalize_validated_draft_output,
    parse_and_validate_answer_grounding,
    parse_and_validate_draft_answer,
    run_answer_agent,
    validate_answer_evidence_contract,
)
from app.agents import AnswerAgentError as ExportedAnswerAgentError
from app.agents import run_answer_agent as exported_run_answer_agent
from app.agents.prompts import (
    ANSWER_GENERATION_OUTPUT_KEYS,
    ANSWER_GROUNDING_SYSTEM_PROMPT,
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
from app.core.config import Settings


VERIFIED_CHUNK_ID = "22222222-2222-2222-2222-222222222222"
REJECTED_CHUNK_ID = "33333333-3333-3333-3333-333333333333"
DOCUMENT_ID = "44444444-4444-4444-4444-444444444444"
VERIFIED_QUOTE = "The probation period starts on 01/06/2026 and lasts 2 months."
REJECTED_QUOTE = "The probation period starts on 01/05/2026 and lasts 3 months."
EXPECTED_INSUFFICIENT_EVIDENCE_ANSWER = (
    "Tài liệu hiện tại chưa cung cấp đủ thông tin để xác định câu trả lời.\n\n"
    "Thông tin còn thiếu:\n"
    "- Bằng chứng đã được xác minh trực tiếp trả lời câu hỏi.\n"
    "- Ngữ cảnh, ngày tháng, điều kiện hoặc dữ kiện cần thiết để suy luận."
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


def _grounding_review_payload(
    *,
    output: AnswerAgentOutput | None = None,
    answers_question: bool = True,
    supported: bool = True,
    confidence: float = 0.82,
    supporting_citations: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    reviewed_output = output or _answer_output()
    citations = (
        [
            citation.model_dump(mode="json")
            for citation in reviewed_output.citations
        ]
        if supporting_citations is None
        else supporting_citations
    )
    claim_citations = citations if supported else []
    return {
        "answers_question": answers_question,
        "field_reviews": [
            {
                "field_name": "final_answer",
                "text": reviewed_output.final_answer,
                "claims": [
                    {
                        "claim": reviewed_output.final_answer,
                        "supported": supported,
                        "supporting_citations": claim_citations,
                    }
                ],
            },
            {
                "field_name": "reasoning_summary",
                "text": reviewed_output.reasoning_summary,
                "claims": [
                    {
                        "claim": reviewed_output.reasoning_summary,
                        "supported": supported,
                        "supporting_citations": claim_citations,
                    }
                ],
            },
        ],
        "confidence": confidence,
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


def _assert_self_check_failed_evidence_output(
    output: AnswerAgentOutput,
    *,
    citations: list[Citation] | None = None,
) -> None:
    assert output.final_answer == answer_agent_module.SELF_CHECK_FAILED_EVIDENCE_ANSWER
    assert output.citations == (
        [Citation(file_name="contract.pdf", quote=VERIFIED_QUOTE)]
        if citations is None
        else citations
    )
    assert output.reasoning_summary == "Answer self-check failed after retry."
    assert output.confidence == 0.0
    assert output.self_check == AnswerSelfCheck(
        uses_only_verified_chunks=True,
        has_citation=True,
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
            json.dumps(_grounding_review_payload()),
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
            json.dumps(_grounding_review_payload()),
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


def test_run_answer_agent_ignores_zero_draft_confidence_when_grounding_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_payload = _draft_answer_payload(confidence=0.0)
    expected_output = AnswerAgentOutput.model_validate(
        {
            **draft_payload,
            "self_check": DRAFT_SELF_CHECK_PLACEHOLDER,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(draft_payload),
            json.dumps(
                _grounding_review_payload(
                    output=expected_output,
                    confidence=0.91,
                )
            ),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    assert output.self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES
    assert output.confidence == pytest.approx(0.82)


def test_run_answer_agent_logs_successful_answer_and_self_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_grounding_review_payload()),
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
    assert log_kwargs["input_payload"] == {
        "agent_run_id": _answer_input_payload()["agent_run_id"],
        "question": "When can I start official work?",
        "missing_information": False,
        "verification_confidence": 0.82,
        "verified_chunk_count": 1,
        "rejected_chunk_count": 1,
        "verified_chunk_ids": [VERIFIED_CHUNK_ID],
        "rejected_chunk_ids": [REJECTED_CHUNK_ID],
    }
    assert VERIFIED_QUOTE not in str(log_kwargs["input_payload"])
    assert REJECTED_QUOTE not in str(log_kwargs["input_payload"])
    assert log_kwargs["output_payload"]["draft_answer"]["final_answer"] == (
        _draft_answer_payload()["final_answer"]
    )
    assert log_kwargs["output_payload"]["self_check_result"] == (
        READY_SELF_CHECK_REQUIRED_VALUES
    )
    assert log_kwargs["output_payload"]["grounding_review"]["answers_question"] is True
    assert log_kwargs["output_payload"]["final_answer"] == output.final_answer
    assert log_kwargs["output_payload"]["confidence"] == output.confidence
    assert log_kwargs["output_payload"]["errors"] == []


def test_run_answer_agent_preserves_success_when_success_log_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_grounding_review_payload()),
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


def test_run_answer_agent_logs_insufficient_step_for_self_check_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(
                _grounding_review_payload(
                    answers_question=False,
                    supported=False,
                )
            ),
            json.dumps(_draft_answer_payload()),
            json.dumps(
                _grounding_review_payload(
                    answers_question=False,
                    supported=False,
                )
            ),
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

    output = run_answer_agent(_answer_input_payload())

    _assert_self_check_failed_evidence_output(output)
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "success"
    assert log_call["error_message"] is None
    assert log_call["output_payload"]["fallback_reason"] == "self_check_failed"
    assert (
        log_call["output_payload"]["final_answer"]
        == answer_agent_module.SELF_CHECK_FAILED_EVIDENCE_ANSWER
    )
    assert log_call["output_payload"]["citations"] == [
        {"file_name": "contract.pdf", "quote": VERIFIED_QUOTE}
    ]
    assert log_call["output_payload"]["confidence"] == 0.0


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


def test_run_answer_agent_retries_then_returns_cited_fallback_for_draft_citation_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_payload = _draft_answer_payload()
    invalid_payload["citations"] = [
        {
            "file_name": "contract.pdf",
            "quote": "The probation period begins in June and lasts two months.",
        }
    ]
    chat_completion = Mock(
        side_effect=[
            json.dumps(invalid_payload),
            json.dumps(invalid_payload),
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

    output = run_answer_agent(_answer_input_payload())

    _assert_self_check_failed_evidence_output(output)
    assert chat_completion.call_count == 2
    retry_messages = chat_completion.call_args_list[1].args[0]
    assert (
        answer_agent_module.ANSWER_GENERATION_RETRY_INSTRUCTION
        in retry_messages[1]["content"]
    )
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "success"
    assert log_call["error_message"] is None
    assert log_call["output_payload"]["fallback_reason"] == "citation_validation_error"
    assert log_call["output_payload"]["citations"] == [
        {"file_name": "contract.pdf", "quote": VERIFIED_QUOTE}
    ]


@pytest.mark.parametrize(
    ("self_check_content", "expected_failure_type"),
    [
        ("not-json", "invalid_grounding_json_response"),
        (
            json.dumps(
                {
                    "uses_only_verified_chunks": True,
                    "has_citation": True,
                    "has_unsupported_claims": False,
                }
            ),
            "grounding_validation_error",
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
            json.dumps(_grounding_review_payload()),
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


def test_run_answer_agent_preserves_positive_lower_draft_confidence_for_ready_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload(confidence=0.41)),
            json.dumps(_grounding_review_payload()),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    assert output.confidence == pytest.approx(0.41)


def test_answer_generation_payload_diagnostics_log_safe_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    answer_input = AnswerAgentInput.model_validate(_answer_input_payload())
    monkeypatch.setattr(
        answer_agent_module,
        "get_settings",
        lambda: Settings(_env_file=None, agent_llm_payload_warn_chars=1),
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        Mock(return_value=json.dumps(_draft_answer_payload())),
    )

    with caplog.at_level(logging.INFO, logger=answer_agent_module.__name__):
        answer_agent_module._generate_validated_draft_answer(answer_input)

    assert "LLM payload prepared." in caplog.text
    assert "agent=answer_agent" in caplog.text
    assert "phase=answer_generation" in caplog.text
    assert "candidate_count=1" in caplog.text
    assert "retry=False" in caplog.text
    assert "message_chars=" in caplog.text
    assert VERIFIED_QUOTE not in caplog.text
    assert "private-shopaikey-value" not in caplog.text


def test_answer_self_check_payload_diagnostics_log_safe_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    answer_input = AnswerAgentInput.model_validate(_answer_input_payload())
    output = AnswerAgentOutput.model_validate(
        _draft_answer_payload(self_check=DRAFT_SELF_CHECK_PLACEHOLDER)
    )
    monkeypatch.setattr(
        answer_agent_module,
        "get_settings",
        lambda: Settings(_env_file=None, agent_llm_payload_warn_chars=1),
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        Mock(return_value=json.dumps(_grounding_review_payload(output=output))),
    )

    with caplog.at_level(logging.INFO, logger=answer_agent_module.__name__):
        execute_answer_self_check(
            answer_input.question,
            output,
            answer_input.verification,
        )

    assert "LLM payload prepared." in caplog.text
    assert "agent=answer_agent" in caplog.text
    assert "phase=answer_self_check" in caplog.text
    assert "candidate_count=1" in caplog.text
    assert "retry=False" in caplog.text
    assert "message_chars=" in caplog.text
    assert VERIFIED_QUOTE not in caplog.text
    assert "private-shopaikey-value" not in caplog.text


def test_execute_answer_self_check_marks_reasoning_ready_when_grounded_in_verified_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_output = _answer_output(
        final_answer="Ban co the lam viec chinh thuc vao thang 8/2026."
    )
    chat_completion = Mock(
        return_value=json.dumps(_grounding_review_payload(output=draft_output))
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    executed_grounding = execute_answer_self_check(
        "When can I start official work?",
        draft_output,
        _verification_output(),
    )

    assert (
        executed_grounding.self_check.model_dump()
        == READY_SELF_CHECK_REQUIRED_VALUES
    )
    chat_completion.assert_called_once()


def test_execute_answer_self_check_rejects_unsupported_numeric_claim_with_valid_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_output = _answer_output(
        final_answer=(
            "Ban co the lam viec chinh thuc vao thang 8/2026 "
            "voi muc luong 1000 USD."
        ),
        self_check=DRAFT_SELF_CHECK_PLACEHOLDER,
    )
    chat_completion = Mock(
        return_value=json.dumps(
            _grounding_review_payload(
                output=draft_output,
                answers_question=False,
                supported=False,
            )
        )
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(
        AnswerEvidenceValidationError,
        match="uses_only_verified_chunks",
    ):
        execute_answer_self_check(
            "When can I start official work?",
            draft_output,
            _verification_output(),
        )
    chat_completion.assert_called_once()


def test_execute_answer_self_check_rejects_unsupported_semantic_claim_with_valid_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_output = _answer_output(
        final_answer=(
            "Ban co the lam viec chinh thuc vao thang 8/2026 va duoc lam viec tu xa."
        ),
        self_check=DRAFT_SELF_CHECK_PLACEHOLDER,
    )
    chat_completion = Mock(
        return_value=json.dumps(
            _grounding_review_payload(
                output=draft_output,
                answers_question=False,
                supported=False,
            )
        )
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(
        AnswerEvidenceValidationError,
        match="uses_only_verified_chunks",
    ):
        execute_answer_self_check(
            "When can I start official work?",
            draft_output,
            _verification_output(),
        )
    chat_completion.assert_called_once()


def test_execute_answer_self_check_derives_uses_only_verified_chunks_from_self_check_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_output = _answer_output(
        final_answer=(
            "Ban co the lam viec chinh thuc vao thang 8/2026 va theo chinh sach noi bo."
        ),
        self_check=DRAFT_SELF_CHECK_PLACEHOLDER,
    )
    chat_completion = Mock(
        return_value=json.dumps(
            _grounding_review_payload(
                output=draft_output,
                supporting_citations=[
                    {
                        "file_name": "policy.pdf",
                        "quote": "An unverified internal policy.",
                    }
                ],
            )
        )
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerEvidenceValidationError, match="non-verified"):
        execute_answer_self_check(
            "When can I start official work?",
            draft_output,
            _verification_output(),
        )
    chat_completion.assert_called_once()


def test_execute_answer_self_check_rejects_mismatched_reviewed_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_output = _answer_output()
    grounding_payload = _grounding_review_payload(output=draft_output)
    grounding_payload["field_reviews"][0]["text"] = "Different answer text."
    chat_completion = Mock(return_value=json.dumps(grounding_payload))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerEvidenceValidationError, match="does not match"):
        execute_answer_self_check(
            "When can I start official work?",
            draft_output,
            _verification_output(),
        )


def test_execute_answer_self_check_rejects_rejected_evidence_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_output = _answer_output()
    grounding_payload = _grounding_review_payload(
        output=draft_output,
        supporting_citations=[
            {
                "file_name": "draft.pdf",
                "quote": REJECTED_QUOTE,
            }
        ],
    )
    chat_completion = Mock(return_value=json.dumps(grounding_payload))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    with pytest.raises(AnswerEvidenceValidationError, match="rejected evidence"):
        execute_answer_self_check(
            "When can I start official work?",
            draft_output,
            _verification_output(),
        )


def test_execute_answer_self_check_canonicalizes_unique_verified_subquote_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_output = _answer_output()
    grounding_payload = _grounding_review_payload(
        output=draft_output,
        supporting_citations=[
            {
                "file_name": "contract.pdf",
                "quote": "starts on 01/06/2026",
            }
        ],
    )
    chat_completion = Mock(return_value=json.dumps(grounding_payload))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    executed = execute_answer_self_check(
        "When can I start official work?",
        draft_output,
        _verification_output(),
    )

    assert executed.self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES
    assert all(
        citation.quote == VERIFIED_QUOTE
        for field_review in executed.review.field_reviews
        for claim in field_review.claims
        for citation in claim.supporting_citations
    )


def test_execute_answer_self_check_canonicalizes_terminal_punctuation_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified_quote = "The participants began running when they liked"
    draft_output = _answer_output(
        final_answer="The participants began running when they liked.",
        citations=[
            {
                "file_name": "race.txt",
                "quote": verified_quote,
            }
        ],
    )
    verification = _verification_output(
        verified_chunks=[
            {
                "chunk_id": VERIFIED_CHUNK_ID,
                "document_id": DOCUMENT_ID,
                "file_name": "race.txt",
                "quote": verified_quote,
                "page_number": 1,
                "verification_reason": "States how the activity began.",
                "supports_simple_reasoning": False,
            }
        ]
    )
    grounding_payload = _grounding_review_payload(
        output=draft_output,
        supporting_citations=[
            {
                "file_name": "race.txt",
                "quote": f"{verified_quote}.",
            }
        ],
    )
    chat_completion = Mock(return_value=json.dumps(grounding_payload))
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    executed = execute_answer_self_check(
        "How did the activity begin?",
        draft_output,
        verification,
    )

    assert executed.self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES
    assert all(
        citation.quote == verified_quote
        for field_review in executed.review.field_reviews
        for claim in field_review.claims
        for citation in claim.supporting_citations
    )


def test_run_answer_agent_caps_confidence_by_grounding_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload(confidence=0.9)),
            json.dumps(_grounding_review_payload(confidence=0.6)),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    assert output.confidence == 0.6


def test_run_answer_agent_returns_insufficient_for_incorrect_simple_reasoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_payload = _draft_answer_payload()
    provider_payload["final_answer"] = (
        "Ban co the lam viec chinh thuc vao thang 9/2026."
    )
    provider_payload["reasoning_summary"] = (
        "Start date plus three months gives 09/2026."
    )
    reviewed_output = AnswerAgentOutput.model_validate(
        provider_payload | {"self_check": DRAFT_SELF_CHECK_PLACEHOLDER}
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(provider_payload),
            json.dumps(
                _grounding_review_payload(
                    output=reviewed_output,
                    answers_question=False,
                    supported=False,
                )
            ),
            json.dumps(provider_payload),
            json.dumps(
                _grounding_review_payload(
                    output=reviewed_output,
                    answers_question=False,
                    supported=False,
                )
            ),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    _assert_self_check_failed_evidence_output(output)
    assert chat_completion.call_count == 4


def test_run_answer_agent_returns_insufficient_for_unsupported_explanation_with_valid_conclusion_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conclusion_quote = (
        "'It's the stupidest tea-party I ever was at in all my life!'"
    )
    verification = _verification_output(
        verified_chunks=[
            {
                "chunk_id": VERIFIED_CHUNK_ID,
                "document_id": DOCUMENT_ID,
                "file_name": "alice-in-wonderland.txt",
                "quote": conclusion_quote,
                "page_number": 0,
                "verification_reason": "Alice states the conclusion.",
                "supports_simple_reasoning": False,
            }
        ]
    )
    draft = {
        "final_answer": (
            "Alice considered it the stupidest tea party because the "
            "situation was absurd."
        ),
        "citations": [
            {
                "file_name": "alice-in-wonderland.txt",
                "quote": conclusion_quote,
            }
        ],
        "reasoning_summary": (
            "The absurd situation caused Alice to reach that conclusion."
        ),
        "confidence": 1.0,
    }
    reviewed_output = AnswerAgentOutput.model_validate(
        draft | {"self_check": DRAFT_SELF_CHECK_PLACEHOLDER}
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(draft),
            json.dumps(
                _grounding_review_payload(
                    output=reviewed_output,
                    answers_question=False,
                    supported=False,
                    confidence=0.1,
                )
            ),
            json.dumps(draft),
            json.dumps(
                _grounding_review_payload(
                    output=reviewed_output,
                    answers_question=False,
                    supported=False,
                    confidence=0.1,
                )
            ),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    payload = _answer_input_payload()
    payload["question"] = (
        "Why did Alice consider the Mad Tea-Party the stupidest tea party?"
    )
    payload["verification"] = verification.model_dump(mode="json")

    output = run_answer_agent(payload)

    _assert_self_check_failed_evidence_output(
        output,
        citations=[Citation(file_name="alice-in-wonderland.txt", quote=conclusion_quote)],
    )


def test_run_answer_agent_retries_explanatory_answer_after_self_check_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _answer_input_payload()
    payload["question"] = "Why can I start official work in August?"
    unsupported_draft = _draft_answer_payload()
    unsupported_draft["final_answer"] = (
        "You can start official work in August because of an unsupported policy."
    )
    unsupported_draft["reasoning_summary"] = "The unsupported policy sets August."
    repaired_draft = _draft_answer_payload()
    repaired_output = AnswerAgentOutput.model_validate(
        repaired_draft | {"self_check": DRAFT_SELF_CHECK_PLACEHOLDER}
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(unsupported_draft),
            json.dumps(
                _grounding_review_payload(
                    output=AnswerAgentOutput.model_validate(
                        unsupported_draft
                        | {"self_check": DRAFT_SELF_CHECK_PLACEHOLDER}
                    ),
                    answers_question=False,
                    supported=False,
                )
            ),
            json.dumps(repaired_draft),
            json.dumps(_grounding_review_payload(output=repaired_output)),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(payload)

    assert output.final_answer == repaired_draft["final_answer"]
    assert output.self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES
    assert chat_completion.call_count == 4
    retry_messages = chat_completion.call_args_list[2].args[0]
    retry_payload = json.loads(retry_messages[1]["content"])
    assert "retry_instruction" in retry_payload


def test_run_answer_agent_retries_factual_answer_after_self_check_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _answer_input_payload()
    payload["question"] = "What label was written on the item?"
    unsupported_draft = _draft_answer_payload()
    unsupported_draft["final_answer"] = "The translated label was unsupported."
    unsupported_draft["reasoning_summary"] = "The label was translated."
    repaired_draft = _draft_answer_payload()
    repaired_output = AnswerAgentOutput.model_validate(
        repaired_draft | {"self_check": DRAFT_SELF_CHECK_PLACEHOLDER}
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(unsupported_draft),
            json.dumps(
                _grounding_review_payload(
                    output=AnswerAgentOutput.model_validate(
                        unsupported_draft
                        | {"self_check": DRAFT_SELF_CHECK_PLACEHOLDER}
                    ),
                    answers_question=False,
                    supported=False,
                )
            ),
            json.dumps(repaired_draft),
            json.dumps(_grounding_review_payload(output=repaired_output)),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(payload)

    assert output.final_answer == repaired_draft["final_answer"]
    assert output.self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES
    assert chat_completion.call_count == 4


@pytest.mark.parametrize(
    "failed_grounding",
    [
        _grounding_review_payload(
            answers_question=False,
            supported=False,
        ),
        _grounding_review_payload(
            answers_question=False,
            supported=True,
        ),
        _grounding_review_payload(
            supported=True,
            supporting_citations=[],
        ),
        _grounding_review_payload(
            supporting_citations=[
                {
                    "file_name": "policy.pdf",
                    "quote": "An unverified internal policy.",
                }
            ],
        ),
    ],
)
def test_run_answer_agent_returns_insufficient_evidence_after_retry_grounding_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
    failed_grounding: dict[str, object],
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(failed_grounding),
            json.dumps(_draft_answer_payload()),
            json.dumps(failed_grounding),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    _assert_self_check_failed_evidence_output(output)
    assert chat_completion.call_count == 4


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
                "chunk_index": None,
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
    messages = build_answer_self_check_messages(
        "Why did the event happen?",
        _answer_output(),
        _verification_output(),
    )

    assert messages[1]["role"] == "user"
    provider_payload = json.loads(messages[1]["content"])
    assert "json" in messages[1]["content"].lower()
    assert provider_payload["question"] == "Why did the event happen?"
    assert provider_payload["draft_answer"]["final_answer"] == (
        "Ban co the lam viec chinh thuc vao thang 8/2026."
    )
    assert provider_payload["verified_chunks"][0]["quote"] == VERIFIED_QUOTE
    serialized = json.dumps(provider_payload)
    assert "verification_reason" not in serialized
    assert "supports_simple_reasoning" not in serialized
    assert "rejection_reason" not in serialized


def test_answer_grounding_payload_excludes_verifier_authored_metadata() -> None:
    payload = build_answer_self_check_payload(
        "Why did the event happen?",
        _answer_output(),
        _verification_output(),
    )

    assert payload["question"] == "Why did the event happen?"
    assert payload["verified_chunks"] == [
        {
            "file_name": "contract.pdf",
            "quote": VERIFIED_QUOTE,
            "page_number": 3,
            "chunk_index": None,
        }
    ]
    assert payload["rejected_chunks"] == []


def test_run_answer_agent_sends_verified_evidence_only_to_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_grounding_review_payload()),
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
            "chunk_index": None,
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
    reviewed_output = AnswerAgentOutput.model_validate(
        provider_payload | {"self_check": DRAFT_SELF_CHECK_PLACEHOLDER}
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(provider_payload),
            json.dumps(_grounding_review_payload(output=reviewed_output)),
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
            "chunk_index": None,
        },
        {
            "file_name": "contract.pdf",
            "quote": duration_quote,
            "page_number": 1,
            "chunk_index": None,
        },
    ]
    assert "rejected_chunks" not in answer_generation_payload
    assert start_date_chunk_id not in answer_generation_messages[1]["content"]
    assert duration_chunk_id not in answer_generation_messages[1]["content"]
    assert REJECTED_QUOTE not in answer_generation_messages[1]["content"]
    assert chat_completion.call_count == 2


def test_run_answer_agent_answers_simple_chronology_without_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(side_effect=AssertionError("ShopAIKey must not be called"))
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
    payload = _answer_input_payload()
    payload["question"] = (
        "Which happened first: Alice saw the White Rabbit, "
        "or Alice fell down the rabbit-hole?"
    )
    payload["verification"] = _verification_output(
        verified_chunks=[
            {
                "chunk_id": VERIFIED_CHUNK_ID,
                "document_id": DOCUMENT_ID,
                "file_name": "alice.txt",
                "quote": "suddenly a White Rabbit with pink eyes ran close by her.",
                "page_number": 1,
                "chunk_index": 0,
                "verification_reason": "Alice saw the White Rabbit.",
                "supports_simple_reasoning": True,
            },
            {
                "chunk_id": "55555555-5555-5555-5555-555555555555",
                "document_id": DOCUMENT_ID,
                "file_name": "alice.txt",
                "quote": "down she came upon a heap of sticks and dry leaves, and the fall was over.",
                "page_number": 1,
                "chunk_index": 1,
                "verification_reason": "Alice fell down the rabbit-hole.",
                "supports_simple_reasoning": True,
            },
        ]
    ).model_dump(mode="json")

    output = run_answer_agent(payload)

    assert output.final_answer == "Sự kiện xảy ra trước là: Alice saw the White Rabbit."
    assert output.reasoning_summary == (
        "Compared verified source order by chunk_index: "
        "Alice saw the White Rabbit appears before Alice fell down the rabbit-hole."
    )
    assert output.confidence == pytest.approx(0.82)
    assert output.citations == [
        Citation(
            file_name="alice.txt",
            quote="suddenly a White Rabbit with pink eyes ran close by her.",
        ),
        Citation(
            file_name="alice.txt",
            quote=(
                "down she came upon a heap of sticks and dry leaves, "
                "and the fall was over."
            ),
        ),
    ]
    assert output.self_check == AnswerSelfCheck(
        uses_only_verified_chunks=True,
        has_citation=True,
        has_unsupported_claims=False,
        is_ready=True,
    )
    chat_completion.assert_not_called()
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["output_payload"]["fallback_reason"] == "simple_chronology"


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


def test_parse_and_validate_answer_grounding_rejects_invalid_json_safely() -> None:
    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        parse_and_validate_answer_grounding("not-json")

    assert exc_info.value.failure_type == "invalid_grounding_json_response"


def test_parse_and_validate_answer_grounding_rejects_schema_invalid_payload_safely() -> None:
    with pytest.raises(AnswerAgentError, match=ANSWER_FAILURE_MESSAGE) as exc_info:
        parse_and_validate_answer_grounding(
            json.dumps({"answers_question": True})
        )

    assert exc_info.value.failure_type == "grounding_validation_error"


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
    chat_completion = Mock(
        side_effect=[
            json.dumps(provider_payload),
            json.dumps(provider_payload),
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

    output = run_answer_agent(_answer_input_payload())

    _assert_self_check_failed_evidence_output(output)
    assert chat_completion.call_count == 2
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "success"
    assert log_call["output_payload"]["fallback_reason"] == "citation_validation_error"


def test_run_answer_agent_accepts_verified_citation_and_renders_required_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(_grounding_review_payload()),
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


def test_run_answer_agent_canonicalizes_unique_verified_subquote_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified_quote = (
        "The meeting became rude enough that the attendee walked away. "
        "'I will not return!' said the attendee while leaving. "
        "'This is the worst meeting I have ever attended!'"
    )
    cited_subquote = (
        "'I will not return!' said the attendee while leaving. "
        "'This is the worst meeting I have ever attended!'"
    )
    payload = _answer_input_payload()
    payload["verification"] = _verification_output(
        verified_chunks=[
            {
                "chunk_id": VERIFIED_CHUNK_ID,
                "document_id": DOCUMENT_ID,
                "file_name": "meeting.txt",
                "quote": verified_quote,
                "page_number": 1,
                "verification_reason": "Provides the cause and conclusion.",
                "supports_simple_reasoning": True,
            }
        ]
    ).model_dump(mode="json")
    provider_payload = {
        "final_answer": (
            "The attendee considered it the worst meeting because it became "
            "rude enough that they walked away."
        ),
        "citations": [
            {
                "file_name": "meeting.txt",
                "quote": cited_subquote,
            }
        ],
        "reasoning_summary": "The cited passage links rudeness, leaving, and the conclusion.",
        "confidence": 0.82,
    }
    canonical_output = AnswerAgentOutput.model_validate(
        provider_payload
        | {
            "citations": [
                {
                    "file_name": "meeting.txt",
                    "quote": verified_quote,
                }
            ],
            "self_check": DRAFT_SELF_CHECK_PLACEHOLDER,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(provider_payload),
            json.dumps(_grounding_review_payload(output=canonical_output)),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(payload)

    assert output.citations == [Citation(file_name="meeting.txt", quote=verified_quote)]
    grounding_messages = chat_completion.call_args_list[1].args[0]
    grounding_payload = json.loads(grounding_messages[1]["content"])
    assert grounding_payload["draft_answer"]["citations"] == [
        {
            "file_name": "meeting.txt",
            "quote": verified_quote,
        }
    ]


def test_run_answer_agent_canonicalizes_terminal_punctuation_subquote_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified_quote = (
        "The host pulled out a box of tokens, and handed them round as prizes"
    )
    cited_subquote = "handed them round as prizes."
    payload = _answer_input_payload()
    payload["verification"] = _verification_output(
        verified_chunks=[
            {
                "chunk_id": VERIFIED_CHUNK_ID,
                "document_id": DOCUMENT_ID,
                "file_name": "race.txt",
                "quote": verified_quote,
                "page_number": 1,
                "verification_reason": "States participant prizes.",
                "supports_simple_reasoning": False,
            }
        ]
    ).model_dump(mode="json")
    provider_payload = {
        "final_answer": "The host handed tokens round as prizes.",
        "citations": [
            {
                "file_name": "race.txt",
                "quote": cited_subquote,
            }
        ],
        "reasoning_summary": "The cited passage states the participant prize.",
        "confidence": 0.82,
    }
    canonical_output = AnswerAgentOutput.model_validate(
        provider_payload
        | {
            "citations": [
                {
                    "file_name": "race.txt",
                    "quote": verified_quote,
                }
            ],
            "self_check": DRAFT_SELF_CHECK_PLACEHOLDER,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(provider_payload),
            json.dumps(_grounding_review_payload(output=canonical_output)),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(payload)

    assert output.citations == [Citation(file_name="race.txt", quote=verified_quote)]


def test_run_answer_agent_canonicalizes_terminal_punctuation_variant_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified_quote = "The participants began running when they liked"
    cited_quote = f"{verified_quote}."
    payload = _answer_input_payload()
    payload["verification"] = _verification_output(
        verified_chunks=[
            {
                "chunk_id": VERIFIED_CHUNK_ID,
                "document_id": DOCUMENT_ID,
                "file_name": "race.txt",
                "quote": verified_quote,
                "page_number": 1,
                "verification_reason": "States how the activity began.",
                "supports_simple_reasoning": False,
            }
        ]
    ).model_dump(mode="json")
    provider_payload = {
        "final_answer": "The participants began running when they liked.",
        "citations": [
            {
                "file_name": "race.txt",
                "quote": cited_quote,
            }
        ],
        "reasoning_summary": "The cited passage states how the activity began.",
        "confidence": 0.82,
    }
    canonical_output = AnswerAgentOutput.model_validate(
        provider_payload
        | {
            "citations": [
                {
                    "file_name": "race.txt",
                    "quote": verified_quote,
                }
            ],
            "self_check": DRAFT_SELF_CHECK_PLACEHOLDER,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(provider_payload),
            json.dumps(_grounding_review_payload(output=canonical_output)),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(payload)

    assert output.citations == [Citation(file_name="race.txt", quote=verified_quote)]
    grounding_messages = chat_completion.call_args_list[1].args[0]
    grounding_payload = json.loads(grounding_messages[1]["content"])
    assert grounding_payload["draft_answer"]["citations"] == [
        {
            "file_name": "race.txt",
            "quote": verified_quote,
        }
    ]


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
            "rejected_evidence_error",
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


def test_run_answer_agent_logs_grounding_exhaustion_as_insufficient_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(
        side_effect=[
            json.dumps(_draft_answer_payload()),
            json.dumps(
                _grounding_review_payload(
                    answers_question=False,
                    supported=False,
                )
            ),
            json.dumps(_draft_answer_payload()),
            json.dumps(
                _grounding_review_payload(
                    answers_question=False,
                    supported=False,
                )
            ),
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

    output = run_answer_agent(_answer_input_payload())

    assert output.final_answer == answer_agent_module.SELF_CHECK_FAILED_EVIDENCE_ANSWER
    assert output.citations == [Citation(file_name="contract.pdf", quote=VERIFIED_QUOTE)]
    assert output.reasoning_summary == "Answer self-check failed after retry."
    assert output.confidence == 0.0
    assert output.self_check == AnswerSelfCheck(
        uses_only_verified_chunks=True,
        has_citation=True,
        has_unsupported_claims=False,
        is_ready=False,
    )
    assert chat_completion.call_count == 4
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "success"
    assert log_call["error_message"] is None
    assert (
        log_call["output_payload"]["final_answer"]
        == answer_agent_module.SELF_CHECK_FAILED_EVIDENCE_ANSWER
    )
    assert log_call["output_payload"]["citations"] == [
        {"file_name": "contract.pdf", "quote": VERIFIED_QUOTE}
    ]
    assert log_call["output_payload"]["confidence"] == 0.0
    assert log_call["output_payload"]["fallback_reason"] == "self_check_failed"
    assert log_call["output_payload"]["self_check_result"] == {
        "uses_only_verified_chunks": True,
        "has_citation": True,
        "has_unsupported_claims": False,
        "is_ready": False,
    }


def test_run_answer_agent_returns_insufficient_evidence_without_provider_for_missing_information(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(side_effect=AssertionError("ShopAIKey must not be called"))
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
    payload = _answer_input_payload()
    payload["verification"] = _verification_output(
        missing_information=True
    ).model_dump(mode="json")

    output = run_answer_agent(payload)

    _assert_insufficient_evidence_output(output)
    chat_completion.assert_not_called()
    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "success"
    assert log_call["error_message"] is None
    assert log_call["output_payload"]["fallback_reason"] == "insufficient_evidence"
    assert log_call["output_payload"]["confidence"] == 0.0


def test_insufficient_evidence_answer_explains_missing_information() -> None:
    payload = _answer_input_payload()
    payload["verification"] = _verification_output(
        missing_information=True
    ).model_dump(mode="json")

    output = run_answer_agent(payload)

    assert EXPECTED_INSUFFICIENT_EVIDENCE_ANSWER in output.final_answer
    assert "Thông tin còn thiếu:" in output.final_answer
    assert "bằng chứng đã được xác minh" in output.final_answer.lower()


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
    assert "why or how" in prompt
    assert "do not add broad labels" in prompt
    assert "do not mention examples or side events" in prompt
    assert "preserve literal labels" in prompt
    assert "do not translate or rewrite those literal values" in prompt
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


def test_answer_grounding_prompt_requires_schema_output_fields() -> None:
    for phrase in [
        '"answers_question"',
        '"field_reviews"',
        '"field_name"',
        '"final_answer"',
        '"reasoning_summary"',
        '"text"',
        '"claims"',
        '"claim"',
        '"supported"',
        '"supporting_citations"',
        '"file_name"',
        '"quote"',
        '"confidence"',
    ]:
        assert phrase in ANSWER_GROUNDING_SYSTEM_PROMPT


def test_answer_grounding_prompt_requires_claims_copied_from_visible_text() -> None:
    prompt = ANSWER_GROUNDING_SYSTEM_PROMPT.lower()

    assert "substring" in prompt
    assert "do not translate" in prompt
    assert "do not paraphrase" in prompt


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
