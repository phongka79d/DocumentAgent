# RAG Quality Priority Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the live RAG quality issues identified in `docs/reports/rag_live_evaluation_2026-06-17.md`, in priority order.

**Architecture:** Keep the current three-agent workflow. Add deterministic guardrails around confidence and simple chronology reasoning, tune retrieval filtering without changing the API contract, and make citation rendering match the MVP rule exactly.

**Tech Stack:** FastAPI, Pydantic, LangGraph, Supabase, Qdrant, ShopAIKey, pytest, React, TypeScript, Vite.

---

## File Structure

Modify these existing files:

- `backend/app/agents/answer_agent.py`
  - Add final confidence calibration helper.
  - Invoke deterministic simple chronology answer before LLM generation when evidence is sufficient.

- `backend/app/agents/schemas.py`
  - Add optional `chunk_index` to `VerifiedChunk` so Agent 3 can reason about source order.

- `backend/app/agents/verification_agent.py`
  - Preserve candidate `chunk_index` when building verified chunks.

- `backend/app/services/answer_log_service.py`
  - Include `chunk_index` in successful answer log payload only if the model dump includes it.

- `backend/app/services/answer_prompt_service.py`
  - Include `chunk_index` in verified evidence payload sent to Agent 3.

- `backend/app/services/hybrid_retrieval_service.py`
  - Add deterministic minimum-score filtering after initial ranking.

- `backend/app/services/retrieval_context_service.py`
  - Avoid expanding adjacent context from weak anchors.

- `backend/app/core/config.py`
  - Add retrieval precision settings.

- `frontend/src/components/AnswerPanel.tsx`
  - Render citations in exact `file_name: "quoted text"` format.

Modify these tests:

- `backend/tests/test_answer_agent.py`
- `backend/tests/test_verification_agent.py`
- `backend/tests/test_answer_prompt_service.py`
- `backend/tests/test_hybrid_retrieval_service.py`
- `backend/tests/test_retrieval_context_service.py`

Verification commands:

- Backend targeted tests:
  - `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py tests/test_verification_agent.py tests/test_answer_prompt_service.py tests/test_hybrid_retrieval_service.py tests/test_retrieval_context_service.py -q`

- Backend broader confidence:
  - `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_chat_api.py tests/test_agent_runs_api.py -q`

- Frontend build:
  - `cd frontend; npm run build`

---

## Task 1: Priority 1 - Fix Grounded Answer Confidence Calibration

**Files:**

- Modify: `backend/app/agents/answer_agent.py`
- Test: `backend/tests/test_answer_agent.py`

### Why

The live direct-answer run had:

- Agent 2 verification confidence: `0.9`
- grounding review confidence: `1.0`
- self-check ready: `true`
- public confidence: `0.0`

Root cause: `run_answer_agent()` caps final confidence with the LLM draft confidence. A provider-generated `0.0` draft confidence should not override verified grounding.

### Steps

- [ ] **Step 1: Add failing confidence test**

Append this test to `backend/tests/test_answer_agent.py` near the other `run_answer_agent` success tests:

```python
def test_run_answer_agent_ignores_zero_draft_confidence_when_grounding_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_payload = _draft_answer_payload(confidence=0.0)
    expected_output = AnswerAgentOutput.model_validate(
        {
            **draft_payload,
            "self_check": DRAFT_SELF_CHECK_PLACEHOLDER,
        }
    )
    chat_completion = Mock(
        side_effect=[
            json.dumps(draft_payload),
            json.dumps(
                _grounding_review_payload(
                    output=expected_output,
                    confidence=0.91,
                )
            ),
        ]
    )
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )

    output = run_answer_agent(_answer_input_payload())

    assert output.self_check.model_dump() == READY_SELF_CHECK_REQUIRED_VALUES
    assert output.confidence == pytest.approx(0.82)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py::test_run_answer_agent_ignores_zero_draft_confidence_when_grounding_passes -q
```

Expected:

```text
FAILED ... assert 0.0 == 0.82 ± ...
```

- [ ] **Step 3: Add confidence helper**

In `backend/app/agents/answer_agent.py`, add this helper near `execute_answer_self_check()`:

