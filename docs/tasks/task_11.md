# Plan 11 - Agent 3 Answer Generation and Self-Check Agent Execution Tasks

## Purpose

Create a detailed execution task file for the approved Agent 3 Answer Generation and Self-Check Agent milestone. This task file guides a future Execution Agent to add backend Agent 3 schemas, prompts, answer generation, citation validation, self-check behavior, `agent_steps` logging, tests, and reporting for `docs/plans/Plan_11.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_11.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Current project context reviewed: `README.md`
- Conflict note: No architecture conflicts were found. `docs/plans/Master_Plan.md` aligns with Plan 11 on Agent 3 generating final answers only from Agent 2 verified chunks, citing `file_name: "quoted text"`, refusing insufficient evidence, self-checking before output, and logging answer/self-check details. `README.md` confirms Agent 1 and Agent 2 backend callables, ShopAIKey chat support, and agent step logging exist, while Agent 3 answer generation, LangGraph orchestration, `/api/chat/ask`, public evidence/log APIs, and frontend chat remain planned. `docs/plans/Plan_11.md` remains the scope authority for this task file.

## Source Section Index

- `docs/plans/Plan_11.md` > `## 1. Goal` -> Agent 3 must generate grounded final answers, cite verified evidence, handle insufficient evidence, self-check, and log the step.
- `docs/plans/Plan_11.md` > `## 2. Why This Plan Exists` -> final answers must be based only on verified document evidence before chat exposure.
- `docs/plans/Plan_11.md` > `## 3. Scope` -> required schemas, prompts, verified-only answer generation, citation format, insufficient-evidence behavior, logging, and tests.
- `docs/plans/Plan_11.md` > `## 4. Out of Scope` -> prohibited LangGraph, `/api/chat/ask`, frontend chat, extra retrieval, rejected chunks, and conversation memory.
- `docs/plans/Plan_11.md` > `## 5. Dependencies` -> completed Plan 10, completed Plan 2 `agent_steps`, and available ShopAIKey chat helper.
- `docs/plans/Plan_11.md` > `## 6. Required Files and Folders` -> expected Agent 3 module, prompts, schemas, services, and tests.
- `docs/plans/Plan_11.md` > `## 7. Data Model / Schema Changes` -> no database schema changes and required Agent 3 output, insufficient evidence text, citation object, and self-check fields.
- `docs/plans/Plan_11.md` > `## 8. API Design` -> no new public endpoint and internal `run_answer_agent` callable contract.
- `docs/plans/Plan_11.md` > `## 9. Implementation Steps` -> ordered implementation requirements from schemas through logging and tests.
- `docs/plans/Plan_11.md` > `## 10. Configuration and Environment Variables` -> backend-only ShopAIKey chat and `SINGLE_USER_ID` variables.
- `docs/plans/Plan_11.md` > `## 11. Required Tests` -> targeted pytest command, concrete test cases, and manual check.
- `docs/plans/Plan_11.md` > `## 12. Acceptance Criteria` -> verified-only, no rejected chunks, citations, insufficient-evidence handling, self-check, validation, and logging.
- `docs/plans/Plan_11.md` > `## 13. Failure Handling` -> missing verified chunks, provider failures, invalid JSON, citation failures, and unsupported-claim prevention.
- `docs/plans/Plan_11.md` > `## 14. Agent Report Requirement` -> required execution report contents and answer examples.
- `docs/plans/Plan_11.md` > `## 15. Reviewer Checklist` -> scope, tests, acceptance, secrets, architecture, citations, chunk IDs, reasoning, and self-check checks.
- `docs/plans/Master_Plan.md` > `### 5.3 Chat With Document Page` -> future workflow order: Agent 1, Agent 2, then Agent 3.
- `docs/plans/Master_Plan.md` > `### 5.4 Evidence Viewer` -> eventual evidence display needs file name, quoted text, score, status, and reason.
- `docs/plans/Master_Plan.md` > `### 5.5 Agent Logs / Debug Page` -> logs should include Agent 3 draft answer, self-check result, final answer, confidence, errors, and timestamps.
- `docs/plans/Master_Plan.md` > `## Table: agent_steps` -> approved step log fields.
- `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` -> Agent 3 goal, answer style, citation style, insufficient evidence behavior, self-check, and output schema.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> backend-only ShopAIKey and single-user configuration boundary.
- `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure` -> expected `backend/app/agents/answer_agent.py`, shared schemas, services, and test locations.
- `docs/plans/Master_Plan.md` > `## Phase 8: Agent 3 Answer and Self-Check` -> phase-level Agent 3 tasks and acceptance criteria.
- `docs/plans/Master_Plan.md` > `## 18.1 Grounding Rule` -> final answers must use verified chunks only and avoid unverified, rejected, outside, or unsupported evidence.
- `docs/plans/Master_Plan.md` > `## 18.2 Simple Reasoning Rule` -> allowed and prohibited reasoning boundaries.
- `docs/plans/Master_Plan.md` > `## 18.3 Citation Rule` -> every final answer must include `file_name: "quoted text"` citations.
- `docs/plans/Master_Plan.md` > `## 18.4 Missing Information Rule` -> insufficient evidence must be stated clearly.
- `docs/plans/Master_Plan.md` > `## 18.5 Debuggability Rule` -> developers must inspect how final answers were generated and whether self-check passed.
- `README.md` > `## Overview` -> current project state and planned Agent 3/runtime workflow context.
- `README.md` > `## Architecture` -> existing layered backend architecture, Agent 1/Agent 2 current state, and missing Agent 3 workflow.
- `README.md` > `## Backend` -> current backend agent files and services.
- `README.md` > `### ShopAIKey` -> existing OpenAI-compatible chat completion helper.
- `README.md` > `## Configuration` -> backend `.env` loading behavior and backend-only provider settings.
- `README.md` > `## Testing and Validation` -> backend pytest conventions and current test coverage context.
- `README.md` > `Important coordination rules` -> backend-only secret boundary, validation expectations, and no fake completion claims.
- `README.md` > `## Known Gaps or Unclear Areas` -> Agent 3, full orchestration, public APIs, and frontend chat remain planned.

## Approved Architecture Summary

Plan 11 approves a backend-only Agent 3 Answer Generation and Self-Check Agent for the single-user Document QA Agent MVP. Agent 3 is an internal callable layer, not a public API. It receives an existing `agent_run_id`, the user question, and Agent 2 verification output; generates a concise Vietnamese-by-default final answer only from `verified_chunks`; attaches citations in `file_name: "quoted text"` form; runs a self-check; and logs answer generation plus self-check output in `agent_steps`.

Agent 3 may use ShopAIKey chat completion for grounded answer drafting and, if chosen, self-checking. Every provider response must be parsed as JSON, Pydantic-validated, and checked against Agent 2 evidence. Citation quotes must come from Agent 2 verified chunk quotes. Rejected chunks must never be cited, copied into the answer, or used as support. Simple reasoning is allowed only when verified evidence clearly supports it, such as adding a probation duration to a start date, comparing dates, extracting a month, or summarizing a clearly stated policy.

If Agent 2 reports `missing_information=true` or provides no verified chunks, Agent 3 must return the exact insufficient-evidence answer `Tài liệu hiện tại chưa cung cấp đủ thông tin để xác định câu trả lời.` without asking the model to invent an answer. Plan 11 allows self-check failure to return a safe insufficient-evidence answer or raise `AnswerAgentError`; the implementation must choose one explicit policy, test it, and never return unsupported content as ready.

No database schema changes, LangGraph orchestration, `/api/chat/ask`, frontend chat, public evidence APIs, public agent log APIs, extra retrieval, rejected evidence usage, or conversation memory are approved by Plan 11.

## Global Implementation Rules

