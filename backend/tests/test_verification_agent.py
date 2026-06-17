import json
import logging
import sys
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.prompts import (
    VERIFICATION_AGENT_OUTPUT_KEYS,
    VERIFICATION_AGENT_SYSTEM_PROMPT,
)
from app.agents.schemas import (
    EvidenceCoverageRequirement,
    EvidenceCoverageReview,
    EvidenceCoverageSelection,
    VerificationAgentInput,
    VerificationAgentOutput,
)
from app.agents import verification_agent
from app.agents.verification_agent import VerificationAgentError, run_verification_agent
from app.core.config import Settings
from app.services import agent_log_service, verification_prompt_service


AGENT_RUN_ID = "11111111-1111-1111-1111-111111111111"
CANDIDATE_CHUNK_ID = "22222222-2222-2222-2222-222222222222"
CANDIDATE_DOCUMENT_ID = "33333333-3333-3333-3333-333333333333"
SECOND_CANDIDATE_CHUNK_ID = "44444444-4444-4444-4444-444444444444"
REAL_RUN_COVERAGE_REVIEW = verification_agent._run_coverage_review


def _coverage_selection(
    *,
    chunk_id: str = CANDIDATE_CHUNK_ID,
    quote: str = "Probation starts on June 1, 2026 and lasts two months.",
    purpose: str = "States the requested probation details.",
    supports_simple_reasoning: bool = False,
) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "quote": quote,
        "purpose": purpose,
        "supports_simple_reasoning": supports_simple_reasoning,
    }


def _with_coverage_requirements(
    payload: dict[str, object],
) -> dict[str, object]:
    if "requirements" in payload:
        return payload

    enriched = dict(payload)
    if payload["answers_question"] is True:
        enriched["requirements"] = [
            {
                "requirement": "Answer every requested part of the question.",
                "satisfied": True,
                "evidence": list(payload["selected_evidence"]),
                "missing_detail": None,
            }
        ]
    else:
        enriched["requirements"] = [
            {
                "requirement": "Answer every requested part of the question.",
                "satisfied": False,
                "evidence": [],
                "missing_detail": "Required evidence is missing.",
            }
        ]
    return enriched


def test_evidence_coverage_review_requires_selected_evidence_when_answerable() -> None:
    with pytest.raises(ValidationError):
        EvidenceCoverageReview.model_validate(
            _with_coverage_requirements({
                "answers_question": True,
                "missing_information": False,
                "selected_evidence": [],
                "confidence": 0.9,
            })
        )


def test_evidence_coverage_review_rejects_selected_evidence_when_not_answerable(
) -> None:
    with pytest.raises(ValidationError):
        EvidenceCoverageReview.model_validate(
            _with_coverage_requirements({
                "answers_question": False,
                "missing_information": True,
                "selected_evidence": [
                    {
                        "chunk_id": CANDIDATE_CHUNK_ID,
                        "quote": "The jar was empty.",
                        "purpose": "States what was inside the jar.",
                        "supports_simple_reasoning": False,
                    }
                ],
                "confidence": 0.0,
            })
        )


def test_coverage_requirement_requires_evidence_when_satisfied() -> None:
    with pytest.raises(ValidationError):
        EvidenceCoverageRequirement.model_validate(
            {
                "requirement": "State what participants received.",
                "satisfied": True,
                "evidence": [],
                "missing_detail": None,
            }
        )


def test_coverage_requirement_requires_missing_detail_when_unsatisfied() -> None:
    with pytest.raises(ValidationError):
        EvidenceCoverageRequirement.model_validate(
            {
                "requirement": "State what participants received.",
                "satisfied": False,
                "evidence": [],
                "missing_detail": "   ",
            }
        )


def test_evidence_coverage_review_rejects_answerable_with_unsatisfied_requirement(
) -> None:
    selection = _coverage_selection()

    with pytest.raises(ValidationError):
        EvidenceCoverageReview.model_validate(
            {
                "answers_question": True,
                "missing_information": False,
                "requirements": [
                    {
                        "requirement": "State when probation starts.",
                        "satisfied": True,
                        "evidence": [selection],
                        "missing_detail": None,
                    },
                    {
                        "requirement": "State when probation ends.",
                        "satisfied": False,
                        "evidence": [],
                        "missing_detail": "The end date is not provided.",
                    },
                ],
                "selected_evidence": [selection],
                "confidence": 0.8,
            }
        )


def test_evidence_coverage_review_requires_selected_union_of_requirement_evidence(
) -> None:
    first = _coverage_selection()
    second = _coverage_selection(
        chunk_id=SECOND_CANDIDATE_CHUNK_ID,
        quote="Official employment begins after probation.",
        purpose="States what follows probation.",
    )

    with pytest.raises(ValidationError):
        EvidenceCoverageReview.model_validate(
            {
                "answers_question": True,
                "missing_information": False,
                "requirements": [
                    {
                        "requirement": "State the probation details.",
                        "satisfied": True,
                        "evidence": [first],
                        "missing_detail": None,
                    },
                    {
                        "requirement": "State what follows probation.",
                        "satisfied": True,
                        "evidence": [second],
                        "missing_detail": None,
                    },
                ],
                "selected_evidence": [first],
                "confidence": 0.9,
            }
        )


def test_verified_chunk_defaults_missing_simple_reasoning_permission_to_false(
) -> None:
    output = verification_agent._parse_verification_output(
        json.dumps(
            {
                "verified_chunks": [
                    {
                        "chunk_id": CANDIDATE_CHUNK_ID,
                        "document_id": CANDIDATE_DOCUMENT_ID,
                        "file_name": "alice-in-wonderland.txt",
                        "quote": "The jar was empty.",
                        "page_number": 0,
                        "verification_reason": "Direct evidence.",
                    }
                ],
                "rejected_chunks": [],
                "missing_information": False,
                "confidence": 0.9,
            }
        )
    )

    assert output.verified_chunks[0].supports_simple_reasoning is False


def test_verification_agent_preserves_chunk_index_on_verified_chunks() -> None:
    candidate = _candidate_payload(chunk_index=7)
    input_data = VerificationAgentInput.model_validate(
        _verification_input_payload(candidates=[candidate])
    )
    output = VerificationAgentOutput.model_validate(
        {
            "verified_chunks": [
                {
                    "chunk_id": CANDIDATE_CHUNK_ID,
                    "document_id": CANDIDATE_DOCUMENT_ID,
                    "file_name": "contract.pdf",
                    "quote": "probation starts on june 1, 2026 and lasts two months.",
                    "page_number": 3,
                    "verification_reason": "Direct evidence.",
                    "supports_simple_reasoning": True,
                }
            ],
            "rejected_chunks": [],
            "missing_information": False,
            "confidence": 0.9,
        }
    )

    validated = verification_agent._validate_candidate_quotes(output, input_data)

    assert validated.verified_chunks[0].chunk_index == 7
    assert validated.verified_chunks[0].quote == candidate["content"]


def test_parse_coverage_review_normalizes_non_answerable_minimal_payload() -> None:
    review = verification_agent._parse_coverage_review(
        '{"answers_question": false, "missing_information": true}'
    )

    assert review.answers_question is False
    assert review.missing_information is True
    assert review.selected_evidence == []
    assert len(review.requirements) == 1
    assert review.requirements[0].satisfied is False
    assert review.confidence == 0.0


@pytest.fixture(autouse=True)
def _disable_verification_agent_log_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_log_service,
        "log_agent_step",
        Mock(return_value={"id": "step-id"}),
    )


@pytest.fixture(autouse=True)
def _default_coverage_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def passthrough_review(
        input_data,
        verification_output,
    ) -> EvidenceCoverageReview:
        del input_data
        selections = [
            EvidenceCoverageSelection(
                chunk_id=chunk.chunk_id,
                quote=chunk.quote,
                purpose=chunk.verification_reason,
                supports_simple_reasoning=chunk.supports_simple_reasoning,
            )
            for chunk in verification_output.verified_chunks
        ]
        is_answerable = (
            bool(selections) and not verification_output.missing_information
        )
        return EvidenceCoverageReview(
            answers_question=is_answerable,
            missing_information=not is_answerable,
            requirements=[
                EvidenceCoverageRequirement(
                    requirement="Answer every requested part of the question.",
                    satisfied=is_answerable,
                    evidence=selections if is_answerable else [],
                    missing_detail=(
                        None if is_answerable else "Required evidence is missing."
                    ),
                )
            ],
            selected_evidence=selections,
            confidence=verification_output.confidence,
        )

    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        passthrough_review,
    )


@pytest.fixture(autouse=True)
def _disable_optimizer_llm_for_verification_agent_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deterministic_optimizer(
        *,
        question,
        candidates,
        max_candidates,
        snippet_max_chars,
        context_sentences,
    ):
        del question, context_sentences
        return [
            candidate.model_copy(
                update={
                    "content": (
                        None
                        if candidate.content is None
                        else candidate.content[:snippet_max_chars].rstrip()
                    )
                }
            )
            for candidate in candidates[:max_candidates]
        ]

    monkeypatch.setattr(
        verification_prompt_service,
        "optimize_candidates_for_verification",
        deterministic_optimizer,
    )