```python
def final_grounded_answer_confidence(
    *,
    draft_confidence: float,
    verification_confidence: float,
    grounding_confidence: float,
    self_check: AnswerSelfCheck,
) -> float:
    """Calibrate final confidence after evidence validation and grounding pass."""

    evidence_confidence = min(verification_confidence, grounding_confidence)
    if (
        self_check.is_ready
        and self_check.uses_only_verified_chunks
        and self_check.has_citation
        and not self_check.has_unsupported_claims
        and draft_confidence <= 0.0
    ):
        return evidence_confidence

    return min(draft_confidence, evidence_confidence)
```

- [ ] **Step 4: Use helper in final output**

In `run_answer_agent()`, replace this block:

```python
"confidence": min(
    draft_output.confidence,
    answer_input.verification.confidence,
    executed_grounding.confidence,
),
```

with:

```python
"confidence": final_grounded_answer_confidence(
    draft_confidence=draft_output.confidence,
    verification_confidence=answer_input.verification.confidence,
    grounding_confidence=executed_grounding.confidence,
    self_check=executed_grounding.self_check,
),
```

- [ ] **Step 5: Export helper for focused testing**

Add `"final_grounded_answer_confidence"` to the `__all__` list in `backend/app/agents/answer_agent.py`.

- [ ] **Step 6: Run targeted tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py -q
```

Expected:

```text
... passed
```

- [ ] **Step 7: Commit**

```powershell
git add backend/app/agents/answer_agent.py backend/tests/test_answer_agent.py
git commit -m "fix: calibrate grounded answer confidence"
```

---

## Task 2: Priority 2 - Add Deterministic Simple Chronology Answering

**Files:**

- Modify: `backend/app/agents/schemas.py`
- Modify: `backend/app/agents/verification_agent.py`
- Modify: `backend/app/services/answer_prompt_service.py`
- Modify: `backend/app/agents/answer_agent.py`
- Test: `backend/tests/test_verification_agent.py`
- Test: `backend/tests/test_answer_prompt_service.py`
- Test: `backend/tests/test_answer_agent.py`

### Why

The live chronology question had enough verified evidence, but Agent 3 failed self-check and returned a fallback. This should be handled as simple reasoning when verified chunks preserve source order.

### Steps

- [ ] **Step 1: Add failing schema/order propagation test**

Append this test to `backend/tests/test_verification_agent.py`:

```python
def test_verification_agent_preserves_chunk_index_on_verified_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _retrieval_candidate(
        chunk_id=CHUNK_ID,
        content="First event happened before the second event.",
        chunk_index=7,
    )
    monkeypatch.setattr(
        verification_agent_module,
        "_run_initial_verification",
        Mock(
            return_value=VerificationAgentOutput.model_validate(
                {
                    "verified_chunks": [
                        {
                            "chunk_id": str(candidate.chunk_id),
                            "document_id": str(candidate.document_id),
                            "file_name": candidate.file_name,
                            "quote": "First event happened before the second event.",
                            "page_number": candidate.page_number,
                            "verification_reason": "Direct evidence.",
                            "supports_simple_reasoning": True,
                        }
                    ],
                    "rejected_chunks": [],
                    "missing_information": False,
                    "confidence": 0.8,
                }
            )
        ),
    )
    monkeypatch.setattr(
        verification_agent_module,
        "_run_coverage_review",
        Mock(
            return_value=EvidenceCoverageReview.model_validate(
                {
                    "answers_question": True,
                    "missing_information": False,
                    "requirements": [
                        {
                            "requirement": "first event",
                            "satisfied": True,
                            "evidence": [
                                {
                                    "chunk_id": str(candidate.chunk_id),
                                    "quote": "First event happened before the second event.",
                                    "purpose": "Direct evidence.",
                                    "supports_simple_reasoning": True,
                                }
                            ],
                            "missing_detail": None,
                        }
                    ],
                    "selected_evidence": [
                        {
                            "chunk_id": str(candidate.chunk_id),
                            "quote": "First event happened before the second event.",
                            "purpose": "Direct evidence.",
                            "supports_simple_reasoning": True,
                        }
                    ],
                    "confidence": 0.8,
                }
            )
        ),
    )

    output = run_verification_agent(
        {
            "agent_run_id": AGENT_RUN_ID,
            "question": "Which happened first?",
            "candidates": [candidate.model_dump(mode="json")],
        }
    )

    assert output.verified_chunks[0].chunk_index == 7
