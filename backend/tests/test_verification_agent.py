import sys
from pathlib import Path

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


AGENT_RUN_ID = "11111111-1111-1111-1111-111111111111"
CANDIDATE_CHUNK_ID = "22222222-2222-2222-2222-222222222222"
CANDIDATE_DOCUMENT_ID = "33333333-3333-3333-3333-333333333333"


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
    def fail_if_called(*args: object, **kwargs: object) -> str:
        raise AssertionError("ShopAIKey chat client must not be called")

    monkeypatch.setattr(
        "app.services.shopaikey_service.chat_completion",
        fail_if_called,
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


def test_verification_agent_rejects_invalid_llm_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_verification_agent_rejects_llm_schema_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_verification_agent_rejects_out_of_range_llm_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
