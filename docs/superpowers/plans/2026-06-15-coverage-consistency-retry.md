# Coverage Consistency Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent contradictory evidence-coverage responses from discarding valid citations.

**Architecture:** Enforce coverage consistency in the Pydantic contract, retry the coverage provider once with a correction payload when validation fails, and fail closed after the bounded retry. Keep all public API schemas unchanged.

**Tech Stack:** Python, Pydantic, pytest, FastAPI agent workflow

---

### Task 1: Add Coverage Consistency Regression Tests

**Files:**
- Modify: `backend/tests/test_verification_agent.py`

- [x] **Step 1: Write a failing retry test**

Add a test where the initial verification selects an exact answer quote, the
first coverage response has populated `selected_evidence` with
`answers_question: false`, and the second coverage response corrects the flags.
Assert that Agent 2 returns the selected quote as verified evidence.

- [x] **Step 2: Write a failing bounded-failure test**

Add a test where both coverage responses remain contradictory. Assert that
`run_verification_agent` raises the existing controlled
`VerificationAgentError` and logs a failed Agent 2 step.

- [x] **Step 3: Run the focused tests**

Run:

```powershell
python -m pytest tests/test_verification_agent.py -k "coverage and inconsistent" -v
```

Expected: the new tests fail because coverage validation has no retry.

### Task 2: Implement Consistency Validation and Retry

**Files:**
- Modify: `backend/app/agents/schemas.py`
- Modify: `backend/app/agents/prompts.py`
- Modify: `backend/app/agents/verification_agent.py`

- [x] **Step 1: Tighten the schema**

Extend `EvidenceCoverageReview.validate_consistent_coverage` so a
non-answerable review rejects populated `selected_evidence`.

- [x] **Step 2: Correct the prompt**

Use a consistent answerable JSON example and state that non-answerable reviews
must return `selected_evidence: []`.

- [x] **Step 3: Add one bounded retry**

When `_parse_coverage_review` raises `coverage_validation_error`, call the
coverage provider once more with the original candidate payload, the invalid
response, and an instruction to correct only the contradictory coverage
fields. Parse the retry through the same strict schema.

- [x] **Step 4: Run focused verification tests**

Run:

```powershell
python -m pytest tests/test_verification_agent.py -v
```

Expected: all verification-agent tests pass.

- [x] **Step 5: Tolerate terminal punctuation-only quote drift**

Add a failing coverage test where the source excerpt ends with a colon and the
provider quote ends with a period. Update quote membership normalization to
ignore only trailing `.`, `,`, `:`, `;`, `!`, and `?` characters while keeping
the quote text otherwise strict.

- [x] **Step 6: Default omitted reasoning permission safely**

Add a parser regression where an otherwise valid verified chunk omits
`supports_simple_reasoning`. Set the Pydantic field default to `false` so the
finalized output remains complete without granting inference permission.

- [x] **Step 7: Preserve literal source values in Agent 3**

Add an answer prompt regression requiring labels, names, titles, identifiers,
codes, and numeric values to remain verbatim from verified evidence. Permit
translation only for surrounding explanatory prose.

- [x] **Step 8: Retry factual grounding failures once**

Add a factual-answer regression where the first grounded draft is rejected and
the second draft passes. Generalize the existing bounded Agent 3 retry guard to
all answers with verified evidence, and keep the second grounding failure
fail-closed.

### Task 3: Verify the Complete Workflow

**Files:**
- No production file changes

- [x] **Step 1: Run the full backend suite**

Run:

```powershell
python -m pytest -q
```

Expected: all backend tests pass.

- [x] **Step 2: Restart backend from main**

Restart Uvicorn on `127.0.0.1:8000` so the live process loads the fix.

- [x] **Step 3: Re-run the Alice jar question**

Ask:

```text
What was the label on the jar that Alice took from the shelf while falling down the well, and what was inside it?
```

Expected: the answer states `ORANGE MARMALADE`, says the jar was empty, and
returns at least one citation from `alice-in-wonderland.txt`.
