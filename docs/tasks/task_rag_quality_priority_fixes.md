# RAG Quality Priority Fixes Execution Tasks

## Purpose

Create a detailed execution task file for the approved RAG quality priority fixes plan. This task file guides a future Execution Agent to fix confidence calibration, simple chronology reasoning, retrieval precision, exact citation rendering, and missing-information diagnostics from `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md`.

## Authoritative Source

- Primary source: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md`
- Evidence source: `docs/reports/rag_live_evaluation_2026-06-17.md`
- Output path note: the primary source is not `docs/plans/Plan_N.md`. `docs/plans/Plan_16.md` already exists, so this file intentionally uses `docs/tasks/task_rag_quality_priority_fixes.md` instead of `docs/tasks/task_16.md`.

## Source Section Index

- `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## File Structure` -> files and modules expected to change.
- `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 1: Priority 1 - Fix Grounded Answer Confidence Calibration` -> confidence bug, test, implementation, and validation requirements.
- `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 2: Priority 2 - Add Deterministic Simple Chronology Answering` -> verified chunk order, chronology answer path, schema/prompt changes, and validation requirements.
- `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 3: Priority 3 - Improve Retrieval Precision With Score Gating` -> retrieval threshold settings, hybrid filtering, context expansion gating, and validation requirements.
- `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 4: Priority 4 - Render Exact MVP Citation Format` -> frontend citation display format and build validation.
- `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 5: Priority 5 - Add Specific Missing-Target Detail to Internal Answer Logs` -> internal missing-target logging while preserving public fallback text.
- `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Final Verification` -> backend and frontend verification commands.
- `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Live Smoke Verification` -> live post-fix smoke questions and expected behavior.
- `docs/reports/rag_live_evaluation_2026-06-17.md` > `## Recommendations by Priority` -> source rationale for priority order.

## Approved Architecture Summary

Keep the existing three-agent RAG workflow and public API contract. The backend remains FastAPI/Pydantic/LangGraph with Supabase, Qdrant, and ShopAIKey integrations; the frontend remains React, TypeScript, Vite, React Router, Axios, and plain CSS.

The fixes are narrow and priority ordered:

1. Calibrate final answer confidence after grounding.
2. Preserve source order and use it for deterministic simple chronology answers.
3. Reduce retrieval noise with score gates.
4. Render citations in exact MVP format.
5. Add question-specific missing target to internal logs without changing the exact public insufficient-evidence answer.

## Global Implementation Rules

- Follow the source plan priority order unless a task is blocked by a validation failure from an earlier batch.
- Use TDD for each code change: add the failing test first, run it, implement the smallest fix, rerun tests.
- Do not change `.env`, commit secrets, print secret values, or create external provider resources.
- Do not replace the existing RAG architecture, providers, frontend framework, or API route structure.
- Keep public response schemas backward compatible unless the source explicitly requires otherwise.
- Preserve exact public missing-information answer text.
- Preserve raw `agent_runs` / `agent_steps` safety boundaries and safe error behavior.
- Use live smoke tests only after local targeted tests pass.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable Python and TypeScript.
- Use descriptive names for modules, functions, variables, settings, components, and tests.
- Keep functions, components, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow existing FastAPI, Pydantic, pytest, React, TypeScript, and CSS conventions already present in the repository.
- Use clear typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless explicitly required by the source plan.
- Add comments only for non-obvious decisions or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Avoid adding formatters, linters, frameworks, libraries, or architecture changes outside the source plan.

## Batch Map

- Batch01 - Confidence Calibration
- Batch02 - Simple Chronology Reasoning
- Batch03 - Retrieval Precision Gates
- Batch04 - Exact Citation Display
- Batch05 - Missing-Information Diagnostics
- Batch06 - Final Verification and Live Smoke

## Mandatory Batch01 - Confidence Calibration

### Goal

Ensure grounded, self-check-passing answers do not return public `confidence: 0.0` only because the LLM draft supplied zero confidence.

### Why this batch exists

The live report found a fully grounded direct answer with Agent 2 confidence `0.9`, grounding confidence `1.0`, self-check ready `true`, and public confidence `0.0`.

### Inputs / Dependencies

