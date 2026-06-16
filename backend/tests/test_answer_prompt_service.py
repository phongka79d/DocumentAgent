import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.prompts import (
    ANSWER_GENERATION_SYSTEM_PROMPT,
    ANSWER_GROUNDING_SYSTEM_PROMPT,
)
from app.agents.schemas import (
    AnswerAgentInput,
    AnswerAgentOutput,
    VerificationAgentOutput,
)
from app.services.answer_prompt_service import (
    build_answer_generation_messages,
    build_answer_generation_payload,
    build_answer_self_check_messages,
    build_answer_self_check_payload,
)


VERIFIED_CHUNK_ID = "22222222-2222-2222-2222-222222222222"
REJECTED_CHUNK_ID = "33333333-3333-3333-3333-333333333333"
DOCUMENT_ID = "44444444-4444-4444-4444-444444444444"
VERIFIED_QUOTE = "The probation period starts on 01/06/2026 and lasts 2 months."
REJECTED_QUOTE = "The probation period starts on 01/05/2026 and lasts 3 months."


def _verification_output() -> VerificationAgentOutput:
    return VerificationAgentOutput.model_validate(
        {
            "verified_chunks": [
                {
                    "chunk_id": VERIFIED_CHUNK_ID,
                    "document_id": DOCUMENT_ID,
                    "file_name": "contract.pdf",
                    "quote": VERIFIED_QUOTE,
                    "page_number": 3,
                    "verification_reason": "Directly answers the probation period.",
                    "supports_simple_reasoning": True,
                }
            ],
            "rejected_chunks": [
                {
                    "chunk_id": REJECTED_CHUNK_ID,
                    "document_id": DOCUMENT_ID,
                    "file_name": "draft.pdf",
                    "quote": REJECTED_QUOTE,
                    "rejection_reason": "Contradicts verified evidence.",
                }
            ],
            "missing_information": False,
            "confidence": 0.82,
        }
    )


def _answer_input() -> AnswerAgentInput:
    return AnswerAgentInput.model_validate(
        {
            "agent_run_id": "11111111-1111-1111-1111-111111111111",
            "question": " When can I start official work? ",
            "verification": _verification_output().model_dump(mode="json"),
        }
    )


def _answer_output() -> AnswerAgentOutput:
    return AnswerAgentOutput.model_validate(
        {
            "final_answer": "You can start official work in August 2026.",
            "citations": [
                {
                    "file_name": "contract.pdf",
                    "quote": VERIFIED_QUOTE,
                }
            ],
            "reasoning_summary": "Start date plus two months gives August 2026.",
            "confidence": 0.82,
            "self_check": {
                "uses_only_verified_chunks": True,
                "has_citation": True,
                "has_unsupported_claims": False,
                "is_ready": True,
            },
        }
    )


def test_generation_payload_is_compact_verified_evidence_only() -> None:
    payload = build_answer_generation_payload(_answer_input())

    assert payload == {
        "response_instruction": "Return only valid JSON.",
        "question": "When can I start official work?",
        "verified_chunks": [
            {
                "file_name": "contract.pdf",
                "quote": VERIFIED_QUOTE,
                "page_number": 3,
            }
        ],
    }
    serialized = json.dumps(payload)
    assert "rejected_chunks" not in payload
    assert "chunk_id" not in serialized
    assert "document_id" not in serialized
    assert "verification_reason" not in serialized
    assert REJECTED_QUOTE not in serialized


def test_generation_messages_use_prompt_and_compact_json_payload() -> None:
    messages = build_answer_generation_messages(_answer_input())

    assert messages[0] == {
        "role": "system",
        "content": ANSWER_GENERATION_SYSTEM_PROMPT,
    }
    assert messages[1]["role"] == "user"

    provider_payload = json.loads(messages[1]["content"])
    assert provider_payload["question"] == "When can I start official work?"
    assert provider_payload["verified_chunks"][0]["quote"] == VERIFIED_QUOTE
    assert "rejected_chunks" not in provider_payload
    assert REJECTED_QUOTE not in messages[1]["content"]


def test_self_check_payload_omits_irrelevant_rejected_evidence_and_drops_internal_metadata() -> None:
    payload = build_answer_self_check_payload(
        "Why did the event happen?",
        _answer_output(),
        _verification_output(),
    )

    assert payload["question"] == "Why did the event happen?"
    assert payload["draft_answer"]["final_answer"] == (
        "You can start official work in August 2026."
    )
    assert payload["verified_chunks"] == [
        {
            "file_name": "contract.pdf",
            "quote": VERIFIED_QUOTE,
            "page_number": 3,
        }
    ]
    assert payload["rejected_chunks"] == []
    serialized = json.dumps(payload)
    assert "chunk_id" not in serialized
    assert "document_id" not in serialized
    assert "verification_reason" not in serialized
    assert "rejection_reason" not in serialized
    assert "supports_simple_reasoning" not in serialized


def test_self_check_payload_keeps_rejected_evidence_used_by_draft() -> None:
    draft_output = _answer_output().model_copy(
        update={
            "final_answer": (
                "You can start official work in August 2026. "
                f"Conflicting rejected text says: {REJECTED_QUOTE}"
            )
        }
    )

    payload = build_answer_self_check_payload(
        "Why did the event happen?",
        draft_output,
        _verification_output(),
    )

    assert payload["rejected_chunks"] == [
        {
            "file_name": "draft.pdf",
            "quote": REJECTED_QUOTE,
        }
    ]


def test_self_check_messages_use_grounding_prompt_and_json_payload() -> None:
    messages = build_answer_self_check_messages(
        "Why did the event happen?",
        _answer_output(),
        _verification_output(),
    )

    assert messages[0] == {
        "role": "system",
        "content": ANSWER_GROUNDING_SYSTEM_PROMPT,
    }
    assert messages[1]["role"] == "user"
    provider_payload = json.loads(messages[1]["content"])
    assert provider_payload["draft_answer"]["citations"] == [
        {
            "file_name": "contract.pdf",
            "quote": VERIFIED_QUOTE,
        }
    ]
