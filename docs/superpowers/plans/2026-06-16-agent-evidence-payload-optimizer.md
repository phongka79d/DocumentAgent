# Agent Evidence Payload Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce ShopAIKey chat-token usage in the RAG workflow while preserving grounded answers, exact citations, multi-part evidence coverage, and existing public API contracts.

**Architecture:** Keep the Master Plan's linear LangGraph workflow (`Agent 1 -> Agent 2 -> Agent 3`). Agent 1 continues broad hybrid retrieval and bounded adjacent-context expansion, then a deterministic payload optimizer compacts candidate text before LLM verification. Agent 2 and Agent 3 remain the only components allowed to verify and answer from evidence; validation continues to use source-backed exact quotes and fails closed on malformed provider output or rejected evidence.

**Tech Stack:** Python 3, FastAPI, Pydantic settings, ShopAIKey chat completions, LangGraph, pytest.

---

## Scope and Master Plan Alignment

This plan aligns with `docs/plans/Master_Plan.md`:

- Section 5.3: preserve the three-agent LangGraph chat workflow.
- Sections 8.3 and 8.5: preserve chunk index and bounded chunk-to-chunk retrieval expansion.
- Sections 10.1-10.3: keep Agent 1 responsible for retrieval, scoring, and Top-K selection.
- Sections 11.1-11.3: keep Agent 2 responsible for relevance, sufficiency, and missing-information verification.
- Sections 12.1-12.5: keep Agent 3 answering only from verified evidence with citations and self-check.
- Section 18: preserve grounding, simple reasoning, citations, missing-information behavior, and traceability.

The implementation must not:

- Add Alice-specific, question-specific, or fixture-specific production logic.
- Hardcode expected answers, expected quotes, or document names.
- Reduce correctness by letting Agent 3 read unverified evidence.
- Remove Agent 2 coverage verification or Agent 3 grounding checks.
- Change public API response schemas for chat, evidence, or agent logs.
- Add a database migration.
- Hide provider, database, schema, or dependency failures behind HTTP 200.
- Depend on a specific language; Vietnamese and English questions must both use the same generic optimizer.

## Current Root Cause

Live logs showed a Mabel question run with:

- Agent 1 returned `13` candidates.
- Agent 1 output was about `87,563` JSON characters.
- Agent 2 received that large candidate payload.
- ShopAIKey billing showed repeated `gpt-4o-mini` calls around `21k-22k` input tokens.

The high token cost comes from sending many full-size retrieved chunks to Agent 2 verification and coverage review, sometimes again during retries. Agent 3 prompts are much smaller because they receive only verified evidence.

## File Map

- Modify `backend/app/core/config.py`
  - Add bounded optimizer and diagnostics settings.
- Modify `backend/.env.example`
  - Document optimizer settings.
- Create `backend/app/services/evidence_payload_optimizer.py`
  - Build compact, source-backed snippets for Agent 2 LLM prompts.
- Modify `backend/app/agents/schemas.py`
  - Add optional source-content metadata for internal validation if needed without changing public API contracts.
- Modify `backend/app/agents/verification_agent.py`
  - Use compact candidates for LLM prompts while validating quotes against original source candidates.
- Modify `backend/app/agents/answer_agent.py`
  - Add prompt-size diagnostics around Agent 3 calls without changing answer behavior.
- Modify `backend/app/services/shopaikey_service.py`
  - Add optional safe diagnostics for chat-completion request sizes.
- Modify `backend/tests/test_config.py`
- Create `backend/tests/test_evidence_payload_optimizer.py`
- Modify `backend/tests/test_verification_agent.py`
- Modify `backend/tests/test_answer_agent.py`
- Modify `backend/tests/test_langgraph_workflow.py`
- Modify `backend/tests/test_chat_api.py`
- Modify `README.md`

---

### Task 1: Add Bounded Optimizer Configuration

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write failing configuration tests**