- Primary source plan.
- Existing answer agent tests and helpers in `backend/tests/test_answer_agent.py`.
- No user action required.

### Tasks

- [x] (01A): Add failing confidence calibration test
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 1: Priority 1 - Fix Grounded Answer Confidence Calibration` > `### Steps`
  - Source Requirements:
    - Add `test_run_answer_agent_ignores_zero_draft_confidence_when_grounding_passes`.
    - Verify the current behavior fails with public confidence `0.0`.
  - Details: Add the test specified in the source plan to `backend/tests/test_answer_agent.py`.
  - Dependencies: None.
  - User Action: None.
  - Agent Work: Add the failing pytest using existing `_draft_answer_payload`, `_grounding_review_payload`, and `run_answer_agent` helpers.
  - Output: New failing unit test.
  - Acceptance: Test fails before implementation because output confidence remains `0.0`.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py::test_run_answer_agent_ignores_zero_draft_confidence_when_grounding_passes -q`
  - Blocked Condition: None.
  - Files: `backend/tests/test_answer_agent.py`

- [x] (01B): Implement grounded confidence calibration helper
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 1: Priority 1 - Fix Grounded Answer Confidence Calibration` > `### Steps`
  - Source Requirements:
    - Add `final_grounded_answer_confidence`.
    - If self-check is ready and draft confidence is `<= 0.0`, use the minimum of verification and grounding confidence.
    - Otherwise keep the conservative minimum behavior.
  - Details: Implement the helper in `answer_agent.py`, use it in final output assembly, and export it through `__all__`.
  - Dependencies: (01A).
  - User Action: None.
  - Agent Work: Modify `backend/app/agents/answer_agent.py` exactly within the answer finalization path.
  - Output: Calibrated final answer confidence.
  - Acceptance: The new focused test passes and existing answer agent success/failure behavior remains compatible.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py -q`
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`

### Files or Modules Likely Created or Updated

- `backend/app/agents/answer_agent.py`
- `backend/tests/test_answer_agent.py`

### Required Outputs / Artifacts

- Passing confidence calibration test.
- Updated answer agent confidence logic.

### Acceptance Criteria

- A grounded, ready answer with zero draft confidence returns non-zero final confidence from verified evidence and grounding confidence.
- Existing answer agent tests pass.

### Required Tests or Validations

- `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py -q`

### Explicit Non-Goals

- Do not change the public chat response schema.
- Do not alter provider prompts in this batch.
- Do not tune retrieval or chronology behavior in this batch.

## Mandatory Batch02 - Simple Chronology Reasoning

### Goal

Answer simple "Which happened first: A, or B?" questions deterministically when verified chunks include source order.

### Why this batch exists

The live report found that the system retrieved and verified enough evidence for a chronology question but returned a self-check fallback instead of answering.

### Inputs / Dependencies

- Batch01 complete.
- Existing verification, answer prompt, and answer agent tests.
- No user action required.

### Tasks

