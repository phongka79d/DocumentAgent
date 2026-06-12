"""LangGraph contract for the backend QA workflow."""

from collections.abc import Sequence
from typing import TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.agents.schemas import (
    AnswerAgentInput,
    AnswerAgentOutput,
    Citation,
    RetrievalAgentInput,
    RetrievalAgentOutput,
    VerificationAgentInput,
    VerificationAgentOutput,
)

from app.agents.answer_agent import run_answer_agent
from app.agents.retrieval_agent import run_retrieval_agent
from app.agents.verification_agent import run_verification_agent
from app.services import agent_run_service


class QAWorkflowState(TypedDict):
    agent_run_id: UUID
    session_id: UUID | None
    question: str
    document_ids: list[UUID]
    retrieval: RetrievalAgentOutput | None
    verification: VerificationAgentOutput | None
    answer: AnswerAgentOutput | None
    error: str | None


class QAWorkflowResult(TypedDict):
    answer: str
    confidence: float
    citations: list[Citation]
    agent_run_id: UUID


def _coerce_uuid(value: UUID | str) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _coerce_optional_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    return _coerce_uuid(value)


def _build_initial_state(
    question: str,
    document_ids: Sequence[UUID | str],
    session_id: UUID | str | None,
    agent_run_id: UUID | str,
) -> QAWorkflowState:
    return {
        "agent_run_id": _coerce_uuid(agent_run_id),
        "session_id": _coerce_optional_uuid(session_id),
        "question": question,
        "document_ids": [_coerce_uuid(document_id) for document_id in document_ids],
        "retrieval": None,
        "verification": None,
        "answer": None,
        "error": None,
    }


def _agent_1_retrieval(state: QAWorkflowState) -> dict[str, RetrievalAgentOutput]:
    retrieval_input = RetrievalAgentInput(
        agent_run_id=state["agent_run_id"],
        question=state["question"],
        document_ids=state["document_ids"],
    )
    return {"retrieval": run_retrieval_agent(retrieval_input)}


def _agent_2_verification(state: QAWorkflowState) -> dict[str, VerificationAgentOutput]:
    if state["retrieval"] is None:
        raise ValueError("retrieval output is required before verification")

    verification_input = VerificationAgentInput(
        agent_run_id=state["agent_run_id"],
        question=state["question"],
        candidates=state["retrieval"].candidates,
    )
    return {"verification": run_verification_agent(verification_input)}


def _agent_3_answer_self_check(state: QAWorkflowState) -> dict[str, AnswerAgentOutput]:
    if state["verification"] is None:
        raise ValueError("verification output is required before answer generation")

    answer_input = AnswerAgentInput(
        agent_run_id=state["agent_run_id"],
        question=state["question"],
        verification=state["verification"],
    )
    return {"answer": run_answer_agent(answer_input)}


def _build_qa_workflow_graph():
    workflow = StateGraph(QAWorkflowState)
    workflow.add_node("agent_1_retrieval", _agent_1_retrieval)
    workflow.add_node("agent_2_verification", _agent_2_verification)
    workflow.add_node("agent_3_answer_self_check", _agent_3_answer_self_check)
    workflow.add_edge(START, "agent_1_retrieval")
    workflow.add_edge("agent_1_retrieval", "agent_2_verification")
    workflow.add_edge("agent_2_verification", "agent_3_answer_self_check")
    workflow.add_edge("agent_3_answer_self_check", END)
    return workflow.compile()


qa_workflow_graph = _build_qa_workflow_graph()


def _agent_run_id_from_row(agent_run: dict) -> UUID:
    return _coerce_uuid(agent_run["id"])


def _answer_from_state(state: QAWorkflowState) -> AnswerAgentOutput:
    answer = state["answer"]
    if answer is None:
        raise ValueError("workflow did not produce an answer")
    return answer


def _mark_failed_after_run_creation(
    agent_run_id: UUID,
    error: BaseException,
) -> None:
    agent_run_service.mark_agent_run_failed(agent_run_id, error=error)


def run_qa_workflow(
    question: str,
    document_ids: Sequence[UUID | str],
    session_id: UUID | str | None = None,
) -> QAWorkflowResult:
    agent_run = agent_run_service.create_running_agent_run(
        session_id=session_id,
        question=question,
        document_ids=document_ids,
    )
    agent_run_id = _agent_run_id_from_row(agent_run)

    try:
        initial_state = _build_initial_state(
            question,
            document_ids,
            session_id,
            agent_run_id,
        )
        final_state = cast(QAWorkflowState, qa_workflow_graph.invoke(initial_state))
        answer = _answer_from_state(final_state)
    except Exception as exc:
        _mark_failed_after_run_creation(agent_run_id, exc)
        raise agent_run_service.AgentRunWorkflowError(exc) from exc

    try:
        agent_run_service.mark_agent_run_success(
            agent_run_id,
            final_answer=answer.final_answer,
            confidence=answer.confidence,
        )
    except Exception as exc:
        _mark_failed_after_run_creation(agent_run_id, exc)
        raise

    return {
        "answer": answer.final_answer,
        "confidence": answer.confidence,
        "citations": answer.citations,
        "agent_run_id": agent_run_id,
    }


__all__ = [
    "END",
    "QAWorkflowResult",
    "QAWorkflowState",
    "START",
    "StateGraph",
    "qa_workflow_graph",
    "run_answer_agent",
    "run_qa_workflow",
    "run_retrieval_agent",
    "run_verification_agent",
]
