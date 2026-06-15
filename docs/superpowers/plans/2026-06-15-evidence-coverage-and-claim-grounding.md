# Evidence Coverage and Claim Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Agent 2 from accepting evidence that only repeats a question premise and prevent Agent 3 from returning explanations that are not supported by exact verified document quotes.

**Architecture:** Add an internal evidence-coverage review after Agent 2's existing verification pass. The review independently selects exact candidate quotes that collectively answer the question, while the public `VerificationAgentOutput` remains unchanged. Agent 3 will receive only document evidence fields, then run a question-aware, claim-level grounding review whose structured result is deterministically validated and converted into the existing public `AnswerSelfCheck`.

**Tech Stack:** Python 3, FastAPI, Pydantic, ShopAIKey chat completion, pytest, existing LangGraph workflow and agent-step logging.

---

## Scope and Constraints

- Follow `docs/plans/Master_Plan.md` sections 11, 12, and 18.
- Do not add question-specific branches or Alice-specific expected values to production code.
- Do not change the public Agent 2 or Agent 3 output schemas.
- Do not add a database migration or change the chat/evidence API response shapes.
- Treat `verification_reason` and `supports_simple_reasoning` as Agent 2 metadata, not source evidence.
- Preserve distinct exact quotes from the same `chunk_id`.
- Fail closed when coverage or grounding output is malformed, references unknown evidence, or reports incomplete support.

## File Map

- Modify `backend/app/agents/schemas.py`
  - Add private/internal structured contracts for evidence coverage and answer grounding.
- Modify `backend/app/agents/prompts.py`
  - Add evidence-coverage and claim-grounding prompts.
- Modify `backend/app/agents/verification_agent.py`
  - Execute and validate the coverage pass, reconcile selected evidence, and cap confidence.
- Modify `backend/app/agents/answer_agent.py`
  - Remove verifier-authored metadata from evidence payloads, include the question in grounding, validate claim support, and derive the existing self-check.
- Modify `backend/tests/test_verification_agent.py`
  - Add coverage-pass unit and regression tests.
- Modify `backend/tests/test_answer_agent.py`
  - Add evidence-isolation, question-aware grounding, unsupported-explanation, and confidence tests.
- Modify `backend/tests/test_langgraph_workflow.py`
  - Confirm the strengthened internal behavior does not change workflow/public output contracts.
- Modify `README.md`
  - Document the new internal safeguards and test commands.

---

### Task 1: Define Internal Coverage and Grounding Contracts

**Files:**
- Modify: `backend/app/agents/schemas.py`
- Modify: `backend/app/agents/prompts.py`
- Test: `backend/tests/test_verification_agent.py`
- Test: `backend/tests/test_answer_agent.py`

- [ ] **Step 1: Write failing schema tests**

Add tests proving that internal reviews reject extra fields, empty evidence, invalid confidence, and incomplete field coverage:

```python
from app.agents.schemas import (
    AnswerGroundingReview,
    EvidenceCoverageReview,
)


def test_evidence_coverage_review_requires_selected_evidence_when_answerable() -> None:
    with pytest.raises(ValidationError):
        EvidenceCoverageReview.model_validate(
            {
                "answers_question": True,
                "missing_information": False,
                "selected_evidence": [],
                "confidence": 0.9,
            }
        )


def test_answer_grounding_review_requires_both_visible_answer_fields() -> None:
    with pytest.raises(ValidationError):
        AnswerGroundingReview.model_validate(
            {
                "answers_question": True,
                "field_reviews": [
                    {
                        "field_name": "final_answer",
                        "text": "Grounded answer.",
                        "claims": [
                            {
                                "claim": "Grounded answer.",
                                "supported": True,
                                "supporting_citations": [
                                    {
                                        "file_name": "source.txt",
                                        "quote": "Grounded source text.",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "confidence": 0.8,
            }
        )
```