Add tests that prove the optimizer has safe defaults and rejects invalid ranges:

```python
def test_evidence_payload_optimizer_settings_have_bounded_defaults() -> None:
    settings = Settings()

    assert settings.agent_evidence_snippet_max_chars == 1800
    assert settings.agent_evidence_snippet_context_sentences == 1
    assert settings.agent_verification_max_candidates == 8
    assert settings.agent_coverage_max_candidates == 8
    assert settings.agent_llm_payload_warn_chars == 30000


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("agent_evidence_snippet_max_chars", 0),
        ("agent_evidence_snippet_max_chars", 20001),
        ("agent_evidence_snippet_context_sentences", -1),
        ("agent_evidence_snippet_context_sentences", 6),
        ("agent_verification_max_candidates", 0),
        ("agent_verification_max_candidates", 51),
        ("agent_coverage_max_candidates", 0),
        ("agent_coverage_max_candidates", 51),
        ("agent_llm_payload_warn_chars", 0),
    ],
)
def test_evidence_payload_optimizer_settings_reject_out_of_range_values(
    field_name: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field_name: value})
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_config.py -k "evidence_payload_optimizer" -v
```

Expected: FAIL because the settings do not exist.

- [ ] **Step 3: Add the settings**

Add to `Settings`:

```python
agent_evidence_snippet_max_chars: int = Field(default=1800, ge=1, le=20000)
agent_evidence_snippet_context_sentences: int = Field(default=1, ge=0, le=5)
agent_verification_max_candidates: int = Field(default=8, ge=1, le=50)
agent_coverage_max_candidates: int = Field(default=8, ge=1, le=50)
agent_llm_payload_warn_chars: int = Field(default=30000, ge=1)
```

- [ ] **Step 4: Document the settings**

Add to `backend/.env.example`:

```text
AGENT_EVIDENCE_SNIPPET_MAX_CHARS=1800
AGENT_EVIDENCE_SNIPPET_CONTEXT_SENTENCES=1
AGENT_VERIFICATION_MAX_CANDIDATES=8
AGENT_COVERAGE_MAX_CANDIDATES=8
AGENT_LLM_PAYLOAD_WARN_CHARS=30000
```

- [ ] **Step 5: Run the tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_config.py -k "evidence_payload_optimizer" -v
```

Expected: PASS.

---

### Task 2: Build Generic Evidence Payload Optimizer

**Files:**
- Create: `backend/app/services/evidence_payload_optimizer.py`
- Test: `backend/tests/test_evidence_payload_optimizer.py`

- [ ] **Step 1: Write failing tests for generic snippet extraction**

Create tests proving the optimizer:

- preserves candidate identity and metadata,
- selects text based on question-term overlap,
- includes neighboring sentence context,
- never invents text,
- caps snippet length,
- works without Alice-specific strings.

Example test:

```python
def test_optimize_candidates_keeps_relevant_sentence_window_without_inventing_text() -> None:
    candidate = _candidate(
        content=(
            "The document starts with unrelated background. "
            "The refund period lasts 30 days after purchase. "
            "Customers must provide the original receipt. "
            "The final paragraph is unrelated."
        )
    )

    optimized = optimize_candidates_for_verification(
        question="What is the refund period and what proof is required?",
        candidates=[candidate],
        max_candidates=8,
        snippet_max_chars=140,
        context_sentences=1,
    )

    assert len(optimized) == 1
    assert optimized[0].chunk_id == candidate.chunk_id
    assert optimized[0].document_id == candidate.document_id
    assert "refund period lasts 30 days" in optimized[0].content
    assert "original receipt" in optimized[0].content
    assert optimized[0].content in candidate.content
```

- [ ] **Step 2: Run the optimizer tests and verify RED**

Run:

```powershell
python -m pytest tests/test_evidence_payload_optimizer.py -q
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement sentence splitting and scoring**

Create `backend/app/services/evidence_payload_optimizer.py` with:

```python
from __future__ import annotations

import re
from collections.abc import Iterable

from app.agents.schemas import RetrievalCandidate

_WORD_PATTERN = re.compile(r"[\\w']+", re.UNICODE)
_SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?。！？])\\s+")


def optimize_candidates_for_verification(
    *,
    question: str,
    candidates: list[RetrievalCandidate],
    max_candidates: int,
    snippet_max_chars: int,
    context_sentences: int,
) -> list[RetrievalCandidate]:
    selected_candidates = candidates[:max_candidates]
    return [
        candidate.model_copy(
            update={
                "content": _snippet_for_candidate(
                    question=question,
                    content=candidate.content,
                    snippet_max_chars=snippet_max_chars,
                    context_sentences=context_sentences,
                )
            }
        )
        for candidate in selected_candidates
    ]
```

Then add helpers:

```python
def _snippet_for_candidate(
    *,
    question: str,
    content: str,
    snippet_max_chars: int,
    context_sentences: int,
) -> str:
    normalized_content = content.strip()
    if len(normalized_content) <= snippet_max_chars:
        return normalized_content

    sentence_spans = _sentence_spans(normalized_content)
    if not sentence_spans:
        return normalized_content[:snippet_max_chars].rstrip()

    question_terms = _content_terms(question)
    scored_indexes = sorted(
        range(len(sentence_spans)),
        key=lambda index: (
            _sentence_score(
                normalized_content[sentence_spans[index][0] : sentence_spans[index][1]],
                question_terms,
            ),
            -index,
        ),
        reverse=True,
    )
    best_index = scored_indexes[0]
    start_index = max(0, best_index - context_sentences)
    end_index = min(len(sentence_spans), best_index + context_sentences + 1)

    while start_index > 0 or end_index < len(sentence_spans):
        start_char = sentence_spans[start_index][0]
        end_char = sentence_spans[end_index - 1][1]
        if end_char - start_char >= snippet_max_chars:
            break
        left_score = (
            _sentence_score(
                normalized_content[
                    sentence_spans[start_index - 1][0] : sentence_spans[start_index - 1][1]
                ],
                question_terms,
            )
            if start_index > 0
            else -1
        )
        right_score = (
            _sentence_score(
                normalized_content[
                    sentence_spans[end_index][0] : sentence_spans[end_index][1]
                ],
                question_terms,
            )
            if end_index < len(sentence_spans)
            else -1
        )
        if right_score > left_score and end_index < len(sentence_spans):
            next_end = sentence_spans[end_index][1]
            if next_end - start_char > snippet_max_chars:
                break
            end_index += 1
        elif start_index > 0:
            next_start = sentence_spans[start_index - 1][0]
            if end_char - next_start > snippet_max_chars:
                break
            start_index -= 1
        else:
            break

    return normalized_content[
        sentence_spans[start_index][0] : sentence_spans[end_index - 1][1]
    ].strip()
```

Use generic tokenization:

```python
def _content_terms(value: str) -> set[str]:
    return {
        token.lower()
        for token in _WORD_PATTERN.findall(value)
        if len(token) > 2
    }


def _sentence_score(sentence: str, question_terms: set[str]) -> int:
    if not question_terms:
        return 0
    sentence_terms = _content_terms(sentence)
    return len(sentence_terms & question_terms)


def _sentence_spans(content: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for part in _SENTENCE_BOUNDARY_PATTERN.split(content):
        if not part:
            continue
        start = content.find(part, cursor)
        if start < 0:
            continue
        end = start + len(part)
        spans.append((start, end))
        cursor = end
    return spans
```