def _verification_output_payload(confidence: float) -> dict[str, object]:
    return {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": confidence,
    }


def _candidate_payload(**overrides: object) -> dict[str, object]:
    payload = {
        "chunk_id": CANDIDATE_CHUNK_ID,
        "document_id": CANDIDATE_DOCUMENT_ID,
        "file_name": "contract.pdf",
        "content": "Probation starts on June 1, 2026 and lasts two months.",
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
    payload.update(overrides)
    return payload


def _second_candidate_payload() -> dict[str, object]:
    payload = _candidate_payload()
    payload["chunk_id"] = SECOND_CANDIDATE_CHUNK_ID
    payload["final_score"] = 0.89
    return payload


def _verification_input_payload(
    *,
    candidates: list[dict[str, object]] | None = None,
    question: str = "What does the document say about probation?",
) -> dict[str, object]:
    return {
        "agent_run_id": AGENT_RUN_ID,
        "question": question,
        "candidates": candidates if candidates is not None else [_candidate_payload()],
    }


def test_verification_prompt_uses_compact_candidates_but_quote_validation_uses_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_quote = "The warranty lasts two years after purchase."
    long_content = (
        "Unrelated start. "
        f"{source_quote} "
        + "Unrelated end. " * 200
    )
    input_data = VerificationAgentInput.model_validate(
        _verification_input_payload(
            question="How long does the warranty last?",
            candidates=[_candidate_payload(content=long_content)],
        )
    )
    monkeypatch.setattr(
        verification_agent,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            agent_evidence_snippet_max_chars=120,
        ),
    )

    messages = verification_agent._build_verification_messages(input_data)
    prompt = messages[1]["content"]

    assert source_quote in prompt
    assert len(prompt) < len(long_content)

    output = VerificationAgentOutput.model_validate(
        {
            "verified_chunks": [
                {
                    "chunk_id": CANDIDATE_CHUNK_ID,
                    "document_id": CANDIDATE_DOCUMENT_ID,
                    "file_name": "contract.pdf",
                    "quote": source_quote,
                    "page_number": 3,
                    "verification_reason": "Direct warranty evidence.",
                }
            ],
            "rejected_chunks": [],
            "missing_information": False,
            "confidence": 0.9,
        }
    )

    validated = verification_agent._validate_candidate_quotes(output, input_data)

    assert validated.verified_chunks[0].quote == source_quote


def test_coverage_prompt_uses_compact_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_quote = "The warranty lasts two years after purchase."
    long_content = (
        "Unrelated start. "
        f"{source_quote} "
        + "Unrelated end. " * 200
    )
    input_data = VerificationAgentInput.model_validate(
        _verification_input_payload(
            question="How long does the warranty last?",
            candidates=[_candidate_payload(content=long_content)],
        )
    )
    monkeypatch.setattr(
        verification_agent,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            agent_evidence_snippet_max_chars=120,
        ),
    )

    messages = verification_agent._build_coverage_messages(input_data)
    prompt = messages[1]["content"]

    assert source_quote in prompt
    assert len(prompt) < len(long_content)


def test_coverage_prompt_uses_configured_candidate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        _candidate_payload(
            chunk_id=UUID(f"22222222-2222-4222-8222-{index:012d}"),
            content=f"Candidate {index} has unique evidence.",
        )
        for index in range(12)
    ]
    input_data = VerificationAgentInput.model_validate(
        _verification_input_payload(candidates=candidates)
    )
    monkeypatch.setattr(
        verification_agent,
        "get_settings",
        lambda: Settings(_env_file=None, agent_coverage_max_candidates=6),
    )

    messages = verification_agent._build_coverage_messages(input_data)
    prompt = messages[1]["content"]

    assert "Candidate 0" in prompt
    assert "Candidate 5" in prompt
    assert "Candidate 6" not in prompt


def test_verification_prompt_uses_configured_candidate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        _candidate_payload(
            chunk_id=UUID(f"22222222-2222-4222-8222-{index:012d}"),
            content=f"Candidate {index} has unique evidence.",
        )
        for index in range(12)
    ]
    input_data = VerificationAgentInput.model_validate(
        _verification_input_payload(candidates=candidates)
    )
    monkeypatch.setattr(
        verification_agent,
        "get_settings",
        lambda: Settings(_env_file=None, agent_verification_max_candidates=5),
    )

    messages = verification_agent._build_verification_messages(input_data)
    prompt = messages[1]["content"]

    assert "Candidate 0" in prompt
    assert "Candidate 4" in prompt
    assert "Candidate 5" not in prompt


def test_verification_payload_diagnostics_log_safe_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_source = "Sensitive warranty source text should stay out of logs."
    input_data = VerificationAgentInput.model_validate(
        _verification_input_payload(
            candidates=[_candidate_payload(content=sensitive_source)]
        )
    )
    monkeypatch.setattr(
        verification_agent,
        "get_settings",
        lambda: Settings(_env_file=None, agent_llm_payload_warn_chars=1),
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        Mock(
            side_effect=[
                "not-json",
                json.dumps(
                    {
                        "verified_chunks": [],
                        "rejected_chunks": [],
                        "missing_information": True,
                        "confidence": 0.0,
                    }
                ),
            ]
        ),
    )

    with caplog.at_level(logging.INFO, logger=verification_agent.__name__):
        verification_agent._run_initial_verification(input_data)

    assert "LLM payload prepared." in caplog.text
    assert "agent=verification_agent" in caplog.text
    assert "phase=initial_verification" in caplog.text
    assert "candidate_count=1" in caplog.text
    assert "retry=False" in caplog.text
    assert "retry=True" in caplog.text
    assert "message_chars=" in caplog.text
    assert sensitive_source not in caplog.text
    assert "private-shopaikey-value" not in caplog.text


def test_agent_2_prompt_size_is_reduced_for_long_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_candidates = [
        _candidate_payload(
            chunk_id=UUID(f"22222222-2222-4222-8222-{index:012d}"),
            content=("Noise sentence. " * 300) + "Refund lasts 30 days.",
        )
        for index in range(12)
    ]
    input_data = VerificationAgentInput.model_validate(
        _verification_input_payload(
            question="How long does the refund last?",
            candidates=long_candidates,
        )
    )
    monkeypatch.setattr(
        verification_agent,
        "get_settings",
        lambda: Settings(_env_file=None),
    )

    messages = verification_agent._build_verification_messages(input_data)
    prompt_chars = sum(len(message["content"]) for message in messages)

    assert prompt_chars < 30000


def _mock_two_pass_verification(
    monkeypatch: pytest.MonkeyPatch,
    initial_verification: dict[str, object],
    coverage_review: dict[str, object],
) -> Mock:
    chat_completion = Mock(
        side_effect=[
            json.dumps(initial_verification),
            json.dumps(_with_coverage_requirements(coverage_review)),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )
    return chat_completion


def test_verification_agent_retries_inconsistent_coverage_review_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["file_name"] = "alice-in-wonderland.txt"
    candidate["content"] = (
        "She took down a jar from one of the shelves as she passed; "
        "it was labelled 'ORANGE MARMALADE', but to her great "
        "disappointment it was empty."
    )
    answer_quote = (
        "it was labelled 'ORANGE MARMALADE', but to her great "
        "disappointment it was empty."
    )
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "alice-in-wonderland.txt",
                "quote": answer_quote,
                "page_number": 0,
                "verification_reason": "Directly answers both requested details.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 1.0,
    }
    selected_evidence = [
        {
            "chunk_id": CANDIDATE_CHUNK_ID,
            "quote": answer_quote,
            "purpose": "States the jar label and that the jar was empty.",
            "supports_simple_reasoning": False,
        }
    ]
    inconsistent_review = _with_coverage_requirements({
        "answers_question": False,
        "missing_information": True,
        "selected_evidence": selected_evidence,
        "confidence": 0.0,
    })
    corrected_review = _with_coverage_requirements({
        "answers_question": True,
        "missing_information": False,
        "selected_evidence": selected_evidence,
        "confidence": 0.95,
    })
    chat_completion = Mock(
        side_effect=[
            json.dumps(initial_verification),
            json.dumps(inconsistent_review),
            json.dumps(corrected_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": (
                "What was the label on the jar, and what was inside it?"
            ),
            "candidates": [candidate],
        }
    )

    assert output.missing_information is False
    assert [chunk.quote for chunk in output.verified_chunks] == [answer_quote]
    assert chat_completion.call_count == 3


