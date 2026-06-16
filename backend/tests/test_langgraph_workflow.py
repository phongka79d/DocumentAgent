import sys
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents import answer_agent, graph, retrieval_agent, verification_agent
from app.agents.prompts import (
    ANSWER_GENERATION_SYSTEM_PROMPT,
    ANSWER_GROUNDING_SYSTEM_PROMPT,
    EVIDENCE_COVERAGE_SYSTEM_PROMPT,
    VERIFICATION_AGENT_SYSTEM_PROMPT,
)
from app.agents.schemas import (
    AnswerAgentOutput,
    AnswerSelfCheck,
    Citation,
    RetrievalCandidate,
    RetrievalAgentOutput,
    VerifiedChunk,
    VerificationAgentOutput,
)
from app.schemas.retrieval import HybridRetrievalCandidate, HybridSearchResponse
from app.services import agent_log_service
from app.services import agent_run_service


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

    retrieval_candidate = RetrievalCandidate(
        chunk_id=UUID("00000000-0000-0000-0000-000000000013"),
        document_id=document_id,
        file_name="policy.pdf",
        content="The policy covers a two-month probation period.",
        page_number=4,
        section_title="Probation",
        semantic_similarity=0.91,
        graph_relevance=0.73,
        keyword_overlap=0.66,
        metadata_match=1.0,
        recency_or_position_score=0.85,
        final_score=0.83,
        retrieval_reason="Matched probation policy section.",
    )
    retrieval = RetrievalAgentOutput(
        question="What is covered?",
        candidates=[retrieval_candidate],
    )
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
        assert input_data.candidates[0].model_dump() == retrieval_candidate.model_dump()
        return verification

    def fake_answer(input_data):
        calls.append(("answer", input_data.model_dump()))
        assert input_data.agent_run_id == agent_run_id
        assert input_data.question == "What is covered?"
        assert input_data.verification is verification
        return answer

    create_run = Mock(return_value={"id": str(agent_run_id), "status": "running"})
    mark_success = Mock(return_value={"id": str(agent_run_id), "status": "success"})
    mark_failed = Mock()
    monkeypatch.setattr(
        graph.agent_run_service,
        "create_running_agent_run",
        create_run,
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_success",
        mark_success,
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_failed",
        mark_failed,
    )
    monkeypatch.setattr(graph, "run_retrieval_agent", fake_retrieval)
    monkeypatch.setattr(graph, "run_verification_agent", fake_verification)
    monkeypatch.setattr(graph, "run_answer_agent", fake_answer)

    result = graph.run_qa_workflow(
        "What is covered?",
        [document_id],
        session_id=session_id,
    )

    assert [call[0] for call in calls] == ["retrieval", "verification", "answer"]
    create_run.assert_called_once_with(
        session_id=session_id,
        question="What is covered?",
        document_ids=[document_id],
    )
    mark_success.assert_called_once_with(
        agent_run_id,
        final_answer=answer.final_answer,
        confidence=answer.confidence,
    )
    mark_failed.assert_not_called()
    assert result == {
        "answer": answer.final_answer,
        "confidence": answer.confidence,
        "citations": answer.citations,
        "agent_run_id": agent_run_id,
    }