```

If helper names differ in the file, use the existing local helpers in `test_verification_agent.py` for candidate construction and constants.

- [ ] **Step 2: Add `chunk_index` to verified chunks**

In `backend/app/agents/schemas.py`, update `VerifiedChunk`:

```python
class VerifiedChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    file_name: str | None
    quote: str = Field(min_length=1)
    page_number: int | None
    chunk_index: int | None = None
    verification_reason: str = Field(min_length=1)
    supports_simple_reasoning: bool = False
```

- [ ] **Step 3: Preserve `chunk_index` in verification output**

In `backend/app/agents/verification_agent.py`, update every `VerifiedChunk(...)` construction that has access to a `candidate`.

For the coverage path inside `_apply_coverage_review()`, include:

```python
chunk_index=candidate.chunk_index,
```

The resulting construction should include:

```python
VerifiedChunk(
    chunk_id=candidate.chunk_id,
    document_id=candidate.document_id,
    file_name=candidate.file_name,
    quote=selection.quote,
    page_number=candidate.page_number,
    chunk_index=candidate.chunk_index,
    verification_reason=selection.purpose,
    supports_simple_reasoning=selection.supports_simple_reasoning,
)
```

For `_canonicalize_verified_chunk_quote()`, when returning `verified_chunk.model_copy(...)`, include:

```python
"chunk_index": selected_candidate.chunk_index,
```

and in the matching-candidate update include:

```python
"chunk_index": matching_candidate.chunk_index,
```

- [ ] **Step 4: Add prompt payload test**

Append this test to `backend/tests/test_answer_prompt_service.py`:

```python
def test_answer_generation_payload_includes_verified_chunk_index() -> None:
    verification = VerificationAgentOutput.model_validate(
        {
            "verified_chunks": [
                {
                    "chunk_id": "11111111-1111-1111-1111-111111111111",
                    "document_id": "22222222-2222-2222-2222-222222222222",
                    "file_name": "story.txt",
                    "quote": "Alice saw the White Rabbit.",
                    "page_number": 1,
                    "chunk_index": 0,
                    "verification_reason": "First event.",
                    "supports_simple_reasoning": True,
                }
            ],
            "rejected_chunks": [],
            "missing_information": False,
            "confidence": 0.9,
        }
    )
    payload = answer_evidence_payload(verification)

    assert payload == [
        {
            "file_name": "story.txt",
            "quote": "Alice saw the White Rabbit.",
            "page_number": 1,
            "chunk_index": 0,
        }
    ]
```

If `test_answer_prompt_service.py` imports individual functions, add:

```python
from app.agents.schemas import VerificationAgentOutput
from app.services.answer_prompt_service import answer_evidence_payload
```

- [ ] **Step 5: Include `chunk_index` in answer evidence payload**

In `backend/app/services/answer_prompt_service.py`, update `answer_evidence_payload()`:

```python
def answer_evidence_payload(
    verification: VerificationAgentOutput,
) -> list[dict[str, Any]]:
    return [
        {
            "file_name": chunk.file_name,
            "quote": chunk.quote,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
        }
        for chunk in verification.verified_chunks
    ]