- [ ] **Step 4: Run the optimizer tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_evidence_payload_optimizer.py -q
```

Expected: PASS.

---

### Task 3: Use Compact Candidates in Agent 2 Without Weakening Validation

**Files:**
- Modify: `backend/app/agents/verification_agent.py`
- Test: `backend/tests/test_verification_agent.py`

- [ ] **Step 1: Write failing tests for compact prompt payloads**

Add tests proving:

- `_build_verification_messages()` uses compact candidate content.
- `_build_coverage_messages()` uses compact candidate content.
- quote validation still checks original candidate content.

Example:

```python
def test_verification_prompt_uses_compact_candidates_but_quote_validation_uses_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_quote = "The warranty lasts two years after purchase."
    long_content = "Unrelated start. " + source_quote + " Unrelated end. " * 200
    payload = _verification_input_payload(
        candidates=[_candidate_payload(content=long_content)]
    )
    monkeypatch.setattr(
        verification_agent_module,
        "get_settings",
        lambda: _settings(agent_evidence_snippet_max_chars=120),
    )

    messages = verification_agent_module._build_verification_messages(
        VerificationAgentInput.model_validate(payload)
    )
    prompt = messages[1]["content"]

    assert source_quote in prompt
    assert len(prompt) < len(long_content)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest tests/test_verification_agent.py -k "compact_candidates" -v
```

Expected: FAIL because Agent 2 still sends full candidate content.

- [ ] **Step 3: Add compact candidate helper**

In `verification_agent.py`, import:

```python
from app.core.config import get_settings
from app.services.evidence_payload_optimizer import optimize_candidates_for_verification
```

Add:

```python
def _compact_candidates_for_llm(
    input_data: VerificationAgentInput,
    *,
    max_candidates: int,
) -> list[RetrievalCandidate]:
    settings = get_settings()
    return optimize_candidates_for_verification(
        question=input_data.question,
        candidates=input_data.candidates,
        max_candidates=max_candidates,
        snippet_max_chars=settings.agent_evidence_snippet_max_chars,
        context_sentences=settings.agent_evidence_snippet_context_sentences,
    )
```

- [ ] **Step 4: Use compact candidates only in prompt builders**

Update `_build_compact_evidence_payload()` and `_build_coverage_messages()` to receive compact candidates for their prompt payloads. Keep validation functions such as `_validate_candidate_membership()`, `_validate_candidate_quotes()`, `_validate_coverage_review_evidence()`, and `_canonicalize_coverage_review_evidence()` using the original `input_data.candidates`.

- [ ] **Step 5: Run verification tests**

Run:

```powershell
python -m pytest tests/test_verification_agent.py -q
```

Expected: PASS.

---

### Task 4: Limit Coverage Review to Source-Backed Relevant Candidates

**Files:**
- Modify: `backend/app/agents/verification_agent.py`
- Test: `backend/tests/test_verification_agent.py`

- [ ] **Step 1: Write failing tests for coverage candidate limit**

Add a test proving coverage review uses `agent_coverage_max_candidates` and does not receive all retrieved candidates when Agent 1 returns more than the coverage limit.

```python
def test_coverage_prompt_uses_configured_candidate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _verification_input_payload(
        candidates=[
            _candidate_payload(content=f"Candidate {index} has unique evidence.")
            for index in range(12)
        ]
    )
    monkeypatch.setattr(
        verification_agent_module,
        "get_settings",
        lambda: _settings(agent_coverage_max_candidates=6),
    )

    messages = verification_agent_module._build_coverage_messages(
        VerificationAgentInput.model_validate(payload)
    )
    prompt = messages[1]["content"]

    assert "Candidate 0" in prompt
    assert "Candidate 5" in prompt
    assert "Candidate 6" not in prompt
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest tests/test_verification_agent.py -k "coverage_prompt_uses_configured_candidate_limit" -v
```

Expected: FAIL because coverage currently receives every candidate.

- [ ] **Step 3: Apply configured limits**

Use:

```python
settings.agent_verification_max_candidates
settings.agent_coverage_max_candidates
```

in Agent 2 prompt construction. Do not mutate `input_data.candidates`.

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_verification_agent.py -q
```

Expected: PASS.

---