- [ ] **Step 2: Run the schema tests and confirm failure**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_verification_agent.py tests/test_answer_agent.py -q
```

Expected: collection or import failure because the internal schemas do not exist.

- [ ] **Step 3: Add strict internal schemas**

Add these contracts to `backend/app/agents/schemas.py` without changing `VerificationAgentOutput`, `AnswerAgentOutput`, or `AnswerSelfCheck`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceCoverageSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: UUID
    quote: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    supports_simple_reasoning: bool

    @field_validator("quote", "purpose")
    @classmethod
    def normalize_coverage_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized


class EvidenceCoverageReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers_question: bool
    missing_information: bool
    selected_evidence: list[EvidenceCoverageSelection]
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_consistent_coverage(self) -> "EvidenceCoverageReview":
        if self.answers_question == self.missing_information:
            raise ValueError(
                "answers_question and missing_information must be opposites"
            )
        if self.answers_question and not self.selected_evidence:
            raise ValueError("answerable coverage requires selected evidence")
        return self


class AnswerClaimGrounding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1)
    supported: bool
    supporting_citations: list[Citation]

    @field_validator("claim")
    @classmethod
    def normalize_claim(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("claim must not be empty")
        return normalized


class AnswerFieldGrounding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: Literal["final_answer", "reasoning_summary"]
    text: str = Field(min_length=1)
    claims: list[AnswerClaimGrounding] = Field(min_length=1)


class AnswerGroundingReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers_question: bool
    field_reviews: list[AnswerFieldGrounding] = Field(min_length=2, max_length=2)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_reviewed_fields(self) -> "AnswerGroundingReview":
        reviewed_fields = {review.field_name for review in self.field_reviews}
        if reviewed_fields != {"final_answer", "reasoning_summary"}:
            raise ValueError(
                "grounding review must cover final_answer and reasoning_summary"
            )
        return self
```

Export the five new classes through `__all__`.

- [ ] **Step 4: Add provider prompts for the internal passes**

Add `EVIDENCE_COVERAGE_SYSTEM_PROMPT`:

```python
EVIDENCE_COVERAGE_SYSTEM_PROMPT = """
You are an evidence coverage reviewer.

Independently decide whether exact quotes from the provided candidate chunks
collectively answer the user's exact question. Use only candidate content.
Do not rely on retrieval reasons, verification reasons, outside knowledge, or
the wording of a proposed answer.

Select the minimum exact excerpts needed to answer. A quote that only repeats
the event or conclusion in the question does not answer a request for its
cause, reason, mechanism, condition, or surrounding context. Multiple distinct
quotes from the same chunk_id are allowed.

Set answers_question to false and missing_information to true if answering
would require guessing. Return only JSON matching the required schema.
""".strip()
```

Replace the boolean-only self-check prompt with `ANSWER_GROUNDING_SYSTEM_PROMPT`:

```python
ANSWER_GROUNDING_SYSTEM_PROMPT = """
You are the final answer grounding reviewer.

Review the exact final_answer and reasoning_summary against the user's question
and only the provided verified document quotes. Split both visible fields into
their factual or inferential claims. For every claim, list exact supporting
file_name and quote pairs from verified evidence.

Mark a claim unsupported when the quote merely repeats the question premise,
does not establish the claimed cause or explanation, or requires outside
knowledge. Do not treat verifier comments, metadata, or unsupported
interpretations as evidence.

Set answers_question to true only when the final answer directly answers the
question and every required explanation is supported. Return only JSON matching
the required schema.
""".strip()
```

Keep `ANSWER_SELF_CHECK_SYSTEM_PROMPT` only as a backwards-compatible alias if tests or imports still require its public name:

```python
ANSWER_SELF_CHECK_SYSTEM_PROMPT = ANSWER_GROUNDING_SYSTEM_PROMPT
```