```

- [ ] **Step 6: Add deterministic chronology test**

Append this test to `backend/tests/test_answer_agent.py`:

```python
def test_run_answer_agent_answers_simple_chronology_without_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(side_effect=AssertionError("ShopAIKey must not be called"))
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    payload = _answer_input_payload()
    payload["question"] = (
        "Which happened first: Alice saw the White Rabbit, "
        "or Alice fell down the rabbit-hole?"
    )
    payload["verification"] = _verification_output(
        verified_chunks=[
            {
                "chunk_id": VERIFIED_CHUNK_ID,
                "document_id": DOCUMENT_ID,
                "file_name": "alice.txt",
                "quote": "suddenly a White Rabbit with pink eyes ran close by her.",
                "page_number": 1,
                "chunk_index": 0,
                "verification_reason": "Alice saw the White Rabbit.",
                "supports_simple_reasoning": True,
            },
            {
                "chunk_id": "55555555-5555-5555-5555-555555555555",
                "document_id": DOCUMENT_ID,
                "file_name": "alice.txt",
                "quote": "down she came upon a heap of sticks and dry leaves, and the fall was over.",
                "page_number": 1,
                "chunk_index": 1,
                "verification_reason": "Alice fell down the rabbit-hole.",
                "supports_simple_reasoning": True,
            },
        ]
    ).model_dump(mode="json")

    output = run_answer_agent(payload)

    assert output.final_answer == (
        "Sự kiện xảy ra trước là: Alice saw the White Rabbit."
    )
    assert output.reasoning_summary == (
        "Compared verified source order by chunk_index: "
        "Alice saw the White Rabbit appears before Alice fell down the rabbit-hole."
    )
    assert output.confidence == pytest.approx(0.82)
    assert output.citations == [
        Citation(
            file_name="alice.txt",
            quote="suddenly a White Rabbit with pink eyes ran close by her.",
        ),
        Citation(
            file_name="alice.txt",
            quote=(
                "down she came upon a heap of sticks and dry leaves, "
                "and the fall was over."
            ),
        ),
    ]
    assert output.self_check == AnswerSelfCheck(
        uses_only_verified_chunks=True,
        has_citation=True,
        has_unsupported_claims=False,
        is_ready=True,
    )
    chat_completion.assert_not_called()
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["output_payload"]["fallback_reason"] == "simple_chronology"
```

- [ ] **Step 7: Implement deterministic chronology helper**

In `backend/app/agents/answer_agent.py`, add imports:

```python
from collections.abc import Sequence
```

Add these constants near `_EXPLANATORY_QUESTION_PATTERN`:

```python
_WHICH_HAPPENED_FIRST_PATTERN = re.compile(
    r"^\s*which\s+happened\s+first\s*:\s*(?P<first>.+?)\s*,\s*or\s*(?P<second>.+?)\??\s*$",
    re.IGNORECASE,
)
_CHRONOLOGY_STOP_WORDS = {
    "a",
    "an",
    "and",
    "or",
    "the",
    "to",
    "of",
    "in",
    "on",
    "down",
    "happened",
    "first",
    "alice",
}
_CHRONOLOGY_TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
```

Add these helpers before `run_answer_agent()`:

```python
def _chronology_terms(value: str) -> set[str]:
    return {
        token.casefold()
        for token in _CHRONOLOGY_TOKEN_PATTERN.findall(value)
        if token.casefold() not in _CHRONOLOGY_STOP_WORDS
    }


def _chunk_order(chunk: Any) -> tuple[int, str]:
    chunk_index = getattr(chunk, "chunk_index", None)
    if chunk_index is None:
        return (10**9, str(getattr(chunk, "chunk_id", "")))
    return (chunk_index, str(getattr(chunk, "chunk_id", "")))


def _best_chunk_for_option(
    option: str,
    verified_chunks: Sequence[Any],
) -> Any | None:
    option_terms = _chronology_terms(option)
    if not option_terms:
        return None

    matches = []
    for chunk in verified_chunks:
        quote_terms = _chronology_terms(chunk.quote)
        overlap = len(option_terms & quote_terms)
        if overlap <= 0:
            continue
        matches.append((overlap, _chunk_order(chunk), chunk))

    if not matches:
        return None

    return sorted(matches, key=lambda item: (-item[0], item[1]))[0][2]


def _try_build_simple_chronology_answer(
    answer_input: AnswerAgentInput,
) -> AnswerAgentOutput | None:
    match = _WHICH_HAPPENED_FIRST_PATTERN.match(answer_input.question)
    if match is None:
        return None

    first_option = match.group("first").strip()
    second_option = match.group("second").strip()
    verified_chunks = answer_input.verification.verified_chunks
    if len(verified_chunks) < 2:
        return None

    first_chunk = _best_chunk_for_option(first_option, verified_chunks)
    second_chunk = _best_chunk_for_option(second_option, verified_chunks)
    if first_chunk is None or second_chunk is None:
        return None
    if first_chunk.chunk_index is None or second_chunk.chunk_index is None:
        return None
    if first_chunk.chunk_index == second_chunk.chunk_index:
        return None

    winning_option = (
        first_option
        if first_chunk.chunk_index < second_chunk.chunk_index
        else second_option
    )
    ordered_citations = [
        Citation(file_name=first_chunk.file_name, quote=first_chunk.quote),
        Citation(file_name=second_chunk.file_name, quote=second_chunk.quote),
    ]

    return AnswerAgentOutput(
        final_answer=f"Sự kiện xảy ra trước là: {winning_option}.",
        citations=ordered_citations,
        reasoning_summary=(
            "Compared verified source order by chunk_index: "
            f"{first_option} appears before {second_option}."
            if first_chunk.chunk_index < second_chunk.chunk_index
            else "Compared verified source order by chunk_index: "
            f"{second_option} appears before {first_option}."
        ),
        confidence=answer_input.verification.confidence,
        self_check=AnswerSelfCheck(
            uses_only_verified_chunks=True,
            has_citation=True,
            has_unsupported_claims=False,
            is_ready=True,
        ),
    )
