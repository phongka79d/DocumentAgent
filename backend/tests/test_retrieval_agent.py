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


def test_retrieval_agent_input_accepts_valid_payload() -> None:
    input_data = RetrievalAgentInput.model_validate(
        {
            "agent_run_id": "11111111-1111-1111-1111-111111111111",
            "question": "  When can I start?  ",
            "document_ids": ["22222222-2222-2222-2222-222222222222"],
        }
    )

    assert input_data.agent_run_id == UUID("11111111-1111-1111-1111-111111111111")
    assert input_data.question == "When can I start?"
    assert input_data.document_ids == [UUID("22222222-2222-2222-2222-222222222222")]


@pytest.mark.parametrize(
    ("input_data", "error_fragment"),
    [
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
        (
            {
                "agent_run_id": "11111111-1111-1111-1111-111111111111",
                "question": "When can I start?",
                "document_ids": [],
            },
            "document_ids",
        ),
        (
            {
                "agent_run_id": "11111111-1111-1111-1111-111111111111",
                "question": "",
                "document_ids": ["22222222-2222-2222-2222-222222222222"],
            },
            "question",
        ),
        (
            {
                "agent_run_id": "11111111-1111-1111-1111-111111111111",
                "question": "   ",
                "document_ids": ["22222222-2222-2222-2222-222222222222"],
            },
            "question",
        ),
    ],
)
def test_retrieval_agent_input_rejects_invalid_payload(
    input_data: dict[str, object],
    error_fragment: str,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        RetrievalAgentInput.model_validate(input_data)

    assert error_fragment in str(exc_info.value)


def test_retrieval_agent_output_accepts_empty_candidates() -> None:
    output = RetrievalAgentOutput.model_validate(
        {
            "question": "  When can I start?  ",
            "candidates": [],
        }
    )

    assert output.question == "When can I start?"
    assert output.candidates == []


def test_retrieval_candidate_rejects_missing_score_fields() -> None:
    candidate_data = {
        "chunk_id": "44444444-4444-4444-4444-444444444444",
        "document_id": "33333333-3333-3333-3333-333333333333",
        "file_name": "contract.pdf",
        "content": "Relevant content",
        "page_number": 3,
        "section_title": "Probation",
        "semantic_similarity": 0.9,
        "graph_relevance": 0.8,
        "keyword_overlap": 0.7,
        "metadata_match": 0.6,
        "retrieval_reason": "Best match",
    }

    with pytest.raises(ValidationError) as exc_info:
        RetrievalCandidate.model_validate(candidate_data)

    assert "recency_or_position_score" in str(exc_info.value)
    assert "final_score" in str(exc_info.value)


def _build_hybrid_candidate(
    *,
    chunk_id: str,
    document_id: str = "33333333-3333-3333-3333-333333333333",
    file_name: str = "contract.pdf",
    content: str = "Relevant contract content",
    page_number: int = 3,
    section_title: str = "Probation",
    chunk_index: int | None = None,
    semantic_similarity: float = 0.9,
    graph_relevance: float = 0.8,
    keyword_overlap: float = 0.7,
    metadata_match: float = 0.6,
    recency_or_position_score: float = 0.5,
    final_score: float,
    retrieval_reason: str,
) -> HybridRetrievalCandidate:
    return HybridRetrievalCandidate(
        chunk_id=UUID(chunk_id),
        document_id=UUID(document_id),
        file_name=file_name,
        content=content,
        page_number=page_number,
        section_title=section_title,
        chunk_index=chunk_index,
        semantic_similarity=semantic_similarity,
        graph_relevance=graph_relevance,
        keyword_overlap=keyword_overlap,
        metadata_match=metadata_match,
        recency_or_position_score=recency_or_position_score,
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
                document_id="33333333-3333-3333-3333-333333333333",
                file_name="contract.pdf",
                content="Official employment begins after probation.",
                page_number=3,
                section_title="Probation period",
                semantic_similarity=0.93,
                graph_relevance=0.81,
                keyword_overlap=0.72,
                metadata_match=0.63,
                recency_or_position_score=0.54,
                final_score=0.91,
                retrieval_reason="Best match",
            ),
            _build_hybrid_candidate(
                chunk_id="55555555-5555-5555-5555-555555555555",
                document_id="66666666-6666-6666-6666-666666666666",
                file_name="handbook.pdf",
                content="Probation details are summarized in the handbook.",
                page_number=5,
                section_title="Employment status",
                semantic_similarity=0.88,
                graph_relevance=0.77,
                keyword_overlap=0.68,
                metadata_match=0.59,
                recency_or_position_score=0.46,
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
        lambda: SimpleNamespace(
            retrieval_final_top_k=11,
            retrieval_context_window=1,
            retrieval_context_max_candidates=8,
        ),
    )
    expand_retrieval_context = Mock(
        return_value=hybrid_response.candidates
    )
    monkeypatch.setattr(
        retrieval_agent.retrieval_context_service,
        "expand_retrieval_context",
        expand_retrieval_context,
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
                file_name="contract.pdf",
                content="Official employment begins after probation.",
                page_number=3,
                section_title="Probation period",
                semantic_similarity=0.93,
                graph_relevance=0.81,
                keyword_overlap=0.72,
                metadata_match=0.63,
                recency_or_position_score=0.54,
                final_score=0.91,
                retrieval_reason="Best match",
            ),
            RetrievalCandidate(
                chunk_id=UUID("55555555-5555-5555-5555-555555555555"),
                document_id=UUID("66666666-6666-6666-6666-666666666666"),
                file_name="handbook.pdf",
                content="Probation details are summarized in the handbook.",
                page_number=5,
                section_title="Employment status",
                semantic_similarity=0.88,
                graph_relevance=0.77,
                keyword_overlap=0.68,
                metadata_match=0.59,
                recency_or_position_score=0.46,
                final_score=0.82,
                retrieval_reason="Secondary match",
            ),
        ],
    )

    assert result == expected_output
    assert [candidate.final_score for candidate in result.candidates] == [0.91, 0.82]
    assert [candidate.chunk_id for candidate in result.candidates] == [
        UUID("44444444-4444-4444-4444-444444444444"),
        UUID("55555555-5555-5555-5555-555555555555"),
    ]
    required_candidate_fields = {
        "chunk_id",
        "document_id",
        "file_name",
        "content",
        "page_number",
        "section_title",
        "chunk_index",
        "semantic_similarity",
        "graph_relevance",
        "keyword_overlap",
        "metadata_match",
        "recency_or_position_score",
        "final_score",
        "retrieval_reason",
    }
    required_logged_candidate_fields = required_candidate_fields - {"content"} | {
        "content_preview",
        "content_char_count",
        "content_omitted",
    }
    assert set(result.candidates[0].model_dump(mode="json")) == required_candidate_fields
    retrieve_hybrid.assert_called_once_with(
        "When can I start?",
        [UUID("22222222-2222-2222-2222-222222222222")],
        11,
    )
    expand_retrieval_context.assert_called_once_with(
        "When can I start?",
        hybrid_response.candidates,
        context_window=1,
        max_context_candidates=8,
    )
    expected_log_output = retrieval_agent._build_retrieval_log_output(expected_output)
    log_agent_step.assert_called_once_with(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        step_name=AGENT_1_RETRIEVAL_STEP_NAME,
        agent_name=RETRIEVAL_AGENT_NAME,
        input_payload=RetrievalAgentInput(
            agent_run_id="11111111-1111-1111-1111-111111111111",
            question="When can I start?",
            document_ids=["22222222-2222-2222-2222-222222222222"],
        ),
        output_payload=expected_log_output,
        status="success",
    )
    log_call = log_agent_step.call_args.kwargs
    assert isinstance(log_call["output_payload"], dict)
    assert log_call["status"] == "success"
    assert log_call.get("error_message") is None
    assert (
        set(log_call["output_payload"]["candidates"][0])
        == required_logged_candidate_fields
    )
    assert "content" not in log_call["output_payload"]["candidates"][0]


