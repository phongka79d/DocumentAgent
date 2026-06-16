import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.schemas import VerificationAgentInput
from app.services.verification_log_service import (
    VERIFICATION_LOG_CONTENT_PREVIEW_CHARS,
    build_safe_failed_verification_input,
    build_safe_failed_verification_output,
    build_verification_log_input,
)


AGENT_RUN_ID = "11111111-1111-4111-8111-111111111111"
CHUNK_ID = "22222222-2222-4222-8222-222222222222"
DOCUMENT_ID = "33333333-3333-4333-8333-333333333333"
QUOTE = "Probation starts on June 1, 2026 and lasts two months."
FAILURE_MESSAGE = "Verification failed. Please try again later."


def _verification_input(content: str) -> VerificationAgentInput:
    return VerificationAgentInput.model_validate(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [
                {
                    "chunk_id": CHUNK_ID,
                    "document_id": DOCUMENT_ID,
                    "file_name": "contract.pdf",
                    "content": content,
                    "page_number": 3,
                    "section_title": "Probation",
                    "chunk_index": 5,
                    "semantic_similarity": 0.88,
                    "graph_relevance": 0.72,
                    "keyword_overlap": 0.64,
                    "metadata_match": 0.5,
                    "recency_or_position_score": 0.4,
                    "final_score": 0.91,
                    "retrieval_reason": "Matched probation date terms.",
                }
            ],
        }
    )


def test_build_verification_log_input_compacts_candidate_content() -> None:
    long_content = QUOTE + " " + ("Additional source detail. " * 120)

    log_input = build_verification_log_input(_verification_input(long_content))

    assert log_input["agent_run_id"] == AGENT_RUN_ID
    assert log_input["question"] == "When does probation start?"
    assert len(log_input["candidates"]) == 1
    candidate = log_input["candidates"][0]
    assert "content" not in candidate
    assert candidate["content_preview"] == long_content[
        :VERIFICATION_LOG_CONTENT_PREVIEW_CHARS
    ]
    assert candidate["content_char_count"] == len(long_content)
    assert candidate["content_omitted"] is True
    assert candidate["chunk_id"] == CHUNK_ID
    assert candidate["final_score"] == 0.91
    assert long_content not in str(log_input)


def test_build_safe_failed_verification_payloads_are_metadata_only() -> None:
    verification_input = _verification_input(QUOTE)

    log_input = build_safe_failed_verification_input(verification_input)
    log_output = build_safe_failed_verification_output(
        failure_type="invalid_json",
        failure_message=FAILURE_MESSAGE,
    )

    assert log_input == {
        "agent_run_id": AGENT_RUN_ID,
        "question": "When does probation start?",
        "candidate_count": 1,
        "candidate_chunk_ids": [CHUNK_ID],
    }
    assert log_output == {
        "error": {
            "type": "invalid_json",
            "message": FAILURE_MESSAGE,
        }
    }
    assert QUOTE not in str(log_input)