- [ ] **Step 5: Run focused schema and prompt tests**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_verification_agent.py tests/test_answer_agent.py -q
```

Expected: new schema/prompt tests pass; runtime tests may still fail until Tasks 2-4 are complete.

- [ ] **Step 6: Commit the contracts**

```powershell
git add backend/app/agents/schemas.py backend/app/agents/prompts.py backend/tests/test_verification_agent.py backend/tests/test_answer_agent.py
git commit -m "feat: add evidence coverage and grounding contracts"
```

---

### Task 2: Enforce Agent 2 Question Coverage

**Files:**
- Modify: `backend/app/agents/verification_agent.py`
- Modify: `backend/tests/test_verification_agent.py`

- [ ] **Step 1: Add the Alice regression test before implementation**

Use one candidate containing both the cause and Alice's conclusion. Mock the first provider response to select only the conclusion, then mock the coverage response to select the causal passage and conclusion:

```python
def test_verification_agent_repairs_conclusion_only_evidence_with_exact_causal_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_payload()
    candidate["file_name"] = "alice-in-wonderland.txt"
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
```

- [ ] **Step 2: Add fail-closed coverage tests**

Add this response helper and the three complete tests:

```python
def _mock_two_pass_verification(
    monkeypatch: pytest.MonkeyPatch,
    initial_verification: dict[str, object],
    coverage_review: dict[str, object],
) -> Mock:
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
    return chat_completion


def test_verification_agent_marks_missing_when_coverage_review_is_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    candidate = _candidate_payload()
    candidate["content"] = "Probation starts on June 1, 2026."
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
    assert output.confidence <= verification_agent.COVERAGE_FAILURE_CONFIDENCE_CAP


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
    _mock_two_pass_verification(
        monkeypatch,
        initial_verification,
        coverage_review,
    )

    with pytest.raises(VerificationAgentError):
        run_verification_agent(
            {
                "agent_run_id": AGENT_RUN_ID,
                "question": "When does probation start?",
                "candidates": [_candidate_payload()],
            }
        )


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

    assert len(output.verified_chunks) == 2
```

Use generic source text in the fail-closed and duplicate tests so production behavior is not coupled to the Alice fixture.

- [ ] **Step 3: Run the new Agent 2 tests and confirm failure**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_verification_agent.py -q
```

Expected: failures because no coverage pass exists.

- [ ] **Step 4: Build and parse the coverage request**

In `verification_agent.py`, add:

```python
COVERAGE_FAILURE_CONFIDENCE_CAP = 0.4
EVIDENCE_COVERAGE_RESPONSE_FORMAT = {"type": "json_object"}


def _build_coverage_messages(
    input_data: VerificationAgentInput,
) -> list[dict[str, str]]:
    payload = {
        "response_instruction": "Return only valid JSON.",
        "question": input_data.question,
        "candidates": [
            {
                "chunk_id": str(candidate.chunk_id),
                "file_name": candidate.file_name,
                "page_number": candidate.page_number,
                "content": candidate.content,
            }
            for candidate in input_data.candidates
        ],
    }
    return [
        {"role": "system", "content": EVIDENCE_COVERAGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def _parse_coverage_review(response_content: str) -> EvidenceCoverageReview:
    try:
        payload = json.loads(response_content)
        return EvidenceCoverageReview.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise _VerificationAgentFailure("coverage_validation_error") from exc


def _run_coverage_review(
    input_data: VerificationAgentInput,
    verification_output: VerificationAgentOutput,
) -> EvidenceCoverageReview:
    del verification_output  # Deliberately keep the review independent.
    try:
        response_content = shopaikey_service.chat_completion(
            _build_coverage_messages(input_data),
            response_format=EVIDENCE_COVERAGE_RESPONSE_FORMAT,
        )
    except shopaikey_service.ShopAIKeyServiceError as exc:
        raise _VerificationAgentFailure("coverage_provider_error") from exc
    return _parse_coverage_review(response_content)
```

- [ ] **Step 5: Validate every selected quote and rebuild verified evidence**