def test_run_qa_workflow_uses_agent_3_output_as_final_answer(monkeypatch):
    agent_run_id = UUID("00000000-0000-0000-0000-000000000020")
    document_id = UUID("00000000-0000-0000-0000-000000000021")
    chunk_id = UUID("00000000-0000-0000-0000-000000000022")
    calls = []

    retrieval = RetrievalAgentOutput(question="When does probation end?", candidates=[])
    verification = VerificationAgentOutput(
        verified_chunks=[
            VerifiedChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                file_name="contract.pdf",
                quote="The probation period lasts two months.",
                page_number=2,
                verification_reason="Directly answers the probation duration.",
                supports_simple_reasoning=True,
            )
        ],
        rejected_chunks=[],
        missing_information=False,
        confidence=0.87,
    )
    self_check = AnswerSelfCheck(
        uses_only_verified_chunks=True,
        has_citation=True,
        has_unsupported_claims=False,
        is_ready=True,
    )
    answer = AnswerAgentOutput(
        final_answer="Agent 3 final answer after self-check.",
        citations=[
            Citation(
                file_name="contract.pdf",
                quote="The probation period lasts two months.",
            )
        ],
        reasoning_summary="Agent 3 used the verified chunk only.",
        confidence=0.82,
        self_check=self_check,
    )

    def fake_retrieval(input_data):
        calls.append("retrieval")
        return retrieval

    def fake_verification(input_data):
        calls.append("verification")
        return verification

    def fake_answer(input_data):
        calls.append("answer_self_check")
        assert input_data.agent_run_id == agent_run_id
        assert input_data.question == "When does probation end?"
        assert input_data.verification is verification
        return answer

    monkeypatch.setattr(
        graph.agent_run_service,
        "create_running_agent_run",
        Mock(return_value={"id": str(agent_run_id), "status": "running"}),
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_success",
        Mock(return_value={"id": str(agent_run_id), "status": "success"}),
    )
    monkeypatch.setattr(graph.agent_run_service, "mark_agent_run_failed", Mock())
    monkeypatch.setattr(graph, "run_retrieval_agent", fake_retrieval)
    monkeypatch.setattr(graph, "run_verification_agent", fake_verification)
    monkeypatch.setattr(graph, "run_answer_agent", fake_answer)

    result = graph.run_qa_workflow("When does probation end?", [document_id])

    assert calls == ["retrieval", "verification", "answer_self_check"]
    assert result["answer"] == "Agent 3 final answer after self-check."
    assert result["confidence"] == 0.82
    assert result["citations"] == answer.citations
    assert result["agent_run_id"] == agent_run_id


def test_run_qa_workflow_success_creates_run_logs_steps_and_returns_agent_3_answer(
    monkeypatch,
):
    agent_run_id = UUID("00000000-0000-0000-0000-000000000050")
    session_id = UUID("00000000-0000-0000-0000-000000000051")
    document_id = UUID("00000000-0000-0000-0000-000000000052")
    chunk_id = UUID("00000000-0000-0000-0000-000000000053")
    question = "When does probation end?"
    order = ["START"]

    retrieval_candidate = RetrievalCandidate(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name="contract.pdf",
        content="The probation period lasts two months.",
        page_number=2,
        section_title="Probation",
        semantic_similarity=0.91,
        graph_relevance=0.79,
        keyword_overlap=0.72,
        metadata_match=1.0,
        recency_or_position_score=0.85,
        final_score=0.86,
        retrieval_reason="Matched probation duration.",
    )
    retrieval = RetrievalAgentOutput(question=question, candidates=[retrieval_candidate])
    verified_chunk = VerifiedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name="contract.pdf",
        quote="The probation period lasts two months.",
        page_number=2,
        verification_reason="Direct answer to the question.",
        supports_simple_reasoning=True,
    )
    verification = VerificationAgentOutput(
        verified_chunks=[verified_chunk],
        rejected_chunks=[],
        missing_information=False,
        confidence=0.9,
    )
    answer = AnswerAgentOutput(
        final_answer="Agent 3 says probation ends after two months.",
        citations=[
            Citation(
                file_name="contract.pdf",
                quote="The probation period lasts two months.",
            )
        ],
        reasoning_summary="Answered only from Agent 2 verified evidence.",
        confidence=0.88,
        self_check=AnswerSelfCheck(
            uses_only_verified_chunks=True,
            has_citation=True,
            has_unsupported_claims=False,
            is_ready=True,
        ),
    )

    create_run = Mock(return_value={"id": str(agent_run_id), "status": "running"})
    mark_success = Mock(return_value={"id": str(agent_run_id), "status": "success"})
    mark_failed = Mock()
    log_step = Mock(
        side_effect=lambda step_name: order.append(f"log:{step_name}")
        or {"step_name": step_name, "status": "success"}
    )

    def fake_retrieval(input_data):
        order.append("Agent 1")
        assert input_data.agent_run_id == agent_run_id
        assert input_data.question == question
        assert input_data.document_ids == [document_id]
        log_step("agent_1_retrieval")
        return retrieval

    def fake_verification(input_data):
        order.append("Agent 2")
        assert input_data.agent_run_id == agent_run_id
        assert input_data.question == question
        assert input_data.candidates == retrieval.candidates
        log_step("agent_2_verification")
        return verification

    def fake_answer(input_data):
        order.append("Agent 3")
        assert input_data.agent_run_id == agent_run_id
        assert input_data.question == question
        assert input_data.verification is verification
        order.append("Self-check")
        assert answer.self_check.is_ready is True
        log_step("agent_3_answer_self_check")
        return answer

    monkeypatch.setattr(
        graph.agent_run_service,
        "create_running_agent_run",
        create_run,
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_success",
        mark_success,
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_failed",
        mark_failed,
    )
    monkeypatch.setattr(graph, "run_retrieval_agent", fake_retrieval)
    monkeypatch.setattr(graph, "run_verification_agent", fake_verification)
    monkeypatch.setattr(graph, "run_answer_agent", fake_answer)

    result = graph.run_qa_workflow(question, [document_id], session_id=session_id)
    order.append("FINAL")

    assert order == [
        "START",
        "Agent 1",
        "log:agent_1_retrieval",
        "Agent 2",
        "log:agent_2_verification",
        "Agent 3",
        "Self-check",
        "log:agent_3_answer_self_check",
        "FINAL",
    ]
    create_run.assert_called_once_with(
        session_id=session_id,
        question=question,
        document_ids=[document_id],
    )
    assert [call.args[0] for call in log_step.call_args_list] == [
        "agent_1_retrieval",
        "agent_2_verification",
        "agent_3_answer_self_check",
    ]
    mark_success.assert_called_once_with(
        agent_run_id,
        final_answer=answer.final_answer,
        confidence=answer.confidence,
    )
    mark_failed.assert_not_called()
    assert result == {
        "answer": answer.final_answer,
        "confidence": answer.confidence,
        "citations": answer.citations,
        "agent_run_id": agent_run_id,
    }