def test_verification_agent_fails_after_second_inconsistent_coverage_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026 and lasts two months.",
                "page_number": 3,
                "verification_reason": "Direct answer.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.9,
    }
    inconsistent_review = _with_coverage_requirements({
        "answers_question": False,
        "missing_information": True,
        "selected_evidence": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": "Probation starts on June 1, 2026 and lasts two months.",
                "purpose": "States the requested probation details.",
                "supports_simple_reasoning": False,
            }
        ],
        "confidence": 0.0,
    })
    chat_completion = Mock(
        side_effect=[
            json.dumps(initial_verification),
            json.dumps(inconsistent_review),
            json.dumps(inconsistent_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    with pytest.raises(VerificationAgentError):
        run_verification_agent(
            {
                "agent_run_id": AGENT_RUN_ID,
                "question": "When does probation start and how long does it last?",
                "candidates": [_candidate_payload()],
            }
        )

    assert chat_completion.call_count == 3


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
    chat_completion = Mock(side_effect=AssertionError("ShopAIKey must not be called"))

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
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
    chat_completion.assert_not_called()


def test_verification_agent_logs_success_for_empty_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_agent_step = Mock(return_value={"id": "empty-step-id"})
    monkeypatch.setattr(
        agent_log_service,
        "log_agent_step",
        log_agent_step,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When can I start?",
            "candidates": [],
        }
    )

    assert output.model_dump() == {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": True,
        "confidence": 0.0,
    }
    log_agent_step.assert_called_once()
    log_call = log_agent_step.call_args.kwargs
    assert log_call["agent_run_id"] == AGENT_RUN_ID
    assert log_call["step_name"] == verification_agent.AGENT_2_VERIFICATION_STEP_NAME
    assert log_call["agent_name"] == verification_agent.VERIFICATION_AGENT_NAME
    assert log_call["status"] == "success"
    assert log_call["input_payload"] == {
        "agent_run_id": AGENT_RUN_ID,
        "question": "When can I start?",
        "candidates": [],
    }
    assert log_call["output_payload"].model_dump(mode="json") == {
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
    assert CANDIDATE_DOCUMENT_ID in user_payload
    assert "contract.pdf" in user_payload
    assert "Probation starts on June 1, 2026 and lasts two months." in user_payload
    assert "semantic_similarity" not in user_payload
    assert "retrieval_reason" not in user_payload
    assert '\n  "question"' not in user_payload
    compact_payload = json.loads(user_payload.splitlines()[-1])
    assert compact_payload["question"] == "When does probation start?"
    assert compact_payload["evidence"][0] == {
        "chunk_id": CANDIDATE_CHUNK_ID,
        "document_id": CANDIDATE_DOCUMENT_ID,
        "file_name": "contract.pdf",
        "page_number": 3,
        "section_title": "Probation",
        "score": 0.91,
        "content": (
            "Probation starts on June 1, 2026 and lasts two months."
        ),
    }


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


def test_verification_agent_accepts_direct_answer_and_rejects_weak_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct_candidate = _candidate_payload()
    direct_candidate["content"] = (
        "The official work start date is August 1, 2026 after the employee "
        "completes a two-month probation period."
    )
    weak_candidate = _second_candidate_payload()
    weak_candidate["content"] = (
        "Employees should follow office etiquette and keep their work area tidy."
    )

    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "The official work start date is August 1, 2026 after the employee completes a two-month probation period.",
              "page_number": 3,
              "verification_reason": "This chunk directly states the official work start date and the probation period.",
              "supports_simple_reasoning": false
            }
          ],
          "rejected_chunks": [
            {
              "chunk_id": "44444444-4444-4444-4444-444444444444",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Employees should follow office etiquette and keep their work area tidy.",
              "rejection_reason": "This chunk is only loosely related to employment and does not mention the official work start date or probation duration."
            }
          ],
          "missing_information": false,
          "confidence": 0.86
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
            "question": "When does official work start after probation?",
            "candidates": [direct_candidate, weak_candidate],
        }
    )

    output_payload = output.model_dump(mode="json")
    assert output_payload == {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": (
                    "The official work start date is August 1, 2026 after "
                    "the employee completes a two-month probation period."
                ),
                "page_number": 3,
                "chunk_index": 5,
                "verification_reason": (
                    "This chunk directly states the official work start date "
                    "and the probation period."
                ),
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [
            {
                "chunk_id": SECOND_CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": (
                    "Employees should follow office etiquette and keep their "
                    "work area tidy."
                ),
                "rejection_reason": (
                    "This chunk is only loosely related to employment and "
                    "does not mention the official work start date or "
                    "probation duration."
                ),
            }
        ],
        "missing_information": False,
        "confidence": 0.86,
    }
    assert SECOND_CANDIDATE_CHUNK_ID not in {
        chunk["chunk_id"] for chunk in output_payload["verified_chunks"]
    }


def test_verification_agent_logs_success_with_final_verification_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_agent_step = Mock(return_value={"id": "step-id"})
    monkeypatch.setattr(
        agent_log_service,
        "log_agent_step",
        log_agent_step,
    )

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
          "rejected_chunks": [
            {
              "chunk_id": "44444444-4444-4444-4444-444444444444",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "rejection_reason": "Duplicate evidence."
            }
          ],
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
            "candidates": [_candidate_payload(), _second_candidate_payload()],
        }
    )

    assert len(output.verified_chunks) == 1
    assert len(output.rejected_chunks) == 1
    log_agent_step.assert_called_once()
    log_call = log_agent_step.call_args.kwargs
    assert log_call["agent_run_id"] == AGENT_RUN_ID
    assert log_call["step_name"] == verification_agent.AGENT_2_VERIFICATION_STEP_NAME
    assert log_call["agent_name"] == verification_agent.VERIFICATION_AGENT_NAME
    assert log_call["status"] == "success"
    assert log_call["input_payload"] == {
        "agent_run_id": AGENT_RUN_ID,
        "question": "When does probation start?",
        "candidates": [
            {
                **{
                    key: value
                    for key, value in _candidate_payload().items()
                    if key != "content"
                },
                "content_preview": (
                    "Probation starts on June 1, 2026 and lasts two months."
                ),
                "content_char_count": len(
                    "Probation starts on June 1, 2026 and lasts two months."
                ),
                "content_omitted": False,
            },
            {
                **{
                    key: value
                    for key, value in _second_candidate_payload().items()
                    if key != "content"
                },
                "content_preview": (
                    "Probation starts on June 1, 2026 and lasts two months."
                ),
                "content_char_count": len(
                    "Probation starts on June 1, 2026 and lasts two months."
                ),
                "content_omitted": False,
            },
        ],
    }
    assert log_call["output_payload"].model_dump(mode="json") == {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026 and lasts two months.",
                "page_number": 3,
                "chunk_index": 5,
                "verification_reason": (
                    "This chunk states the probation start and duration."
                ),
                "supports_simple_reasoning": True,
            }
        ],
        "rejected_chunks": [
            {
                "chunk_id": SECOND_CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026 and lasts two months.",
                "rejection_reason": "Duplicate evidence.",
            }
        ],
        "missing_information": False,
        "confidence": 0.82,
    }


def test_verification_agent_logs_compact_candidate_input_without_mutating_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_agent_step = Mock(return_value={"id": "step-id"})
    monkeypatch.setattr(
        agent_log_service,
        "log_agent_step",
        log_agent_step,
    )
    long_content = (
        "Probation starts on June 1, 2026 and lasts two months. "
        + "Additional source detail. " * 120
    )

    def fake_chat_completion(messages, response_format=None):
        return json.dumps(
            {
                "verified_chunks": [
                    {
                        "chunk_id": CANDIDATE_CHUNK_ID,
                        "document_id": CANDIDATE_DOCUMENT_ID,
                        "file_name": "contract.pdf",
                        "quote": "Probation starts on June 1, 2026 and lasts two months.",
                        "page_number": 3,
                        "verification_reason": "This chunk states the probation start and duration.",
                        "supports_simple_reasoning": True,
                    }
                ],
                "rejected_chunks": [],
                "missing_information": False,
                "confidence": 0.82,
            }
        )

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload(content=long_content)],
        }
    )

    assert output.verified_chunks[0].quote == (
        "Probation starts on June 1, 2026 and lasts two months."
    )
    log_agent_step.assert_called_once()
    log_input = log_agent_step.call_args.kwargs["input_payload"]
    assert log_input["agent_run_id"] == AGENT_RUN_ID
    assert log_input["question"] == "When does probation start?"
    assert len(log_input["candidates"]) == 1
    logged_candidate = log_input["candidates"][0]
    assert "content" not in logged_candidate
    assert logged_candidate["content_preview"] == long_content[:500]
    assert logged_candidate["content_char_count"] == len(long_content)
    assert logged_candidate["content_omitted"] is True
    assert logged_candidate["chunk_id"] == CANDIDATE_CHUNK_ID
    assert logged_candidate["final_score"] == 0.91
    assert long_content not in str(log_input)


def test_verification_agent_warns_when_success_log_insert_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_attempt = agent_log_service.AgentStepLogAttempt(
        persisted=False,
        row=None,
        persistence_error=agent_log_service.AgentLogPersistenceError(
            step_name=verification_agent.AGENT_2_VERIFICATION_STEP_NAME,
            agent_name=verification_agent.VERIFICATION_AGENT_NAME,
            status="success",
        ),
    )
    try_log_agent_step = Mock(return_value=log_attempt)
    logger_warning = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    monkeypatch.setattr(verification_agent.logger, "warning", logger_warning)

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
    try_log_agent_step.assert_called_once()
    logger_warning.assert_called_once_with(
        "Agent 2 step log persistence failed for %s::%s [%s].",
        verification_agent.VERIFICATION_AGENT_NAME,
        verification_agent.AGENT_2_VERIFICATION_STEP_NAME,
        "success",
    )
    assert "Probation starts on June 1, 2026" not in str(logger_warning.call_args)