- Keep `docs/plans/Plan_11.md` as the source of truth for scope, output shape, validation, failure handling, tests, and out-of-scope boundaries.
- Use `docs/plans/Master_Plan.md` only to clarify Agent 3's target architecture, citation style, answer style, self-check expectations, `agent_steps` fields, ShopAIKey backend-only boundary, and expected package locations.
- Use `README.md` only to understand current code state: Agent 1 and Agent 2 callables exist, Agent 3 does not yet exist, ShopAIKey chat helper exists, and public chat/evidence/log APIs are not implemented yet.
- Depend on completed Plan 10 Agent 2 verification output; do not reimplement Agent 1 retrieval, Agent 2 verification, hybrid retrieval, graph retrieval, semantic search, Qdrant search, or rerank behavior.
- Depend on completed Plan 2 `agent_steps`; do not add or modify database migrations or table schemas.
- Reuse existing backend agent schemas, prompt organization, ShopAIKey service, and agent log service patterns where they fit Plan 11.
- Keep Agent 3 internal and backend-only; do not add public API routes.
- Do not implement LangGraph orchestration, `/api/chat/ask`, frontend chat, public evidence APIs, public agent log APIs, chat sessions/messages, conversation memory, or full agent run workflow.
- Do not retrieve new chunks beyond Agent 2 verified evidence.
- Do not use rejected chunks in prompts as supporting evidence, answer content, reasoning support, or citations except where needed for deterministic exclusion checks.
- Do not expose internal chunk IDs in normal final answers or normal citation output; chunk IDs may appear only in logs/debug payloads.
- Do not expose `SHOPAIKEY_API_KEY`, Supabase service role keys, Qdrant keys, backend-only settings, raw provider errors, stack traces, or private document content beyond expected Agent 3 input/output/log payloads.
- Use `.env.example` for placeholder names only and never commit real secrets.
- Keep input, output, self-check, and log payloads JSON-serializable and Pydantic-validated where applicable.
- Treat provider, parsing, validation, citation, rejected-evidence, unsupported-claim, invalid-JSON, and self-check failures as controlled failures with safe `AnswerAgentError` or safe insufficient-evidence behavior.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, schemas, settings, services, prompts, tests, and errors.
- Keep functions, services, schemas, prompts, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, service-layer, and provider-client conventions already present in the backend.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless Plan 11 explicitly requires them.
- Add comments only where they clarify a non-obvious validation, citation, self-check, serialization, or logging decision.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Avoid adding formatters, linters, frameworks, LLM orchestration frameworks, or architecture changes outside Plan 11 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Answer Contracts, Prompts, and Backend-Only Configuration
- Batch02 - Answer Agent Callable and Insufficient-Evidence Path
- Batch03 - LLM Draft Answer Parsing and Citation Enforcement
- Batch04 - Self-Check, Safe Failure Handling, and Logging
- Batch05 - Required Automated Tests
- Batch06 - Manual Validation, Reporting, and Scope Review

## Mandatory Batch01 - Answer Contracts, Prompts, and Backend-Only Configuration

### Goal

Prepare Agent 3 schemas, prompt rules, self-check contract, and backend-only configuration boundaries before runtime answer generation logic is added.

### Why this batch exists

Agent 3 cannot safely call an LLM, validate citations, self-check output, or log results until the accepted input, output shape, citation format, self-check fields, and provider settings are explicit.

### Inputs / Dependencies

- `docs/plans/Plan_11.md`
- `docs/plans/Master_Plan.md`
- `README.md`
- Completed Plan 10 Agent 2 verification output schemas and callable
- Completed Plan 2 `agent_steps`
- Existing backend Pydantic, prompt, settings, ShopAIKey, and agent log service conventions

### Tasks

- [x] (01A): Extend agent schemas for Agent 3 answer output
  - Source of Truth: `docs/plans/Plan_11.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_11.md` > `## 8. API Design`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.6 Agent 3 Output Schema`
  - Source Requirements:
    - Add `Citation`, `AnswerSelfCheck`, `AnswerAgentInput`, and `AnswerAgentOutput`.
    - Agent 3 output includes `final_answer`, `citations`, `reasoning_summary`, `confidence`, and `self_check`.
    - Citation objects include `file_name` and `quote`.
    - Self-check includes `uses_only_verified_chunks`, `has_citation`, `has_unsupported_claims`, and `is_ready`.
  - Details: Extend `backend/app/agents/schemas.py` using the repo's current Pydantic style. Reuse existing Agent 2 verification schema types when practical instead of duplicating verified/rejected chunk fields loosely.
  - Dependencies: Completed Plan 10 Agent 2 schemas.
  - User Action: None.
  - Agent Work: Add Agent 3 Pydantic models, exports, stable JSON serialization, bounded confidence validation, and import compatibility through `backend/app/agents/__init__.py` if that file currently exports agent contracts.
  - Output: Typed Agent 3 input, citation, self-check, and output schema models.
  - Acceptance: Agent 3 schema models import successfully; output has the required top-level fields; citations and self-check fields are required; confidence is bounded between `0.0` and `1.0`.
  - Validation: Add or run targeted schema validation tests once Batch05 tests exist; run a direct Pydantic import/smoke check if tests are not present yet.
  - Blocked Condition: None.
  - Files: `backend/app/agents/schemas.py`, `backend/app/agents/__init__.py`, `backend/tests/test_answer_agent.py`

- [x] (01B): Define citation and evidence validation contract
  - Source of Truth: `docs/plans/Plan_11.md` > `## 3. Scope`; `docs/plans/Plan_11.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.3 Citation Style`; `docs/plans/Master_Plan.md` > `## 18.3 Citation Rule`
  - Source Requirements:
    - Implement citation format `file_name: "quoted text"`.
    - Require every citation quote to come from a verified chunk quote.
    - Reject citations from rejected chunks.
    - Do not show internal chunk IDs to normal users.
  - Details: Decide which checks belong in Pydantic schema validation and which require runtime validation against `AnswerAgentInput.verification`. Runtime evidence checks may live in `answer_agent.py` if they need access to verified and rejected chunk collections.
  - Dependencies: (01A).
  - User Action: None.
  - Agent Work: Define helper functions or validation utilities for citation presence, `file_name` plus `quote` formatting, quote membership in verified evidence, rejected chunk exclusion, and no chunk IDs in normal answer text.
  - Output: Clear validation contract ready for runtime enforcement in later batches.
  - Acceptance: The intended validation points are implemented or documented in code tests; future runtime logic can reject missing, malformed, non-verified, or rejected citations.
  - Validation: Unit tests for citation schema and helper behavior in `backend/tests/test_answer_agent.py`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/schemas.py`, `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

- [x] (01C): Add answer generation prompt rules
  - Source of Truth: `docs/plans/Plan_11.md` > `## 3. Scope`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.1 Goal`; `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.2 Answer Style`; `docs/plans/Master_Plan.md` > `## 18.1 Grounding Rule`; `docs/plans/Master_Plan.md` > `## 18.2 Simple Reasoning Rule`
  - Source Requirements:
    - Prompt must use verified chunks only.
    - Prompt must never use rejected chunks.
    - Prompt must never use outside knowledge.
    - Prompt must include citations.
    - Prompt must answer in Vietnamese by default.
    - Prompt must only perform simple reasoning when evidence is clear.
  - Details: Extend `backend/app/agents/prompts.py` with reusable Agent 3 answer generation prompt text or a small prompt builder. Keep the prompt JSON-only for provider output and avoid embedding secrets or runtime data directly in module constants.
  - Dependencies: (01A), (01B).
  - User Action: None.
  - Agent Work: Add concise Agent 3 answer-generation prompt rules compatible with the existing prompt organization.
  - Output: Reusable answer generation prompt for Agent 3.
  - Acceptance: Prompt includes all verified-only, no-rejected, no-outside-knowledge, citation, Vietnamese-default, and simple-reasoning rules.
  - Validation: Prompt-focused unit test or assertions that key rules and required output fields are present.
  - Blocked Condition: None.
  - Files: `backend/app/agents/prompts.py`, `backend/tests/test_answer_agent.py`

