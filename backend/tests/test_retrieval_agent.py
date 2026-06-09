import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents import retrieval_agent
from app.agents.retrieval_agent import (
    AGENT_1_RETRIEVAL_STEP_NAME,
    RETRIEVAL_AGENT_NAME,
    RetrievalAgentError,
)
from app.agents.schemas import (
    RetrievalAgentInput,
    RetrievalAgentOutput,
    RetrievalCandidate,
)
from app.services.agent_log_service import AgentLogPersistenceError, AgentStepLogAttempt
from app.schemas.retrieval import HybridRetrievalCandidate, HybridSearchResponse

EXPECTED_RETRIEVAL_FAILURE_MESSAGE = "Retrieval failed. Please try again later."


def _build_hybrid_candidate(
    *,
    chunk_id: str,
    final_score: float,
    retrieval_reason: str,
) -> HybridRetrievalCandidate:
    return HybridRetrievalCandidate(
        chunk_id=UUID(chunk_id),
        document_id=UUID("33333333-3333-3333-3333-333333333333"),
        semantic_similarity=0.9,
        graph_relevance=0.8,
        keyword_overlap=0.7,
        metadata_match=0.6,
        recency_or_position_score=0.5,
        final_score=final_score,
        retrieval_reason=retrieval_reason,
    )


def test_run_retrieval_agent_validates_input_and_calls_hybrid_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hybrid_response = HybridSearchResponse(
        question="When can I start?",
        candidates=[
            _build_hybrid_candidate(
                chunk_id="44444444-4444-4444-4444-444444444444",
                final_score=0.91,
                retrieval_reason="Best match",
            ),
            _build_hybrid_candidate(
                chunk_id="55555555-5555-5555-5555-555555555555",
                final_score=0.82,
                retrieval_reason="Secondary match",
            ),
        ],
    )
    retrieve_hybrid = Mock(return_value=hybrid_response)
    log_agent_step = Mock(return_value={"id": "step-id"})
    monkeypatch.setattr(
        retrieval_agent.hybrid_retrieval_service,
        "retrieve_hybrid",
        retrieve_hybrid,
    )
    monkeypatch.setattr(
        retrieval_agent.agent_log_service,
        "log_agent_step",
        log_agent_step,
    )
    monkeypatch.setattr(
        retrieval_agent,
        "get_settings",
        lambda: SimpleNamespace(retrieval_final_top_k=11),
    )

    result = retrieval_agent.run_retrieval_agent(
        {
            "agent_run_id": "11111111-1111-1111-1111-111111111111",
            "question": "  When can I start?  ",
            "document_ids": ["22222222-2222-2222-2222-222222222222"],
        }
    )

    expected_output = RetrievalAgentOutput(
        question="When can I start?",
        candidates=[
            RetrievalCandidate(
                chunk_id=UUID("44444444-4444-4444-4444-444444444444"),
                document_id=UUID("33333333-3333-3333-3333-333333333333"),
                file_name=None,
                content=None,
                page_number=None,
                section_title=None,
                semantic_similarity=0.9,
                graph_relevance=0.8,
                keyword_overlap=0.7,
                metadata_match=0.6,
                recency_or_position_score=0.5,
                final_score=0.91,
                retrieval_reason="Best match",
            ),
            RetrievalCandidate(
                chunk_id=UUID("55555555-5555-5555-5555-555555555555"),
                document_id=UUID("33333333-3333-3333-3333-333333333333"),
                file_name=None,
                content=None,
                page_number=None,
                section_title=None,
                semantic_similarity=0.9,
                graph_relevance=0.8,
                keyword_overlap=0.7,
                metadata_match=0.6,
                recency_or_position_score=0.5,
                final_score=0.82,
                retrieval_reason="Secondary match",
            ),
        ],
    )

    assert result == expected_output
    retrieve_hybrid.assert_called_once_with(
        "When can I start?",
        [UUID("22222222-2222-2222-2222-222222222222")],
        11,
    )
    log_agent_step.assert_called_once_with(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        input_payload=RetrievalAgentInput(
            agent_run_id="11111111-1111-1111-1111-111111111111",
            question="When can I start?",
            document_ids=["22222222-2222-2222-2222-222222222222"],
        ),
        output_payload=expected_output,
        status="success",
    )