```

- [ ] **Step 8: Invoke deterministic chronology helper**

In `run_answer_agent()`, after the insufficient-evidence branch and before `_generate_validated_draft_answer()`, add:

```python
    simple_chronology_output = _try_build_simple_chronology_answer(answer_input)
    if simple_chronology_output is not None:
        _log_insufficient_answer(
            answer_input,
            failure_type="simple_chronology",
            output=simple_chronology_output,
        )
        return simple_chronology_output
```

This reuses the existing safe success-step logging shape. Rename `_log_insufficient_answer` only if a later refactor is desired; do not rename it in this task.

- [ ] **Step 9: Run targeted chronology tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py::test_run_answer_agent_answers_simple_chronology_without_provider tests/test_verification_agent.py::test_verification_agent_preserves_chunk_index_on_verified_chunks tests/test_answer_prompt_service.py::test_answer_generation_payload_includes_verified_chunk_index -q
```

Expected:

```text
3 passed
```

- [ ] **Step 10: Run broader affected backend tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py tests/test_verification_agent.py tests/test_answer_prompt_service.py tests/test_agent_runs_api.py -q
```

Expected:

```text
... passed
```

- [ ] **Step 11: Commit**

```powershell
git add backend/app/agents/schemas.py backend/app/agents/verification_agent.py backend/app/services/answer_prompt_service.py backend/app/agents/answer_agent.py backend/tests/test_verification_agent.py backend/tests/test_answer_prompt_service.py backend/tests/test_answer_agent.py
git commit -m "feat: answer simple chronology from verified evidence order"
```

---

## Task 3: Priority 3 - Improve Retrieval Precision With Score Gating

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/hybrid_retrieval_service.py`
- Modify: `backend/app/services/retrieval_context_service.py`
- Test: `backend/tests/test_hybrid_retrieval_service.py`
- Test: `backend/tests/test_retrieval_context_service.py`

### Why

The live audit showed 13-14 retrieved candidates for simple questions, with many irrelevant chunks. This task reduces low-value candidates and prevents adjacent-context expansion from weak anchors.

### Steps

- [ ] **Step 1: Add failing hybrid retrieval filter test**

Append this test to `backend/tests/test_hybrid_retrieval_service.py`:

```python
def test_retrieve_hybrid_filters_candidates_below_min_final_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kept_chunk_id = "abababab-1111-1111-1111-abababababab"
    filtered_chunk_id = "cdcdcdcd-2222-2222-2222-cdcdcdcdcdcd"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="What object did the White Rabbit carry?",
            results=[
                _semantic_candidate(
                    kept_chunk_id,
                    content="The White Rabbit carried a watch.",
                    semantic_similarity=0.9,
                    chunk_index=0,
                ),
                _semantic_candidate(
                    filtered_chunk_id,
                    content="Tea party chairs and unrelated chatter.",
                    semantic_similarity=0.05,
                    chunk_index=18,
                ),
            ],
        )
    )
    graph_retrieval = Mock(return_value=[])
    settings = _settings(final_top_k=5)
    settings.retrieval_min_final_score = 0.2
    monkeypatch.setattr(
        hybrid_retrieval_service,
        "get_settings",
        lambda: settings,
    )

    response = hybrid_retrieval_service.retrieve_hybrid(
        "What object did the White Rabbit carry?",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert [candidate.chunk_id for candidate in response.candidates] == [
        UUID(kept_chunk_id)
    ]
```

- [ ] **Step 2: Add failing context expansion gate test**

Append this test to `backend/tests/test_retrieval_context_service.py`:

```python
def test_expand_retrieval_context_skips_weak_anchor_below_min_parent_score() -> None:
    anchor = HybridRetrievalCandidate(
        chunk_id=UUID("11111111-1111-1111-1111-111111111111"),
        document_id=UUID("22222222-2222-2222-2222-222222222222"),
        file_name="story.txt",
        file_type="text/plain",
        content="Weak unrelated anchor.",
        content_preview=None,
        page_number=None,
        section_title=None,
        chunk_index=4,
        semantic_similarity=0.1,
        metadata=None,
        graph_relevance=0.0,
        keyword_overlap=0.0,
        metadata_match=0.0,
        recency_or_position_score=0.0,
        final_score=0.05,
        retrieval_reason=None,
    )
    chunk_lookup = Mock(
        return_value=[
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "chunk_index": 5,
                "content": "Adjacent but not requested.",
                "page_number": None,
                "section_title": None,
            }
        ]
    )

    expanded = retrieval_context_service.expand_retrieval_context(
        "What did the Rabbit carry?",
        [anchor],
        context_window=1,
        max_context_candidates=8,
        min_parent_score=0.2,
        chunk_lookup=chunk_lookup,
    )

    assert expanded == [anchor]
    chunk_lookup.assert_not_called()
```

If `test_retrieval_context_service.py` does not already import `Mock`, `UUID`, `HybridRetrievalCandidate`, and `retrieval_context_service`, add:

```python
from unittest.mock import Mock
from uuid import UUID

from app.schemas.retrieval import HybridRetrievalCandidate
from app.services import retrieval_context_service
```

- [ ] **Step 3: Add settings**

In `backend/app/core/config.py`, add fields near the retrieval settings:

```python
    retrieval_min_final_score: float = Field(default=0.2, ge=0.0, le=1.0)
    retrieval_context_min_parent_score: float = Field(default=0.2, ge=0.0, le=1.0)
```

- [ ] **Step 4: Filter weak hybrid candidates**

In `backend/app/services/hybrid_retrieval_service.py`, add helper near `_rank_and_limit_candidates()`:

```python
def _filter_by_min_final_score(
    candidates: list[HybridRetrievalCandidate],
    min_final_score: float,
) -> list[HybridRetrievalCandidate]:
    if min_final_score <= 0.0:
        return candidates
    return [
        candidate
        for candidate in candidates
        if candidate.final_score >= min_final_score
    ]
```

In `retrieve_hybrid()`, replace:

```python
ranked_candidates = _rank_and_limit_candidates(scored_candidates, resolved_final_top_k)
```

with:

```python
filtered_candidates = _filter_by_min_final_score(
    scored_candidates,
    settings.retrieval_min_final_score,
)
ranked_candidates = _rank_and_limit_candidates(
    filtered_candidates,
    resolved_final_top_k,
)
```

- [ ] **Step 5: Gate adjacent context expansion**

In `backend/app/services/retrieval_context_service.py`, update function signature:

```python
def expand_retrieval_context(
    question: str,
    anchors: list[HybridRetrievalCandidate],
    *,
    context_window: int,
    max_context_candidates: int,
    min_parent_score: float = 0.0,
    chunk_lookup: ChunkLookup = supabase_service.list_document_chunks_by_indexes,
) -> list[HybridRetrievalCandidate]:
```

Inside the loop over anchors, add before `if anchor.chunk_index is None`:

```python
        if anchor.final_score < min_parent_score:
            continue
```

- [ ] **Step 6: Pass context parent score setting**

In `backend/app/agents/retrieval_agent.py`, update the call:

```python
expanded_candidates = retrieval_context_service.expand_retrieval_context(
    validated_input.question,
    hybrid_response.candidates,
    context_window=settings.retrieval_context_window,
    max_context_candidates=settings.retrieval_context_max_candidates,
    min_parent_score=settings.retrieval_context_min_parent_score,
)
```

- [ ] **Step 7: Run targeted retrieval tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_hybrid_retrieval_service.py::test_retrieve_hybrid_filters_candidates_below_min_final_score tests/test_retrieval_context_service.py::test_expand_retrieval_context_skips_weak_anchor_below_min_parent_score -q
```

Expected:

```text
2 passed
```

- [ ] **Step 8: Run full retrieval service tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_hybrid_retrieval_service.py tests/test_retrieval_context_service.py tests/test_retrieval_agent.py tests/test_retrieval_api.py -q
```

Expected:

```text
... passed
```

- [ ] **Step 9: Commit**

```powershell
git add backend/app/core/config.py backend/app/services/hybrid_retrieval_service.py backend/app/services/retrieval_context_service.py backend/app/agents/retrieval_agent.py backend/tests/test_hybrid_retrieval_service.py backend/tests/test_retrieval_context_service.py
git commit -m "fix: gate weak retrieval candidates and context expansion"
```