- [x] (01D): Add self-check prompt or deterministic self-check rules
  - Source of Truth: `docs/plans/Plan_11.md` > `## 3. Scope`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.5 Self-Check`; `docs/plans/Master_Plan.md` > `## 18.5 Debuggability Rule`
  - Source Requirements:
    - Self-check confirms the answer uses only verified chunks.
    - Self-check confirms the answer avoids rejected chunks.
    - Self-check confirms the answer includes citations.
    - Self-check confirms reasoning follows clearly from evidence.
    - Self-check confirms there are no unsupported claims.
    - Self-check confirms the answer is understandable to the user.
  - Details: Implement either a deterministic self-check function, a self-check prompt, or a hybrid approach. If an LLM self-check is used, its result must still be normalized into `AnswerSelfCheck` and enforced deterministically before returning.
  - Dependencies: (01A), (01B), (01C).
  - User Action: None.
  - Agent Work: Add self-check prompt/rules and any constants needed for required boolean fields.
  - Output: Reusable self-check contract for Agent 3.
  - Acceptance: Self-check behavior maps to `AnswerSelfCheck` fields and cannot be ignored by later runtime logic.
  - Validation: Prompt/rule tests and self-check schema tests in `backend/tests/test_answer_agent.py`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/prompts.py`, `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

- [x] (01E): Confirm backend-only ShopAIKey chat configuration boundary
  - Source of Truth: `docs/plans/Plan_11.md` > `## 5. Dependencies`; `docs/plans/Plan_11.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_11.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Master_Plan.md` > `# 15. Environment Variables`; `README.md` > `### ShopAIKey`; `README.md` > `## Configuration`
  - Source Requirements:
    - Reuse ShopAIKey chat completion helper.
    - `SHOPAIKEY_API_KEY`, `SHOPAIKEY_BASE_URL`, and `SHOPAIKEY_CHAT_MODEL` are backend-only.
    - `SINGLE_USER_ID` indirectly scopes previous retrieval and verification.
    - Real secret values must not be committed.
  - Details: Inspect the existing `shopaikey_service.py` chat helper and backend settings. Only add missing placeholders or required-setting checks if needed for Agent 3. Do not add frontend variables.
  - Dependencies: Existing ShopAIKey service and settings.
  - User Action: User must provide real ShopAIKey values in `backend/.env` for live provider validation.
  - Agent Work: Reuse existing chat helper, or add a focused chat helper only if missing; keep model and base URL environment-driven; update `.env.example` only with safe placeholder names if missing.
  - Output: Confirmed backend-only ShopAIKey chat configuration for Agent 3.
  - Acceptance: Agent 3 can resolve required chat settings through backend configuration; frontend code does not contain backend-only ShopAIKey settings or secrets.
  - Validation: Backend settings import test; mocked ShopAIKey chat test; optional frontend scan for `SHOPAIKEY_` names if configuration is touched.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live ShopAIKey validation when real backend credentials are missing.
  - Files: `backend/app/services/shopaikey_service.py`, `backend/app/core/config.py`, `backend/.env.example`, frontend files only for inspection

### Files or Modules Likely Created or Updated

- `backend/app/agents/schemas.py`
- `backend/app/agents/prompts.py`
- `backend/app/agents/__init__.py`
- `backend/app/agents/answer_agent.py`
- `backend/app/services/shopaikey_service.py` only if the chat helper is missing or incomplete
- `backend/app/core/config.py` only if required settings behavior is missing
- `backend/.env.example` only for safe placeholders if missing
- `backend/tests/test_answer_agent.py`

### Required Outputs / Artifacts

- Agent 3 Pydantic input and output schemas.
- Citation and self-check schema contracts.
- Reusable answer generation prompt.
- Reusable self-check prompt or deterministic rule contract.
- Confirmed backend-only ShopAIKey chat configuration boundary.

### Acceptance Criteria

- Agent 3 schemas match Plan 11 required input and output shape.
- Citation object contains `file_name` and `quote`.
- Self-check schema contains the required readiness and safety fields.
- Answer prompt includes verified-only, no-rejected, no-outside-knowledge, citation, Vietnamese-default, and simple-reasoning rules.
- Self-check rules cover citation, verified-only, rejected evidence, unsupported claims, reasoning support, and understandable output.
- ShopAIKey chat settings remain backend-only and environment-driven.

### Required Tests or Validations

- Backend import check for `app.agents.schemas` and `app.agents.prompts`.
- Direct Pydantic schema validation smoke checks or targeted schema tests.
- Prompt-content assertions for required output keys and rules.
- Backend settings import/config validation.
- Frontend scan for `SHOPAIKEY_` names if configuration is touched.

### Explicit Non-Goals

- Do not implement LangGraph orchestration.
- Do not add public API routes.
- Do not add frontend chat, evidence viewer, or agent log screens.
- Do not retrieve additional chunks.
- Do not use rejected chunks as evidence.
- Do not add conversation memory.

## Mandatory Batch02 - Answer Agent Callable and Insufficient-Evidence Path

### Goal

Create the Agent 3 callable and deterministic insufficient-evidence behavior before LLM answer drafting is enabled.

### Why this batch exists

Agent 3 must refuse unsupported answers when Agent 2 reports missing information or provides no verified evidence. This safe path should be deterministic and not depend on provider output.

### Inputs / Dependencies

- Batch01 completed
- Completed Plan 10 Agent 2 verification schemas/output
- Existing agent log service and ShopAIKey service patterns
- `docs/plans/Plan_11.md`

### Tasks

- [x] (02A): Create answer agent module and controlled error type
  - Source of Truth: `docs/plans/Plan_11.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_11.md` > `## 8. API Design`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure`
  - Source Requirements:
    - Add `backend/app/agents/answer_agent.py`.
    - Implement `run_answer_agent(input_data)`.
    - Expose `AnswerAgentError` for LLM, validation, or self-check failure.
    - No new public API endpoints are part of this plan.
  - Details: Follow the structure of existing backend agent modules, including controlled errors, validation boundaries, and safe messages. Keep the callable internal and importable by future orchestration.
  - Dependencies: Batch01 schemas.
  - User Action: None.
  - Agent Work: Add `answer_agent.py`, `AnswerAgentError`, input normalization, and public module exports as needed.
  - Output: Internal callable shell for Agent 3.
  - Acceptance: `run_answer_agent` imports successfully and accepts `AnswerAgentInput` or a compatible mapping for validation.
  - Validation: Import smoke check and targeted tests.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/app/agents/__init__.py`, `backend/tests/test_answer_agent.py`

- [x] (02B): Implement deterministic missing-information behavior
  - Source of Truth: `docs/plans/Plan_11.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.4 Insufficient Evidence Answer`; `docs/plans/Master_Plan.md` > `## 18.4 Missing Information Rule`
  - Source Requirements:
    - If `missing_information=true`, return insufficient-evidence answer.
    - If `verified_chunks` is empty, return insufficient-evidence answer.
    - Do not ask the model to invent an answer for insufficient evidence.
    - Missing verified chunks returns insufficient-evidence answer.
  - Details: Use the exact answer text `Tài liệu hiện tại chưa cung cấp đủ thông tin để xác định câu trả lời.`. Populate citations as an empty list, confidence safely, and self-check values that truthfully reflect insufficient evidence without marking unsupported content as ready.
  - Dependencies: (02A).
  - User Action: None.
  - Agent Work: Add deterministic branch before any ShopAIKey call and make it easy to test that the provider is not called.
  - Output: Safe insufficient-evidence Agent 3 output.
  - Acceptance: Missing information and empty verified chunks return the insufficient-evidence output without provider calls.
  - Validation: Tests with mocked ShopAIKey asserting no call.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

