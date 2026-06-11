import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents import graph
from app.agents.schemas import (
    AnswerAgentOutput,
    AnswerSelfCheck,
    RetrievalAgentOutput,
    VerificationAgentOutput,
)


def test_workflow_state_schema_carries_agent_outputs_without_conversion():
    state_fields = graph.QAWorkflowState.__annotations__

    assert set(state_fields) == {
        "agent_run_id",
        "session_id",
        "question",
        "document_ids",
        "retrieval",
        "verification",
        "answer",
        "error",
    }

    retrieval = RetrievalAgentOutput(question="What is covered?", candidates=[])
    verification = VerificationAgentOutput(
        verified_chunks=[],
        rejected_chunks=[],
        missing_information=True,
        confidence=0.0,
    )
    answer = AnswerAgentOutput(
        final_answer="The document does not provide enough information.",
        citations=[],
        reasoning_summary="Insufficient verified evidence.",
        confidence=0.0,
        self_check=AnswerSelfCheck(
            uses_only_verified_chunks=True,
            has_citation=False,
            has_unsupported_claims=False,
            is_ready=False,
        ),
    )

    workflow_state = graph.QAWorkflowState(
        agent_run_id=UUID("00000000-0000-0000-0000-000000000001"),
        session_id=None,
        question="What is covered?",
        document_ids=[UUID("00000000-0000-0000-0000-000000000002")],
        retrieval=retrieval,
        verification=verification,
        answer=answer,
        error=None,
    )

    assert workflow_state["retrieval"] is retrieval
    assert workflow_state["verification"] is verification
    assert workflow_state["answer"] is answer


def test_run_qa_workflow_executes_agent_contracts_in_order(monkeypatch):
    agent_run_id = UUID("00000000-0000-0000-0000-000000000010")
    session_id = UUID("00000000-0000-0000-0000-000000000011")
    document_id = UUID("00000000-0000-0000-0000-000000000012")
    calls = []

    retrieval = RetrievalAgentOutput(question="What is covered?", candidates=[])
    verification = VerificationAgentOutput(
        verified_chunks=[],
        rejected_chunks=[],
        missing_information=True,
        confidence=0.0,
    )
    answer = AnswerAgentOutput(
        final_answer="The document does not provide enough information.",
        citations=[],
        reasoning_summary="Insufficient verified evidence.",
        confidence=0.0,
        self_check=AnswerSelfCheck(
            uses_only_verified_chunks=True,
            has_citation=False,
            has_unsupported_claims=False,
            is_ready=False,
        ),
    )

    def fake_retrieval(input_data):
        calls.append(("retrieval", input_data.model_dump()))
        assert input_data.agent_run_id == agent_run_id
        assert input_data.question == "What is covered?"
        assert input_data.document_ids == [document_id]
        return retrieval

    def fake_verification(input_data):
        calls.append(("verification", input_data.model_dump()))
        assert input_data.agent_run_id == agent_run_id
        assert input_data.question == "What is covered?"
        assert input_data.candidates == retrieval.candidates
        return verification

    def fake_answer(input_data):
        calls.append(("answer", input_data.model_dump()))
        assert input_data.agent_run_id == agent_run_id
        assert input_data.question == "What is covered?"
        assert input_data.verification is verification
        return answer

    monkeypatch.setattr(graph, "uuid4", lambda: agent_run_id)
    monkeypatch.setattr(graph, "run_retrieval_agent", fake_retrieval)
    monkeypatch.setattr(graph, "run_verification_agent", fake_verification)
    monkeypatch.setattr(graph, "run_answer_agent", fake_answer)

    state = graph.run_qa_workflow(
        "What is covered?",
        [document_id],
        session_id=session_id,
    )

    assert [call[0] for call in calls] == ["retrieval", "verification", "answer"]
    assert state["agent_run_id"] == agent_run_id
    assert state["session_id"] == session_id
    assert state["question"] == "What is covered?"
    assert state["document_ids"] == [document_id]
    assert state["retrieval"] is retrieval
    assert state["verification"] is verification
    assert state["answer"] is answer
    assert state["error"] is None


def test_qa_workflow_graph_is_compiled():
    assert hasattr(graph.qa_workflow_graph, "invoke")