---

## Task 4: Priority 4 - Render Exact MVP Citation Format

**Files:**

- Modify: `frontend/src/components/AnswerPanel.tsx`
- Verify: `frontend` TypeScript build

### Why

The backend returns structured citations and hides raw IDs, but the UI displays file name and quote separately. MVP requires visible citations in this exact format:

```text
file_name: "quoted text"
```

### Steps

- [ ] **Step 1: Add citation formatter**

In `frontend/src/components/AnswerPanel.tsx`, add this helper below `formatConfidence()`:

```tsx
export function formatCitation(citation: ChatCitation): string {
  return `${citation.file_name}: "${citation.quote}"`;
}
```

- [ ] **Step 2: Render exact citation text**

Replace this block:

```tsx
<p className="answer-panel__citation-file">
  {citation.file_name}
</p>
<blockquote className="answer-panel__citation-quote">
  {citation.quote}
</blockquote>
```

with:

```tsx
<p className="answer-panel__citation-text">
  {formatCitation(citation)}
</p>
```

- [ ] **Step 3: Keep existing CSS compatible**

If `frontend/src/styles.css` has styles for `.answer-panel__citation-file` or `.answer-panel__citation-quote`, add this style near the answer-panel citation styles:

```css
.answer-panel__citation-text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
```

Do not remove old CSS selectors in this task. Keeping unused selectors is lower risk than broad CSS churn.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected:

```text
tsc --noEmit && vite build
...
built in ...
```

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/AnswerPanel.tsx frontend/src/styles.css
git commit -m "fix: render citations in exact MVP format"
```

---

## Task 5: Priority 5 - Add Specific Missing-Target Detail to Internal Answer Logs

**Files:**

- Modify: `backend/app/agents/answer_agent.py`
- Modify: `backend/app/services/answer_log_service.py`
- Test: `backend/tests/test_answer_agent.py`

### Why

The public missing-information answer must stay exact. The audit found that missing details are generic. To preserve the exact public safety response while improving diagnostics, add a specific missing target to the internal Agent 3 log output.

### Steps

- [ ] **Step 1: Add failing log-specificity test**

Append this test to `backend/tests/test_answer_agent.py`:

```python
def test_missing_information_log_includes_question_specific_missing_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_completion = Mock(side_effect=AssertionError("ShopAIKey must not be called"))
    try_log_agent_step = Mock()
    monkeypatch.setattr(
        answer_agent_module.shopaikey_service,
        "chat_completion",
        chat_completion,
    )
    monkeypatch.setattr(
        answer_agent_module.agent_log_service,
        "try_log_agent_step",
        try_log_agent_step,
    )
    payload = _answer_input_payload()
    payload["question"] = "What is Alice's bank account number?"
    payload["verification"] = _verification_output(
        missing_information=True,
        verified_chunks=[],
    ).model_dump(mode="json")

    output = run_answer_agent(payload)

    assert output.final_answer == answer_agent_module.INSUFFICIENT_EVIDENCE_ANSWER
    log_call = try_log_agent_step.call_args.kwargs
    assert log_call["output_payload"]["fallback_reason"] == "insufficient_evidence"
    assert log_call["output_payload"]["missing_target"] == (
        "Alice's bank account number"
    )
```

- [ ] **Step 2: Add missing-target extraction helper**

In `backend/app/agents/answer_agent.py`, add near `_has_insufficient_evidence()`:

```python
_WHAT_IS_QUESTION_PATTERN = re.compile(
    r"^\s*what\s+is\s+(?P<target>.+?)\??\s*$",
    re.IGNORECASE,
)


def _missing_target_from_question(question: str) -> str | None:
    match = _WHAT_IS_QUESTION_PATTERN.match(question)
    if match is None:
        return None
    target = match.group("target").strip()
    if not target:
        return None
    return target