- [x] (02C): Normalize Agent 2 verification input for Agent 3
  - Source of Truth: `docs/plans/Plan_11.md` > `## 8. API Design`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 12. Acceptance Criteria`; `README.md` > `## Architecture`; `README.md` > `## Known Gaps or Unclear Areas`
  - Source Requirements:
    - Input includes `agent_run_id`, `question`, and `verification`.
    - Verification includes `verified_chunks`, `rejected_chunks`, `missing_information`, and `confidence`.
    - Agent 3 uses Agent 2 verified chunks only.
    - Agent 3 never uses rejected chunks.
  - Details: Accept Agent 2 verification output consistently with current schemas. Build in-memory lookup sets for verified quotes/file names and rejected quotes/file names for later citation and content safety checks.
  - Dependencies: (02A), completed Plan 10.
  - User Action: None.
  - Agent Work: Add input validation and normalized evidence lookup helpers without mutating Agent 2 output.
  - Output: Normalized Agent 3 input and evidence lookup structure.
  - Acceptance: Invalid input raises controlled `AnswerAgentError` or Pydantic validation; valid Agent 2 verification output is accepted.
  - Validation: Unit tests for mapping and Pydantic input cases.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/app/agents/schemas.py`, `backend/tests/test_answer_agent.py`

- [x] (02D): Prepare compact verified-evidence payload for answer generation
  - Source of Truth: `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 18.1 Grounding Rule`; `docs/plans/Master_Plan.md` > `## 18.2 Simple Reasoning Rule`
  - Source Requirements:
    - For sufficient evidence, send question and verified chunks to ShopAIKey chat completion.
    - Answer generation must use verified chunks only.
    - Simple reasoning is allowed only when verified evidence clearly supports it.
    - Rejected chunks must not be used.
  - Details: Build a compact provider payload containing the question and only the fields from verified chunks needed for answering and citations, such as file name, quote, page number if useful, and verification reason if needed. Do not include rejected chunks in the provider answer-generation prompt as evidence.
  - Dependencies: (02C), Batch01 prompts.
  - User Action: None.
  - Agent Work: Add payload builder and tests that rejected chunks are absent from provider messages.
  - Output: Provider-ready verified evidence payload.
  - Acceptance: Provider messages contain the question and verified evidence only; rejected chunks are excluded from the generation prompt.
  - Validation: Unit test inspecting mocked ShopAIKey messages.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

### Files or Modules Likely Created or Updated

- `backend/app/agents/answer_agent.py`
- `backend/app/agents/schemas.py`
- `backend/app/agents/__init__.py`
- `backend/tests/test_answer_agent.py`

### Required Outputs / Artifacts

- Internal `run_answer_agent` callable.
- Controlled `AnswerAgentError`.
- Deterministic insufficient-evidence branch.
- Normalized Agent 2 verification input handling.
- Compact verified-evidence payload builder for LLM answer drafting.

### Acceptance Criteria

- Agent 3 is internal and backend-only.
- Missing-information and empty-verified evidence return the safe insufficient-evidence answer without calling ShopAIKey.
- Agent 3 accepts the current Agent 2 verification output shape.
- Rejected chunks are not included as evidence in the answer-generation prompt.
- No public API, LangGraph orchestration, frontend, or retrieval expansion is added.

### Required Tests or Validations

- Import smoke check for `app.agents.answer_agent`.
- Unit tests for insufficient-evidence behavior.
- Unit tests proving ShopAIKey is not called for insufficient evidence.
- Unit tests proving provider payload excludes rejected chunks.

### Explicit Non-Goals

- Do not call ShopAIKey for insufficient evidence.
- Do not implement public chat endpoint behavior.
- Do not create or update chat session/message persistence.
- Do not retrieve more chunks.
- Do not implement self-check readiness enforcement in this batch unless needed for deterministic insufficient output.

## Mandatory Batch03 - LLM Draft Answer Parsing and Citation Enforcement

### Goal

Implement sufficient-evidence answer drafting through ShopAIKey chat completion and enforce strict JSON, citation, and verified-evidence validation before self-check.

### Why this batch exists

Agent 3's model output is not trustworthy until it is parsed, schema-validated, and checked against Agent 2 verified evidence. This batch prevents missing citations, fabricated quotes, rejected evidence, and unsupported output from reaching self-check as valid draft content.

### Inputs / Dependencies

- Batch01 and Batch02 completed
- Existing `shopaikey_service.chat_completion(messages, response_format=None)`
- Current Agent 2 verification output fixtures or test builders
- `docs/plans/Plan_11.md`

### Tasks

- [x] (03A): Call ShopAIKey for sufficient-evidence answer drafting
  - Source of Truth: `docs/plans/Plan_11.md` > `## 5. Dependencies`; `docs/plans/Plan_11.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `README.md` > `### ShopAIKey`
  - Source Requirements:
    - ShopAIKey chat completion helper must exist.
    - For sufficient evidence, send question and verified chunks to ShopAIKey chat completion.
    - Require JSON output matching `AnswerAgentOutput` without final self-check or with draft self-check that will be revalidated.
  - Details: Use the existing ShopAIKey chat helper and pass an OpenAI-compatible response format if the service pattern supports it. Keep tests mocked; do not require live provider access for unit tests.
  - Dependencies: Batch02, (01C).
  - User Action: User must provide real ShopAIKey values only for live manual validation.
  - Agent Work: Wire sufficient-evidence branch to `shopaikey_service.chat_completion` with answer-generation prompt and verified-evidence payload.
  - Output: Draft answer content string from ShopAIKey for valid evidence.
  - Acceptance: Sufficient evidence triggers one mocked chat completion call with backend-configured model behavior hidden in the service.
  - Validation: Unit test with mocked `chat_completion`.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live provider validation when real backend credentials are missing.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

- [x] (03B): Parse and validate draft answer JSON
  - Source of Truth: `docs/plans/Plan_11.md` > `## 8. API Design`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Require JSON output matching `AnswerAgentOutput` without final self-check or with draft self-check that will be revalidated.
    - Parse and validate the draft answer.
    - Invalid JSON response is rejected.
    - Output is Pydantic-validated.
  - Details: Handle JSON parsing errors, malformed payloads, and schema errors with `AnswerAgentError` and safe messages. If the model omits final `self_check`, normalize through an internal draft schema or add a draft self-check placeholder that will be overwritten in Batch04.
  - Dependencies: (03A), Batch01 schemas.
  - User Action: None.
  - Agent Work: Add parser and validation helpers for provider response content.
  - Output: Validated draft answer object.
  - Acceptance: Invalid JSON and schema-invalid payloads fail controlled validation; valid payloads continue to citation checks.
  - Validation: Unit tests for invalid JSON, missing required fields, invalid confidence, and valid draft payload.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/app/agents/schemas.py`, `backend/tests/test_answer_agent.py`

- [x] (03C): Enforce citation presence and format
  - Source of Truth: `docs/plans/Plan_11.md` > `## 3. Scope`; `docs/plans/Plan_11.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.3 Citation Style`; `docs/plans/Master_Plan.md` > `## 18.3 Citation Rule`
  - Source Requirements:
    - Implement citation format `file_name: "quoted text"`.
    - Agent 3 includes citations with file name and quote.
    - Missing citation fails validation.
    - Every final answer must include citations.
  - Details: Require at least one citation for sufficient-evidence answers. Ensure citations are structured as `Citation(file_name, quote)` and can be rendered as `file_name: "quoted text"` for normal users without exposing chunk IDs.
  - Dependencies: (03B), (01B).
  - User Action: None.
  - Agent Work: Add citation list validation and renderer or formatting helper if needed for manual check/test assertions.
  - Output: Draft answers without citations are rejected.
  - Acceptance: Missing or empty citations fail for sufficient-evidence answers; valid citations preserve file names and exact quotes.
  - Validation: Unit tests for missing citation and valid citation shape.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/app/agents/schemas.py`, `backend/tests/test_answer_agent.py`

- [x] (03D): Validate citation quotes against verified evidence
  - Source of Truth: `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Plan_11.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## 18.1 Grounding Rule`
  - Source Requirements:
    - Every citation quote must come from a verified chunk quote.
    - Citation quote not present in verified evidence fails validation.
    - Final answer must be grounded in verified chunks.
  - Details: Compare citation quotes to Agent 2 verified quote text. Prefer exact or normalized containment rules that are deterministic and tested. Do not accept fabricated quote text even when semantically similar.
  - Dependencies: (03C), Batch02 evidence lookup.
  - User Action: None.
  - Agent Work: Add verified-quote membership checks and safe failure behavior.
  - Output: Citation quote fidelity enforcement.
  - Acceptance: Draft answers citing quotes not found in verified evidence fail validation and are not returned.
  - Validation: Unit test for LLM citation not present in verified quote.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