### Task 5: Add Safe LLM Payload Diagnostics

**Files:**
- Modify: `backend/app/services/shopaikey_service.py`
- Modify: `backend/app/agents/verification_agent.py`
- Modify: `backend/app/agents/answer_agent.py`
- Test: `backend/tests/test_verification_agent.py`
- Test: `backend/tests/test_answer_agent.py`

- [ ] **Step 1: Write failing tests for diagnostics**

Tests should assert logs include safe metadata only:

- agent phase label,
- message character count,
- candidate count,
- retry flag,
- no raw API key,
- no full evidence text in warning logs.

- [ ] **Step 2: Add helper to estimate message size**

In `shopaikey_service.py`:

```python
def estimate_chat_messages_chars(messages: list[dict[str, str]]) -> int:
    return sum(len(message.get("content", "")) for message in messages)
```

- [ ] **Step 3: Add diagnostics at Agent 2/3 call sites**

Before each `chat_completion()` call, log:

```python
logger.info(
    "LLM payload prepared. agent=%s phase=%s message_chars=%s candidate_count=%s retry=%s",
    VERIFICATION_AGENT_NAME,
    phase,
    shopaikey_service.estimate_chat_messages_chars(messages),
    len(input_data.candidates),
    retry,
)
```

If `message_chars >= settings.agent_llm_payload_warn_chars`, log a warning with the same metadata only.

- [ ] **Step 4: Run diagnostics tests**

Run:

```powershell
python -m pytest tests/test_verification_agent.py tests/test_answer_agent.py -k "payload" -q
```

Expected: PASS.

---

### Task 6: Preserve End-to-End Behavior and Measure Reduction

**Files:**
- Modify: `backend/tests/test_langgraph_workflow.py`
- Modify: `backend/tests/test_chat_api.py`
- Modify: `README.md`

- [ ] **Step 1: Add end-to-end regression tests**

Cover:

- multi-part question still reaches Agent 2 and Agent 3,
- output schemas are unchanged,
- citations are exact verified quotes,
- insufficient evidence still returns safe output,
- provider/schema failures still fail closed.

- [ ] **Step 2: Add a payload-size regression test**

Use a synthetic long-candidate fixture and assert Agent 2 prompt chars are lower after optimization:

```python
def test_agent_2_prompt_size_is_reduced_for_long_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_candidates = [
        _candidate_payload(content=("Noise sentence. " * 300) + "Refund lasts 30 days.")
        for _ in range(12)
    ]
    payload = _verification_input_payload(candidates=long_candidates)

    messages = verification_agent_module._build_verification_messages(
        VerificationAgentInput.model_validate(payload)
    )
    prompt_chars = sum(len(message["content"]) for message in messages)

    assert prompt_chars < 30000
```

- [ ] **Step 3: Update README**

Document:

- why payload optimization exists,
- which env vars control it,
- how to inspect LLM payload diagnostics,
- safe tuning guidance.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/test_evidence_payload_optimizer.py tests/test_verification_agent.py tests/test_answer_agent.py tests/test_langgraph_workflow.py tests/test_chat_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Run full backend suite**

Run:

```powershell
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 6: Live smoke test**

Start backend:

```powershell
Set-Location backend
python -m uvicorn app.main:app --reload
```

Run a multi-part document question through:

```text
POST http://127.0.0.1:8000/api/chat/ask
```

Verify:

- HTTP 200 for answerable questions,
- citations are present,
- agent logs still show Agent 1, Agent 2, Agent 3,
- Agent 2 payload diagnostics are below the pre-optimization baseline.

---

## Success Criteria

- Full backend tests pass.
- No public API response shape changes.
- Agent 2 prompt size drops materially for long retrieved candidates.
- Multi-part, cross-chunk questions remain answerable when evidence exists.
- Agent 3 still uses only verified evidence.
- Rejected evidence still fails closed.
- No production code branches on document name, Alice content, or specific question text.