- [x] (02A): Preserve `chunk_index` in verified evidence schema and verifier output
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 2: Priority 2 - Add Deterministic Simple Chronology Answering` > `### Steps`
  - Source Requirements:
    - Add optional `chunk_index` to `VerifiedChunk`.
    - Preserve candidate `chunk_index` when verification creates or canonicalizes verified chunks.
    - Add `test_verification_agent_preserves_chunk_index_on_verified_chunks`.
  - Details: Update `VerifiedChunk`, relevant `VerifiedChunk(...)` construction sites, canonicalization update payloads, and test coverage.
  - Dependencies: Batch01.
  - User Action: None.
  - Agent Work: Modify schema and verifier code only enough to carry existing retrieval order into verified evidence.
  - Output: Verified chunks may include `chunk_index`.
  - Acceptance: Verification output preserves candidate chunk index.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_verification_agent.py::test_verification_agent_preserves_chunk_index_on_verified_chunks -q`
  - Blocked Condition: None.
  - Files: `backend/app/agents/schemas.py`, `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`

- [x] (02B): Include `chunk_index` in Agent 3 evidence payload
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 2: Priority 2 - Add Deterministic Simple Chronology Answering` > `### Steps`
  - Source Requirements:
    - Add `test_answer_generation_payload_includes_verified_chunk_index`.
    - Include `chunk_index` in `answer_evidence_payload`.
  - Details: Update Agent 3 prompt payload so LLM and deterministic helpers can see verified source order.
  - Dependencies: (02A).
  - User Action: None.
  - Agent Work: Modify `answer_prompt_service.answer_evidence_payload()` and add focused test.
  - Output: Verified evidence payload contains `chunk_index`.
  - Acceptance: Payload test passes with expected file name, quote, page number, and chunk index.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_prompt_service.py::test_answer_generation_payload_includes_verified_chunk_index -q`
  - Blocked Condition: None.
  - Files: `backend/app/services/answer_prompt_service.py`, `backend/tests/test_answer_prompt_service.py`

- [x] (02C): Add deterministic chronology answer path
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 2: Priority 2 - Add Deterministic Simple Chronology Answering` > `### Steps`
  - Source Requirements:
    - Add `test_run_answer_agent_answers_simple_chronology_without_provider`.
    - Detect "Which happened first: A, or B?" questions.
    - Use verified chunk `chunk_index` to answer without ShopAIKey when both events are found.
    - Return citations for both compared evidence quotes.
  - Details: Implement `_try_build_simple_chronology_answer` and supporting helpers in `answer_agent.py`; invoke it after insufficient-evidence checks and before provider generation.
  - Dependencies: (02A), (02B).
  - User Action: None.
  - Agent Work: Add deterministic path, produce `AnswerAgentOutput`, and reuse existing safe logging with `fallback_reason="simple_chronology"`.
  - Output: Chronology questions can return a ready answer without provider calls.
  - Acceptance: Focused chronology test passes; ShopAIKey mock is not called; output has ready self-check and both citations.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py::test_run_answer_agent_answers_simple_chronology_without_provider -q`
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

### Files or Modules Likely Created or Updated

- `backend/app/agents/schemas.py`
- `backend/app/agents/verification_agent.py`
- `backend/app/services/answer_prompt_service.py`
- `backend/app/agents/answer_agent.py`
- `backend/tests/test_verification_agent.py`
- `backend/tests/test_answer_prompt_service.py`
- `backend/tests/test_answer_agent.py`

### Required Outputs / Artifacts

- Verified evidence carries `chunk_index`.
- Agent 3 evidence payload includes `chunk_index`.
- Deterministic chronology answer path.

### Acceptance Criteria

- The chronology-focused tests pass.
- The provider is not called for supported simple chronology questions.
- Existing answer and verification tests still pass.

### Required Tests or Validations

- `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py::test_run_answer_agent_answers_simple_chronology_without_provider tests/test_verification_agent.py::test_verification_agent_preserves_chunk_index_on_verified_chunks tests/test_answer_prompt_service.py::test_answer_generation_payload_includes_verified_chunk_index -q`
- `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py tests/test_verification_agent.py tests/test_answer_prompt_service.py tests/test_agent_runs_api.py -q`

### Explicit Non-Goals

- Do not build a general temporal reasoning engine.
- Do not infer chronology when chunks lack source order.
- Do not make provider calls mandatory for simple supported chronology.

## Mandatory Batch03 - Retrieval Precision Gates

### Goal

Reduce low-value retrieval candidates and avoid adjacent context expansion from weak anchors.

### Why this batch exists

The live report showed 13-14 retrieved candidates for simple questions, many of them loosely related or irrelevant.

### Inputs / Dependencies

- Batch01 and Batch02 complete.
- Existing retrieval service tests.
- No user action required.

### Tasks

- [x] (03A): Add retrieval precision settings
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 3: Priority 3 - Improve Retrieval Precision With Score Gating` > `### Steps`
  - Source Requirements:
    - Add `retrieval_min_final_score`.
    - Add `retrieval_context_min_parent_score`.
    - Defaults must be `0.2` and constrained between `0.0` and `1.0`.
  - Details: Add Pydantic settings fields near current retrieval settings.
  - Dependencies: Batch02.
  - User Action: None.
  - Agent Work: Modify `backend/app/core/config.py`.
  - Output: Configurable retrieval precision thresholds.
  - Acceptance: Settings instantiate with defaults and pass existing config tests.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_config.py -q`
  - Blocked Condition: None.
  - Files: `backend/app/core/config.py`

- [x] (03B): Filter hybrid candidates below minimum final score
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 3: Priority 3 - Improve Retrieval Precision With Score Gating` > `### Steps`
  - Source Requirements:
    - Add `test_retrieve_hybrid_filters_candidates_below_min_final_score`.
    - Add `_filter_by_min_final_score`.
    - Filter scored candidates before final top-k ranking.
  - Details: Add deterministic filtering in `retrieve_hybrid()` using the new setting.
  - Dependencies: (03A).
  - User Action: None.
  - Agent Work: Modify hybrid retrieval implementation and test.
  - Output: Weak final-score candidates are removed before rerank/return.
  - Acceptance: Focused hybrid retrieval filter test passes.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_hybrid_retrieval_service.py::test_retrieve_hybrid_filters_candidates_below_min_final_score -q`
  - Blocked Condition: None.
  - Files: `backend/app/services/hybrid_retrieval_service.py`, `backend/tests/test_hybrid_retrieval_service.py`

- [x] (03C): Gate adjacent context expansion by parent score
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 3: Priority 3 - Improve Retrieval Precision With Score Gating` > `### Steps`
  - Source Requirements:
    - Add `test_expand_retrieval_context_skips_weak_anchor_below_min_parent_score`.
    - Add `min_parent_score` to context expansion.
    - Pass `settings.retrieval_context_min_parent_score` from retrieval agent.
  - Details: Prevent weak anchors from pulling adjacent chunks into the candidate set.
  - Dependencies: (03A).
  - User Action: None.
  - Agent Work: Modify context expansion signature, anchor loop, retrieval agent call, and tests.
  - Output: Adjacent context expansion only occurs for sufficiently strong anchors.
  - Acceptance: Focused context expansion gate test passes.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_retrieval_context_service.py::test_expand_retrieval_context_skips_weak_anchor_below_min_parent_score -q`
  - Blocked Condition: None.
  - Files: `backend/app/services/retrieval_context_service.py`, `backend/app/agents/retrieval_agent.py`, `backend/tests/test_retrieval_context_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/core/config.py`
- `backend/app/services/hybrid_retrieval_service.py`
- `backend/app/services/retrieval_context_service.py`
- `backend/app/agents/retrieval_agent.py`
- `backend/tests/test_hybrid_retrieval_service.py`
- `backend/tests/test_retrieval_context_service.py`

### Required Outputs / Artifacts

- New retrieval precision settings.
- Hybrid final-score filtering.
- Context expansion parent-score gating.

### Acceptance Criteria

- Retrieval precision tests pass.
- Existing retrieval tests pass.
- No public retrieval API schema changes are introduced.

### Required Tests or Validations

- `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_hybrid_retrieval_service.py::test_retrieve_hybrid_filters_candidates_below_min_final_score tests/test_retrieval_context_service.py::test_expand_retrieval_context_skips_weak_anchor_below_min_parent_score -q`
- `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_hybrid_retrieval_service.py tests/test_retrieval_context_service.py tests/test_retrieval_agent.py tests/test_retrieval_api.py -q`

### Explicit Non-Goals

- Do not replace the scoring formula wholesale.
- Do not require rerank to be enabled.
- Do not remove graph retrieval.

## Mandatory Batch04 - Exact Citation Display

### Goal

Render visible citations in the exact MVP format `file_name: "quoted text"`.

### Why this batch exists

The backend already returns structured citations and hides raw IDs, but the frontend currently renders file name and quote separately.

### Inputs / Dependencies

- Prior backend batches complete.
- Existing frontend project and build script.
- No user action required.

### Tasks

- [ ] (04A): Add frontend citation formatter
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 4: Priority 4 - Render Exact MVP Citation Format` > `### Steps`
  - Source Requirements:
    - Add `formatCitation(citation: ChatCitation): string`.
    - Format must be `${file_name}: "${quote}"`.
  - Details: Add exported helper below `formatConfidence()`.
  - Dependencies: Batch03.
  - User Action: None.
  - Agent Work: Modify `AnswerPanel.tsx`.
  - Output: Citation formatting helper.
  - Acceptance: TypeScript build accepts the exported helper.
  - Validation: `cd frontend; npm run build`
  - Blocked Condition: None.
  - Files: `frontend/src/components/AnswerPanel.tsx`