- [x] (03E): Reject rejected chunk usage in citations and answer content
  - Source of Truth: `docs/plans/Plan_11.md` > `## 3. Scope`; `docs/plans/Plan_11.md` > `## 4. Out of Scope`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Master_Plan.md` > `## 18.1 Grounding Rule`
  - Source Requirements:
    - Never use rejected chunks.
    - Add validators that reject citations from rejected chunks.
    - LLM uses rejected chunk -> fail self-check.
    - Agent 3 never uses rejected chunks.
  - Details: Detect rejected quote/file-name citation attempts and obvious rejected quote reuse in `final_answer` or `reasoning_summary`. More nuanced unsupported-claim checks continue in Batch04 self-check.
  - Dependencies: (03D), Batch02 evidence lookup.
  - User Action: None.
  - Agent Work: Add rejected evidence exclusion checks that fail safely before returning output.
  - Output: Rejected chunks cannot be cited or copied into normal answer output.
  - Acceptance: Draft answers using rejected quote text are blocked.
  - Validation: Unit test for LLM uses rejected chunk.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

- [x] (03F): Preserve final output shape after draft validation
  - Source of Truth: `docs/plans/Plan_11.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_11.md` > `## 8. API Design`; `docs/plans/Plan_11.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Output contains `final_answer`, `citations`, `reasoning_summary`, `confidence`, and `self_check`.
    - Output is Pydantic-validated.
    - Agent 3 includes citations with file name and quote.
  - Details: Ensure draft validation and citation checks return a model or mapping that can be passed into self-check without dropping required fields or adding public-only fields such as chunk IDs.
  - Dependencies: (03B), (03C), (03D), (03E).
  - User Action: None.
  - Agent Work: Normalize validated draft output for Batch04 self-check and final output generation.
  - Output: Stable draft/final output shape.
  - Acceptance: Valid draft answers remain JSON-serializable and Pydantic-valid after evidence checks.
  - Validation: Unit test asserting exact expected output keys.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

### Files or Modules Likely Created or Updated

- `backend/app/agents/answer_agent.py`
- `backend/app/agents/schemas.py`
- `backend/app/agents/prompts.py`
- `backend/tests/test_answer_agent.py`

### Required Outputs / Artifacts

- ShopAIKey answer-generation call for sufficient evidence.
- JSON parser and controlled validation failure behavior.
- Citation presence and `file_name` plus `quote` validation.
- Verified quote fidelity checks.
- Rejected evidence exclusion checks.
- Stable draft answer shape ready for self-check.

### Acceptance Criteria

- Sufficient evidence calls ShopAIKey through the backend service.
- Invalid JSON and malformed model output are rejected.
- Sufficient-evidence answers require citations.
- Citation quotes must come from verified chunks.
- Rejected chunks cannot be cited or copied into normal answer output.
- Output shape remains compatible with `AnswerAgentOutput`.

### Required Tests or Validations

- Mocked ShopAIKey chat completion test.
- Invalid JSON provider response test.
- Missing citation test.
- Citation quote not in verified quote test.
- Rejected chunk citation/content test.
- Exact output-key validation test.

### Explicit Non-Goals

- Do not perform live ShopAIKey calls in automated tests.
- Do not rely on semantic similarity for quote validation.
- Do not implement LangGraph or public chat routes.
- Do not expose chunk IDs in normal answer output.

## Mandatory Batch04 - Self-Check, Safe Failure Handling, and Logging

### Goal

Run Agent 3 self-check before returning a ready answer, enforce safe behavior when self-check fails, and log answer generation plus self-check output in `agent_steps`.

### Why this batch exists

Citation validation alone does not prove that the answer is fully grounded or ready. Plan 11 requires Agent 3 to self-check before final output and to make the step traceable for debugging.

### Inputs / Dependencies

- Batch01 through Batch03 completed
- Existing `backend/app/services/agent_log_service.py`
- Completed Plan 2 `agent_steps`
- `docs/plans/Plan_11.md`
- `docs/plans/Master_Plan.md`

### Tasks

- [x] (04A): Implement self-check execution
  - Source of Truth: `docs/plans/Plan_11.md` > `## 3. Scope`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.5 Self-Check`; `docs/plans/Master_Plan.md` > `## 18.2 Simple Reasoning Rule`
  - Source Requirements:
    - Run self-check to confirm the answer uses only verified chunks.
    - Confirm it includes citations.
    - Confirm it avoids rejected chunks.
    - Confirm it has no unsupported claims.
    - Confirm it is ready.
    - Confirm reasoning follows clearly from the evidence.
  - Details: Implement the self-check policy chosen in Batch01. It may be deterministic, LLM-assisted, or hybrid, but final readiness must be represented in `AnswerSelfCheck` and enforced in code.
  - Dependencies: Batch03 validated draft output.
  - User Action: None.
  - Agent Work: Add self-check execution and normalization to `AnswerSelfCheck`.
  - Output: Self-check result attached to Agent 3 output.
  - Acceptance: Ready answers have `uses_only_verified_chunks=true`, `has_citation=true`, `has_unsupported_claims=false`, and `is_ready=true`.
  - Validation: Unit tests for successful self-check and reasoning-ready grounded answer.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/app/agents/prompts.py`, `backend/tests/test_answer_agent.py`

- [x] (04B): Enforce self-check failure policy
  - Source of Truth: `docs/plans/Plan_11.md` > `## 8. API Design`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Plan_11.md` > `## 13. Failure Handling`
  - Source Requirements:
    - `AnswerAgentError` covers self-check failure.
    - If self-check fails, return an insufficient-evidence answer or raise `AnswerAgentError`.
    - Do not return unsupported content.
    - Self-check `has_unsupported_claims=true` must not return answer as ready.
  - Details: Plan 11 allows either a safe insufficient-evidence fallback or a controlled `AnswerAgentError` for self-check failure. Choose one explicit policy, keep it documented in tests, and never return unsupported draft content as ready.
  - Dependencies: (04A).
  - User Action: None.
  - Agent Work: Add enforcement for failed self-check booleans, unsupported claims, missing citation, rejected evidence, and not-ready status.
  - Output: Safe self-check failure handling.
  - Acceptance: Failed self-check never returns unsupported content with `is_ready=true`.
  - Validation: Unit test for `has_unsupported_claims=true` and at least one not-ready self-check case.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