Add a reconciliation function that uses candidate metadata rather than provider-supplied document metadata:

```python
def _apply_coverage_review(
    input_data: VerificationAgentInput,
    verification_output: VerificationAgentOutput,
    coverage_review: EvidenceCoverageReview,
) -> VerificationAgentOutput:
    if not coverage_review.answers_question:
        return verification_output.model_copy(
            update={
                "missing_information": True,
                "confidence": min(
                    verification_output.confidence,
                    coverage_review.confidence,
                    COVERAGE_FAILURE_CONFIDENCE_CAP,
                ),
            }
        )

    candidates_by_chunk_id = {
        candidate.chunk_id: candidate for candidate in input_data.candidates
    }
    selected_chunks: list[VerifiedChunk] = []
    for selection in coverage_review.selected_evidence:
        candidate = candidates_by_chunk_id.get(selection.chunk_id)
        if candidate is None:
            raise _VerificationAgentFailure("coverage_unknown_chunk_id")
        if not _quote_matches_candidate_content(
            selection.quote,
            candidate.content,
        ):
            raise _VerificationAgentFailure("coverage_quote_validation_error")
        selected_chunks.append(
            VerifiedChunk(
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                file_name=candidate.file_name,
                quote=selection.quote,
                page_number=candidate.page_number,
                verification_reason=selection.purpose,
                supports_simple_reasoning=selection.supports_simple_reasoning,
            )
        )

    selected_keys = {
        (chunk.chunk_id, _normalize_quote_text(chunk.quote))
        for chunk in selected_chunks
    }
    remaining_rejected_chunks = [
        chunk
        for chunk in verification_output.rejected_chunks
        if (
            chunk.chunk_id,
            _normalize_quote_text(chunk.quote),
        )
        not in selected_keys
    ]
    covered_output = verification_output.model_copy(
        update={
            "verified_chunks": selected_chunks,
            "rejected_chunks": remaining_rejected_chunks,
            "missing_information": False,
            "confidence": min(
                verification_output.confidence,
                coverage_review.confidence,
            ),
        }
    )
    return _filter_duplicate_verified_chunks(covered_output)
```

- [ ] **Step 6: Insert the coverage pass into Agent 2**

After the current membership, quote, and duplicate validation:

```python
coverage_review = _run_coverage_review(
    validated_input,
    duplicate_filtered_output,
)
coverage_checked_output = _apply_coverage_review(
    validated_input,
    duplicate_filtered_output,
    coverage_review,
)
post_processed_output = _apply_missing_information_adjustments(
    coverage_checked_output
)
```

Keep the empty-candidate fast path unchanged. Provider or parsing failures must use controlled Agent 2 failure logging and must not return the first-pass result as if it were safe.

- [ ] **Step 7: Keep existing tests focused**

At module load, preserve the real helper:

```python
REAL_RUN_COVERAGE_REVIEW = verification_agent._run_coverage_review
```

Add an autouse fixture in `test_verification_agent.py` that replaces `_run_coverage_review` with a deterministic review built from the already verified quotes for legacy tests:

```python
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
        is_answerable = bool(selections) and not verification_output.missing_information
        return EvidenceCoverageReview(
            answers_question=is_answerable,
            missing_information=not is_answerable,
            selected_evidence=selections,
            confidence=verification_output.confidence,
        )

    monkeypatch.setattr(
        verification_agent,
        "_run_coverage_review",
        passthrough_review,
    )
```

Import `EvidenceCoverageReview` and `EvidenceCoverageSelection` from `app.agents.schemas`. The new coverage-specific tests restore `REAL_RUN_COVERAGE_REVIEW` through `_mock_two_pass_verification`, so they exercise the real provider path.