```

- [ ] **Step 3: Thread missing target into insufficient-answer logging**

Change `_log_insufficient_answer()` signature in `backend/app/agents/answer_agent.py`:

```python
def _log_insufficient_answer(
    answer_input: AnswerAgentInput,
    *,
    failure_type: str,
    output: AnswerAgentOutput,
    missing_target: str | None = None,
) -> None:
```

Update its call to `build_insufficient_answer_log_output()`:

```python
output_payload=build_insufficient_answer_log_output(
    output=output,
    failure_type=failure_type,
    missing_target=missing_target,
),
```

In the insufficient-evidence branch, pass:

```python
missing_target=_missing_target_from_question(answer_input.question),
```

The branch should become:

```python
    if _has_insufficient_evidence(answer_input.verification):
        insufficient_output = _build_insufficient_evidence_output()
        _log_insufficient_answer(
            answer_input,
            failure_type="insufficient_evidence",
            output=insufficient_output,
            missing_target=_missing_target_from_question(answer_input.question),
        )
        return insufficient_output
```

- [ ] **Step 4: Update answer log service**

In `backend/app/services/answer_log_service.py`, update `build_insufficient_answer_log_output()` signature:

```python
def build_insufficient_answer_log_output(
    *,
    output: AnswerAgentOutput,
    failure_type: str,
    missing_target: str | None = None,
) -> dict[str, Any]:
```

Inside the function, build the payload as a variable and include the field only when present:

```python
    payload = {
        "final_answer": output.final_answer,
        "citations": [citation.model_dump(mode="json") for citation in output.citations],
        "reasoning_summary": output.reasoning_summary,
        "confidence": output.confidence,
        "self_check_result": output.self_check.model_dump(mode="json"),
        "fallback_reason": failure_type,
        "errors": [],
    }
    if missing_target is not None:
        payload["missing_target"] = missing_target
    return payload
```

Preserve the existing keys and values exactly if the current function has a different order; only add `missing_target`.

- [ ] **Step 5: Run targeted test**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py::test_missing_information_log_includes_question_specific_missing_target -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run answer logging tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py tests/test_answer_log_service.py -q
```

Expected:

```text
... passed
```

- [ ] **Step 7: Commit**

```powershell
git add backend/app/agents/answer_agent.py backend/app/services/answer_log_service.py backend/tests/test_answer_agent.py
git commit -m "chore: log question-specific missing information target"
```

---

## Final Verification

After all tasks are complete, run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py tests/test_verification_agent.py tests/test_answer_prompt_service.py tests/test_answer_log_service.py tests/test_hybrid_retrieval_service.py tests/test_retrieval_context_service.py tests/test_retrieval_agent.py tests/test_retrieval_api.py tests/test_chat_api.py tests/test_agent_runs_api.py -q
```

Expected:

```text
... passed
```

Then run:

```powershell
cd frontend
npm run build
```

Expected:

```text
tsc --noEmit && vite build
...
built in ...
```

## Live Smoke Verification

Start backend with live network access on a free port, then run:

```powershell
$doc='c90c48f9-0e3c-4d2c-9464-31594ae85820'
$base='http://127.0.0.1:8001'
$questions=@(
  'What animal does Alice see before she runs across the field?',
  'Which happened first: Alice saw the White Rabbit, or Alice fell down the rabbit-hole?',
  "What is Alice's bank account number?"
)
foreach ($q in $questions) {
  $body=@{question=$q; document_ids=@($doc)} | ConvertTo-Json -Compress
  Invoke-RestMethod -Method Post -Uri "$base/api/chat/ask" -ContentType 'application/json' -Body $body -TimeoutSec 180 |
    ConvertTo-Json -Depth 20
}
```

Expected:

- Direct rabbit question returns grounded answer with non-zero confidence.
- Chronology question answers that Alice saw the White Rabbit first.
- Bank-account question keeps the exact insufficient-evidence public answer.
- Citations contain no raw chunk IDs.

## Self-Review

Spec coverage:

- Priority 1 confidence calibration: Task 1.
- Priority 2 simple chronology reasoning: Task 2.
- Priority 3 retrieval precision: Task 3.
- Priority 4 exact citation display: Task 4.
- Priority 5 more specific missing-information diagnostics while preserving exact public response: Task 5.

Placeholder scan:

- No `TBD`, `TODO`, or unspecified "add tests" steps remain.
- Each task has exact file paths, test code, implementation snippets, commands, and expected results.

Type consistency:

- `VerifiedChunk.chunk_index` is optional and mirrored from `RetrievalCandidate.chunk_index`.
- `answer_evidence_payload()` includes `chunk_index` after schema support.
- Deterministic chronology returns the existing `AnswerAgentOutput` type and uses existing `Citation` / `AnswerSelfCheck` models.