- [x] (04C): Add Agent 3 success-step logging
  - Source of Truth: `docs/plans/Plan_11.md` > `## 3. Scope`; `docs/plans/Plan_11.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `### 5.5 Agent Logs / Debug Page`; `docs/plans/Master_Plan.md` > `## Table: agent_steps`; `docs/plans/Master_Plan.md` > `## 18.5 Debuggability Rule`
  - Source Requirements:
    - Log Agent 3 answer and self-check outputs.
    - Log in `agent_steps` with step name `agent_3_answer_self_check`.
    - Agent 3 logs answer and self-check output.
    - Logs should include Agent 3 draft answer, self-check result, final answer, confidence, errors, and timestamps where relevant.
  - Details: Reuse `agent_log_service` patterns. Include safe input/output payloads sufficient for debugging how the answer was generated and whether self-check passed. Do not expose secrets or raw provider internals.
  - Dependencies: (04A), (04B), existing agent log service.
  - User Action: None.
  - Agent Work: Log successful Agent 3 answer/self-check with `step_name="agent_3_answer_self_check"` and a consistent `agent_name`.
  - Output: Successful Agent 3 `agent_steps` logging.
  - Acceptance: Success path attempts one log insertion with safe input/output, status success, and the required step name.
  - Validation: Unit test with mocked `agent_log_service.log_agent_step`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`

- [x] (04D): Add Agent 3 failed-step logging
  - Source of Truth: `docs/plans/Plan_11.md` > `## 13. Failure Handling`; `docs/plans/Plan_11.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `### 5.5 Agent Logs / Debug Page`; `docs/plans/Master_Plan.md` > `## Table: agent_steps`
  - Source Requirements:
    - ShopAIKey failure logs failed step and raises `AnswerAgentError`.
    - Invalid JSON response is rejected.
    - Missing citation fails validation.
    - Citation quote not present in verified evidence fails validation.
    - Unsupported claim detected by self-check prevents final answer from being marked ready.
    - No fake success.
  - Details: Use `try_log_agent_step` or the existing safe failed-log pattern so the original controlled error remains visible even if logging fails. Do not include raw provider secrets or stack traces in logs.
  - Dependencies: (04B), (04C).
  - User Action: None.
  - Agent Work: Add failed-step logging for provider, parsing, validation, citation, rejected-evidence, and self-check failures.
  - Output: Failed Agent 3 logging behavior.
  - Acceptance: Controlled failures attempt failed-step logging and raise or return only the chosen safe behavior.
  - Validation: Unit tests for ShopAIKey failure, invalid JSON, citation failure, and self-check failure logging.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`, `backend/tests/test_agent_log_service.py` only if shared service behavior changes

- [x] (04E): Keep logging failures safe and visible
  - Source of Truth: `docs/plans/Plan_11.md` > `## 13. Failure Handling`; `docs/plans/Plan_11.md` > `## 15. Reviewer Checklist`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - No fake success.
    - Agent 3 logs answer and self-check output.
    - Provider and validation failures are controlled.
    - No hardcoded secrets.
  - Details: If an Agent 3 output is otherwise valid but log insertion fails, follow the existing project policy for retrieval/verification logging. Surface a safe warning or controlled behavior consistently with the current agent modules.
  - Dependencies: (04C), (04D).
  - User Action: None.
  - Agent Work: Reuse existing log-attempt result behavior and cover log insertion failure in tests if Agent 3 needs explicit handling.
  - Output: Safe behavior when `agent_steps` persistence fails.
  - Acceptance: Log persistence failures do not leak secrets or silently fabricate persisted logs.
  - Validation: Mocked logging failure test if applicable.
  - Blocked Condition: None.
  - Files: `backend/app/agents/answer_agent.py`, `backend/tests/test_answer_agent.py`, `backend/tests/test_agent_log_service.py` only if shared service behavior changes

### Files or Modules Likely Created or Updated

- `backend/app/agents/answer_agent.py`
- `backend/app/agents/prompts.py`
- `backend/app/agents/schemas.py`
- `backend/app/services/agent_log_service.py` only if existing service behavior is insufficient
- `backend/tests/test_answer_agent.py`
- `backend/tests/test_agent_log_service.py` only if logging service behavior changes

### Required Outputs / Artifacts

- Self-check execution and normalized self-check output.
- Explicit self-check failure policy.
- Agent 3 success logging with `agent_3_answer_self_check`.
- Agent 3 failed-step logging for provider, parse, validation, citation, rejected-evidence, and self-check failures.
- Safe behavior for log persistence failures.

### Acceptance Criteria

- Agent 3 self-checks before returning a ready answer.
- Ready answers have safe self-check booleans.
- Failed self-check never returns unsupported content as ready.
- Successful Agent 3 output is logged with answer and self-check details.
- Failed Agent 3 paths attempt safe failed-step logging.
- Logging failures do not leak secrets or create fake success.

### Required Tests or Validations

- Successful self-check test.
- `has_unsupported_claims=true` failure test.
- Success logging test.
- Failed logging tests for provider/invalid JSON/citation/self-check failures.
- Log insertion failure test if Agent 3 adds behavior beyond existing service guarantees.

### Explicit Non-Goals

- Do not implement public log APIs or debug pages.
- Do not expose chunk IDs in normal output to satisfy debug logging.
- Do not introduce a new logging table or migration.
- Do not require live Supabase for unit tests.

## Mandatory Batch05 - Required Automated Tests

### Goal

Add and run focused automated tests proving Agent 3's grounded answer behavior, insufficient-evidence behavior, citation enforcement, rejected chunk exclusion, self-check failure behavior, and logging.

### Why this batch exists

Plan 11 is safety-critical: a final answer must never be returned as ready unless it is grounded in Agent 2 verified evidence. Automated tests must catch fabricated quotes, missing citations, rejected evidence usage, unsupported claims, invalid JSON, provider failure, and unsafe logging behavior.

### Inputs / Dependencies

- Batch01 through Batch04 completed
- Current pytest setup
- Mocked ShopAIKey and agent log service fixtures
- `docs/plans/Plan_11.md`

### Tasks

- [ ] (05A): Add grounded answer and simple reasoning tests
  - Source of Truth: `docs/plans/Plan_11.md` > `## 1. Goal`; `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Plan_11.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 18.2 Simple Reasoning Rule`
  - Source Requirements:
    - Verified chunks include start date and probation duration -> answer may infer August 2026.
    - Agent 3 uses verified chunks only.
    - Agent 3 allows simple reasoning only when verified evidence clearly supports it.
    - Agent 3 includes citations with file name and quote.
  - Details: Use mocked ShopAIKey responses and Agent 2 verification fixtures containing clear start date and probation duration evidence. Assert final answer, citations, confidence, reasoning summary, self-check readiness, and no normal-user chunk IDs.
  - Dependencies: Batch03, Batch04.
  - User Action: None.
  - Agent Work: Add tests for grounded answer generation and allowed simple reasoning.
  - Output: Automated coverage for normal Agent 3 success behavior.
  - Acceptance: Tests fail without verified-only citations and ready self-check output.
  - Validation: `cd backend` then `pytest tests/test_answer_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_answer_agent.py`

- [ ] (05B): Add insufficient-evidence tests
  - Source of Truth: `docs/plans/Plan_11.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Plan_11.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## 18.4 Missing Information Rule`
  - Source Requirements:
    - `missing_information=true` -> insufficient-evidence answer.
    - No verified chunks -> insufficient-evidence answer.
    - Missing verified chunks returns insufficient-evidence answer.
    - Do not force an answer.
  - Details: Assert the exact insufficient-evidence answer text and that ShopAIKey is not called. Include both `missing_information=true` and empty `verified_chunks` cases.
  - Dependencies: Batch02.
  - User Action: None.
  - Agent Work: Add deterministic insufficient-evidence tests.
  - Output: Automated coverage for safe refusal behavior.
  - Acceptance: Tests prove insufficient evidence is handled without provider calls or invented answers.
  - Validation: `cd backend` then `pytest tests/test_answer_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_answer_agent.py`

- [ ] (05C): Add citation enforcement tests
  - Source of Truth: `docs/plans/Plan_11.md` > `## 3. Scope`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Plan_11.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## 18.3 Citation Rule`
  - Source Requirements:
    - Missing citation fails validation.
    - LLM citation not present in verified quote -> fail validation.
    - Citation quote not present in verified evidence fails validation.
    - Confirm final answer includes citations in `file_name: "quoted text"` form.
  - Details: Mock LLM payloads with missing citations, empty citation lists, fabricated quote text, and valid citations. Assert controlled failures and the accepted citation rendering format.
  - Dependencies: Batch03.
  - User Action: None.
  - Agent Work: Add citation validation tests.
  - Output: Automated coverage for citation safety.
  - Acceptance: Tests fail if missing or fabricated citations are accepted.
  - Validation: `cd backend` then `pytest tests/test_answer_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_answer_agent.py`

- [ ] (05D): Add rejected chunk exclusion and unsupported claim tests
  - Source of Truth: `docs/plans/Plan_11.md` > `## 4. Out of Scope`; `docs/plans/Plan_11.md` > `## 9. Implementation Steps`; `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Plan_11.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## 18.1 Grounding Rule`
  - Source Requirements:
    - Do not use rejected chunks.
    - LLM uses rejected chunk -> fail self-check.
    - Self-check `has_unsupported_claims=true` -> do not return answer as ready.
    - Unsupported claim detected by self-check prevents final answer from being marked ready.
  - Details: Include one test where a mocked answer cites or copies rejected quote text, and one test where self-check reports unsupported claims. Assert the chosen safe failure policy from Batch04.
  - Dependencies: Batch03, Batch04.
  - User Action: None.
  - Agent Work: Add rejected evidence and unsupported-claim tests.
  - Output: Automated coverage for no-rejected-evidence and no-unsupported-ready-answer behavior.
  - Acceptance: Tests prove rejected chunks and unsupported claims cannot produce ready output.
  - Validation: `cd backend` then `pytest tests/test_answer_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_answer_agent.py`