- [ ] **Step 8: Run Agent 2 tests**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_verification_agent.py -q
```

Expected: all Agent 2 tests pass, including the conclusion-only regression.

- [ ] **Step 9: Commit Agent 2 coverage**

```powershell
git add backend/app/agents/verification_agent.py backend/tests/test_verification_agent.py
git commit -m "fix: enforce agent evidence question coverage"
```

---

### Task 3: Restrict Agent 3 Inputs to Document Evidence

**Files:**
- Modify: `backend/app/agents/answer_agent.py`
- Modify: `backend/tests/test_answer_agent.py`

- [ ] **Step 1: Write failing payload-isolation tests**

Add assertions for both generation and grounding payloads:

```python
def test_answer_generation_payload_excludes_verifier_authored_metadata() -> None:
    payload = build_answer_generation_payload(
        AnswerAgentInput.model_validate(_answer_input_payload())
    )

    serialized = json.dumps(payload)
    assert "verification_reason" not in serialized
    assert "supports_simple_reasoning" not in serialized
    assert payload["verified_chunks"] == [
        {
            "file_name": "contract.pdf",
            "quote": VERIFIED_QUOTE,
            "page_number": 3,
        }
    ]


def test_answer_grounding_payload_includes_question_but_excludes_verifier_metadata() -> None:
    payload = build_answer_self_check_payload(
        "Why did the event happen?",
        _answer_output(),
        _verification_output(),
    )

    serialized = json.dumps(payload)
    assert payload["question"] == "Why did the event happen?"
    assert "verification_reason" not in serialized
    assert "supports_simple_reasoning" not in serialized
    assert "rejection_reason" not in serialized
```

- [ ] **Step 2: Run the payload tests and confirm failure**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_answer_agent.py -q
```

Expected: failures because metadata is still included and the grounding payload has no question.

- [ ] **Step 3: Reduce both evidence payloads to source fields**

Use exactly:

```python
def _answer_evidence_payload(
    verification: VerificationAgentOutput,
) -> list[dict[str, Any]]:
    return [
        {
            "file_name": chunk.file_name,
            "quote": chunk.quote,
            "page_number": chunk.page_number,
        }
        for chunk in verification.verified_chunks
    ]


def _rejected_evidence_payload(
    verification: VerificationAgentOutput,
) -> list[dict[str, Any]]:
    return [
        {
            "file_name": chunk.file_name,
            "quote": chunk.quote,
        }
        for chunk in verification.rejected_chunks
    ]
```

Call `_answer_evidence_payload` from `build_answer_generation_payload` and `build_answer_self_check_payload`. Use `_rejected_evidence_payload` only in the grounding payload so it can detect rejected-evidence reuse. Do not include `verification_reason`, `supports_simple_reasoning`, `rejection_reason`, chunk IDs, or retrieval scores in either Agent 3 provider payload. Do not include rejected evidence at all in the generation payload.

- [ ] **Step 4: Make grounding question-aware**

Change these signatures:

```python
def build_answer_self_check_payload(
    question: str,
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> dict[str, Any]:


def build_answer_self_check_messages(
    question: str,
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> list[dict[str, str]]:


def execute_answer_self_check(
    question: str,
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> ExecutedAnswerGrounding:
```

Pass `answer_input.question` from `run_answer_agent`.

- [ ] **Step 5: Run focused payload tests**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_answer_agent.py -k "payload or messages" -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit evidence isolation**

```powershell
git add backend/app/agents/answer_agent.py backend/tests/test_answer_agent.py
git commit -m "fix: isolate answer generation from verifier metadata"
```

---

### Task 4: Derive Agent 3 Self-Check from Claim Grounding

**Files:**
- Modify: `backend/app/agents/answer_agent.py`
- Modify: `backend/tests/test_answer_agent.py`

- [ ] **Step 1: Write the unsupported-explanation regression**

The verified quote states only the conclusion, while the draft invents a cause. The grounding result must make the answer fail even though the citation pair is valid:

```python
def test_run_answer_agent_rejects_unsupported_explanation_with_valid_conclusion_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conclusion_quote = (
        "'It's the stupidest tea-party I ever was at in all my life!'"
    )
    verification = _verification_output(
        verified_chunks=[
            {
                "chunk_id": VERIFIED_CHUNK_ID,
                "document_id": DOCUMENT_ID,
                "file_name": "alice-in-wonderland.txt",
                "quote": conclusion_quote,
                "page_number": 0,
                "verification_reason": "Alice states the conclusion.",
                "supports_simple_reasoning": False,
            }
        ]
    )
    draft = {
        "final_answer": (
            "Alice cho rằng đó là bữa tiệc trà ngớ ngẩn nhất "
            "vì hoàn cảnh vô lý."
        ),
        "citations": [
            {
                "file_name": "alice-in-wonderland.txt",
                "quote": conclusion_quote,
            }
        ],
        "reasoning_summary": "Hoàn cảnh vô lý khiến Alice kết luận như vậy.",
        "confidence": 1.0,
    }
    grounding = {
        "answers_question": False,
        "field_reviews": [
            {
                "field_name": "final_answer",
                "text": draft["final_answer"],
                "claims": [
                    {
                        "claim": "hoàn cảnh vô lý",
                        "supported": False,
                        "supporting_citations": [],
                    }
                ],
            },
            {
                "field_name": "reasoning_summary",
                "text": draft["reasoning_summary"],
                "claims": [
                    {
                        "claim": draft["reasoning_summary"],
                        "supported": False,
                        "supporting_citations": [],
                    }
                ],
            },
        ],
        "confidence": 0.1,
    }
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        Mock(side_effect=[json.dumps(draft), json.dumps(grounding)]),
    )
    payload = _answer_input_payload()
    payload["question"] = (
        "Why did Alice consider the Mad Tea-Party the stupidest tea party?"
    )
    payload["verification"] = verification.model_dump(mode="json")

    with pytest.raises(AnswerAgentError) as exc_info:
        run_answer_agent(payload)

    assert exc_info.value.failure_type == "self_check_failed"
```

- [ ] **Step 2: Write the supported causal-answer test**

Use the exact rudeness passage as verified evidence and a grounding review mapping both answer fields to that citation. Assert:

```python
assert output.self_check == AnswerSelfCheck(
    uses_only_verified_chunks=True,
    has_citation=True,
    has_unsupported_claims=False,
    is_ready=True,
)
assert output.confidence == min(
    draft_confidence,
    verification_confidence,
    grounding_confidence,
)
```

- [ ] **Step 3: Write deterministic grounding-integrity tests**

Add tests that reject:

- A field review whose `text` differs from the actual draft field.
- A supported claim with no supporting citation.
- A supporting citation not present in verified evidence.
- A claim using rejected evidence.
- Duplicate field names or a missing `reasoning_summary` review.
- `answers_question=False` even when every listed claim is marked supported.

- [ ] **Step 4: Run the new tests and confirm failure**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_answer_agent.py -q
```

Expected: failures because Agent 3 still parses and trusts four provider booleans.

- [ ] **Step 5: Parse grounding output instead of public self-check booleans**

Add:

```python
@dataclass(frozen=True)
class ExecutedAnswerGrounding:
    self_check: AnswerSelfCheck
    confidence: float
    review: AnswerGroundingReview


def parse_and_validate_answer_grounding(
    provider_content: str,
) -> AnswerGroundingReview:
    try:
        payload = json.loads(provider_content)
        return AnswerGroundingReview.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise _AnswerAgentFailure("grounding_validation_error") from exc
