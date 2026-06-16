import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.prompts import (
    EVIDENCE_COVERAGE_SYSTEM_PROMPT,
    VERIFICATION_AGENT_SYSTEM_PROMPT,
)
from app.agents.schemas import RetrievalCandidate, VerificationAgentInput
from app.services.verification_prompt_service import (
    build_coverage_messages,
    build_coverage_retry_messages,
    build_verification_messages,
)


AGENT_RUN_ID = "11111111-1111-4111-8111-111111111111"
CHUNK_ID = "22222222-2222-4222-8222-222222222222"
DOCUMENT_ID = "33333333-3333-4333-8333-333333333333"


def _candidate(
    *,
    content: str,
    chunk_id: str = CHUNK_ID,
    final_score: float = 0.91,
) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
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
        "final_score": final_score,
        "retrieval_reason": "Matched probation date terms.",
    }


def _input(candidates: list[dict[str, object]]) -> VerificationAgentInput:
    return VerificationAgentInput.model_validate(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": candidates,
        }
    )


def test_build_verification_messages_uses_compact_json_and_selected_fields() -> None:
    messages = build_verification_messages(
        _input(
            [
                _candidate(
                    content="Probation starts on June 1, 2026 and lasts two months."
                )
            ]
        ),
        max_candidates=8,
        snippet_max_chars=200,
        context_sentences=0,
    )

    assert messages[0] == {
        "role": "system",
        "content": VERIFICATION_AGENT_SYSTEM_PROMPT,
    }
    assert messages[1]["role"] == "user"
    assert '\n  "question"' not in messages[1]["content"]
    payload = json.loads(messages[1]["content"].splitlines()[-1])
    assert payload == {
        "question": "When does probation start?",
        "evidence": [
            {
                "chunk_id": CHUNK_ID,
                "document_id": DOCUMENT_ID,
                "file_name": "contract.pdf",
                "page_number": 3,
                "section_title": "Probation",
                "score": 0.91,
                "content": "Probation starts on June 1, 2026 and lasts two months.",
            }
        ],
    }
    serialized = messages[1]["content"]
    assert "semantic_similarity" not in serialized
    assert "retrieval_reason" not in serialized


def test_build_coverage_messages_limits_candidates_and_uses_compact_payload() -> None:
    candidates = [
        _candidate(
            chunk_id=str(UUID(f"22222222-2222-4222-8222-{index:012d}")),
            content=f"Candidate {index} has unique evidence.",
            final_score=0.9 - index / 100,
        )
        for index in range(4)
    ]

    messages = build_coverage_messages(
        _input(candidates),
        max_candidates=2,
        snippet_max_chars=200,
        context_sentences=0,
    )

    assert messages[0] == {
        "role": "system",
        "content": EVIDENCE_COVERAGE_SYSTEM_PROMPT,
    }
    payload = json.loads(messages[1]["content"])
    assert len(payload["candidates"]) == 2
    assert payload["candidates"][0]["content"] == "Candidate 0 has unique evidence."
    assert payload["candidates"][1]["content"] == "Candidate 1 has unique evidence."
    assert "Candidate 2" not in messages[1]["content"]
    assert "\n" not in messages[1]["content"]


def test_build_coverage_retry_messages_caps_invalid_response_preview() -> None:
    invalid_response = "not-json " + ("echoed source detail " * 300)

    messages = build_coverage_retry_messages(
        _input([_candidate(content="Probation starts on June 1, 2026.")]),
        invalid_response=invalid_response,
        failure_type="coverage_invalid_json",
        max_candidates=1,
        snippet_max_chars=200,
        context_sentences=0,
    )

    assert [message["role"] for message in messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert messages[2]["content"].startswith("not-json echoed source")
    assert len(messages[2]["content"]) <= 2080
    assert len(messages[2]["content"]) < len(invalid_response)
    assert "omitted" in messages[2]["content"]
    assert "coverage_invalid_json" in messages[3]["content"]