@pytest.mark.parametrize(
    ("input_data", "error_fragment"),
    [
        (
            {
                "agent_run_id": "11111111-1111-1111-1111-111111111111",
                "question": "   ",
                "document_ids": ["22222222-2222-2222-2222-222222222222"],
            },
            "question",
        ),
        (
            {
                "agent_run_id": "not-a-uuid",
                "question": "When can I start?",
                "document_ids": ["22222222-2222-2222-2222-222222222222"],
            },
            "agent_run_id",
        ),
        (
            {
                "agent_run_id": "11111111-1111-1111-1111-111111111111",
                "question": "When can I start?",
                "document_ids": ["not-a-uuid"],
            },
            "document_ids",
        ),
    ],
)
def test_run_retrieval_agent_rejects_invalid_input_before_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    input_data: dict[str, object],
    error_fragment: str,
) -> None:
    retrieve_hybrid = Mock()
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        retrieval_agent.hybrid_retrieval_service,
        "retrieve_hybrid",
        retrieve_hybrid,
    )
    monkeypatch.setattr(
        retrieval_agent.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    with pytest.raises(ValidationError) as exc_info:
        retrieval_agent.run_retrieval_agent(input_data)

    assert error_fragment in str(exc_info.value)
    retrieve_hybrid.assert_not_called()
    try_log_agent_step.assert_not_called()


def test_run_retrieval_agent_logs_failed_step_and_raises_controlled_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieval_failure = RuntimeError("Qdrant provider stack trace details")
    retrieve_hybrid = Mock(side_effect=retrieval_failure)
    try_log_agent_step = Mock(
        return_value=AgentStepLogAttempt(persisted=True, row={"id": "failed-step"})
    )
    monkeypatch.setattr(
        retrieval_agent.hybrid_retrieval_service,
        "retrieve_hybrid",
        retrieve_hybrid,
    )
    monkeypatch.setattr(
        retrieval_agent.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    monkeypatch.setattr(
        retrieval_agent,
        "get_settings",
        lambda: SimpleNamespace(retrieval_final_top_k=7),
    )

    with pytest.raises(RetrievalAgentError) as exc_info:
        retrieval_agent.run_retrieval_agent(
            {
                "agent_run_id": "11111111-1111-1111-1111-111111111111",
                "question": "When can I start?",
                "document_ids": ["22222222-2222-2222-2222-222222222222"],
            }
        )

    assert str(exc_info.value) == EXPECTED_RETRIEVAL_FAILURE_MESSAGE
    assert "Qdrant" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    try_log_agent_step.assert_called_once_with(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        input_payload=RetrievalAgentInput(
            agent_run_id="11111111-1111-1111-1111-111111111111",
            question="When can I start?",
            document_ids=["22222222-2222-2222-2222-222222222222"],
        ),
        output_payload={},
        status="failed",
        error_message=EXPECTED_RETRIEVAL_FAILURE_MESSAGE,
    )


def test_run_retrieval_agent_reports_failed_log_insert_without_erasing_retrieval_error(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieve_hybrid = Mock(side_effect=RuntimeError("Supabase raw detail"))
    persistence_error = AgentLogPersistenceError(
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        status="failed",
        error_message=EXPECTED_RETRIEVAL_FAILURE_MESSAGE,
    )
    try_log_agent_step = Mock(
        return_value=AgentStepLogAttempt(
            persisted=False,
            row=None,
            persistence_error=persistence_error,
        )
    )
    monkeypatch.setattr(
        retrieval_agent.hybrid_retrieval_service,
        "retrieve_hybrid",
        retrieve_hybrid,
    )
    monkeypatch.setattr(
        retrieval_agent.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    monkeypatch.setattr(
        retrieval_agent,
        "get_settings",
        lambda: SimpleNamespace(retrieval_final_top_k=7),
    )

    with caplog.at_level("ERROR", logger=retrieval_agent.logger.name):
        with pytest.raises(RetrievalAgentError) as exc_info:
            retrieval_agent.run_retrieval_agent(
                {
                    "agent_run_id": "11111111-1111-1111-1111-111111111111",
                    "question": "When can I start?",
                    "document_ids": ["22222222-2222-2222-2222-222222222222"],
                }
            )

    assert str(exc_info.value) == EXPECTED_RETRIEVAL_FAILURE_MESSAGE
    assert "Supabase raw detail" not in str(exc_info.value)
    assert "Failed to persist retrieval failure agent step log" in caplog.text
    assert "Supabase raw detail" not in caplog.text
