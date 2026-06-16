# Cross-Chunk Multi-Part Evidence Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make multi-part questions reliable when the required evidence spans adjacent document chunks, while preserving grounded answers, exact citations, safe insufficient-information responses, and existing public API contracts.

**Architecture:** Keep the Master Plan's linear LangGraph workflow (`Agent 1 -> Agent 2 -> Agent 3`). Agent 1 will deterministically add a bounded window of adjacent source chunks around ranked retrieval anchors. Agent 2 will validate coverage per independently requested requirement and may mark ordinary evidence gaps as missing information. Agent 3 will remain the final grounding guard and will convert exhausted grounding gaps into the existing insufficient-evidence result instead of turning a normal evidence gap into HTTP 500.

**Tech Stack:** Python 3, FastAPI, Pydantic, Supabase PostgreSQL, ShopAIKey chat completion, LangGraph, pytest.

---

## Scope and Master Plan Alignment

This plan aligns with:

- `docs/plans/Master_Plan.md` section 8.3: preserve `chunk_index` and source order.
- Section 8.5: allow chunk-to-chunk retrieval expansion.
- Sections 10.1-10.3: Agent 1 performs retrieval, expansion, scoring, and configurable Top-K selection.
- Sections 11.1-11.3: Agent 2 verifies relevance, sufficiency, context, and missing information.
- Sections 12.1-12.5: Agent 3 uses only verified evidence and fails safely when evidence is insufficient.
- Section 17 phases 6-9: preserve existing agent responsibilities and LangGraph orchestration.
- Sections 18.1-18.5: grounding, simple reasoning, citations, missing information, and traceability.

The implementation must not:

- Match the Alice question, Dodo, Caucus-race, comfits, thimble, or any test fixture in production code.
- Add expected answers or question-specific branches.
- Bypass Agent 2 verification for adjacent chunks.
- Treat adjacency alone as proof that a chunk answers the question.
- Use rejected evidence in Agent 3.
- Change `POST /api/chat/ask`, evidence, or agent-log response schemas.
- Add a database migration.
- Replace genuine provider, database, or malformed-schema failures with HTTP 200.
- Expand without a configured bound.

## Rejected Approaches

1. Increase `RETRIEVAL_FINAL_TOP_K` globally.
   This raises cost and noise but does not guarantee the neighboring continuation chunk is retained.

2. Special-case conjunctions or the reported question.
   This is language-dependent and violates the no-hardcoding requirement.

3. Let Agent 3 read unverified neighboring chunks.
   This violates Master Plan sections 12 and 18.1.

4. Convert every workflow exception to an insufficient-information response.
   This would hide genuine dependency and provider failures that must remain visible as errors.

## File Map

- Modify `backend/app/core/config.py`
  - Add bounded, configurable adjacent-context settings.
- Modify `backend/.env.example`
  - Document the new retrieval settings.
- Modify `backend/app/services/supabase_service.py`
  - Add a single-user, document-scoped chunk-index lookup.
- Modify `backend/app/services/hybrid_retrieval_service.py`
  - Expose the existing deterministic candidate scoring function for context candidates.
- Create `backend/app/services/retrieval_context_service.py`
  - Expand ranked anchors with deduplicated adjacent chunks and deterministic metadata.
- Modify `backend/app/schemas/retrieval.py`
  - Reuse existing `chunk_index` metadata for context candidates.
- Modify `backend/app/agents/schemas.py`
  - Preserve `chunk_index` in Agent 1 candidates and add internal requirement-level coverage contracts.
- Modify `backend/app/agents/retrieval_agent.py`
  - Invoke bounded context expansion before logging Agent 1 output.
- Modify `backend/app/agents/prompts.py`
  - Require Agent 2 coverage of every independently requested fact.
- Modify `backend/app/agents/verification_agent.py`
  - Validate requirement-level coverage and retry correctable coverage output once.
- Modify `backend/app/agents/answer_agent.py`
  - Return and log the existing insufficient-evidence output after repeated grounding insufficiency.
- Modify `backend/tests/test_config.py`
- Modify `backend/tests/test_supabase_service.py`
- Modify `backend/tests/test_hybrid_retrieval_service.py`
- Create `backend/tests/test_retrieval_context_service.py`
- Modify `backend/tests/test_retrieval_agent.py`
- Modify `backend/tests/test_verification_agent.py`
- Modify `backend/tests/test_answer_agent.py`
- Modify `backend/tests/test_langgraph_workflow.py`
- Modify `backend/tests/test_chat_api.py`
- Modify `README.md`

