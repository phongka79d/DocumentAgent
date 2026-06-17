import json
import sys
from pathlib import Path
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.schemas import RetrievalCandidate
from app.services import evidence_payload_optimizer
from app.services.evidence_payload_optimizer import optimize_candidates_for_verification


CHUNK_ID = UUID("11111111-1111-4111-8111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")


def _candidate(
    *,
    content: str | None,
    chunk_id: UUID = CHUNK_ID,
    document_id: UUID = DOCUMENT_ID,
    file_name: str | None = "policy.pdf",
    page_number: int | None = 3,
    section_title: str | None = "Returns",
    chunk_index: int | None = 4,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name=file_name,
        content=content,
        page_number=page_number,
        section_title=section_title,
        chunk_index=chunk_index,
        semantic_similarity=0.8,
        graph_relevance=0.2,
        keyword_overlap=0.1,
        metadata_match=0.3,
        recency_or_position_score=0.4,
        final_score=0.7,
        retrieval_reason="semantic match",
    )


def test_optimize_candidates_uses_single_llm_batch_response_without_reordering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _candidate(
        chunk_id=UUID("11111111-1111-4111-8111-000000000001"),
        content=(
            "The document starts with unrelated background. "
            "The refund period lasts 30 days after purchase. "
            "Customers must provide the original receipt."
        ),
    )
    second = _candidate(
        chunk_id=UUID("11111111-1111-4111-8111-000000000002"),
        content="Payment policy evidence appears in this chunk.",
    )
    third = _candidate(
        chunk_id=UUID("11111111-1111-4111-8111-000000000003"),
        content="This candidate should not be sent because max_candidates is two.",
    )
    calls: list[tuple[list[dict[str, object]], dict[str, str] | None]] = []

    def fake_chat_completion(messages, response_format=None):
        calls.append((messages, response_format))
        request_payload = json.loads(messages[1]["content"])
        assert request_payload["question"] == (
            "What is the refund period and what proof is required?"
        )
        assert request_payload["snippet_max_chars"] == 140
        assert request_payload["context_sentences"] == 1
        assert [item["chunk_id"] for item in request_payload["candidates"]] == [
            str(first.chunk_id),
            str(second.chunk_id),
        ]
        assert str(third.chunk_id) not in messages[1]["content"]
        return json.dumps(
            {
                "optimized_snippets": [
                    {
                        "chunk_id": str(first.chunk_id),
                        "optimized_content": (
                            "The refund period lasts 30 days after purchase. "
                            "Customers must provide the original receipt."
                        ),
                    },
                    {
                        "chunk_id": str(second.chunk_id),
                        "optimized_content": "Payment policy evidence appears in this chunk.",
                    },
                ]
            }
        )

    monkeypatch.setattr(
        evidence_payload_optimizer.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    optimized = optimize_candidates_for_verification(
        question="What is the refund period and what proof is required?",
        candidates=[first, second, third],
        max_candidates=2,
        snippet_max_chars=140,
        context_sentences=1,
    )

    assert len(calls) == 1
    assert calls[0][1] == {"type": "json_object"}
    assert [candidate.chunk_id for candidate in optimized] == [
        first.chunk_id,
        second.chunk_id,
    ]
    assert optimized[0].document_id == first.document_id
    assert optimized[0].file_name == first.file_name
    assert optimized[0].page_number == first.page_number
    assert optimized[0].section_title == first.section_title
    assert optimized[0].chunk_index == first.chunk_index
    assert optimized[0].content == (
        "The refund period lasts 30 days after purchase. "
        "Customers must provide the original receipt."
    )
    assert optimized[1].content == "Payment policy evidence appears in this chunk."


def test_optimize_candidates_allows_llm_to_mark_empty_content_as_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate(content=None)

    def fake_chat_completion(messages, response_format=None):
        return json.dumps(
            {
                "optimized_snippets": [
                    {
                        "chunk_id": str(candidate.chunk_id),
                        "optimized_content": None,
                    }
                ]
            }
        )

    monkeypatch.setattr(
        evidence_payload_optimizer.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    optimized = optimize_candidates_for_verification(
        question="What is the policy?",
        candidates=[candidate],
        max_candidates=8,
        snippet_max_chars=120,
        context_sentences=0,
    )

    assert optimized[0].content is None


def test_optimize_candidates_truncates_original_content_when_llm_call_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate(content="0123456789 " * 20)

    def fail_chat_completion(messages, response_format=None):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        evidence_payload_optimizer.shopaikey_service,
        "chat_completion",
        fail_chat_completion,
    )

    optimized = optimize_candidates_for_verification(
        question="What is the policy?",
        candidates=[candidate],
        max_candidates=1,
        snippet_max_chars=25,
        context_sentences=0,
    )

    assert optimized[0].content == candidate.content[:25].rstrip()


def test_optimize_candidates_truncates_original_content_when_llm_json_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate(content="The useful evidence is after this prefix.")

    monkeypatch.setattr(
        evidence_payload_optimizer.shopaikey_service,
        "chat_completion",
        lambda messages, response_format=None: "not json",
    )

    optimized = optimize_candidates_for_verification(
        question="What is the policy?",
        candidates=[candidate],
        max_candidates=1,
        snippet_max_chars=18,
        context_sentences=0,
    )

    assert optimized[0].content == "The useful evidenc"