- [ ] (05E): Add provider, parsing, and logging failure tests
  - Source of Truth: `docs/plans/Plan_11.md` > `## 8. API Design`; `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Plan_11.md` > `## 13. Failure Handling`; `docs/plans/Plan_11.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - ShopAIKey failure logs failed step and raises `AnswerAgentError`.
    - Invalid JSON response is rejected.
    - Output is Pydantic-validated.
    - Agent 3 logs answer and self-check output.
    - No fake success.
  - Details: Mock provider exceptions, invalid JSON content, schema-invalid payloads, success logging, failed-step logging, and log insertion failure behavior if Agent 3 has explicit handling for it.
  - Dependencies: Batch04.
  - User Action: None.
  - Agent Work: Add provider/parsing/logging failure tests.
  - Output: Automated coverage for controlled failures and logging.
  - Acceptance: Tests prove failures are safe, logged when possible, and not falsely reported as success.
  - Validation: `cd backend` then `pytest tests/test_answer_agent.py -v`; run `pytest tests/test_agent_log_service.py -v` if shared log service changed.
  - Blocked Condition: None.
  - Files: `backend/tests/test_answer_agent.py`, `backend/tests/test_agent_log_service.py` if changed

- [ ] (05F): Run required targeted automated validation
  - Source of Truth: `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Plan_11.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_11.md` > `## 15. Reviewer Checklist`; `README.md` > `## Testing and Validation`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - Run `cd backend` then `pytest tests/test_answer_agent.py -v`.
    - Tests were actually run.
    - Acceptance criteria passed.
    - No fake success.
  - Details: Run the exact targeted pytest command. If shared schema, ShopAIKey, or agent log service tests were changed, run those targeted tests too. Report failures honestly and do not mark completion unless required tests pass or a blocked status is documented.
  - Dependencies: (05A), (05B), (05C), (05D), (05E).
  - User Action: None.
  - Agent Work: Execute targeted tests, capture results, and fix in-scope failures.
  - Output: Test result evidence for Plan 11.
  - Acceptance: Required tests pass, or failures are documented with remaining in-scope work.
  - Validation: `cd backend` then `pytest tests/test_answer_agent.py -v`; plus related targeted tests if touched.
  - Blocked Condition: None unless local environment lacks required test dependencies; report dependency issue safely instead of claiming success.
  - Files: `backend/tests/test_answer_agent.py`, related backend test files if touched

### Files or Modules Likely Created or Updated

- `backend/tests/test_answer_agent.py`
- `backend/tests/test_agent_log_service.py` if logging service behavior changes
- Runtime files from earlier batches only as needed to make tests pass

### Required Outputs / Artifacts

- Automated test coverage for grounded answer generation and simple reasoning.
- Automated test coverage for insufficient-evidence behavior.
- Automated test coverage for missing citations and citation quote validation.
- Automated test coverage for rejected chunk exclusion and self-check failure.
- Automated test coverage for provider, parsing, validation, and logging failures.
- Required pytest command output summarized in the execution report.

### Acceptance Criteria

- `backend/tests/test_answer_agent.py` exists and covers all Plan 11 required cases.
- Targeted pytest command was run.
- Tests pass before completion is claimed.
- Mocked tests avoid live ShopAIKey and Supabase dependency unless explicitly performing manual/live validation.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_answer_agent.py -v`
- `pytest tests/test_agent_log_service.py -v` if agent log service tests changed
- Other related targeted tests if shared schemas, prompts, settings, or ShopAIKey service behavior changed

### Explicit Non-Goals

- Do not rely on live ShopAIKey calls for automated tests.
- Do not fabricate passing test output.
- Do not broaden tests into LangGraph, public chat APIs, frontend screens, or conversation memory.

## Mandatory Batch06 - Manual Validation, Reporting, and Scope Review

### Goal

Run the required manual Agent 2 to Agent 3 smoke check when setup is available, write the execution report, and confirm Plan 11 scope boundaries before reviewer handoff.

### Why this batch exists

Automated tests prove deterministic behavior, but Plan 11 also requires a manual sample check and a clear report of files, commands, test results, known issues, out-of-scope work, and examples of grounded and insufficient-evidence answers.

### Inputs / Dependencies

- Batch01 through Batch05 completed or safely blocked
- Sample Agent 2 verification output
- Real backend `.env` values for ShopAIKey and Supabase only if live provider/log checks are attempted
- Valid `agent_run_id` only if live log persistence is attempted
- `docs/plans/Plan_11.md`

### Tasks

- [ ] (06A): Run manual Agent 2 output into Agent 3 when setup is available
  - Source of Truth: `docs/plans/Plan_11.md` > `## 11. Required Tests`; `docs/plans/Plan_11.md` > `## 14. Agent Report Requirement`; `README.md` > `## Configuration`; `README.md` > `## Known Gaps or Unclear Areas`
  - Source Requirements:
    - Pass sample Agent 2 output to Agent 3.
    - Confirm final answer includes citations in `file_name: "quoted text"` form.
    - Confirm no chunk IDs are shown to normal users.
    - Report one grounded answer example and one insufficient-evidence example.
  - Details: Use existing backend scripts, tests, or direct callable invocation patterns. If no valid `agent_run_id`, live Supabase setup, ShopAIKey credentials, or sample Agent 2 payload is available for live validation, report `BLOCKED_BY_USER_ACTION` for live manual validation and rely on automated mocked tests for code behavior.
  - Dependencies: Batch05 passing tests.
  - User Action: User must provide real backend `.env` settings, valid `agent_run_id`, and sample Agent 2 output if live provider/log validation is required.
  - Agent Work: Attempt manual smoke check only when setup is available; otherwise record exact safe blocking reason.
  - Output: Manual Agent 3 validation result or blocked status.
  - Acceptance: Agent 3 returns a grounded answer with file-name/quote citations and no normal-user chunk IDs, or manual validation is explicitly blocked with a safe setup reason.
  - Validation: Direct callable smoke check or documented `BLOCKED_BY_USER_ACTION`.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if required ShopAIKey credentials, Supabase settings, valid `agent_run_id`, or sample Agent 2 output are missing.
  - Files: No runtime files expected; execution report records result

- [ ] (06B): Create execution report with grounded and insufficient-evidence examples
  - Source of Truth: `docs/plans/Plan_11.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_11.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Report files created.
    - Report files modified.
    - Report commands run.
    - Report test results.
    - Report known issues.
    - Report intentionally not implemented out-of-scope work.
    - Include one grounded answer example.
    - Include one insufficient-evidence example.
  - Details: Create the standard report artifact for Plan 11 using the repo's existing reports pattern. Keep examples safe and synthetic if needed; do not include secrets or private raw document content.
  - Dependencies: Batch05, (06A).
  - User Action: None.
  - Agent Work: Write report with accurate commands/results and safe examples.
  - Output: Plan 11 execution report.
  - Acceptance: Report includes all Plan 11 required sections and does not claim blocked live validation as completed.
  - Validation: Read report before handoff and confirm every required report item is present.
  - Blocked Condition: None.
  - Files: `docs/reports/report_11_execute_agent.md`

- [ ] (06C): Complete scope, secret, and architecture review
  - Source of Truth: `docs/plans/Plan_11.md` > `## 4. Out of Scope`; `docs/plans/Plan_11.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_11.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 18.1 Grounding Rule`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - Scope was followed.
    - Out-of-scope work was not added.
    - Tests were actually run.
    - Acceptance criteria passed.
    - No hardcoded secrets.
    - Architecture still matches `docs/plans/Master_Plan.md`.
    - Citation format is file name plus quoted text.
    - Normal user output does not expose chunk IDs.
    - Self-check failure is not ignored.
  - Details: Inspect changed files and tests for scope boundaries. Confirm no API route, frontend screen, LangGraph workflow, extra retrieval, conversation memory, or committed secret was added.
  - Dependencies: Batch05, (06B).
  - User Action: None.
  - Agent Work: Run focused scans or code review checks, update report with scope findings, and update this task tracker only after validations pass or blocks are recorded.
  - Output: Reviewer-ready scope boundary confirmation.
  - Acceptance: Scope review confirms Plan 11 boundaries or documents exact deviations requiring fixes before reviewer handoff.
  - Validation: Git diff review, secret-name scan, and targeted search for out-of-scope route/workflow/frontend additions.
  - Blocked Condition: None.
  - Files: `docs/reports/report_11_execute_agent.md`, `docs/tasks/task_11.md` progress tracker during execution