- [ ] (04B): Render citation as one exact visible string
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 4: Priority 4 - Render Exact MVP Citation Format` > `### Steps`
  - Source Requirements:
    - Replace separate file and blockquote display.
    - Render `<p className="answer-panel__citation-text">{formatCitation(citation)}</p>`.
    - Add compatible CSS if needed.
  - Details: Update the citation list item markup and add `.answer-panel__citation-text` style while preserving old selectors.
  - Dependencies: (04A).
  - User Action: None.
  - Agent Work: Modify frontend component and CSS only.
  - Output: Visible citations match MVP format exactly.
  - Acceptance: Frontend build passes.
  - Validation: `cd frontend; npm run build`
  - Blocked Condition: None.
  - Files: `frontend/src/components/AnswerPanel.tsx`, `frontend/src/styles.css`

### Files or Modules Likely Created or Updated

- `frontend/src/components/AnswerPanel.tsx`
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- Citation formatter.
- Updated citation rendering.
- Frontend build output.

### Acceptance Criteria

- Visible citations are rendered as `file_name: "quoted text"`.
- No raw database IDs are introduced in the frontend citation display.
- Frontend build passes.

### Required Tests or Validations

- `cd frontend; npm run build`

### Explicit Non-Goals

- Do not change backend citation schema.
- Do not add a frontend test framework.
- Do not redesign the answer panel.