def test_verification_agent_rejects_invalid_llm_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

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

    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["agent_run_id"] == AGENT_RUN_ID
    assert log_call["step_name"] == verification_agent.AGENT_2_VERIFICATION_STEP_NAME
    assert log_call["agent_name"] == verification_agent.VERIFICATION_AGENT_NAME
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == verification_agent.VERIFICATION_FAILURE_MESSAGE
    assert log_call["input_payload"] == {
        "agent_run_id": AGENT_RUN_ID,
        "question": "When does probation start?",
        "candidate_count": 1,
        "candidate_chunk_ids": [CANDIDATE_CHUNK_ID],
    }
    assert log_call["output_payload"] == {
        "error": {
            "type": "invalid_json",
            "message": verification_agent.VERIFICATION_FAILURE_MESSAGE,
        }
    }
    assert "Here is the JSON" not in str(log_call)
    assert "Probation starts on June 1, 2026" not in str(log_call)


def test_verification_agent_preserves_failure_when_failed_log_insert_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_attempt = agent_log_service.AgentStepLogAttempt(
        persisted=False,
        row=None,
        persistence_error=agent_log_service.AgentLogPersistenceError(
            step_name=verification_agent.AGENT_2_VERIFICATION_STEP_NAME,
            agent_name=verification_agent.VERIFICATION_AGENT_NAME,
            status="failed",
            error_message=verification_agent.VERIFICATION_FAILURE_MESSAGE,
        ),
    )
    try_log_agent_step = Mock(return_value=log_attempt)
    logger_warning = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    monkeypatch.setattr(verification_agent.logger, "warning", logger_warning)

    def fake_chat_completion(messages, response_format=None):
        return "raw invalid JSON with provider internal detail"

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

    try_log_agent_step.assert_called_once()
    assert (
        (
            "Agent 2 step log persistence failed for %s::%s [%s].",
            verification_agent.VERIFICATION_AGENT_NAME,
            verification_agent.AGENT_2_VERIFICATION_STEP_NAME,
            "failed",
        ),
        {},
    ) in logger_warning.call_args_list
    assert "raw invalid JSON" not in str(logger_warning.call_args)
    assert "Probation starts on June 1, 2026" not in str(logger_warning.call_args)


def test_verification_agent_logs_failed_step_for_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    def fake_chat_completion(messages, response_format=None):
        raise verification_agent.shopaikey_service.ShopAIKeyServiceError(
            "provider raw secret detail"
        )

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

    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == verification_agent.VERIFICATION_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": "provider_error",
            "message": verification_agent.VERIFICATION_FAILURE_MESSAGE,
        }
    }
    assert "provider raw secret detail" not in str(log_call)
    assert "Probation starts on June 1, 2026" not in str(log_call)


def test_verification_agent_rejects_llm_schema_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

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

    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == verification_agent.VERIFICATION_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": "schema_validation_error",
            "message": verification_agent.VERIFICATION_FAILURE_MESSAGE,
        }
    }
    assert "missing_information" not in str(log_call)
    assert "Probation starts on June 1, 2026" not in str(log_call)


def test_verification_agent_rejects_out_of_range_llm_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

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

    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == verification_agent.VERIFICATION_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": "schema_validation_error",
            "message": verification_agent.VERIFICATION_FAILURE_MESSAGE,
        }
    }
    assert "1.5" not in str(log_call)
    assert "Probation starts on June 1, 2026" not in str(log_call)


@pytest.mark.parametrize("chunk_list_name", ["verified_chunks", "rejected_chunks"])
def test_verification_agent_rejects_unknown_returned_chunk_ids(
    monkeypatch: pytest.MonkeyPatch,
    chunk_list_name: str,
) -> None:
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )

    unknown_chunk_id = "44444444-4444-4444-4444-444444444444"
    response_payload: dict[str, object] = {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.5,
    }
    if chunk_list_name == "verified_chunks":
        response_payload[chunk_list_name] = [
            {
                "chunk_id": unknown_chunk_id,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026.",
                "page_number": 3,
                "verification_reason": "States the requested date.",
                "supports_simple_reasoning": False,
            }
        ]
    else:
        response_payload[chunk_list_name] = [
            {
                "chunk_id": unknown_chunk_id,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "This chunk is unrelated.",
                "rejection_reason": "Does not answer the question.",
            }
        ]

    def fake_chat_completion(messages, response_format=None):
        return json.dumps(response_payload)

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

    try_log_agent_step.assert_called_once()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["status"] == "failed"
    assert log_call["error_message"] == verification_agent.VERIFICATION_FAILURE_MESSAGE
    assert log_call["output_payload"] == {
        "error": {
            "type": "unknown_chunk_id",
            "message": verification_agent.VERIFICATION_FAILURE_MESSAGE,
        }
    }
    assert unknown_chunk_id not in str(log_call)
    assert "Probation starts on June 1, 2026" not in str(log_call)


def test_verification_agent_retries_unknown_returned_chunk_id_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unknown_chunk_id = "55555555-5555-5555-5555-555555555555"
    invalid_response = {
        "verified_chunks": [
            {
                "chunk_id": unknown_chunk_id,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026 and lasts two months.",
                "page_number": 3,
                "verification_reason": "States the requested date.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.5,
    }
    corrected_response = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026 and lasts two months.",
                "page_number": 3,
                "verification_reason": "States the requested date.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.8,
    }
    chat_completion = Mock(
        side_effect=[json.dumps(invalid_response), json.dumps(corrected_response)]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert output.missing_information is False
    assert [str(chunk.chunk_id) for chunk in output.verified_chunks] == [
        CANDIDATE_CHUNK_ID
    ]
    assert chat_completion.call_count == 2
    retry_messages = chat_completion.call_args_list[1].args[0]
    assert "unknown_chunk_id" in retry_messages[-1]["content"]
    assert unknown_chunk_id not in retry_messages[-1]["content"]


def test_verification_agent_keeps_verified_quote_found_in_candidate_content(
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

    assert len(output.verified_chunks) == 1
    assert output.verified_chunks[0].quote == (
        "Probation starts on June 1, 2026 and lasts two months."
    )
    assert output.rejected_chunks == []


def test_verification_agent_accepts_quote_with_whitespace_variation(
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
              "quote": "Probation starts on June 1, 2026\\n   and lasts two months.",
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

    assert len(output.verified_chunks) == 1
    assert output.verified_chunks[0].quote == _candidate_payload()["content"]
    assert output.rejected_chunks == []


def test_verification_agent_moves_fabricated_verified_quote_to_rejected_chunks(
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
              "quote": "Probation starts on May 1, 2026 and lasts six months.",
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

    assert output.verified_chunks == []
    assert len(output.rejected_chunks) == 1
    assert output.rejected_chunks[0].chunk_id.hex == CANDIDATE_CHUNK_ID.replace("-", "")
    assert output.rejected_chunks[0].quote == (
        "Probation starts on June 1, 2026 and lasts two months."
    )
    assert (
        "Quote was not found in source candidate content."
        in output.rejected_chunks[0].rejection_reason
    )


def test_verification_agent_corrects_fabricated_rejected_quote_to_source_excerpt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [],
          "rejected_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "The office closes on Fridays.",
              "rejection_reason": "Does not answer the probation question."
            }
          ],
          "missing_information": true,
          "confidence": 0.1
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

    assert output.verified_chunks == []
    assert len(output.rejected_chunks) == 1
    assert output.rejected_chunks[0].quote == (
        "Probation starts on June 1, 2026 and lasts two months."
    )
    assert output.rejected_chunks[0].rejection_reason == (
        "Does not answer the probation question."
    )


def test_verification_agent_marks_missing_information_when_no_verified_chunks_remain(
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
              "quote": "Probation starts on May 1, 2026 and lasts six months.",
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

    assert output.verified_chunks == []
    assert len(output.rejected_chunks) == 1
    assert output.missing_information is True
    assert output.confidence == verification_agent.NO_VERIFIED_CHUNKS_CONFIDENCE_CAP


def test_verification_agent_filters_duplicate_verified_chunk_ids(
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
            },
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This is a repeated verified copy.",
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

    assert len(output.verified_chunks) == 1
    assert output.verified_chunks[0].chunk_id.hex == CANDIDATE_CHUNK_ID.replace("-", "")
    assert output.rejected_chunks == []


def test_verification_agent_keeps_distinct_verified_quotes_from_same_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["content"] = (
        "The item is not mine. I keep these items to sell and own none myself."
    )

    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "The item is not mine.",
              "page_number": 3,
              "verification_reason": "This states that the item is not owned.",
              "supports_simple_reasoning": false
            },
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "I keep these items to sell and own none myself.",
              "page_number": 3,
              "verification_reason": "This explains why the item is not owned.",
              "supports_simple_reasoning": true
            }
          ],
          "rejected_chunks": [],
          "missing_information": false,
          "confidence": 0.92
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
            "question": "Why is the item not theirs?",
            "candidates": [candidate],
        }
    )

    assert [chunk.quote for chunk in output.verified_chunks] == [
        "The item is not mine.",
        "I keep these items to sell and own none myself.",
    ]
    assert output.rejected_chunks == []


