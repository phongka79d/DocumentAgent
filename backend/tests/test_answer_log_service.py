import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.schemas import (
    AnswerAgentInput,
    AnswerAgentOutput,
    AnswerGroundingReview,
)
from app.services.answer_log_service import (
    build_answer_log_input,
    build_insufficient_answer_log_output,
    build_safe_failed_answer_input,
    build_safe_failed_answer_output,
    build_successful_answer_log_output,
)


AGENT_RUN_ID = "11111111-1111-4111-8111-111111111111"
VERIFIED_CHUNK_ID = "22222222-2222-4222-8222-222222222222"
REJECTED_CHUNK_ID = "33333333-3333-4333-8333-333333333333"
DOCUMENT_ID = "44444444-4444-4444-8444-444444444444"
VERIFIED_QUOTE = "The probation period starts on 01/06/2026 and lasts 2 months."
REJECTED_QUOTE = "The probation period starts on 01/05/2026 and lasts 3 months."


def _answer_input() -> AnswerAgentInput:
    return AnswerAgentInput.model_validate(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When can I start official work?",
            "verification": {
                "verified_chunks": [
                    {
                        "chunk_id": VERIFIED_CHUNK_ID,
                        "document_id": DOCUMENT_ID,
                        "file_name": "contract.pdf",
                        "quote": VERIFIED_QUOTE,
                        "page_number": 3,
                        "verification_reason": "Direct timing evidence.",
                        "supports_simple_reasoning": True,
                    }
                ],
                "rejected_chunks": [
                    {
                        "chunk_id": REJECTED_CHUNK_ID,
                        "document_id": DOCUMENT_ID,
                        "file_name": "draft.pdf",
                        "quote": REJECTED_QUOTE,
                        "rejection_reason": "Contradicted by stronger evidence.",
                    }
                ],
                "missing_information": False,
                "confidence": 0.82,
            },
        }
    )


def _answer_output() -> AnswerAgentOutput:
    return AnswerAgentOutput.model_validate(
        {
            "final_answer": "Bạn có thể làm việc chính thức vào tháng 8/2026.",
            "citations": [{"file_name": "contract.pdf", "quote": VERIFIED_QUOTE}],
            "reasoning_summary": "01/06/2026 plus 2 months gives 08/2026.",
            "confidence": 0.82,
            "self_check": {
                "uses_only_verified_chunks": True,
                "has_citation": True,
                "has_unsupported_claims": False,
                "is_ready": True,
            },
        }
    )


def _grounding_review() -> AnswerGroundingReview:
    return AnswerGroundingReview.model_validate(
        {
            "answers_question": True,
            "field_reviews": [
                {
                    "field_name": "final_answer",
                    "text": "Bạn có thể làm việc chính thức vào tháng 8/2026.",
                    "claims": [
                        {
                            "claim": "Official work can start in August 2026.",
                            "supported": True,
                            "supporting_citations": [
                                {
                                    "file_name": "contract.pdf",
                                    "quote": VERIFIED_QUOTE,
                                }
                            ],
                        }
                    ],
                },
                {
                    "field_name": "reasoning_summary",
                    "text": "01/06/2026 plus 2 months gives 08/2026.",
                    "claims": [
                        {
                            "claim": "The date reasoning follows the verified quote.",
                            "supported": True,
                            "supporting_citations": [
                                {
                                    "file_name": "contract.pdf",
                                    "quote": VERIFIED_QUOTE,
                                }
                            ],
                        }
                    ],
                },
            ],
            "confidence": 0.82,
        }
    )


def test_build_successful_answer_log_output_preserves_existing_shape() -> None:
    output = _answer_output()

    log_output = build_successful_answer_log_output(
        draft_output=output,
        final_output=output,
        grounding_review=_grounding_review(),
    )

    assert log_output["draft_answer"]["final_answer"] == output.final_answer
    assert log_output["draft_answer"]["citations"] == [
        {"file_name": "contract.pdf", "quote": VERIFIED_QUOTE}
    ]
    assert log_output["grounding_review"]["answers_question"] is True
    assert log_output["self_check_result"] == output.self_check.model_dump(mode="json")
    assert log_output["final_answer"] == output.final_answer
    assert log_output["citations"] == [
        {"file_name": "contract.pdf", "quote": VERIFIED_QUOTE}
    ]
    assert log_output["reasoning_summary"] == output.reasoning_summary
    assert log_output["confidence"] == 0.82
    assert log_output["errors"] == []


def test_build_answer_log_input_is_compact_metadata_without_quotes() -> None:
    answer_input = _answer_input()

    log_input = build_answer_log_input(answer_input)

    assert log_input == {
        "agent_run_id": AGENT_RUN_ID,
        "question": "When can I start official work?",
        "missing_information": False,
        "verification_confidence": 0.82,
        "verified_chunk_count": 1,
        "rejected_chunk_count": 1,
        "verified_chunk_ids": [VERIFIED_CHUNK_ID],
        "rejected_chunk_ids": [REJECTED_CHUNK_ID],
    }
    assert VERIFIED_QUOTE not in str(log_input)
    assert REJECTED_QUOTE not in str(log_input)


def test_build_insufficient_answer_log_output_preserves_fallback_shape() -> None:
    output = _answer_output()

    log_output = build_insufficient_answer_log_output(
        output=output,
        failure_type="self_check_failed",
    )

    assert log_output == {
        "final_answer": output.final_answer,
        "citations": [{"file_name": "contract.pdf", "quote": VERIFIED_QUOTE}],
        "reasoning_summary": output.reasoning_summary,
        "confidence": output.confidence,
        "self_check_result": output.self_check.model_dump(mode="json"),
        "fallback_reason": "self_check_failed",
        "errors": [],
    }


def test_failed_answer_log_payloads_are_safe_metadata_only() -> None:
    answer_input = _answer_input()

    log_input = build_safe_failed_answer_input(answer_input)
    log_output = build_safe_failed_answer_output(
        failure_type="provider_error",
        failure_message="Answer generation failed. Please try again later.",
    )

    assert log_input == {
        "agent_run_id": AGENT_RUN_ID,
        "question": "When can I start official work?",
        "verified_chunk_count": 1,
        "rejected_chunk_count": 1,
        "verified_chunk_ids": [VERIFIED_CHUNK_ID],
        "rejected_chunk_ids": [REJECTED_CHUNK_ID],
    }
    assert log_output == {
        "error": {
            "type": "provider_error",
            "message": "Answer generation failed. Please try again later.",
        }
    }
    assert VERIFIED_QUOTE not in str(log_input)
    assert REJECTED_QUOTE not in str(log_input)