def test_run_retrieval_agent_logs_compact_candidates_without_mutating_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_content = (
        "The policy starts with background context. "
        + "Detailed probation evidence sentence. "
        + "Extra retrieved text. " * 80
    )
    hybrid_response = HybridSearchResponse(
        question="What evidence is retrieved?",
        candidates=[
            _build_hybrid_candidate(
                chunk_id="44444444-4444-4444-4444-444444444444",
                content=long_content,
                final_score=0.91,
                retrieval_reason="Best match",
            )
        ],
    )
    monkeypatch.setattr(
        retrieval_agent.hybrid_retrieval_service,
        "retrieve_hybrid",
        Mock(return_value=hybrid_response),
    )
    monkeypatch.setattr(
        retrieval_agent.retrieval_context_service,
        "expand_retrieval_context",
        Mock(return_value=hybrid_response.candidates),
    )
    log_agent_step = Mock(return_value={"id": "step-id"})
    monkeypatch.setattr(
        retrieval_agent.agent_log_service,
        "log_agent_step",
        log_agent_step,
    )
    monkeypatch.setattr(
        retrieval_agent,
        "get_settings",
        lambda: SimpleNamespace(
            retrieval_final_top_k=8,
            retrieval_context_window=1,
            retrieval_context_max_candidates=8,
        ),
    )

    result = retrieval_agent.run_retrieval_agent(
        {
            "agent_run_id": "11111111-1111-1111-1111-111111111111",
            "question": "What evidence is retrieved?",
            "document_ids": ["22222222-2222-2222-2222-222222222222"],
        }
    )

    assert result.candidates[0].content == long_content
    log_output = log_agent_step.call_args.kwargs["output_payload"]

    assert isinstance(log_output, dict)
    logged_candidate = log_output["candidates"][0]
    assert "content" not in logged_candidate
    assert logged_candidate["content_preview"] == long_content[:500]
    assert logged_candidate["content_char_count"] == len(long_content)
    assert logged_candidate["content_omitted"] is True
    assert logged_candidate["final_score"] == 0.91
    assert logged_candidate["retrieval_reason"] == "Best match"
    assert logged_candidate["chunk_id"] == "44444444-4444-4444-4444-444444444444"