### Files or Modules Likely Created or Updated

- `docs/reports/report_11_execute_agent.md`
- `docs/tasks/task_11.md` progress tracker during execution
- No runtime files unless test or scope feedback from earlier batches requires fixes

### Required Outputs / Artifacts

- Manual Agent 3 validation result or blocked status.
- Execution report for Plan 11 reviewer handoff.
- Grounded answer example with file-name/quote citation.
- Insufficient-evidence answer example.
- Scope, secret, and architecture boundary confirmation.

### Acceptance Criteria

- Automated tests were run and reported.
- Manual check was completed or safely blocked.
- Success and failure logging behavior is reported honestly.
- Out-of-scope work was not implemented.
- No secrets or fake success appear in the report.
- Grounded and insufficient-evidence examples are included.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_answer_agent.py -v`
- Manual Agent 2 -> Agent 3 smoke check when setup is available.
- Safe `agent_steps` row verification when live Supabase setup is available.
- Scope and secret inspection.

### Explicit Non-Goals

- Do not fabricate live provider, database, or document validation.
- Do not create real provider keys, Supabase projects, Qdrant collections, documents, or agent runs on behalf of the user unless explicitly requested.
- Do not implement public chat, evidence, or agent log screens.
- Do not implement LangGraph orchestration, retrieval expansion, or conversation memory.

## Optional Future Tracks

No optional future tracks are part of the mandatory Plan 11 batch chain.

LangGraph orchestration, `/api/chat/ask`, public evidence APIs, public agent log APIs, frontend chat, frontend evidence display, frontend agent logs, chat sessions/messages, conversation memory, and additional retrieval remain future work outside this task file unless a later approved plan explicitly includes them.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05
- Batch05 -> Batch06

Optional future tracks are outside the mandatory dependency chain.

## Global Verification Checklist

- [ ] `docs/plans/Plan_11.md` remained the scope authority.
- [ ] No database schema changes were added.
- [ ] `backend/app/agents/schemas.py` defines Agent 3 input, citation, self-check, and output schemas.
- [ ] Agent 3 output contains `final_answer`, `citations`, `reasoning_summary`, `confidence`, and `self_check`.
- [ ] `confidence` is validated between `0.0` and `1.0`.
- [ ] Citation objects contain `file_name` and `quote`.
- [ ] Citation output can be rendered as `file_name: "quoted text"`.
- [ ] `backend/app/agents/prompts.py` contains Agent 3 answer-generation rules.
- [ ] Answer prompt uses verified chunks only.
- [ ] Answer prompt forbids rejected chunks.
- [ ] Answer prompt forbids outside knowledge.
- [ ] Answer prompt requires citations.
- [ ] Answer prompt answers in Vietnamese by default.
- [ ] Answer prompt allows simple reasoning only when evidence is clear.
- [ ] Self-check prompt or deterministic rule checks verified-only evidence, citations, rejected evidence, unsupported claims, reasoning support, and readiness.
- [ ] `backend/app/agents/answer_agent.py` exposes `run_answer_agent`.
- [ ] `AnswerAgentError` handles provider, parse, validation, citation, rejected-evidence, and self-check failures.
- [ ] `missing_information=true` returns the insufficient-evidence answer without calling ShopAIKey.
- [ ] Empty `verified_chunks` returns the insufficient-evidence answer without calling ShopAIKey.
- [ ] Sufficient evidence calls ShopAIKey chat completion through backend service code.
- [ ] LLM JSON output is parsed and Pydantic-validated.
- [ ] Missing citations fail validation.
- [ ] Citation quotes not found in verified evidence fail validation.
- [ ] Rejected chunks are not cited or copied into normal answer output.
- [ ] Normal user output does not expose chunk IDs.
- [ ] Self-check runs before a ready final answer is returned.
- [ ] Self-check failure does not return unsupported content as ready.
- [ ] Agent 3 logs successful answer/self-check steps to `agent_steps` with step name `agent_3_answer_self_check`.
- [ ] Agent 3 logs failed answer/self-check steps when possible.
- [ ] ShopAIKey failures log failed step and raise `AnswerAgentError`.
- [ ] Invalid JSON responses are rejected.
- [ ] No new public API route was added.
- [ ] LangGraph workflow was not implemented.
- [ ] Frontend chat was not implemented.
- [ ] Additional retrieval was not implemented.
- [ ] Conversation memory was not added.
- [ ] Backend-only secrets and provider settings stayed out of frontend code.
- [ ] `cd backend` then `pytest tests/test_answer_agent.py -v` was run and reported.
- [ ] Manual Agent 2 -> Agent 3 smoke check was completed or marked `BLOCKED_BY_USER_ACTION` with a safe reason.
- [ ] Execution report includes files created, files modified, commands run, test results, known issues, out-of-scope work, one grounded answer example, and one insufficient-evidence example.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [x] Batch01 - Answer Contracts, Prompts, and Backend-Only Configuration
- [x] Batch02 - Answer Agent Callable and Insufficient-Evidence Path
- [x] Batch03 - LLM Draft Answer Parsing and Citation Enforcement
- [ ] Batch04 - Self-Check, Safe Failure Handling, and Logging
- [ ] Batch05 - Required Automated Tests
- [ ] Batch06 - Manual Validation, Reporting, and Scope Review

### Task IDs

#### Batch01

- [x] (01A): Extend agent schemas for Agent 3 answer output
- [x] (01B): Define citation and evidence validation contract
- [x] (01C): Add answer generation prompt rules
- [x] (01D): Add self-check prompt or deterministic self-check rules
- [x] (01E): Confirm backend-only ShopAIKey chat configuration boundary

#### Batch02

- [x] (02A): Create answer agent module and controlled error type
- [x] (02B): Implement deterministic missing-information behavior
- [x] (02C): Normalize Agent 2 verification input for Agent 3
- [x] (02D): Prepare compact verified-evidence payload for answer generation

#### Batch03

- [x] (03A): Call ShopAIKey for sufficient-evidence answer drafting
- [x] (03B): Parse and validate draft answer JSON
- [x] (03C): Enforce citation presence and format
- [x] (03D): Validate citation quotes against verified evidence
- [x] (03E): Reject rejected chunk usage in citations and answer content
- [x] (03F): Preserve final output shape after draft validation

#### Batch04

- [x] (04A): Implement self-check execution
- [x] (04B): Enforce self-check failure policy
- [x] (04C): Add Agent 3 success-step logging
- [x] (04D): Add Agent 3 failed-step logging
- [x] (04E): Keep logging failures safe and visible

#### Batch05

- [ ] (05A): Add grounded answer and simple reasoning tests
- [ ] (05B): Add insufficient-evidence tests
- [ ] (05C): Add citation enforcement tests
- [ ] (05D): Add rejected chunk exclusion and unsupported claim tests
- [ ] (05E): Add provider, parsing, and logging failure tests
- [ ] (05F): Run required targeted automated validation

#### Batch06

- [ ] (06A): Run manual Agent 2 output into Agent 3 when setup is available
- [ ] (06B): Create execution report with grounded and insufficient-evidence examples
- [ ] (06C): Complete scope, secret, and architecture review

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
- reason: missing ShopAIKey API key, missing Supabase credentials, missing valid `agent_run_id`, missing Agent 2 output, missing verified chunks for grounded live validation, missing provider setup, missing manual setup, or other safe summary

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