## Mandatory Batch05 - Missing-Information Diagnostics

### Goal

Add a question-specific missing target to internal Agent 3 logs while preserving the exact public insufficient-evidence response.

### Why this batch exists

The live report found missing-information behavior is safe but generic. The public fallback must remain exact, so specificity belongs in internal logs.

### Inputs / Dependencies

- Batch04 complete.
- Existing answer agent and answer log service tests.
- No user action required.

### Tasks

- [ ] (05A): Add failing missing-target log test
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 5: Priority 5 - Add Specific Missing-Target Detail to Internal Answer Logs` > `### Steps`
  - Source Requirements:
    - Add `test_missing_information_log_includes_question_specific_missing_target`.
    - Public final answer must still equal `INSUFFICIENT_EVIDENCE_ANSWER`.
    - Log payload must include `missing_target` for "What is Alice's bank account number?"
  - Details: Add test to `backend/tests/test_answer_agent.py`.
  - Dependencies: Batch04.
  - User Action: None.
  - Agent Work: Add failing test using mocked ShopAIKey and mocked log service.
  - Output: New failing log-specificity test.
  - Acceptance: Test fails before implementation because `missing_target` is absent.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py::test_missing_information_log_includes_question_specific_missing_target -q`
  - Blocked Condition: None.
  - Files: `backend/tests/test_answer_agent.py`

- [ ] (05B): Extract missing target and pass it to insufficient-answer logs
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 5: Priority 5 - Add Specific Missing-Target Detail to Internal Answer Logs` > `### Steps`
  - Source Requirements:
    - Add `_WHAT_IS_QUESTION_PATTERN`.
    - Add `_missing_target_from_question`.
    - Pass `missing_target` to `_log_insufficient_answer`.
  - Details: Extract the target from simple "what is ..." questions and thread it only into log payload construction.
  - Dependencies: (05A).
  - User Action: None.
  - Agent Work: Modify answer agent logging path without changing public answer text.
  - Output: Missing target available for insufficient-evidence logs.
  - Acceptance: Public answer remains exact; log receives missing target.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py::test_missing_information_log_includes_question_specific_missing_target -q`
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`