def test_run_retrieval_agent_treats_empty_candidates_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hybrid_response = HybridSearchResponse(
        question="When can I start?",
        candidates=[],
    )
    retrieve_hybrid = Mock(return_value=hybrid_response)
    log_agent_step = Mock(return_value={"id": "empty-step"})
    try_log_agent_step = Mock()
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
        retrieval_agent.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    monkeypatch.setattr(
        retrieval_agent,
        "get_settings",
        lambda: SimpleNamespace(
            retrieval_final_top_k=5,
            retrieval_context_window=1,
            retrieval_context_max_candidates=8,
        ),
    )
    expand_retrieval_context = Mock(return_value=[])
    monkeypatch.setattr(
        retrieval_agent.retrieval_context_service,
        "expand_retrieval_context",
        expand_retrieval_context,
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
        candidates=[],
    )
    assert result == expected_output
    retrieve_hybrid.assert_called_once_with(
        "When can I start?",
        [UUID("22222222-2222-2222-2222-222222222222")],
        5,
    )
    expand_retrieval_context.assert_called_once_with(
        "When can I start?",
        [],
        context_window=1,
        max_context_candidates=8,
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
        output_payload={"question": "When can I start?", "candidates": []},
        status="success",
    )
    log_call = log_agent_step.call_args.kwargs
    assert log_call["output_payload"]["candidates"] == []
    assert log_call["status"] == "success"
    assert log_call.get("error_message") is None
    try_log_agent_step.assert_not_called()


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


def test_run_retrieval_agent_rejects_candidate_schema_mismatch_before_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    malformed_candidate = SimpleNamespace(
        model_dump=lambda include: {
            "chunk_id": UUID("44444444-4444-4444-4444-444444444444"),
            "document_id": UUID("33333333-3333-3333-3333-333333333333"),
            "file_name": "contract.pdf",
            "content": "Relevant content",
            "page_number": 3,
            "section_title": "Probation",
            "semantic_similarity": 0.9,
            "graph_relevance": 0.8,
            "keyword_overlap": 0.7,
            "metadata_match": 0.6,
            "retrieval_reason": "Best match",
        }
    )
    retrieve_hybrid = Mock(
        return_value=SimpleNamespace(
            question="When can I start?",
            candidates=[malformed_candidate],
        )
    )
    log_agent_step = Mock()
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
        lambda: SimpleNamespace(
            retrieval_final_top_k=7,
            retrieval_context_window=1,
            retrieval_context_max_candidates=8,
        ),
    )
    monkeypatch.setattr(
        retrieval_agent.retrieval_context_service,
        "expand_retrieval_context",
        Mock(return_value=[malformed_candidate]),
    )

    with pytest.raises(ValidationError) as exc_info:
        retrieval_agent.run_retrieval_agent(
            {
                "agent_run_id": "11111111-1111-1111-1111-111111111111",
                "question": "When can I start?",
                "document_ids": ["22222222-2222-2222-2222-222222222222"],
            }
        )

    assert "recency_or_position_score" in str(exc_info.value)
    assert "final_score" in str(exc_info.value)
    retrieve_hybrid.assert_called_once()
    log_agent_step.assert_not_called()


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
        lambda: SimpleNamespace(
            retrieval_final_top_k=7,
            retrieval_context_window=1,
            retrieval_context_max_candidates=8,
        ),
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
        lambda: SimpleNamespace(
            retrieval_final_top_k=7,
            retrieval_context_window=1,
            retrieval_context_max_candidates=8,
        ),
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