def test_run_qa_workflow_answers_multi_part_question_across_adjacent_chunks(
    monkeypatch,
):
    agent_run_id = UUID("00000000-0000-0000-0000-000000000070")
    document_id = UUID("00000000-0000-0000-0000-000000000071")
    anchor_chunk_id = UUID("00000000-0000-0000-0000-000000000072")
    adjacent_chunk_id = UUID("00000000-0000-0000-0000-000000000073")
    question = (
        "How was the meadow ceremony organized, who succeeded, and what prizes "
        "were distributed to the participants and host?"
    )
    anchor_quote = (
        "The meadow ceremony was organized by drawing a wide chalk circle on "
        "the grass; everyone started whenever they liked and stopped when the "
        "bell rang. Mira succeeded because she crossed the finish cord first."
    )
    adjacent_quote = (
        "After the result, each participant received a silver token, and the "
        "host received a blue ribbon."
    )
    final_answer = (
        "The ceremony was organized by drawing a wide chalk circle on the "
        "grass; everyone started whenever they liked and stopped when the bell "
        "rang. Mira succeeded because she crossed the finish cord first. Each "
        "participant received a silver token, and the host received a blue "
        "ribbon."
    )
    reasoning_summary = (
        "The first verified quote states the organization and winner. The "
        "second verified quote states both prize recipients."
    )
    logged_steps: dict[str, dict] = {}

    anchor_candidate = HybridRetrievalCandidate(
        chunk_id=anchor_chunk_id,
        document_id=document_id,
        file_name="ceremony-notes.txt",
        file_type="txt",
        content=anchor_quote,
        page_number=1,
        section_title="Ceremony",
        chunk_index=4,
        semantic_similarity=0.94,
        graph_relevance=0.2,
        keyword_overlap=0.8,
        metadata_match=1.0,
        recency_or_position_score=0.7,
        final_score=0.9,
        retrieval_reason="Matched ceremony organization and winner.",
    )
    hybrid_response = HybridSearchResponse(
        question=question,
        candidates=[anchor_candidate],
    )

    def fake_chunk_lookup(document_id_value: str, chunk_indexes: list[int]):
        assert document_id_value == str(document_id)
        assert chunk_indexes == [3, 5]
        return [
            {
                "id": str(adjacent_chunk_id),
                "chunk_index": 5,
                "content": adjacent_quote,
                "page_number": 1,
                "section_title": "Ceremony",
            }
        ]

    original_expand = retrieval_agent.retrieval_context_service.expand_retrieval_context

    def expand_with_fake_lookup(
        question_value,
        anchors,
        *,
        context_window,
        max_context_candidates,
    ):
        return original_expand(
            question_value,
            anchors,
            context_window=context_window,
            max_context_candidates=max_context_candidates,
            chunk_lookup=fake_chunk_lookup,
        )

    def fake_log_agent_step(**kwargs):
        logged_steps[kwargs["step_name"]] = {
            "input_payload": kwargs["input_payload"],
            "output_payload": kwargs["output_payload"],
            "status": kwargs["status"],
        }
        return {"id": f"{kwargs['step_name']}-log", "status": kwargs["status"]}

    def fake_try_log_agent_step(**kwargs):
        row = fake_log_agent_step(**kwargs)
        return agent_log_service.AgentStepLogAttempt(persisted=True, row=row)

    verification_payload = {
        "verified_chunks": [
            {
                "chunk_id": str(anchor_chunk_id),
                "document_id": str(document_id),
                "file_name": "ceremony-notes.txt",
                "quote": anchor_quote,
                "page_number": 1,
                "verification_reason": "Covers organization and winner.",
                "supports_simple_reasoning": True,
            },
            {
                "chunk_id": str(adjacent_chunk_id),
                "document_id": str(document_id),
                "file_name": "ceremony-notes.txt",
                "quote": adjacent_quote,
                "page_number": 1,
                "verification_reason": "Covers the distributed prizes.",
                "supports_simple_reasoning": True,
            },
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.88,
    }
    coverage_evidence = [
        {
            "chunk_id": str(anchor_chunk_id),
            "quote": anchor_quote,
            "purpose": "Shows how the ceremony was organized and who succeeded.",
            "supports_simple_reasoning": True,
        },
        {
            "chunk_id": str(adjacent_chunk_id),
            "quote": adjacent_quote,
            "purpose": "Shows the prizes for participants and the host.",
            "supports_simple_reasoning": True,
        },
    ]
    coverage_payload = {
        "answers_question": True,
        "missing_information": False,
        "requirements": [
            {
                "requirement": "Identify how the ceremony was organized.",
                "satisfied": True,
                "evidence": [coverage_evidence[0]],
            },
            {
                "requirement": "Identify who succeeded.",
                "satisfied": True,
                "evidence": [coverage_evidence[0]],
            },
            {
                "requirement": "Identify participant prizes.",
                "satisfied": True,
                "evidence": [coverage_evidence[1]],
            },
            {
                "requirement": "Identify the host prize.",
                "satisfied": True,
                "evidence": [coverage_evidence[1]],
            },
        ],
        "selected_evidence": coverage_evidence,
        "confidence": 0.86,
    }
    answer_payload = {
        "final_answer": final_answer,
        "citations": [
            {"file_name": "ceremony-notes.txt", "quote": anchor_quote},
            {"file_name": "ceremony-notes.txt", "quote": adjacent_quote},
        ],
        "reasoning_summary": reasoning_summary,
        "confidence": 0.84,
    }
    grounding_payload = {
        "answers_question": True,
        "field_reviews": [
            {
                "field_name": "final_answer",
                "text": final_answer,
                "claims": [
                    {
                        "claim": (
                            "The ceremony was organized by drawing a wide "
                            "chalk circle on the grass; everyone started "
                            "whenever they liked and stopped when the bell "
                            "rang."
                        ),
                        "supported": True,
                        "supporting_citations": [
                            {"file_name": "ceremony-notes.txt", "quote": anchor_quote}
                        ],
                    },
                    {
                        "claim": (
                            "Mira succeeded because she crossed the finish "
                            "cord first."
                        ),
                        "supported": True,
                        "supporting_citations": [
                            {"file_name": "ceremony-notes.txt", "quote": anchor_quote}
                        ],
                    },
                    {
                        "claim": "Each participant received a silver token",
                        "supported": True,
                        "supporting_citations": [
                            {
                                "file_name": "ceremony-notes.txt",
                                "quote": adjacent_quote,
                            }
                        ],
                    },
                    {
                        "claim": "the host received a blue ribbon",
                        "supported": True,
                        "supporting_citations": [
                            {
                                "file_name": "ceremony-notes.txt",
                                "quote": adjacent_quote,
                            }
                        ],
                    },
                ],
            },
            {
                "field_name": "reasoning_summary",
                "text": reasoning_summary,
                "claims": [
                    {
                        "claim": (
                            "The first verified quote states the organization "
                            "and winner."
                        ),
                        "supported": True,
                        "supporting_citations": [
                            {"file_name": "ceremony-notes.txt", "quote": anchor_quote}
                        ],
                    },
                    {
                        "claim": (
                            "The second verified quote states both prize "
                            "recipients."
                        ),
                        "supported": True,
                        "supporting_citations": [
                            {
                                "file_name": "ceremony-notes.txt",
                                "quote": adjacent_quote,
                            }
                        ],
                    },
                ],
            },
        ],
        "confidence": 0.83,
    }

    def fake_chat_completion(messages, *, response_format):
        assert response_format == {"type": "json_object"}
        system_prompt = messages[0]["content"]
        if system_prompt == VERIFICATION_AGENT_SYSTEM_PROMPT:
            return json.dumps(verification_payload)
        if system_prompt == EVIDENCE_COVERAGE_SYSTEM_PROMPT:
            return json.dumps(coverage_payload)
        if system_prompt == ANSWER_GENERATION_SYSTEM_PROMPT:
            return json.dumps(answer_payload)
        if system_prompt == ANSWER_GROUNDING_SYSTEM_PROMPT:
            return json.dumps(grounding_payload)
        raise AssertionError(f"Unexpected system prompt: {system_prompt}")

    monkeypatch.setattr(
        graph.agent_run_service,
        "create_running_agent_run",
        Mock(return_value={"id": str(agent_run_id), "status": "running"}),
    )
    mark_success = Mock(return_value={"id": str(agent_run_id), "status": "success"})
    mark_failed = Mock()
    monkeypatch.setattr(graph.agent_run_service, "mark_agent_run_success", mark_success)
    monkeypatch.setattr(graph.agent_run_service, "mark_agent_run_failed", mark_failed)
    monkeypatch.setattr(
        retrieval_agent,
        "get_settings",
        lambda: SimpleNamespace(
            retrieval_final_top_k=1,
            retrieval_context_window=1,
            retrieval_context_max_candidates=4,
        ),
    )
    monkeypatch.setattr(
        retrieval_agent.hybrid_retrieval_service,
        "retrieve_hybrid",
        Mock(return_value=hybrid_response),
    )
    monkeypatch.setattr(
        retrieval_agent.retrieval_context_service,
        "expand_retrieval_context",
        expand_with_fake_lookup,
    )
    monkeypatch.setattr(
        retrieval_agent.agent_log_service,
        "log_agent_step",
        fake_log_agent_step,
    )
    monkeypatch.setattr(
        verification_agent.agent_log_service,
        "try_log_agent_step",
        fake_try_log_agent_step,
    )
    monkeypatch.setattr(
        answer_agent.agent_log_service,
        "try_log_agent_step",
        fake_try_log_agent_step,
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )
    monkeypatch.setattr(
        answer_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    result = graph.run_qa_workflow(question, [document_id])

    retrieval_output = logged_steps["agent_1_retrieval"]["output_payload"]
    assert {
        candidate["chunk_index"] for candidate in retrieval_output["candidates"]
    } == {4, 5}
    assert {
        UUID(candidate["chunk_id"]) for candidate in retrieval_output["candidates"]
    } == {anchor_chunk_id, adjacent_chunk_id}
    assert all("content" not in candidate for candidate in retrieval_output["candidates"])
    assert all("content_preview" in candidate for candidate in retrieval_output["candidates"])
    verification_output = logged_steps["agent_2_verification"]["output_payload"]
    assert verification_output.missing_information is False
    assert [chunk.quote for chunk in verification_output.verified_chunks] == [
        anchor_quote,
        adjacent_quote,
    ]
    assert {
        chunk.verification_reason for chunk in verification_output.verified_chunks
    } == {
        "Shows how the ceremony was organized and who succeeded.",
        "Shows the prizes for participants and the host.",
    }
    assert result["answer"] == final_answer
    assert result["confidence"] == 0.83
    assert [citation.quote for citation in result["citations"]] == [
        anchor_quote,
        adjacent_quote,
    ]
    assert result["agent_run_id"] == agent_run_id
    answer_log = logged_steps["agent_3_answer_self_check"]["output_payload"]
    assert answer_log["self_check_result"]["is_ready"] is True
    mark_success.assert_called_once_with(
        agent_run_id,
        final_answer=final_answer,
        confidence=0.83,
    )
    mark_failed.assert_not_called()


def test_run_qa_workflow_marks_success_for_insufficient_evidence(monkeypatch):
    agent_run_id = UUID("00000000-0000-0000-0000-000000000040")
    document_id = UUID("00000000-0000-0000-0000-000000000041")
    question = "What is the renewal policy?"

    retrieval = RetrievalAgentOutput(question=question, candidates=[])
    verification = VerificationAgentOutput(
        verified_chunks=[],
        rejected_chunks=[],
        missing_information=True,
        confidence=0.0,
    )
    answer = AnswerAgentOutput(
        final_answer="The document does not provide enough information to answer.",
        citations=[],
        reasoning_summary="Agent 2 found insufficient verified evidence.",
        confidence=0.0,
        self_check=AnswerSelfCheck(
            uses_only_verified_chunks=True,
            has_citation=False,
            has_unsupported_claims=False,
            is_ready=False,
        ),
    )

    create_run = Mock(return_value={"id": str(agent_run_id), "status": "running"})
    mark_success = Mock(return_value={"id": str(agent_run_id), "status": "success"})
    mark_failed = Mock()

    def fake_retrieval(input_data):
        return retrieval

    def fake_verification(input_data):
        return verification

    def fake_answer(input_data):
        assert input_data.agent_run_id == agent_run_id
        assert input_data.question == question
        assert input_data.verification is verification
        assert input_data.verification.missing_information is True
        return answer

    monkeypatch.setattr(
        graph.agent_run_service,
        "create_running_agent_run",
        create_run,
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_success",
        mark_success,
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_failed",
        mark_failed,
    )
    monkeypatch.setattr(graph, "run_retrieval_agent", fake_retrieval)
    monkeypatch.setattr(graph, "run_verification_agent", fake_verification)
    monkeypatch.setattr(graph, "run_answer_agent", fake_answer)

    result = graph.run_qa_workflow(question, [document_id])

    assert "does not provide enough information" in result["answer"]
    assert result == {
        "answer": answer.final_answer,
        "confidence": 0.0,
        "citations": [],
        "agent_run_id": agent_run_id,
    }
    mark_success.assert_called_once_with(
        agent_run_id,
        final_answer=answer.final_answer,
        confidence=answer.confidence,
    )
    mark_failed.assert_not_called()


def test_run_qa_workflow_marks_success_when_grounding_exhaustion_returns_insufficient(
    monkeypatch,
):
    agent_run_id = UUID("00000000-0000-0000-0000-000000000042")
    document_id = UUID("00000000-0000-0000-0000-000000000043")
    question = "What happened and what result followed?"

    retrieval = RetrievalAgentOutput(question=question, candidates=[])
    verification = VerificationAgentOutput(
        verified_chunks=[
            VerifiedChunk(
                chunk_id=UUID("00000000-0000-0000-0000-000000000044"),
                document_id=document_id,
                file_name="event.txt",
                quote="The event was organized in a circle.",
                page_number=1,
                verification_reason="Partially answers the question.",
            )
        ],
        rejected_chunks=[],
        missing_information=False,
        confidence=0.8,
    )
    answer = AnswerAgentOutput(
        final_answer="The current documents do not provide enough verified evidence.",
        citations=[],
        reasoning_summary="Agent 3 grounding exhausted the available verified evidence.",
        confidence=0.0,
        self_check=AnswerSelfCheck(
            uses_only_verified_chunks=True,
            has_citation=False,
            has_unsupported_claims=False,
            is_ready=False,
        ),
    )

    create_run = Mock(return_value={"id": str(agent_run_id), "status": "running"})
    mark_success = Mock(return_value={"id": str(agent_run_id), "status": "success"})
    mark_failed = Mock()

    monkeypatch.setattr(
        graph.agent_run_service,
        "create_running_agent_run",
        create_run,
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_success",
        mark_success,
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_failed",
        mark_failed,
    )
    monkeypatch.setattr(graph, "run_retrieval_agent", Mock(return_value=retrieval))
    monkeypatch.setattr(graph, "run_verification_agent", Mock(return_value=verification))
    monkeypatch.setattr(graph, "run_answer_agent", Mock(return_value=answer))

    result = graph.run_qa_workflow(question, [document_id])

    assert result == {
        "answer": answer.final_answer,
        "confidence": 0.0,
        "citations": [],
        "agent_run_id": agent_run_id,
    }
    mark_success.assert_called_once_with(
        agent_run_id,
        final_answer=answer.final_answer,
        confidence=answer.confidence,
    )
    mark_failed.assert_not_called()


def _assert_run_qa_workflow_marks_created_run_failed_on_agent_error(
    monkeypatch,
    failing_agent,
):
    agent_run_id = UUID("00000000-0000-0000-0000-000000000030")
    document_id = UUID("00000000-0000-0000-0000-000000000031")
    create_run = Mock(return_value={"id": str(agent_run_id), "status": "running"})
    mark_success = Mock()
    mark_failed = Mock(return_value={"id": str(agent_run_id), "status": "failed"})
    retrieval = RetrievalAgentOutput(question="What is covered?", candidates=[])
    verification = VerificationAgentOutput(
        verified_chunks=[],
        rejected_chunks=[],
        missing_information=True,
        confidence=0.0,
    )

    def fail_retrieval(input_data):
        raise RuntimeError("raw provider secret")

    def fake_retrieval(input_data):
        return retrieval

    def fail_verification(input_data):
        raise RuntimeError("raw provider secret")

    def fake_verification(input_data):
        return verification

    def fail_answer(input_data):
        raise RuntimeError("raw provider secret")

    monkeypatch.setattr(
        graph.agent_run_service,
        "create_running_agent_run",
        create_run,
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_success",
        mark_success,
    )
    monkeypatch.setattr(
        graph.agent_run_service,
        "mark_agent_run_failed",
        mark_failed,
    )
    monkeypatch.setattr(
        graph,
        "run_retrieval_agent",
        fail_retrieval if failing_agent == "agent_1" else fake_retrieval,
    )
    monkeypatch.setattr(
        graph,
        "run_verification_agent",
        fail_verification if failing_agent == "agent_2" else fake_verification,
    )
    monkeypatch.setattr(
        graph,
        "run_answer_agent",
        fail_answer if failing_agent == "agent_3" else Mock(),
    )

    with pytest.raises(agent_run_service.AgentRunWorkflowError) as exc_info:
        graph.run_qa_workflow("What is covered?", [document_id])

    assert str(exc_info.value) == agent_run_service.SAFE_AGENT_RUN_FAILURE_MESSAGE
    assert "provider secret" not in str(exc_info.value).lower()
    create_run.assert_called_once_with(
        session_id=None,
        question="What is covered?",
        document_ids=[document_id],
    )
    mark_success.assert_not_called()
    mark_failed.assert_called_once()
    assert mark_failed.call_args.args == (agent_run_id,)
    assert isinstance(mark_failed.call_args.kwargs["error"], RuntimeError)
    assert mark_failed.return_value["status"] == "failed"


def test_run_qa_workflow_marks_created_run_failed_on_agent_1_error(monkeypatch):
    _assert_run_qa_workflow_marks_created_run_failed_on_agent_error(
        monkeypatch,
        "agent_1",
    )


def test_run_qa_workflow_marks_created_run_failed_on_agent_2_error(monkeypatch):
    _assert_run_qa_workflow_marks_created_run_failed_on_agent_error(
        monkeypatch,
        "agent_2",
    )


def test_run_qa_workflow_marks_created_run_failed_on_agent_3_error(monkeypatch):
    _assert_run_qa_workflow_marks_created_run_failed_on_agent_error(
        monkeypatch,
        "agent_3",
    )


def test_qa_workflow_graph_is_compiled_in_required_order():
    assert hasattr(graph.qa_workflow_graph, "invoke")

    compiled_graph = graph.qa_workflow_graph.get_graph()
    edge_order = [(edge.source, edge.target) for edge in compiled_graph.edges]

    assert edge_order == [
        (graph.START, "agent_1_retrieval"),
        ("agent_1_retrieval", "agent_2_verification"),
        ("agent_2_verification", "agent_3_answer_self_check"),
        ("agent_3_answer_self_check", graph.END),
    ]