- [ ] (05C): Include optional missing target in answer log service payload
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Task 5: Priority 5 - Add Specific Missing-Target Detail to Internal Answer Logs` > `### Steps`
  - Source Requirements:
    - Update `build_insufficient_answer_log_output`.
    - Include `missing_target` only when present.
    - Preserve existing keys and values.
  - Details: Update answer log service to accept optional missing target and include it conditionally.
  - Dependencies: (05B).
  - User Action: None.
  - Agent Work: Modify answer log payload builder and update existing answer log service tests if they assert exact signatures.
  - Output: Internal log payload includes `missing_target` only when available.
  - Acceptance: Answer agent and answer log service tests pass.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py tests/test_answer_log_service.py -q`
  - Blocked Condition: None.
  - Files: `backend/app/services/answer_log_service.py`, `backend/tests/test_answer_log_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/agents/answer_agent.py`
- `backend/app/services/answer_log_service.py`
- `backend/tests/test_answer_agent.py`
- `backend/tests/test_answer_log_service.py`

### Required Outputs / Artifacts

- Missing-target extraction helper.
- Optional `missing_target` field in insufficient-evidence log payloads.
- Passing answer logging tests.

### Acceptance Criteria

- Public insufficient-evidence response is unchanged.
- Internal logs can identify the missing target for simple "what is ..." questions.
- Existing log payload safety remains intact.

### Required Tests or Validations

- `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py::test_missing_information_log_includes_question_specific_missing_target -q`
- `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py tests/test_answer_log_service.py -q`

### Explicit Non-Goals

- Do not change the exact public insufficient-evidence answer.
- Do not add user-visible missing-target text unless separately approved.
- Do not log secrets or raw provider errors.

## Mandatory Batch06 - Final Verification and Live Smoke

### Goal

Verify all priority fixes together with targeted automated tests, frontend build, and live smoke checks.

### Why this batch exists

The source plan requires final verification after all task batches and live smoke validation against the same three RAG questions from the report.

### Inputs / Dependencies

- Batch01 through Batch05 complete.
- Backend and frontend dependencies installed.
- Live smoke requires configured Supabase, Qdrant, and ShopAIKey credentials in local backend environment.

### Tasks

- [ ] (06A): Run backend final verification suite
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Final Verification`
  - Source Requirements:
    - Run answer, verification, prompt, log, retrieval, chat, and agent-run tests.
  - Details: Run the exact backend pytest command from the source plan.
  - Dependencies: Batch05.
  - User Action: None.
  - Agent Work: Execute tests and record output summary.
  - Output: Backend verification result.
  - Acceptance: Command exits successfully with all selected tests passing.
  - Validation: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_answer_agent.py tests/test_verification_agent.py tests/test_answer_prompt_service.py tests/test_answer_log_service.py tests/test_hybrid_retrieval_service.py tests/test_retrieval_context_service.py tests/test_retrieval_agent.py tests/test_retrieval_api.py tests/test_chat_api.py tests/test_agent_runs_api.py -q`
  - Blocked Condition: None.
  - Files: No source files expected.

- [ ] (06B): Run frontend production build
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Final Verification`
  - Source Requirements:
    - Run `npm run build` in `frontend`.
  - Details: Verify TypeScript and Vite build after citation rendering changes.
  - Dependencies: Batch04.
  - User Action: None.
  - Agent Work: Execute frontend build and record output summary.
  - Output: Frontend build result.
  - Acceptance: Build exits successfully.
  - Validation: `cd frontend; npm run build`
  - Blocked Condition: None.
  - Files: No source files expected.

- [ ] (06C): Run live smoke verification
  - Source of Truth: `docs/superpowers/plans/2026-06-17-rag-quality-priority-fixes.md` > `## Live Smoke Verification`
  - Source Requirements:
    - Direct rabbit question returns grounded answer with non-zero confidence.
    - Chronology question answers that Alice saw the White Rabbit first.
    - Bank-account question keeps exact insufficient-evidence public answer.
    - Citations contain no raw chunk IDs.
  - Details: Start backend with live network access on a free port and run the three documented `POST /api/chat/ask` requests against document `c90c48f9-0e3c-4d2c-9464-31594ae85820`.
  - Dependencies: (06A), (06B).
  - User Action: User must ensure real Supabase, Qdrant, and ShopAIKey credentials exist in local `.env`; agent must not print them.
  - Agent Work: Start backend, run smoke requests, inspect responses and relevant `agent_run` logs, then stop the backend process started for smoke.
  - Output: Live smoke result summary with safe response excerpts and agent run IDs.
  - Acceptance: All expected live smoke behaviors match the source plan.
  - Validation: Execute the PowerShell smoke script from the source plan, using the active local backend port.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if credentials are missing; failed if credentials exist but live provider calls fail.
  - Files: No source files expected.