```

- [ ] **Step 6: Deterministically validate the grounding review**

Add:

```python
def _derive_answer_self_check(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
    review: AnswerGroundingReview,
) -> AnswerSelfCheck:
    evidence_lookup = build_answer_evidence_lookup(verification)
    expected_text = {
        "final_answer": output.final_answer,
        "reasoning_summary": output.reasoning_summary,
    }
    all_claims_supported = True

    for field_review in review.field_reviews:
        if field_review.text != expected_text[field_review.field_name]:
            raise AnswerEvidenceValidationError(
                f"Grounding review text does not match {field_review.field_name}."
            )
        for claim in field_review.claims:
            if _normalize_visible_text(claim.claim) not in _normalize_visible_text(
                field_review.text
            ):
                raise AnswerEvidenceValidationError(
                    "Grounding review claim is not present in the reviewed field."
                )
            if not claim.supported or not claim.supporting_citations:
                all_claims_supported = False
                continue
            for citation in claim.supporting_citations:
                citation_pair = (citation.file_name, citation.quote)
                if citation_pair not in evidence_lookup.verified_citation_pairs:
                    raise AnswerEvidenceValidationError(
                        "Grounding review references non-verified evidence."
                    )
                if (
                    citation_pair in evidence_lookup.rejected_citation_pairs
                    or citation.quote in evidence_lookup.rejected_quotes
                ):
                    raise AnswerEvidenceValidationError(
                        "Grounding review references rejected evidence."
                    )

    has_citation = bool(output.citations)
    has_unsupported_claims = (
        not review.answers_question or not all_claims_supported
    )
    return AnswerSelfCheck(
        uses_only_verified_chunks=all_claims_supported,
        has_citation=has_citation,
        has_unsupported_claims=has_unsupported_claims,
        is_ready=(
            review.answers_question
            and all_claims_supported
            and has_citation
        ),
    )
```

Define `_normalize_visible_text` as whitespace normalization plus case folding:

```python
def _normalize_visible_text(value: str) -> str:
    return " ".join(value.casefold().split())