def test_verification_agent_filters_duplicate_verified_content_across_chunk_ids(
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
            },
            {
              "chunk_id": "44444444-4444-4444-4444-444444444444",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on June 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This duplicate content states the same facts.",
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
            "candidates": [_candidate_payload(), _second_candidate_payload()],
        }
    )

    assert [chunk.chunk_id.hex for chunk in output.verified_chunks] == [
        CANDIDATE_CHUNK_ID.replace("-", "")
    ]
    assert len(output.rejected_chunks) == 1
    assert output.rejected_chunks[0].chunk_id.hex == SECOND_CANDIDATE_CHUNK_ID.replace(
        "-",
        "",
    )
    assert (
        "Duplicate verified content"
        in output.rejected_chunks[0].rejection_reason
    )


def test_verification_agent_marks_missing_information_for_conflicting_verified_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_candidate = _second_candidate_payload()
    second_candidate["content"] = (
        "Probation starts on July 1, 2026 and lasts two months."
    )

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
              "verification_reason": "This chunk states the probation start date.",
              "supports_simple_reasoning": true
            },
            {
              "chunk_id": "44444444-4444-4444-4444-444444444444",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "Probation starts on July 1, 2026 and lasts two months.",
              "page_number": 3,
              "verification_reason": "This chunk states a different probation start date.",
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
            "candidates": [_candidate_payload(), second_candidate],
        }
    )

    assert len(output.verified_chunks) == 2
    assert output.missing_information is True
    assert output.confidence < 0.82
    assert 0.0 <= output.confidence <= 1.0
    assert any(
        "contradict" in chunk.verification_reason.lower()
        for chunk in output.verified_chunks
    )