### Files or Modules Likely Created or Updated

- No source files expected.
- Future execution agent may write a short execution report if following the repository's task reporting convention.

### Required Outputs / Artifacts

- Backend test result summary.
- Frontend build result summary.
- Live smoke result summary.

### Acceptance Criteria

- Backend tests pass.
- Frontend build passes.
- Live smoke confirms the three priority behaviors.
- No secrets are printed or committed.

### Required Tests or Validations

- Backend final pytest command from (06A).
- Frontend build command from (06B).
- Live smoke script from (06C).

### Explicit Non-Goals

- Do not upload new live documents unless a future reviewer explicitly requests it.
- Do not change provider credentials.
- Do not leave smoke backend processes running.

## Optional Future Tracks

- Broader retrieval evaluation dataset: not part of this mandatory chain.
- Frontend automated component tests for `AnswerPanel`: not part of this mandatory chain because the current frontend has no test script or test framework.
- More general temporal reasoning engine: not part of this mandatory chain.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05
- Batch05 -> Batch06

Optional future tracks are outside the mandatory chain.

## Global Verification Checklist

- [ ] Batch01 confidence calibration tests pass.
- [ ] Batch02 chronology tests pass.
- [ ] Batch03 retrieval precision tests pass.
- [ ] Batch04 frontend build passes.
- [ ] Batch05 missing-information log tests pass.
- [ ] Batch06 backend final verification command passes.
- [ ] Batch06 live smoke behavior matches source expectations.
- [ ] Public insufficient-evidence answer text is unchanged.
- [ ] Citations render as `file_name: "quoted text"` and expose no raw chunk IDs.
- [ ] No secrets are printed, logged, committed, or added to frontend code.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [ ] Batch01 - Confidence Calibration
- [ ] Batch02 - Simple Chronology Reasoning
- [ ] Batch03 - Retrieval Precision Gates
- [ ] Batch04 - Exact Citation Display
- [ ] Batch05 - Missing-Information Diagnostics
- [ ] Batch06 - Final Verification and Live Smoke

### Task IDs

#### Batch01

- [x] (01A): Add failing confidence calibration test
- [x] (01B): Implement grounded confidence calibration helper

#### Batch02

- [x] (02A): Preserve `chunk_index` in verified evidence schema and verifier output
- [x] (02B): Include `chunk_index` in Agent 3 evidence payload
- [x] (02C): Add deterministic chronology answer path

#### Batch03

- [x] (03A): Add retrieval precision settings
- [x] (03B): Filter hybrid candidates below minimum final score
- [x] (03C): Gate adjacent context expansion by parent score

#### Batch04

- [ ] (04A): Add frontend citation formatter
- [ ] (04B): Render citation as one exact visible string

#### Batch05

- [ ] (05A): Add failing missing-target log test
- [ ] (05B): Extract missing target and pass it to insufficient-answer logs
- [ ] (05C): Include optional missing target in answer log service payload

#### Batch06

- [ ] (06A): Run backend final verification suite
- [ ] (06B): Run frontend production build
- [ ] (06C): Run live smoke verification

## Completion Reporting Rules for Future Execution Agents

### BatchXX Execution Result

#### Completed Task IDs

- (XXA): complete / partial / blocked

#### Files Created or Modified

- path

#### Tests or Validations Run

- command: result

#### User Actions Required

- action: completed / pending / not required
- details: safe summary only, never include secrets

#### Blocked-by-User Status

- status: none / BLOCKED_BY_USER_ACTION
- reason: missing API key, missing provider project, missing manual setup, or other safe summary

#### Validation Responsibility

- user-provided setup confirmed: yes / no / not required
- agent validation run after setup: yes / no
- validation command: result

#### Acceptance Criteria Check

- criterion: satisfied / not satisfied / blocked

#### Artifacts Produced

- artifact

#### Progress Tracker Update

- task IDs updated

#### Key Implementation Decisions

- decision

#### Risks or Open Issues

- issue

#### Notes for Next Batch

- handoff notes

Future execution agents must not claim completion unless task validations and acceptance criteria are satisfied.