---

### Task 1: Add Bounded Adjacent-Context Configuration

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_config.py`

- [x] **Step 1: Write failing configuration tests**

Add tests proving defaults are bounded and invalid values are rejected:

```python
def test_retrieval_context_settings_have_bounded_defaults() -> None:
    settings = Settings()

    assert settings.retrieval_context_window == 1
    assert settings.retrieval_context_max_candidates == 8


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("retrieval_context_window", -1),
        ("retrieval_context_window", 4),
        ("retrieval_context_max_candidates", -1),
        ("retrieval_context_max_candidates", 51),
    ],
)
def test_retrieval_context_settings_reject_out_of_range_values(
    field_name: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field_name: value})
```

- [x] **Step 2: Run the tests and verify RED**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_config.py -k "retrieval_context" -v
```

Expected: FAIL because the settings do not exist.

- [x] **Step 3: Add the settings**

Add:

```python
retrieval_context_window: int = Field(default=1, ge=0, le=3)
retrieval_context_max_candidates: int = Field(default=8, ge=0, le=50)
```

Document:

```text
RETRIEVAL_CONTEXT_WINDOW=1
RETRIEVAL_CONTEXT_MAX_CANDIDATES=8
```

- [x] **Step 4: Run the tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_config.py -k "retrieval_context" -v
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/core/config.py backend/.env.example backend/tests/test_config.py
git commit -m "feat: configure bounded retrieval context"
```

---

### Task 2: Add Document-Scoped Chunk Index Lookup

**Files:**
- Modify: `backend/app/services/supabase_service.py`
- Test: `backend/tests/test_supabase_service.py`

- [x] **Step 1: Write failing service tests**

Cover:

- Empty index input returns `[]` without calling Supabase.
- Queries filter by `document_id` and `SINGLE_USER_ID`.
- Queries use `.in_("chunk_index", sorted_unique_indexes)`.
- Results are ordered by `chunk_index`.
- Dependency failures use the existing safe `SupabaseConnectionError`.

Representative test:

```python
def test_list_document_chunks_by_indexes_is_scoped_and_ordered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {"id": "chunk-5", "document_id": "doc-1", "chunk_index": 5},
        {"id": "chunk-6", "document_id": "doc-1", "chunk_index": 6},
    ]
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.in_.return_value = query
    query.order.return_value = query
    query.execute.return_value = SimpleNamespace(data=rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    rows = supabase_service.list_document_chunks_by_indexes(
        "doc-1",
        [6, 5, 6],
    )

    query.eq.assert_any_call("document_id", "doc-1")
    query.eq.assert_any_call("user_id", "single_user")
    query.in_.assert_called_once_with("chunk_index", [5, 6])
    query.order.assert_called_once_with("chunk_index")
    assert [row["chunk_index"] for row in rows] == [5, 6]
```

- [x] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest tests/test_supabase_service.py -k "chunks_by_indexes" -v
```

Expected: FAIL because `list_document_chunks_by_indexes` does not exist.

- [x] **Step 3: Implement the lookup**

Add:

```python
def list_document_chunks_by_indexes(
    document_id: str,
    chunk_indexes: list[int],
) -> list[dict]:
    normalized_indexes = sorted(set(chunk_indexes))
    if not normalized_indexes:
        return []

    client = get_supabase_client()
    try:
        response = (
            client.table("document_chunks")
            .select(
                "id, document_id, chunk_index, content, page_number, "
                "section_title"
            )
            .eq("document_id", document_id)
            .eq("user_id", _get_single_user_id())
            .in_("chunk_index", normalized_indexes)
            .order("chunk_index")
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document chunks index lookup", exc)

    return _response_rows(response)
```

- [x] **Step 4: Run the tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_supabase_service.py -k "chunks_by_indexes" -v
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/services/supabase_service.py backend/tests/test_supabase_service.py
git commit -m "feat: query source chunks by document position"
```

---

### Task 3: Expand Retrieval Anchors With Adjacent Source Context

**Files:**
- Create: `backend/app/services/retrieval_context_service.py`
- Modify: `backend/app/services/hybrid_retrieval_service.py`
- Modify: `backend/app/agents/schemas.py`
- Modify: `backend/app/agents/retrieval_agent.py`
- Test: `backend/tests/test_hybrid_retrieval_service.py`
- Test: `backend/tests/test_retrieval_context_service.py`
- Test: `backend/tests/test_retrieval_agent.py`

- [x] **Step 1: Write failing context-expansion tests**

Test these general behaviors:

- Window `0` or max candidates `0` returns anchors unchanged.
- An anchor at index `5` requests indexes `4` and `6`.
- Multiple anchors in one document perform one bulk lookup.
- Multiple documents stay document-scoped.
- Existing anchors are not duplicated.
- Missing boundary indexes are ignored.
- Added chunks preserve source metadata and have normalized scores.
- Added chunks have a deterministic retrieval reason identifying source adjacency.
- Expansion stops at `retrieval_context_max_candidates`.
- Final output remains sorted by `final_score`.

Use arbitrary document text, not Alice fixtures:

```python
def test_expand_retrieval_context_adds_missing_adjacent_continuation() -> None:
    anchors = [_candidate(chunk_id=ANCHOR_ID, document_id=DOC_ID, chunk_index=5)]

    expanded = retrieval_context_service.expand_retrieval_context(
        "What happened and what result followed?",
        anchors,
        context_window=1,
        max_context_candidates=2,
        chunk_lookup=lambda document_id, indexes: [
            {
                "id": str(NEXT_ID),
                "document_id": str(DOC_ID),
                "chunk_index": 6,
                "content": "The next source chunk states the requested result.",
                "page_number": 2,
                "section_title": "Result",
            }
        ],
    )

    assert {candidate.chunk_id for candidate in expanded} == {ANCHOR_ID, NEXT_ID}
    neighbor = next(item for item in expanded if item.chunk_id == NEXT_ID)
    assert neighbor.chunk_index == 6
    assert "adjacent source context" in neighbor.retrieval_reason.lower()
```

- [x] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest tests/test_retrieval_context_service.py tests/test_retrieval_agent.py -k "context or adjacent" -v
```

Expected: FAIL because expansion does not exist and Agent 1 drops `chunk_index`.

- [x] **Step 3: Preserve `chunk_index` in Agent 1 candidates**

Add to `RetrievalCandidate`:

```python
chunk_index: int | None = None
```

This is internal agent/debug metadata already required by Master Plan section 8.3. It does not alter public chat or evidence APIs.

- [x] **Step 4: Implement isolated expansion logic**

Rename `_score_candidate` in `hybrid_retrieval_service.py` to the public internal-service function `score_hybrid_candidate`, update `_score_candidates` to call it, export it in `__all__`, and retain its existing scoring behavior. Add a focused test proving the renamed function produces the same normalized component and final scores.

Create `retrieval_context_service.py` with this implementation shape:

```python
ChunkLookup = Callable[[str, list[int]], list[dict[str, Any]]]


def expand_retrieval_context(
    question: str,
    anchors: list[HybridRetrievalCandidate],
    *,
    context_window: int,
    max_context_candidates: int,
    chunk_lookup: ChunkLookup = supabase_service.list_document_chunks_by_indexes,
) -> list[HybridRetrievalCandidate]:
    if context_window <= 0 or max_context_candidates <= 0 or not anchors:
        return list(anchors)

    existing_ids = {candidate.chunk_id for candidate in anchors}
    requested_indexes: dict[UUID, set[int]] = {}
    parent_by_position: dict[
        tuple[UUID, int],
        HybridRetrievalCandidate,
    ] = {}

    for anchor in anchors:
        if anchor.chunk_index is None:
            continue
        for offset in range(-context_window, context_window + 1):
            neighbor_index = anchor.chunk_index + offset
            if offset == 0 or neighbor_index < 0:
                continue
            requested_indexes.setdefault(anchor.document_id, set()).add(
                neighbor_index
            )
            parent_by_position.setdefault(
                (anchor.document_id, neighbor_index),
                anchor,
            )

    context_candidates: list[HybridRetrievalCandidate] = []
    for document_id, indexes in requested_indexes.items():
        rows = chunk_lookup(str(document_id), sorted(indexes))
        for row in rows:
            chunk_id = UUID(str(row["id"]))
            chunk_index = int(row["chunk_index"])
            if chunk_id in existing_ids:
                continue
            parent = parent_by_position.get((document_id, chunk_index))
            if parent is None:
                continue
            candidate = HybridRetrievalCandidate(
                chunk_id=chunk_id,
                document_id=document_id,
                file_name=parent.file_name,
                file_type=parent.file_type,
                content=row.get("content"),
                content_preview=None,
                page_number=row.get("page_number"),
                section_title=row.get("section_title"),
                chunk_index=chunk_index,
                semantic_similarity=0.0,
                metadata=None,
                graph_relevance=0.0,
                keyword_overlap=0.0,
                metadata_match=0.0,
                recency_or_position_score=0.0,
                final_score=0.0,
                retrieval_reason=(
                    "Adjacent source context for retrieved chunk "
                    f"index {parent.chunk_index}."
                ),
            )
            context_candidates.append(
                hybrid_retrieval_service.score_hybrid_candidate(
                    candidate,
                    question=question,
                    document_ids=[item.document_id for item in anchors],
                    preserve_retrieval_reason=True,
                )
            )
            existing_ids.add(chunk_id)
            if len(context_candidates) >= max_context_candidates:
                break
        if len(context_candidates) >= max_context_candidates:
            break

    return sorted(
        [*anchors, *context_candidates],
        key=lambda candidate: candidate.final_score,
        reverse=True,
    )
```

Implementation rules:

- Group anchor indexes by document.
- Build indexes from `anchor_index - window` through `anchor_index + window`.
- Exclude negative indexes and existing anchor indexes.
- Query once per document.
- Convert returned rows into `HybridRetrievalCandidate`.
- Set semantic and graph scores to `0.0`; calculate keyword, metadata, position, and final score through `score_hybrid_candidate`.
- Add `preserve_retrieval_reason: bool = False` to `score_hybrid_candidate`; when true, keep the supplied adjacency reason instead of replacing it.
- Use retrieval reason `Adjacent source context for retrieved chunk index {anchor_index}.`
- Dedupe by `chunk_id`.
- Limit only newly added context candidates.
- Return all anchors plus context candidates sorted by final score.

- [x] **Step 5: Integrate expansion in Agent 1**

After `retrieve_hybrid` and before `RetrievalAgentOutput` validation:

```python
expanded_candidates = retrieval_context_service.expand_retrieval_context(
    validated_input.question,
    hybrid_response.candidates,
    context_window=settings.retrieval_context_window,
    max_context_candidates=settings.retrieval_context_max_candidates,
)
```

Build and log Agent 1 output from `expanded_candidates`.

- [x] **Step 6: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_hybrid_retrieval_service.py tests/test_retrieval_context_service.py tests/test_retrieval_agent.py -v
```

Expected: PASS.

- [x] **Step 7: Commit**

```powershell
git add backend/app/services/hybrid_retrieval_service.py backend/app/services/retrieval_context_service.py backend/app/agents/schemas.py backend/app/agents/retrieval_agent.py backend/tests/test_hybrid_retrieval_service.py backend/tests/test_retrieval_context_service.py backend/tests/test_retrieval_agent.py
git commit -m "feat: expand retrieval with adjacent source context"
```

---

### Task 4: Require Agent 2 Coverage for Every Requested Requirement

**Files:**
- Modify: `backend/app/agents/schemas.py`
- Modify: `backend/app/agents/prompts.py`
- Modify: `backend/app/agents/verification_agent.py`
- Test: `backend/tests/test_verification_agent.py`

- [x] **Step 1: Write failing requirement-level schema tests**

Add internal models:

```python
class EvidenceCoverageRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: str = Field(min_length=1)
    satisfied: bool
    evidence: list[EvidenceCoverageSelection]
    missing_detail: str | None = None
```

Extend `EvidenceCoverageReview` with:

```python
requirements: list[EvidenceCoverageRequirement] = Field(min_length=1)
```

Tests must reject:

- `answers_question=True` when any requirement is unsatisfied.
- A satisfied requirement with no evidence.
- An unsatisfied requirement with a blank `missing_detail`.
- Aggregate `selected_evidence` that is not the deduplicated union of satisfied requirement evidence.
- Unknown chunk IDs or non-source quotes inside requirement evidence.

- [x] **Step 2: Run schema tests and verify RED**

Run:

```powershell
python -m pytest tests/test_verification_agent.py -k "coverage_requirement" -v
```

Expected: FAIL because requirement-level coverage is absent.

- [x] **Step 3: Implement deterministic consistency validation**

The validator must enforce:

```text
answers_question == all(requirement.satisfied for requirement in requirements)
missing_information == not answers_question
satisfied requirement -> non-empty evidence and missing_detail is null
unsatisfied requirement -> missing_detail is non-empty
answerable review -> selected_evidence equals union of requirement evidence
non-answerable review -> selected_evidence is empty
```

Do not infer answerability from confidence.

- [x] **Step 4: Update the coverage prompt**

Require the reviewer to:

- Split the question into independently requested facts or actions.
- Keep requirements separate when connected by conjunctions, punctuation, or interrogatives.
- Evaluate each requirement against exact source quotes.
- Return non-answerable if any requirement is missing.
- Never claim that asking for a prize identifies what the prize was.
- Use generic instructions only; do not mention the regression question or expected answer.

The prompt JSON example must include at least two generic requirements, one evidence item per requirement, and a consistent aggregate `selected_evidence`.

- [x] **Step 5: Add multi-part regression tests**

Use synthetic source chunks:

```text
Chunk 10: The coordinator arranged the activity and declared everyone a winner.
Chunk 11: Each participant received a token, while the coordinator received a badge.
```

Verify:

- With only chunk 10, coverage returns `missing_information=True`.
- With chunks 10 and 11, all requirements can be satisfied.
- Agent 2 preserves exact quotes from both chunks.
- Distinct evidence from the same or adjacent chunks remains allowed.

- [x] **Step 6: Retry correctable coverage failures once**

Extend the existing bounded coverage retry to include:

- Invalid JSON/schema.
- Inconsistent requirement coverage.
- Unknown coverage chunk ID.
- Coverage quote not found in candidate source.

The correction message must identify only the failure category and restate exact-source requirements. It must not insert an answer or source quote. A second invalid response remains a controlled Agent 2 failure.

- [x] **Step 7: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_verification_agent.py -k "coverage" -v
```

Expected: PASS.

- [x] **Step 8: Commit**

```powershell
git add backend/app/agents/schemas.py backend/app/agents/prompts.py backend/app/agents/verification_agent.py backend/tests/test_verification_agent.py
git commit -m "fix: verify every requested evidence requirement"
```

---

### Task 5: Treat Exhausted Grounding Gaps as Insufficient Evidence

**Files:**
- Modify: `backend/app/agents/answer_agent.py`
- Test: `backend/tests/test_answer_agent.py`
- Test: `backend/tests/test_langgraph_workflow.py`
- Test: `backend/tests/test_chat_api.py`

- [x] **Step 1: Write failing Agent 3 tests**

Prove the distinction:

- Provider/network errors still raise `_AnswerAgentFailure("provider_error")`.
- Invalid provider JSON/schema still raises a controlled workflow failure.
- After one bounded regeneration, a second claim-grounding/readiness failure returns `_build_insufficient_evidence_output()`.
- The fallback has confidence `0.0`, no unsupported citations, and `is_ready=False`.
- The fallback is logged as an Agent 3 completed insufficient-evidence outcome with the failure category.

- [x] **Step 2: Write failing API/workflow tests**

Add `from app.agents import answer_agent as answer_agent_module` to
`backend/tests/test_chat_api.py`, then add:

```python
def test_chat_ask_returns_200_when_grounding_exhaustion_becomes_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, chat_api = _chat_client()
    monkeypatch.setattr(
        chat_api.chat_service,
        "prepare_chat_persistence",
        Mock(
            return_value=chat_service.ChatPersistenceContext(
                session={"id": str(SESSION_ID)},
                user_message={"id": "user-message-id"},
            )
        ),
    )
    monkeypatch.setattr(
        chat_api,
        "run_qa_workflow",
        Mock(
            return_value={
                "answer": answer_agent_module.INSUFFICIENT_EVIDENCE_ANSWER,
                "confidence": 0.0,
                "citations": [],
                "agent_run_id": AGENT_RUN_ID,
            }
        ),
    )
    monkeypatch.setattr(
        chat_api.chat_service,
        "persist_assistant_message",
        Mock(),
    )

    response = client.post(
        "/api/chat/ask",
        json={
            "question": "What happened and what result followed?",
            "document_ids": [str(DOCUMENT_ID)],
        },
    )

    assert response.status_code == 200
    assert response.json()["confidence"] == 0.0
    assert response.json()["citations"] == []
```

Retain existing tests proving dependency/provider failures return HTTP 500.

- [x] **Step 3: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_answer_agent.py tests/test_langgraph_workflow.py tests/test_chat_api.py -k "grounding_exhaustion or workflow_failure" -v
```

Expected: the grounding exhaustion case raises `AgentRunWorkflowError` and returns 500.

- [x] **Step 4: Implement the narrow fallback**

Only catch the second `AnswerEvidenceValidationError` produced by claim-grounding/readiness validation. Do not catch provider, JSON, Pydantic, persistence, or citation-membership failures.

Return:

```python
insufficient_output = _build_insufficient_evidence_output()
_log_insufficient_answer(
    answer_input,
    failure_type="self_check_failed",
    output=insufficient_output,
)
return insufficient_output
```

Also log the pre-existing early insufficient-evidence path so every Agent 3 execution remains traceable under Master Plan section 18.5.

- [x] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_answer_agent.py tests/test_langgraph_workflow.py tests/test_chat_api.py -k "insufficient or grounding or workflow_failure" -v
```

Expected: PASS. Genuine workflow dependency failures still return 500.

- [x] **Step 6: Commit**

```powershell
git add backend/app/agents/answer_agent.py backend/tests/test_answer_agent.py backend/tests/test_langgraph_workflow.py backend/tests/test_chat_api.py
git commit -m "fix: fail safely on exhausted answer grounding"
```

---

### Task 6: End-to-End Regression, Documentation, and Verification

**Files:**
- Modify: `README.md`
- Test: all backend tests

- [x] **Step 1: Add an end-to-end synthetic workflow regression**

In `backend/tests/test_langgraph_workflow.py`, model a question requiring:

1. How an event was organized.
2. Who succeeded.
3. What two recipient groups received.

Place the organization and winner in one chunk and the distributed items in the next chunk. Assert:

- Agent 1 output contains both source indexes after context expansion.
- Agent 2 verifies evidence for every requirement.
- Agent 3 returns a grounded answer with citations from both chunks.
- Confidence is greater than `0.0`.
- No production code or test helper depends on Alice-specific terms.

- [x] **Step 2: Update README**

Document:

- Adjacent source context is bounded and configurable.
- Adjacent chunks are candidates only and still require Agent 2 verification.
- Multi-part coverage must satisfy every requested requirement.
- Ordinary grounding insufficiency returns the safe insufficient-evidence answer.
- Provider, storage, and malformed-contract failures remain errors.

- [x] **Step 3: Run focused regression suites**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_hybrid_retrieval_service.py tests/test_retrieval_context_service.py tests/test_retrieval_agent.py tests/test_verification_agent.py tests/test_answer_agent.py tests/test_langgraph_workflow.py tests/test_chat_api.py -q
```

Expected: PASS.

- [x] **Step 4: Run the full backend suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass. Existing unrelated deprecation warnings may remain, but no new warnings or failures are introduced.

- [x] **Step 5: Check formatting and accidental hardcoding**

Run:

```powershell
git diff --check
rg -n -i "dodo|caucus|comfits|thimble|alice" backend/app
```

Expected:

- `git diff --check` reports no errors.
- The source scan reports no newly added regression-specific production logic.

- [x] **Step 6: Live verification**

Restart the backend from the modified workspace and ask:

```text
How did the Dodo organize the Caucus-race to get the animals dry, who won the race, and what prizes were distributed to the participants and Alice?
```

Expected:

- HTTP 200.
- The answer covers organization, winner, participant prizes, and Alice's prize.
- Citations include the exact source passages required for all parts.
- Confidence is greater than `0.0`.
- Agent logs show adjacent context retrieval, successful requirement coverage, and successful Agent 3 grounding.

Also ask one unrelated synthetic multi-part question whose evidence crosses a chunk boundary. Expected: the same behavior without question-specific code.

- [x] **Step 7: Commit**

```powershell
git add README.md backend/tests/test_langgraph_workflow.py
git commit -m "test: cover cross-chunk multi-part answers"
```

---

## Completion Criteria

- Adjacent context expansion is bounded, configurable, document-scoped, and deduplicated.
- Every adjacent chunk still passes Agent 2 exact-quote verification.
- Agent 2 cannot mark a multi-part question answerable while a requested requirement is unsatisfied.
- Correctable coverage formatting/quote errors receive at most one retry.
- Agent 3 does not return an incomplete grounded answer.
- Repeated grounding insufficiency returns the existing insufficient-evidence response, not HTTP 500.
- Genuine provider, database, malformed-contract, and persistence failures still return controlled errors.
- Public API schemas remain unchanged.
- Agent logs remain complete and explain retrieval, verification, fallback, and final output.
- Full backend test suite and two live cross-chunk questions pass.