def test_verification_agent_marks_missing_information_for_incompatible_short_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_candidate = _candidate_payload()
    first_candidate["content"] = "The employee is eligible for official work."
    second_candidate = _second_candidate_payload()
    second_candidate["content"] = "The employee is not eligible for official work."

    def fake_chat_completion(messages, response_format=None):
        return """
        {
          "verified_chunks": [
            {
              "chunk_id": "22222222-2222-2222-2222-222222222222",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "The employee is eligible for official work.",
              "page_number": 3,
              "verification_reason": "This chunk states eligibility.",
              "supports_simple_reasoning": false
            },
            {
              "chunk_id": "44444444-4444-4444-4444-444444444444",
              "document_id": "33333333-3333-3333-3333-333333333333",
              "file_name": "contract.pdf",
              "quote": "The employee is not eligible for official work.",
              "page_number": 3,
              "verification_reason": "This chunk states ineligibility.",
              "supports_simple_reasoning": false
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
            "question": "Is the employee eligible for official work?",
            "candidates": [first_candidate, second_candidate],
        }
    )

    assert output.missing_information is True
    assert output.confidence < 0.82
    assert any(
        "contradict" in chunk.verification_reason.lower()
        for chunk in output.verified_chunks
    )


def test_verification_agent_final_output_serializes_with_exact_top_level_keys(
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

    def add_internal_helper_metadata(output):
        payload = output.model_dump()
        payload["internal_reasons"] = ["post-processing diagnostic metadata"]
        return payload

    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_apply_missing_information_adjustments",
        add_internal_helper_metadata,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start?",
            "candidates": [_candidate_payload()],
        }
    )

    assert isinstance(output, VerificationAgentOutput)
    assert list(output.model_dump().keys()) == [
        "verified_chunks",
        "rejected_chunks",
        "missing_information",
        "confidence",
    ]


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
        "interpretive questions",
        "what a person means",
        "surrounding context",
        "simple interpretation",
        "loosely related",
        "duplicated",
        "contradicted",
        "unclear",
        "wrong document",
        "missing_information",
        "guessing beyond the document",
    ]:
        assert phrase in prompt


def test_verification_prompt_requires_explanatory_evidence_for_why_and_how_questions(
) -> None:
    prompt = VERIFICATION_AGENT_SYSTEM_PROMPT.lower()

    for phrase in [
        "questions asking why or how",
        "merely repeats",
        "cause, reason, mechanism, or surrounding context",
        "same chunk_id",
        "distinct useful excerpts",
        "collectively answer the exact question",
    ]:
        assert phrase in prompt


def test_evidence_coverage_prompt_contains_required_output_schema() -> None:
    prompt = verification_agent.EVIDENCE_COVERAGE_SYSTEM_PROMPT

    for phrase in [
        '"answers_question"',
        '"missing_information"',
        '"requirements"',
        '"requirement"',
        '"satisfied"',
        '"evidence"',
        '"missing_detail"',
        '"selected_evidence"',
        '"chunk_id"',
        '"quote"',
        '"purpose"',
        '"supports_simple_reasoning"',
        '"confidence"',
    ]:
        assert phrase in prompt


def test_evidence_coverage_prompt_requires_consistent_answerability_fields() -> None:
    prompt = verification_agent.EVIDENCE_COVERAGE_SYSTEM_PROMPT.lower()

    for phrase in [
        "selected_evidence must not be empty",
        "selected_evidence must be an empty list",
        '"answers_question": true',
        '"missing_information": false',
    ]:
        assert phrase in prompt


def test_evidence_coverage_prompt_requires_every_requested_part() -> None:
    prompt = verification_agent.EVIDENCE_COVERAGE_SYSTEM_PROMPT.lower()

    for phrase in [
        "independently requested",
        "every requirement",
        "if any requirement is missing",
        "exact substring",
    ]:
        assert phrase in prompt


def test_evidence_coverage_prompt_does_not_require_incidental_scene_setting() -> None:
    prompt = verification_agent.EVIDENCE_COVERAGE_SYSTEM_PROMPT.lower()

    for phrase in [
        "incidental scene-setting",
        "use it only to identify the relevant event",
        "do not mark the answer missing solely because",
        "unless the user explicitly asks to verify that premise",
    ]:
        assert phrase in prompt


def test_verification_prompt_limits_agent_scope() -> None:
    prompt = VERIFICATION_AGENT_SYSTEM_PROMPT.lower()

    assert "evaluate only the provided agent 1 candidate chunks" in prompt
    assert "do not retrieve more chunks" in prompt
    assert "generate a final answer" in prompt
    assert "user-facing citations" in prompt


def test_verification_agent_marks_multi_part_question_missing_when_one_requirement_is_unsatisfied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_candidate = _candidate_payload()
    first_candidate["content"] = (
        "The coordinator arranged the activity in a circle and declared "
        "everyone a winner."
    )
    initial_verification = {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": True,
        "confidence": 0.5,
    }
    first_selection = _coverage_selection(
        quote="The coordinator arranged the activity in a circle",
        purpose="States how the activity was organized.",
    )
    coverage_review = {
        "answers_question": False,
        "missing_information": True,
        "requirements": [
            {
                "requirement": "Explain how the activity was organized.",
                "satisfied": True,
                "evidence": [first_selection],
                "missing_detail": None,
            },
            {
                "requirement": "State what participants received.",
                "satisfied": False,
                "evidence": [],
                "missing_detail": "The participant item is not in the candidates.",
            },
        ],
        "selected_evidence": [],
        "confidence": 0.2,
    }
    _mock_two_pass_verification(
        monkeypatch,
        initial_verification,
        coverage_review,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": (
                "How was the activity organized, who won, and what did "
                "participants receive?"
            ),
            "candidates": [first_candidate],
        }
    )

    assert output.missing_information is True
    assert output.confidence <= verification_agent.COVERAGE_FAILURE_CONFIDENCE_CAP


def test_verification_agent_accepts_complete_multi_part_cross_chunk_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_candidate = _candidate_payload()
    first_candidate["content"] = (
        "The coordinator arranged the activity in a circle. "
        "Every participant won."
    )
    second_candidate = _second_candidate_payload()
    second_candidate["content"] = (
        "Each participant received a token, while the coordinator received "
        "a badge."
    )
    first_selection = _coverage_selection(
        quote="The coordinator arranged the activity in a circle.",
        purpose="States how the activity was organized.",
    )
    winner_selection = _coverage_selection(
        quote="Every participant won.",
        purpose="States who won.",
    )
    participant_selection = _coverage_selection(
        chunk_id=SECOND_CANDIDATE_CHUNK_ID,
        quote="Each participant received a token",
        purpose="States the participant prize.",
    )
    coordinator_selection = _coverage_selection(
        chunk_id=SECOND_CANDIDATE_CHUNK_ID,
        quote="the coordinator received a badge.",
        purpose="States the coordinator prize.",
    )
    selected_evidence = [
        first_selection,
        winner_selection,
        participant_selection,
        coordinator_selection,
    ]
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "requirements": [
            {
                "requirement": "Explain how the activity was organized.",
                "satisfied": True,
                "evidence": [first_selection],
                "missing_detail": None,
            },
            {
                "requirement": "State who won.",
                "satisfied": True,
                "evidence": [winner_selection],
                "missing_detail": None,
            },
            {
                "requirement": "State what participants received.",
                "satisfied": True,
                "evidence": [participant_selection],
                "missing_detail": None,
            },
            {
                "requirement": "State what the coordinator received.",
                "satisfied": True,
                "evidence": [coordinator_selection],
                "missing_detail": None,
            },
        ],
        "selected_evidence": selected_evidence,
        "confidence": 0.9,
    }
    _mock_two_pass_verification(
        monkeypatch,
        {
            "verified_chunks": [],
            "rejected_chunks": [],
            "missing_information": True,
            "confidence": 0.9,
        },
        coverage_review,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": (
                "How was the activity organized, who won, and what did "
                "participants and the coordinator receive?"
            ),
            "candidates": [first_candidate, second_candidate],
        }
    )

    assert output.missing_information is False
    assert output.confidence == 0.9
    assert [chunk.quote for chunk in output.verified_chunks] == [
        selection["quote"] for selection in selected_evidence
    ]


def test_verification_agent_preserves_low_confidence_for_answerable_verified_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["file_name"] = "alice-in-wonderland.txt"
    candidate["content"] = (
        "Alice wondered whether she had changed in the night. "
        "She said she could not be Mabel because she knew many things, "
        "then tested multiplication, geography, and a recitation."
    )
    selected = _coverage_selection(
        quote="then tested multiplication, geography, and a recitation.",
        purpose="States the tests Alice used to verify her identity.",
    )
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "alice-in-wonderland.txt",
                "quote": selected["quote"],
                "page_number": 0,
                "verification_reason": selected["purpose"],
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.0,
    }
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "requirements": [
            {
                "requirement": "Explain Alice's identity test.",
                "satisfied": True,
                "evidence": [selected],
                "missing_detail": None,
            }
        ],
        "selected_evidence": [selected],
        "confidence": 0.0,
    }
    _mock_two_pass_verification(monkeypatch, initial_verification, coverage_review)

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "What tests did Alice use to verify her identity?",
            "candidates": [candidate],
        }
    )

    assert output.missing_information is False
    assert output.verified_chunks
    assert output.confidence == 0.0


def test_verification_agent_reassigns_coverage_selection_to_unique_matching_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_candidate = _candidate_payload()
    first_candidate["content"] = "The activity began in a marked circle."
    second_candidate = _second_candidate_payload()
    second_candidate["content"] = "Each participant received a token."
    first_selection = _coverage_selection(
        quote="The activity began in a marked circle.",
        purpose="States how the activity began.",
    )
    wrong_chunk_selection = _coverage_selection(
        chunk_id=CANDIDATE_CHUNK_ID,
        quote="Each participant received a token.",
        purpose="States the participant prize.",
    )
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "requirements": [
            {
                "requirement": "Explain how the activity began.",
                "satisfied": True,
                "evidence": [first_selection],
                "missing_detail": None,
            },
            {
                "requirement": "State what participants received.",
                "satisfied": True,
                "evidence": [wrong_chunk_selection],
                "missing_detail": None,
            },
        ],
        "selected_evidence": [first_selection, wrong_chunk_selection],
        "confidence": 0.9,
    }
    chat_completion = Mock(
        side_effect=[
            json.dumps(
                {
                    "verified_chunks": [],
                    "rejected_chunks": [],
                    "missing_information": True,
                    "confidence": 0.9,
                }
            ),
            json.dumps(_with_coverage_requirements(coverage_review)),
            json.dumps(_with_coverage_requirements(coverage_review)),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "How did the activity begin, and what did participants receive?",
            "candidates": [first_candidate, second_candidate],
        }
    )

    assert output.missing_information is False
    assert [(chunk.chunk_id.hex, chunk.quote) for chunk in output.verified_chunks] == [
        (
            CANDIDATE_CHUNK_ID.replace("-", ""),
            "The activity began in a marked circle.",
        ),
        (
            SECOND_CANDIDATE_CHUNK_ID.replace("-", ""),
            "Each participant received a token.",
        ),
    ]
    assert chat_completion.call_count == 2


def test_verification_agent_ignores_redundant_non_selected_requirement_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["content"] = "The activity began in a marked circle."
    valid_selection = _coverage_selection(
        quote="The activity began in a marked circle.",
        purpose="States how the activity began.",
    )
    redundant_selection = _coverage_selection(
        quote="The activity began [...] in a marked circle.",
        purpose="Redundant malformed quote.",
    )
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "requirements": [
            {
                "requirement": "Explain how the activity began.",
                "satisfied": True,
                "evidence": [valid_selection, redundant_selection],
                "missing_detail": None,
            }
        ],
        "selected_evidence": [valid_selection],
        "confidence": 0.9,
    }
    chat_completion = Mock(
        side_effect=[
            json.dumps(
                {
                    "verified_chunks": [],
                    "rejected_chunks": [],
                    "missing_information": True,
                    "confidence": 0.9,
                }
            ),
            json.dumps(coverage_review),
            json.dumps(coverage_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "How did the activity begin?",
            "candidates": [candidate],
        }
    )

    assert output.missing_information is False
    assert [chunk.quote for chunk in output.verified_chunks] == [
        "The activity began in a marked circle."
    ]
    assert chat_completion.call_count == 2


def test_verification_agent_rebuilds_selected_evidence_from_requirements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_candidate = _candidate_payload()
    first_candidate["content"] = "The activity began in a marked circle."
    second_candidate = _second_candidate_payload()
    second_candidate["content"] = "Each participant received a token."
    first_selection = _coverage_selection(
        quote="The activity began in a marked circle.",
        purpose="States how the activity began.",
    )
    second_selection = _coverage_selection(
        chunk_id=SECOND_CANDIDATE_CHUNK_ID,
        quote="Each participant received a token.",
        purpose="States the participant prize.",
    )
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "requirements": [
            {
                "requirement": "Explain how the activity began.",
                "satisfied": True,
                "evidence": [first_selection],
                "missing_detail": None,
            },
            {
                "requirement": "State what participants received.",
                "satisfied": True,
                "evidence": [second_selection],
                "missing_detail": None,
            },
        ],
        "selected_evidence": [first_selection],
        "confidence": 0.9,
    }
    chat_completion = Mock(
        side_effect=[
            json.dumps(
                {
                    "verified_chunks": [],
                    "rejected_chunks": [],
                    "missing_information": True,
                    "confidence": 0.9,
                }
            ),
            json.dumps(coverage_review),
            json.dumps(coverage_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "How did the activity begin, and what did participants receive?",
            "candidates": [first_candidate, second_candidate],
        }
    )

    assert output.missing_information is False
    assert [chunk.quote for chunk in output.verified_chunks] == [
        "The activity began in a marked circle.",
        "Each participant received a token.",
    ]
    assert chat_completion.call_count == 2


def test_verification_agent_canonicalizes_ellipsized_coverage_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["content"] = (
        "First it marked out a race-course, in a sort of circle, and then "
        "all the party were placed along the course."
    )
    ellipsized_selection = _coverage_selection(
        quote=(
            "First it marked out a race-course, [...] all the party were "
            "placed along the course."
        ),
        purpose="States how the race was organized.",
    )
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "requirements": [
            {
                "requirement": "Explain how the race was organized.",
                "satisfied": True,
                "evidence": [ellipsized_selection],
                "missing_detail": None,
            }
        ],
        "selected_evidence": [ellipsized_selection],
        "confidence": 0.9,
    }
    chat_completion = Mock(
        side_effect=[
            json.dumps(
                {
                    "verified_chunks": [],
                    "rejected_chunks": [],
                    "missing_information": True,
                    "confidence": 0.9,
                }
            ),
            json.dumps(coverage_review),
            json.dumps(coverage_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "How was the race organized?",
            "candidates": [candidate],
        }
    )

    assert output.missing_information is False
    assert [chunk.quote for chunk in output.verified_chunks] == [
        candidate["content"]
    ]
    assert chat_completion.call_count == 2


def test_verification_agent_canonicalizes_ellipsized_initial_verified_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["content"] = (
        "Alice put her hand in her pocket, pulled out a box of comfits, "
        "and handed them round as prizes."
    )
    ellipsized_quote = (
        "Alice put her hand in her pocket... box of comfits... as prizes."
    )
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "source.txt",
                "quote": ellipsized_quote,
                "page_number": 1,
                "verification_reason": "States participant prizes.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.9,
    }
    coverage_review = _with_coverage_requirements(
        {
            "answers_question": True,
            "missing_information": False,
            "selected_evidence": [
                {
                    "chunk_id": CANDIDATE_CHUNK_ID,
                    "quote": ellipsized_quote,
                    "purpose": "States participant prizes.",
                    "supports_simple_reasoning": False,
                }
            ],
            "confidence": 0.9,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(initial_verification),
            json.dumps(coverage_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "What prizes were handed round?",
            "candidates": [candidate],
        }
    )

    assert output.missing_information is False
    assert [chunk.quote for chunk in output.verified_chunks] == [candidate["content"]]


def test_verification_agent_canonicalizes_ordered_coverage_quote_to_source_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_candidate = _candidate_payload()
    first_candidate["content"] = "The activity began in a marked circle."
    second_candidate = _second_candidate_payload()
    second_candidate["content"] = (
        "The host had no idea what to do, and in despair she put her hand "
        "in her pocket, pulled out a box of tokens, and handed them round "
        "as prizes. There was exactly one apiece all round."
    )
    compressed_quote = (
        "host pulled out a box of tokens and handed them round as prizes"
    )
    expected_quote = (
        "host had no idea what to do, and in despair she put her hand "
        "in her pocket, pulled out a box of tokens, and handed them round "
        "as prizes"
    )
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "The activity began in a marked circle.",
                "page_number": 3,
                "verification_reason": "States how the activity began.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.9,
    }
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "requirements": [
            {
                "requirement": "Explain how the activity began.",
                "satisfied": True,
                "evidence": [
                    {
                        "chunk_id": CANDIDATE_CHUNK_ID,
                        "quote": "The activity began in a marked circle.",
                        "purpose": "States how the activity began.",
                        "supports_simple_reasoning": False,
                    }
                ],
                "missing_detail": None,
            },
            {
                "requirement": "State what participants received.",
                "satisfied": True,
                "evidence": [
                    {
                        "chunk_id": CANDIDATE_CHUNK_ID,
                        "quote": compressed_quote,
                        "purpose": "States what participants received.",
                        "supports_simple_reasoning": False,
                    }
                ],
                "missing_detail": None,
            },
        ],
        "selected_evidence": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": "The activity began in a marked circle.",
                "purpose": "States how the activity began.",
                "supports_simple_reasoning": False,
            },
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": compressed_quote,
                "purpose": "States what participants received.",
                "supports_simple_reasoning": False,
            },
        ],
        "confidence": 0.9,
    }
    chat_completion = _mock_two_pass_verification(
        monkeypatch,
        initial_verification,
        coverage_review,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "How did the activity begin, and what did participants receive?",
            "candidates": [first_candidate, second_candidate],
        }
    )

    assert output.missing_information is False
    assert [(str(chunk.chunk_id), chunk.quote) for chunk in output.verified_chunks] == [
        (CANDIDATE_CHUNK_ID, "The activity began in a marked circle."),
        (SECOND_CANDIDATE_CHUNK_ID, expected_quote),
    ]
    assert chat_completion.call_count == 2


def test_verification_agent_reassigns_initial_ordered_quote_to_matching_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_candidate = _candidate_payload()
    first_candidate["content"] = "The activity began in a marked circle."
    second_candidate = _second_candidate_payload()
    second_candidate["content"] = (
        "The host had no idea what to do, and in despair she put her hand "
        "in her pocket, pulled out a box of tokens, and handed them round "
        "as prizes. There was exactly one apiece all round."
    )
    compressed_quote = (
        "host pulled out a box of tokens and handed them round as prizes"
    )
    expected_quote = (
        "host had no idea what to do, and in despair she put her hand "
        "in her pocket, pulled out a box of tokens, and handed them round "
        "as prizes"
    )
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": compressed_quote,
                "page_number": 3,
                "verification_reason": "States what participants received.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.9,
    }
    selected = _coverage_selection(
        quote="The activity began in a marked circle.",
        purpose="States how the activity began.",
    )
    coverage_review = _with_coverage_requirements(
        {
            "answers_question": True,
            "missing_information": False,
            "selected_evidence": [selected],
            "confidence": 0.9,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(initial_verification),
            json.dumps(coverage_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "How did the activity begin, and what did participants receive?",
            "candidates": [first_candidate, second_candidate],
        }
    )

    assert output.missing_information is False
    assert [(str(chunk.chunk_id), chunk.quote) for chunk in output.verified_chunks] == [
        (CANDIDATE_CHUNK_ID, "The activity began in a marked circle."),
        (SECOND_CANDIDATE_CHUNK_ID, expected_quote),
    ]
    assert chat_completion.call_count == 2


def test_verification_agent_retains_initial_verified_chunks_with_answerable_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_candidate = _candidate_payload()
    first_candidate["content"] = "The activity began in a marked circle."
    second_candidate = _second_candidate_payload()
    second_candidate["content"] = "Each participant received a token."
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": SECOND_CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Each participant received a token.",
                "page_number": 3,
                "verification_reason": "States the participant prize.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.9,
    }
    selected = _coverage_selection(
        quote="The activity began in a marked circle.",
        purpose="States how the activity began.",
    )
    coverage_review = _with_coverage_requirements(
        {
            "answers_question": True,
            "missing_information": False,
            "selected_evidence": [selected],
            "confidence": 0.9,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(initial_verification),
            json.dumps(coverage_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "How did the activity begin, and what did participants receive?",
            "candidates": [first_candidate, second_candidate],
        }
    )

    assert output.missing_information is False
    assert [chunk.quote for chunk in output.verified_chunks] == [
        "The activity began in a marked circle.",
        "Each participant received a token.",
    ]


def test_verification_agent_retries_invalid_coverage_json_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = _coverage_selection()
    corrected_review = _with_coverage_requirements(
        {
            "answers_question": True,
            "missing_information": False,
            "selected_evidence": [selection],
            "confidence": 0.8,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(
                {
                    "verified_chunks": [],
                    "rejected_chunks": [],
                    "missing_information": True,
                    "confidence": 0.5,
                }
            ),
            "not valid json",
            json.dumps(corrected_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start and how long does it last?",
            "candidates": [_candidate_payload()],
        }
    )

    assert output.missing_information is False
    assert chat_completion.call_count == 3


def test_verification_agent_retries_unknown_coverage_chunk_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_selection = _coverage_selection(
        chunk_id="99999999-9999-9999-9999-999999999999"
    )
    corrected_selection = _coverage_selection()
    invalid_review = _with_coverage_requirements(
        {
            "answers_question": True,
            "missing_information": False,
            "selected_evidence": [invalid_selection],
            "confidence": 0.8,
        }
    )
    corrected_review = _with_coverage_requirements(
        {
            "answers_question": True,
            "missing_information": False,
            "selected_evidence": [corrected_selection],
            "confidence": 0.8,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(
                {
                    "verified_chunks": [],
                    "rejected_chunks": [],
                    "missing_information": True,
                    "confidence": 0.5,
                }
            ),
            json.dumps(invalid_review),
            json.dumps(corrected_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start and how long does it last?",
            "candidates": [_candidate_payload()],
        }
    )

    assert output.missing_information is False
    assert chat_completion.call_count == 3


def test_verification_agent_repairs_conclusion_only_evidence_with_exact_causal_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["file_name"] = "alice-in-wonderland.txt"
    candidate["page_number"] = 0
    candidate["content"] = (
        "'Then you shouldn't talk,' said the Hatter. "
        "This piece of rudeness was more than Alice could bear: "
        "she got up in great disgust, and walked off. "
        "'It's the stupidest tea-party I ever was at in all my life!'"
    )
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "alice-in-wonderland.txt",
                "quote": "'It's the stupidest tea-party I ever was at in all my life!'",
                "page_number": 0,
                "verification_reason": "Alice states her conclusion.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 1.0,
    }
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "selected_evidence": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": (
                    "This piece of rudeness was more than Alice could bear: "
                    "she got up in great disgust, and walked off."
                ),
                "purpose": "States the cause of Alice leaving and condemning the party.",
                "supports_simple_reasoning": True,
            },
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": "'It's the stupidest tea-party I ever was at in all my life!'",
                "purpose": "States Alice's conclusion about the party.",
                "supports_simple_reasoning": False,
            },
        ],
        "confidence": 0.92,
    }
    _mock_two_pass_verification(
        monkeypatch,
        initial_verification,
        coverage_review,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": (
                "Why did Alice consider the Mad Tea-Party the stupidest "
                "tea party she had ever attended?"
            ),
            "candidates": [candidate],
        }
    )

    assert output.missing_information is False
    assert output.confidence == 0.92
    assert [chunk.quote for chunk in output.verified_chunks] == [
        (
            "This piece of rudeness was more than Alice could bear: "
            "she got up in great disgust, and walked off."
        ),
        "'It's the stupidest tea-party I ever was at in all my life!'",
    ]


def test_verification_agent_marks_missing_when_coverage_review_is_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["content"] = "Probation starts on June 1, 2026."
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026.",
                "page_number": 3,
                "verification_reason": "States the start date only.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.9,
    }
    coverage_review = {
        "answers_question": False,
        "missing_information": True,
        "selected_evidence": [],
        "confidence": 0.2,
    }
    _mock_two_pass_verification(
        monkeypatch,
        initial_verification,
        coverage_review,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "Why does probation end in August?",
            "candidates": [candidate],
        }
    )

    assert output.missing_information is True
    assert (
        output.confidence
        <= verification_agent.COVERAGE_FAILURE_CONFIDENCE_CAP
    )


def test_expanded_quote_with_surrounding_context_handles_multi_sentence_quote() -> None:
    content = (
        "The meeting became rude enough that the attendee walked away. "
        "'I will not return!' said the attendee while leaving. "
        "'This is the worst meeting I have ever attended!' "
        "Afterward, the attendee noticed an unrelated sign."
    )
    quote = (
        "'I will not return!' said the attendee while leaving. "
        "'This is the worst meeting I have ever attended!'"
    )

    expanded_quote = verification_agent._expanded_quote_with_surrounding_context(
        quote,
        content,
    )

    assert expanded_quote is not None
    assert "The meeting became rude enough" in expanded_quote
    assert "'I will not return!'" in expanded_quote
    assert "'This is the worst meeting" in expanded_quote
    assert "unrelated sign" not in expanded_quote


def test_verification_agent_expands_context_for_explanatory_question_when_coverage_is_too_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["file_name"] = "alice-in-wonderland.txt"
    candidate["page_number"] = 0
    candidate["content"] = (
        "'Then you shouldn't talk,' said the Hatter. "
        "This piece of rudeness was more than Alice could bear: "
        "she got up in great disgust, and walked off; "
        "the others later discussed unrelated snacks. "
        "'It's the stupidest tea-party I ever was at in all my life!'"
    )
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "alice-in-wonderland.txt",
                "quote": "'It's the stupidest tea-party I ever was at in all my life!'",
                "page_number": 0,
                "verification_reason": "Alice states her conclusion.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 1.0,
    }
    coverage_review = {
        "answers_question": False,
        "missing_information": True,
        "selected_evidence": [],
        "confidence": 0.0,
    }
    _mock_two_pass_verification(
        monkeypatch,
        initial_verification,
        coverage_review,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": (
                "Why did Alice consider the Mad Tea-Party the stupidest "
                "tea party she had ever attended?"
            ),
            "candidates": [candidate],
        }
    )

    assert output.missing_information is False
    assert output.confidence == verification_agent.CONTEXT_EXPANSION_CONFIDENCE_CAP
    assert len(output.verified_chunks) == 2
    assert "This piece of rudeness was more than Alice could bear" in (
        output.verified_chunks[0].quote
    )
    assert "unrelated snacks" not in output.verified_chunks[0].quote
    assert "It's the stupidest tea-party" in output.verified_chunks[1].quote


def test_verification_agent_rejects_coverage_quote_not_in_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_verification = {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": True,
        "confidence": 0.1,
    }
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "selected_evidence": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": "This sentence is not in the candidate.",
                "purpose": "Purports to answer the question.",
                "supports_simple_reasoning": False,
            }
        ],
        "confidence": 0.8,
    }
    enriched_review = _with_coverage_requirements(coverage_review)
    chat_completion = Mock(
        side_effect=[
            json.dumps(initial_verification),
            json.dumps(enriched_review),
            json.dumps(enriched_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    with pytest.raises(VerificationAgentError):
        run_verification_agent(
            {
                "agent_run_id": AGENT_RUN_ID,
                "question": "When does probation start?",
                "candidates": [_candidate_payload()],
            }
        )

    assert chat_completion.call_count == 3


def test_verification_agent_retries_coverage_quote_not_in_candidate_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_verification = {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": True,
        "confidence": 0.5,
    }
    invalid_selection = _coverage_selection(
        quote="This sentence is not in the candidate."
    )
    corrected_selection = _coverage_selection()
    invalid_review = _with_coverage_requirements(
        {
            "answers_question": True,
            "missing_information": False,
            "selected_evidence": [invalid_selection],
            "confidence": 0.8,
        }
    )
    corrected_review = _with_coverage_requirements(
        {
            "answers_question": True,
            "missing_information": False,
            "selected_evidence": [corrected_selection],
            "confidence": 0.8,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(initial_verification),
            json.dumps(invalid_review),
            json.dumps(corrected_review),
        ]
    )
    monkeypatch.setattr(
        verification_agent.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        REAL_RUN_COVERAGE_REVIEW,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "When does probation start and how long does it last?",
            "candidates": [_candidate_payload()],
        }
    )

    assert output.missing_information is False
    assert [chunk.quote for chunk in output.verified_chunks] == [
        corrected_selection["quote"]
    ]
    assert chat_completion.call_count == 3


def test_verification_agent_accepts_coverage_quote_with_terminal_punctuation_variation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["file_name"] = "alice-in-wonderland.txt"
    candidate["content"] = (
        "It was labelled 'ORANGE MARMALADE', but to her great "
        "disappointment it was empty: she put the jar back."
    )
    source_quote = (
        "It was labelled 'ORANGE MARMALADE', but to her great "
        "disappointment it was empty:"
    )
    coverage_quote = (
        "It was labelled 'ORANGE MARMALADE', but to her great "
        "disappointment it was empty."
    )
    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "alice-in-wonderland.txt",
                "quote": source_quote,
                "page_number": 0,
                "verification_reason": "Directly states the label and contents.",
                "supports_simple_reasoning": False,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 1.0,
    }
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "selected_evidence": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": coverage_quote,
                "purpose": "States the label and that the jar was empty.",
                "supports_simple_reasoning": False,
            }
        ],
        "confidence": 0.9,
    }
    _mock_two_pass_verification(
        monkeypatch,
        initial_verification,
        coverage_review,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "What was the label, and what was inside the jar?",
            "candidates": [candidate],
        }
    )

    assert output.missing_information is False
    assert [chunk.quote for chunk in output.verified_chunks] == [source_quote]


def test_verification_agent_keeps_two_distinct_coverage_quotes_from_same_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["content"] = (
        "The item is not mine. I keep the items to sell and own none myself."
    )
    initial_verification = {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": True,
        "confidence": 0.5,
    }
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "selected_evidence": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": "The item is not mine.",
                "purpose": "States the ownership conclusion.",
                "supports_simple_reasoning": False,
            },
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": "I keep the items to sell and own none myself.",
                "purpose": "States the reason the item is not owned.",
                "supports_simple_reasoning": True,
            },
        ],
        "confidence": 0.5,
    }
    _mock_two_pass_verification(
        monkeypatch,
        initial_verification,
        coverage_review,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "Why is the item not theirs?",
            "candidates": [candidate],
        }
    )

    assert [chunk.quote for chunk in output.verified_chunks] == [
        "The item is not mine.",
        "I keep the items to sell and own none myself.",
    ]


def test_verification_agent_removes_overlapping_same_chunk_coverage_quotes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    full_quote = (
        "The refund period lasts 30 days after purchase and customers must "
        "provide the original receipt."
    )
    subquote = "The refund period lasts 30 days after purchase"
    candidate["content"] = full_quote
    initial_verification = {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": True,
        "confidence": 0.5,
    }
    coverage_review = {
        "answers_question": True,
        "missing_information": False,
        "selected_evidence": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": subquote,
                "purpose": "States the refund period.",
                "supports_simple_reasoning": False,
            },
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "quote": full_quote,
                "purpose": "States the refund period and required proof.",
                "supports_simple_reasoning": False,
            },
        ],
        "confidence": 0.5,
    }
    _mock_two_pass_verification(
        monkeypatch,
        initial_verification,
        coverage_review,
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "What is the refund period and what proof is required?",
            "candidates": [candidate],
        }
    )

    assert [chunk.quote for chunk in output.verified_chunks] == [full_quote]
    assert [chunk.quote for chunk in output.rejected_chunks] == [subquote]


def test_verification_agent_accepts_quote_with_quote_style_variations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["content"] = "It was labelled 'ORANGE MARMALADE', but it was empty."

    # LLM returns quote with double quotes
    llm_quote = 'It was labelled "ORANGE MARMALADE", but it was empty.'

    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "test.txt",
                "quote": llm_quote,
                "page_number": 1,
                "verification_reason": "Direct answer",
                "supports_simple_reasoning": True,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.9,
    }

    monkeypatch.setattr(
        "app.services.shopaikey_service.chat_completion",
        lambda *args, **kwargs: json.dumps(initial_verification),
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "What was the label?",
            "candidates": [candidate],
        }
    )

    assert len(output.verified_chunks) == 1
    assert output.verified_chunks[0].quote == candidate["content"]
    assert len(output.rejected_chunks) == 0


def test_verification_agent_accepts_quote_with_case_variations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["content"] = "She took down a jar from the shelf."

    # LLM returns lowercase quote
    llm_quote = "she took down a jar from the shelf."

    initial_verification = {
        "verified_chunks": [
            {
                "chunk_id": CANDIDATE_CHUNK_ID,
                "document_id": CANDIDATE_DOCUMENT_ID,
                "file_name": "test.txt",
                "quote": llm_quote,
                "page_number": 1,
                "verification_reason": "Direct answer",
                "supports_simple_reasoning": True,
            }
        ],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": 0.9,
    }

    monkeypatch.setattr(
        "app.services.shopaikey_service.chat_completion",
        lambda *args, **kwargs: json.dumps(initial_verification),
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "Who took the jar?",
            "candidates": [candidate],
        }
    )

    assert len(output.verified_chunks) == 1
    assert output.verified_chunks[0].quote == candidate["content"]
    assert len(output.rejected_chunks) == 0