```

The provider no longer decides the public booleans. The application derives them from exact reviewed text, exact citation membership, and the structured support decisions.

- [ ] **Step 7: Return grounding confidence and preserve fail-closed enforcement**

Implement:

```python
def execute_answer_self_check(
    question: str,
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> ExecutedAnswerGrounding:
    validate_answer_evidence_contract(output, verification)
    provider_content = shopaikey_service.chat_completion(
        build_answer_self_check_messages(question, output, verification),
        response_format=ANSWER_SELF_CHECK_RESPONSE_FORMAT,
    )
    review = parse_and_validate_answer_grounding(provider_content)
    self_check = _derive_answer_self_check(
        output,
        verification,
        review,
    )
    checked_output = output.model_copy(update={"self_check": self_check})
    enforce_answer_self_check(checked_output, verification)
    return ExecutedAnswerGrounding(
        self_check=self_check,
        confidence=review.confidence,
        review=review,
    )
```

In `run_answer_agent`, set:

```python
"self_check": executed_grounding.self_check,
"confidence": min(
    draft_output.confidence,
    answer_input.verification.confidence,
    executed_grounding.confidence,
),
```

Include `executed_grounding.review.model_dump(mode="json")` in the successful Agent 3 step log as `grounding_review`, while retaining the existing public `self_check_result`.

- [ ] **Step 8: Update existing self-check tests**

Replace mocked four-boolean provider responses with `AnswerGroundingReview` payloads. Keep direct tests for `enforce_answer_self_check` because the public readiness contract remains unchanged.

Remove `parse_and_validate_answer_self_check` from `answer_agent.py`, its `__all__` export, and test imports. Replace it with `parse_and_validate_answer_grounding`. Update every direct `execute_answer_self_check` call to pass `question` as the first argument.

- [ ] **Step 9: Run Agent 3 tests**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_answer_agent.py -q
```

Expected: all Agent 3 tests pass, including the unsupported explanation regression.

- [ ] **Step 10: Commit claim grounding**

```powershell
git add backend/app/agents/answer_agent.py backend/tests/test_answer_agent.py
git commit -m "fix: derive answer readiness from claim grounding"
```

---

### Task 5: Verify Workflow Compatibility and Live Behavior

**Files:**
- Modify: `backend/tests/test_langgraph_workflow.py`
- Modify: `README.md`

- [ ] **Step 1: Add a workflow contract regression**

Add a workflow test with mocked agents proving the final workflow result remains:

```python
{
    "answer": "string",
    "confidence": 0.0,
    "citations": [
        {
            "file_name": "source.txt",
            "quote": "Exact verified source quote.",
        }
    ],
    "agent_run_id": "uuid",
}
```

Assert no internal `EvidenceCoverageReview`, `AnswerGroundingReview`, verification reason, or claim map crosses the public chat response boundary.

- [ ] **Step 2: Run workflow and API tests**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_langgraph_workflow.py tests/test_chat_api.py tests/test_agent_runs_api.py -q
```

Expected: all tests pass and existing API schemas remain unchanged.

- [ ] **Step 3: Run the complete backend suite**

Run:

```powershell
Set-Location backend
python -m pytest -q
```

Expected: all backend tests pass with no warnings caused by the new schemas or provider parsing.

- [ ] **Step 4: Update README safeguards**

Document:

- Agent 2 now performs an independent exact-quote coverage review.
- Agent 3 receives source quote fields only.
- Agent 3 grounding is question-aware and claim-level.
- Public Agent 2, Agent 3, chat, evidence, and logs API contracts remain compatible.
- Verification commands:

```powershell
Set-Location backend
python -m pytest tests/test_verification_agent.py -q
python -m pytest tests/test_answer_agent.py -q
python -m pytest -q
```

- [ ] **Step 5: Run the live Alice regression**

With backend running on port `8000`, submit:

```powershell
$body = @{
    question = "Why did Alice consider the Mad Tea-Party the stupidest tea party she had ever attended?"
    document_ids = @("bab204fd-2b0f-4acb-9706-0bd7576be26f")
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/chat/ask" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$response | ConvertTo-Json -Depth 10
Invoke-RestMethod `
    -Uri "http://localhost:8000/api/agent-runs/$($response.agent_run_id)/logs" `
    -Method Get |
    ConvertTo-Json -Depth 30
```

Expected:

- Agent 2 verifies the rudeness/disgust passage, not only Alice's conclusion.
- The answer explains that the Hatter's rudeness and the party's treatment drove Alice away.
- The answer does not introduce “absurdity of the situation” unless an exact verified quote supports that interpretation.
- Citations contain exact verified document quotes.
- Agent 3 grounding contains both visible fields and no unsupported claims.
- Final confidence is the minimum of verification, draft, and grounding confidence rather than automatically remaining `1.0`.

- [ ] **Step 6: Inspect the evidence endpoint**

Run:

```powershell
Invoke-RestMethod `
    -Uri "http://localhost:8000/api/agent-runs/$($response.agent_run_id)/evidence" `
    -Method Get |
    ConvertTo-Json -Depth 20
```

Expected: verified evidence contains exact causal context and preserves distinct useful excerpts from the same chunk.

- [ ] **Step 7: Commit workflow coverage and documentation**

```powershell
git add backend/tests/test_langgraph_workflow.py README.md
git commit -m "test: cover grounded explanatory answers"
```

---

## Completion Criteria

- The exact Alice regression no longer returns a cause supported only by verifier-authored metadata.
- Agent 2 cannot report complete evidence unless its selected exact quotes collectively answer the question.
- Agent 3 cannot consume `verification_reason` or `supports_simple_reasoning` as document evidence.
- Agent 3 receives the original question during grounding.
- Public self-check booleans are derived by application logic from a structured grounding review.
- Unsupported or malformed grounding fails closed.
- Confidence is capped by verification, draft, and grounding confidence.
- Distinct evidence excerpts from one chunk remain supported.
- Public schemas and APIs remain unchanged.
- Targeted and full backend test suites pass.
- A new live Alice run verifies the causal passage and returns a grounded answer.
