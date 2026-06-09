# Plan 10 - Agent 2 Evidence Verification Agent Execution Tasks

## Purpose

Create a detailed execution task file for the approved Agent 2 Evidence Verification Agent milestone. This task file guides a future Execution Agent to add backend Agent 2 schemas, verification prompts, ShopAIKey chat-completion verification, deterministic evidence safety checks, `agent_steps` logging, tests, and reporting for `docs/plans/Plan_10.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_10.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Current project context reviewed: `README.md`
- Conflict note: No architecture conflicts were found. `docs/plans/Master_Plan.md` aligns with Plan 10 on Agent 2 verifying Agent 1 candidates, returning verified and rejected chunks, setting `missing_information`, enforcing confidence between `0.0` and `1.0`, and keeping final answer generation in Agent 3. `README.md` confirms Agent 1 schemas, retrieval callable, ShopAIKey chat support, and Agent 1 step logging currently exist, while Agent 2, Agent 3, LangGraph orchestration, chat APIs, evidence APIs, and public agent log APIs remain planned. `docs/plans/Plan_10.md` remains the scope authority for this task file.

## Source Section Index

- `docs/plans/Plan_10.md` > `## 1. Goal` -> Agent 2 must review Agent 1 candidates and return the exact structured verification shape.
- `docs/plans/Plan_10.md` > `## 2. Why This Plan Exists` -> Agent 2 is the evidence gate before answer generation.
- `docs/plans/Plan_10.md` > `## 3. Scope` -> required schemas, prompt, ShopAIKey call, validation, checks, logging, and tests.
- `docs/plans/Plan_10.md` > `## 4. Out of Scope` -> prohibited final answers, citations for users, Agent 3, LangGraph, retrieval expansion, and rejected evidence usage.
- `docs/plans/Plan_10.md` > `## 5. Dependencies` -> completed Plan 9, completed Plan 2 `agent_steps`, and available ShopAIKey chat helper.
- `docs/plans/Plan_10.md` > `## 6. Required Files and Folders` -> expected Agent 2 module, prompts, schemas, ShopAIKey service, agent log service, and tests.
- `docs/plans/Plan_10.md` > `## 7. Data Model / Schema Changes` -> no database schema changes and required verification output, verified chunk, rejected chunk, and confidence shapes.
- `docs/plans/Plan_10.md` > `## 8. API Design` -> no new public endpoint and internal `run_verification_agent` callable contract.
- `docs/plans/Plan_10.md` > `## 9. Implementation Steps` -> ordered implementation requirements from schemas through logging and tests.
- `docs/plans/Plan_10.md` > `## 10. Configuration and Environment Variables` -> backend-only ShopAIKey and `SINGLE_USER_ID` variables.
- `docs/plans/Plan_10.md` > `## 11. Required Tests` -> targeted pytest command, concrete test cases, and manual check.
- `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria` -> required output shape, validation, rejection, missing information, contradiction, logging, and no-answer boundaries.
- `docs/plans/Plan_10.md` > `## 13. Failure Handling` -> empty candidates, ShopAIKey failures, invalid JSON, unknown IDs, quote mismatches, and contradictions.
- `docs/plans/Plan_10.md` > `## 14. Agent Report Requirement` -> required execution report contents and example Agent 2 output.
- `docs/plans/Plan_10.md` > `## 15. Reviewer Checklist` -> scope, tests, acceptance, secrets, architecture, invalid JSON, missing information, and rejected chunk checks.
- `docs/plans/Master_Plan.md` > `# 2. Technical Stack` -> ShopAIKey OpenAI-compatible API usage for chat completions.
- `docs/plans/Master_Plan.md` > `# 3. Authentication Policy` -> single-user policy and backend-only provider secret boundary.
- `docs/plans/Master_Plan.md` > `### 5.3 Chat With Document Page` -> eventual workflow order of Agent 1, Agent 2, and Agent 3.
- `docs/plans/Master_Plan.md` > `### 5.4 Evidence Viewer` -> accepted and rejected evidence information that later UI can inspect.
- `docs/plans/Master_Plan.md` > `### 5.5 Agent Logs / Debug Page` -> logs should include Agent 2 verified and rejected chunks.
- `docs/plans/Master_Plan.md` > `## Table: agent_steps` -> approved log fields for agent step persistence.
- `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` -> Agent 2 verification goal, rules, missing-information behavior, and output schema.
- `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure` -> expected `backend/app/agents`, services, and test locations.
- `docs/plans/Master_Plan.md` > `## Phase 7: Agent 2 Evidence Verification` -> phase-level Agent 2 tasks and acceptance criteria.
- `docs/plans/Master_Plan.md` > `## 18.1 Grounding Rule` -> final answers must use verified chunks only and must not use rejected or outside evidence.
- `README.md` > `## Overview` -> current project state and incomplete Agent 2/runtime workflow context.
- `README.md` > `## Architecture` -> current layered backend architecture and existing Agent 1/logging context.
- `README.md` > `### ShopAIKey` -> existing OpenAI-compatible chat completion helper and backend model settings.
- `README.md` > `## Configuration` -> backend `.env` loading behavior and backend-only provider settings.
- `README.md` > `Important coordination rules` -> backend-only secret boundary and validation expectations.
- `README.md` > `## Known Gaps or Unclear Areas` -> Agent 1 exists, full agent run workflow remains planned, and frontend/chat/evidence APIs are not yet implemented.

## Approved Architecture Summary

Plan 10 approves a backend-only Agent 2 Evidence Verification Agent for the single-user Document QA Agent MVP. Agent 2 is an internal callable layer, not a public API. It receives an existing `agent_run_id`, the user question, and Agent 1 candidate chunks; evaluates whether the candidates are useful and reliable evidence; returns only the exact top-level fields `verified_chunks`, `rejected_chunks`, `missing_information`, and `confidence`; and logs the verification step through `agent_steps`.

Agent 2 may use ShopAIKey chat completion for evidence verification, but all LLM output must be parsed as JSON, validated with Pydantic, and post-checked against the original Agent 1 candidates. Empty candidates must return a deterministic missing-information result without calling the LLM. Returned chunk IDs must come from the candidate set. Verified quotes must be faithful excerpts from candidate content. Duplicate chunks must not be verified twice. Clear contradictions, especially conflicting dates or mutually incompatible claims, must be detected and reflected by lower confidence and `missing_information = true` when unresolved.

The Agent 2 prompt must reject weak, loose, duplicate, unclear, contradicted, or wrong-document chunks. It must accept chunks that directly answer the question or provide necessary dates, periods, conditions, definitions, or clear support for simple reasoning. The prompt must require valid JSON only.

Agent 2 must preserve the grounding boundary for later Agent 3 work. It does not generate final answers, does not add user citation formatting, does not retrieve new chunks, does not implement LangGraph, does not create public chat/evidence/log APIs, and does not allow rejected chunks to be used as verified evidence. No database schema changes are approved by Plan 10.

## Global Implementation Rules

- Keep `docs/plans/Plan_10.md` as the source of truth for scope, output shape, validation, failure handling, tests, and out-of-scope boundaries.
- Use `docs/plans/Master_Plan.md` only to clarify the broader Agent 2 contract, `agent_steps` fields, ShopAIKey backend-only boundary, workflow position, and expected package locations.
- Use `README.md` only to understand current code state: Agent 1 schemas/callable/logging exist, ShopAIKey chat helper exists, and Agent 2/full workflow APIs are not implemented yet.
- Depend on completed Plan 9 Agent 1 candidate output; do not reimplement retrieval, hybrid scoring, graph retrieval, semantic search, Qdrant search, or rerank behavior.
- Depend on completed Plan 2 `agent_steps`; do not add or modify database migrations or table schemas.
- Reuse or extend existing backend agent schemas and agent log service patterns where they fit Plan 10.
- Keep Agent 2 internal and backend-only; do not add public API routes.
- Do not implement Agent 3 answer generation, Agent 3 self-check, citation formatting for users, LangGraph orchestration, `/api/chat/ask`, evidence APIs, agent log APIs, or frontend screens.
- Do not retrieve new chunks beyond Agent 1 candidates.
- Do not pass rejected chunks as verified evidence or mark them as answer-usable.
- Do not expose `SHOPAIKEY_API_KEY`, Supabase service role keys, Qdrant keys, backend-only settings, raw provider errors, stack traces, or private document content beyond expected verification payloads.
- Use `.env.example` for placeholder names only and never commit real secrets.
- Keep input, output, and log payloads JSON-serializable and Pydantic-validated where applicable.
- Treat provider, parsing, validation, unknown-ID, and invalid-JSON failures as controlled failures with safe `VerificationAgentError` behavior.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, schemas, settings, services, tests, and errors.
- Keep functions, services, schemas, prompts, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, service-layer, and provider-client conventions already present in the backend.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless Plan 10 explicitly requires them.
- Add comments only where they clarify a non-obvious validation, contradiction-detection, serialization, or logging decision.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Avoid adding formatters, linters, frameworks, LLM orchestration frameworks, or architecture changes outside Plan 10 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Verification Contracts, Prompt, and Backend-Only Configuration
- Batch02 - Verification Agent Callable and LLM JSON Validation
- Batch03 - Deterministic Evidence Safety Checks
- Batch04 - Agent Step Logging and Failure Handling
- Batch05 - Required Automated Tests
- Batch06 - Manual Validation, Reporting, and Scope Review

## Mandatory Batch01 - Verification Contracts, Prompt, and Backend-Only Configuration

### Goal

Prepare the Agent 2 schemas, verification prompt, and backend-only configuration boundary before runtime verification logic is added.

### Why this batch exists

Agent 2 cannot safely call an LLM or log verification results until the accepted input, exact output shape, prompt rules, confidence range, and provider settings are explicit and validated.

### Inputs / Dependencies

- `docs/plans/Plan_10.md`
- `docs/plans/Master_Plan.md`
- `README.md`
- Completed Plan 9 Agent 1 candidate schema and retrieval output
- Existing backend Pydantic and settings conventions
- Existing ShopAIKey chat helper if available

### Tasks

- [x] (01A): Extend agent schemas for Agent 2 verification
  - Source of Truth: `docs/plans/Plan_10.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_10.md` > `## 8. API Design`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.4 Agent 2 Output Schema`
  - Source Requirements:
    - Add `VerificationAgentInput`, `VerifiedChunk`, `RejectedChunk`, and `VerificationAgentOutput`.
    - Agent 2 input includes `agent_run_id`, `question`, and `candidates`.
    - Agent 2 output must contain exactly `verified_chunks`, `rejected_chunks`, `missing_information`, and `confidence`.
    - Verified chunks include chunk/document identity, file name, quote, page number, verification reason, and `supports_simple_reasoning`.
    - Rejected chunks include chunk/document identity, file name, quote, and rejection reason.
  - Details: Extend `backend/app/agents/schemas.py` using the repo's current Pydantic version and existing Agent 1 schema style. Reuse existing Agent 1 candidate schema types when practical instead of duplicating candidate fields loosely.
  - Dependencies: Completed Plan 9 Agent 1 schemas.
  - User Action: None.
  - Agent Work: Add Agent 2 Pydantic models, exports, and direct validation for required fields, stable JSON serialization, and candidate-compatible identifiers.
  - Output: Typed Agent 2 verification input and output schema models.
  - Acceptance: Agent 2 input and output models import successfully; the exact top-level output keys are enforced; empty `verified_chunks` and `rejected_chunks` lists are valid.
  - Validation: Add or run targeted schema validation tests once Batch05 tests exist; run a direct Pydantic import/smoke check if tests are not present yet.
  - Blocked Condition: None.
  - Files: `backend/app/agents/schemas.py`, `backend/app/agents/__init__.py`

- [x] (01B): Enforce confidence validation behavior
  - Source of Truth: `docs/plans/Plan_10.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.4 Agent 2 Output Schema`
  - Source Requirements:
    - `confidence` type is `float`.
    - `confidence` range is `0.0` to `1.0`.
    - Add strict validators that clamp or reject invalid confidence values outside `0.0` to `1.0`.
  - Details: Prefer rejecting out-of-range confidence unless the existing backend schema style already uses clamping for bounded scores. Document the chosen behavior in tests and keep it consistent across Agent 2 output validation.
  - Dependencies: (01A).
  - User Action: None.
  - Agent Work: Add confidence validator constraints and tests for lower bound, upper bound, and invalid values.
  - Output: Bounded, validated `confidence` field behavior.
  - Acceptance: `0.0`, values between `0.0` and `1.0`, and `1.0` validate; out-of-range values are safely handled according to the chosen validator behavior.
  - Validation: Targeted schema tests in `backend/tests/test_verification_agent.py`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/schemas.py`, `backend/tests/test_verification_agent.py`

- [x] (01C): Add reusable verification prompt rules
  - Source of Truth: `docs/plans/Plan_10.md` > `## 3. Scope`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.2 Verification Rules`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.3 Missing Information Rule`
  - Source Requirements:
    - Add a verification prompt in `backend/app/agents/prompts.py`.
    - Reject loosely related, duplicate, contradicted, unclear, or wrong-document chunks.
    - Accept chunks that directly answer or provide necessary date, period, condition, definition, ambiguity-resolution, or simple-reasoning evidence.
    - Return only valid JSON in the required shape.
  - Details: Create a concise prompt constant or builder compatible with existing prompt organization. Include explicit JSON-only instructions and explain that the model must evaluate only the provided candidates.
  - Dependencies: (01A).
  - User Action: None.
  - Agent Work: Add prompt text and any small helper needed to build the verification instruction without hardcoding secrets or runtime data in the prompt module.
  - Output: Reusable Agent 2 verification prompt.
  - Acceptance: Prompt includes all Plan 10 accept/reject/missing-information rules and does not instruct the model to generate a final answer or retrieve new chunks.
  - Validation: Prompt-focused unit test or assertion that the prompt contains key rules and required output keys.
  - Blocked Condition: None.
  - Files: `backend/app/agents/prompts.py`, `backend/tests/test_verification_agent.py`

- [x] (01D): Confirm ShopAIKey chat configuration boundary
  - Source of Truth: `docs/plans/Plan_10.md` > `## 5. Dependencies`; `docs/plans/Plan_10.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_10.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Master_Plan.md` > `# 2. Technical Stack`; `docs/plans/Master_Plan.md` > `# 3. Authentication Policy`; `README.md` > `### ShopAIKey`; `README.md` > `## Configuration`
  - Source Requirements:
    - Reuse or add ShopAIKey chat completion helper.
    - `SHOPAIKEY_API_KEY`, `SHOPAIKEY_BASE_URL`, and `SHOPAIKEY_CHAT_MODEL` are backend-only.
    - `SINGLE_USER_ID` indirectly scopes retrieved candidate chunks.
    - Real secret values must not be committed.
  - Details: Inspect the existing `shopaikey_service.py` chat helper and backend settings. Only add missing placeholders or required-setting checks if needed for Agent 2. Do not add frontend variables.
  - Dependencies: Existing ShopAIKey service from Plan 5 or Plan 7, if present.
  - User Action: User must provide real ShopAIKey values in `backend/.env` for live provider validation.
  - Agent Work: Reuse existing chat helper, or add a focused chat helper if missing; keep model and base URL environment-driven; update `.env.example` only with safe placeholder names if missing.
  - Output: Confirmed backend-only ShopAIKey chat configuration for Agent 2.
  - Acceptance: Agent 2 can resolve required chat settings through backend configuration; frontend code does not contain backend-only ShopAIKey settings or secrets.
  - Validation: Backend settings import test; mocked ShopAIKey chat test; optional frontend scan for `SHOPAIKEY_` names.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live ShopAIKey validation when real backend credentials are missing.
  - Files: `backend/app/services/shopaikey_service.py`, `backend/app/core/config.py`, `backend/.env.example`, frontend files only for inspection

### Files or Modules Likely Created or Updated

- `backend/app/agents/schemas.py`
- `backend/app/agents/prompts.py`
- `backend/app/agents/__init__.py`
- `backend/app/services/shopaikey_service.py` only if the chat helper is missing or incomplete
- `backend/app/core/config.py` only if required settings behavior is missing
- `backend/.env.example` only for safe placeholders if missing
- `backend/tests/test_verification_agent.py`

### Required Outputs / Artifacts

- Agent 2 Pydantic input and output schemas.
- Confidence validation behavior.
- Reusable Agent 2 verification prompt.
- Confirmed backend-only ShopAIKey chat configuration boundary.

### Acceptance Criteria

- Agent 2 schemas match Plan 10 required input and output shape.
- `confidence` is constrained to `0.0` through `1.0`.
- Verification prompt includes the required accept, reject, missing-information, and JSON-only rules.
- ShopAIKey chat settings remain backend-only and environment-driven.
- No runtime verification logic is implemented before schemas and prompt are ready.

### Required Tests or Validations

- Backend import check for `app.agents.schemas` and `app.agents.prompts`.
- Direct Pydantic schema validation smoke checks or targeted schema tests.
- Prompt-content assertions for required output keys and rules.
- Backend settings import/config validation.
- Frontend scan for `SHOPAIKEY_` names if configuration is touched.

### Explicit Non-Goals

- Do not implement `run_verification_agent` in this batch.
- Do not call ShopAIKey in this batch except through an existing mocked/unit path.
- Do not add public API routes.
- Do not implement Agent 3, LangGraph, final answers, or citation formatting.

## Mandatory Batch02 - Verification Agent Callable and LLM JSON Validation

### Goal

Implement the backend-only `run_verification_agent` callable that validates input, handles empty candidate input deterministically, calls ShopAIKey for non-empty candidate verification, parses JSON, and validates the structured output.

### Why this batch exists

The evidence verification contract must be executable and safe against malformed LLM/provider output before deterministic post-processing and logging are finalized.

### Inputs / Dependencies

- Batch01 schemas, prompt, and configuration boundary
- Completed Plan 9 Agent 1 output shape
- Existing ShopAIKey chat helper
- `docs/plans/Plan_10.md`
- `docs/plans/Master_Plan.md` Agent 2 output schema

### Tasks

- [ ] (02A): Create verification agent module and controlled error type
  - Source of Truth: `docs/plans/Plan_10.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_10.md` > `## 8. API Design`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure`
  - Source Requirements:
    - Add `backend/app/agents/verification_agent.py`.
    - Expose `run_verification_agent(input: VerificationAgentInput) -> VerificationAgentOutput`.
    - Raise `VerificationAgentError` for LLM or validation failures.
    - Do not add a public API endpoint.
  - Details: Follow the style of the existing Agent 1 retrieval callable. Keep input validation, provider call, post-processing, and logging readable and easy to test.
  - Dependencies: Batch01 schemas.
  - User Action: None.
  - Agent Work: Create module, error class, public callable, and imports/exports needed for tests and future orchestration.
  - Output: Importable Agent 2 verification module.
  - Acceptance: `run_verification_agent` can be imported and accepts Pydantic input or data compatible with `VerificationAgentInput`; no new API route is registered.
  - Validation: Targeted import test and direct callable smoke test with empty candidates.
  - Blocked Condition: None.
  - Files: `backend/app/agents/verification_agent.py`, `backend/app/agents/__init__.py`

- [ ] (02B): Implement deterministic empty-candidates behavior
  - Source of Truth: `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.3 Missing Information Rule`
  - Source Requirements:
    - If `candidates` is empty, return no verified chunks, no rejected chunks, `missing_information = true`, and `confidence = 0.0`.
    - Do not call the LLM for empty candidates.
  - Details: Short-circuit after input validation. This path should later log a successful Agent 2 step once Batch04 logging is connected.
  - Dependencies: (02A), Batch01 schemas.
  - User Action: None.
  - Agent Work: Add empty-list branch and ensure the output is constructed through `VerificationAgentOutput`.
  - Output: Safe missing-information result for empty candidates.
  - Acceptance: Empty candidates return exactly the required shape with `missing_information = true` and `confidence = 0.0`; mocked ShopAIKey client is not called.
  - Validation: Unit test in `backend/tests/test_verification_agent.py`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`

- [ ] (02C): Build compact evidence payload and call ShopAIKey chat
  - Source of Truth: `docs/plans/Plan_10.md` > `## 3. Scope`; `docs/plans/Plan_10.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 10. Configuration and Environment Variables`; `README.md` > `### ShopAIKey`
  - Source Requirements:
    - Prepare a compact evidence list for the LLM.
    - Evidence list contains chunk ID, file name, page number, section title, score, and content.
    - Call ShopAIKey chat completion with low temperature if supported.
  - Details: Keep the prompt payload compact but complete enough for verification. Do not include unneeded secrets, internal stack traces, or unrelated metadata. Preserve candidate content needed for quote validation.
  - Dependencies: (02A), (02B), Batch01 prompt and settings.
  - User Action: User must provide real ShopAIKey settings for live provider validation; mocked tests do not require real credentials.
  - Agent Work: Add payload builder, call the chat helper, pass model/settings through existing service conventions, and set low temperature only if the helper supports it.
  - Output: ShopAIKey-backed verification request path for non-empty candidates.
  - Acceptance: Non-empty candidates produce a single chat-completion request with the verification prompt and compact evidence payload; provider details remain backend-only.
  - Validation: Mocked test asserts prompt/payload shape and chat helper invocation without making live network calls.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live ShopAIKey provider validation when real credentials are missing.
  - Files: `backend/app/agents/verification_agent.py`, `backend/app/services/shopaikey_service.py`, `backend/tests/test_verification_agent.py`

- [ ] (02D): Parse and validate LLM JSON response
  - Source of Truth: `docs/plans/Plan_10.md` > `## 3. Scope`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Parse response JSON.
    - Validate output with Pydantic.
    - Invalid LLM JSON is rejected and logged later.
    - VerificationAgentError is raised for LLM or validation failures.
  - Details: Add strict JSON parsing that does not accept natural-language wrappers as successful output unless the implementation explicitly extracts a valid JSON object safely. Validate through `VerificationAgentOutput` before any success result is returned.
  - Dependencies: (02C), Batch01 schemas.
  - User Action: None.
  - Agent Work: Implement JSON parsing, Pydantic validation, and controlled error wrapping for invalid JSON or schema mismatch.
  - Output: Validated preliminary Agent 2 output from LLM response.
  - Acceptance: Valid JSON in the required shape passes; invalid JSON and missing/extra malformed fields raise `VerificationAgentError` and do not return partial success.
  - Validation: Unit tests for valid JSON, invalid JSON, schema mismatch, and out-of-range confidence.
  - Blocked Condition: None.
  - Files: `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`

### Files or Modules Likely Created or Updated

- `backend/app/agents/verification_agent.py`
- `backend/app/agents/__init__.py`
- `backend/app/services/shopaikey_service.py` only if existing chat helper must be extended
- `backend/tests/test_verification_agent.py`

### Required Outputs / Artifacts

- Importable `run_verification_agent`.
- Controlled `VerificationAgentError`.
- Empty-candidate deterministic result.
- Mockable ShopAIKey verification call.
- JSON parsing and Pydantic validation path.

### Acceptance Criteria

- No public endpoints are added.
- Empty candidates do not call ShopAIKey.
- Non-empty candidates call ShopAIKey chat completion through backend service code.
- LLM output is parsed as JSON and validated before use.
- Provider and validation failures raise controlled errors.

### Required Tests or Validations

- Import test for `app.agents.verification_agent`.
- Empty candidates test proving no LLM call.
- Mocked successful LLM JSON response test.
- Invalid JSON test.
- Schema mismatch/confidence validation tests.

### Explicit Non-Goals

- Do not finalize deterministic contradiction or duplicate filtering in this batch unless needed to keep tests isolated.
- Do not implement Agent 3 answer generation.
- Do not add LangGraph workflow or public chat APIs.
- Do not perform live ShopAIKey calls in automated tests.

## Mandatory Batch03 - Deterministic Evidence Safety Checks

### Goal

Post-process the LLM verification result so only candidate-backed, quote-faithful, non-duplicated, and contradiction-aware evidence can appear in the final Agent 2 success output.

### Why this batch exists

The final answer must rely only on verified chunks. Agent 2 must not trust LLM output blindly when it invents chunk IDs, fabricates quotes, duplicates evidence, or misses obvious contradictions.

### Inputs / Dependencies

- Batch02 preliminary LLM verification output
- Original Agent 1 candidates
- Plan 10 validation and failure-handling rules
- Master Plan Agent 2 verification and missing-information rules

### Tasks

- [ ] (03A): Reject or fail unknown returned chunk IDs
  - Source of Truth: `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`; `docs/plans/Plan_10.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Confirm every returned `chunk_id` exists in Agent 1 candidates.
    - LLM returns unknown `chunk_id` -> validation failure.
    - Agent 2 cannot verify chunks not returned by Agent 1.
  - Details: Build a candidate lookup by `chunk_id`. Treat any unknown verified or rejected chunk ID as invalid verification output that raises `VerificationAgentError` after Batch04 failure logging is connected.
  - Dependencies: Batch02 validated preliminary output.
  - User Action: None.
  - Agent Work: Add candidate membership validation for verified and rejected chunks and tests for unknown IDs.
  - Output: Candidate-bound verification result.
  - Acceptance: Unknown IDs never appear in successful Agent 2 output; unknown-ID output triggers controlled validation failure.
  - Validation: Unit test for unknown `chunk_id` in LLM response.
  - Blocked Condition: None.
  - Files: `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`

- [ ] (03B): Validate verified and rejected quotes against source candidate content
  - Source of Truth: `docs/plans/Plan_10.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Ensure quotes are substrings or faithful excerpts from candidate content.
    - Quotes not found in source content must be rejected or corrected to a source excerpt.
  - Details: Prefer simple deterministic substring checks with light whitespace normalization. If a verified quote is not faithful and cannot be safely corrected, remove it from `verified_chunks` and add or preserve a rejected chunk with a safe rejection reason. Do not fabricate quotes.
  - Dependencies: (03A).
  - User Action: None.
  - Agent Work: Add quote normalization/validation helper and tests for faithful quote, whitespace variation, and fabricated quote handling.
  - Output: Quote-faithful verified and rejected evidence.
  - Acceptance: Verified chunks contain only source-backed quotes; fabricated or untraceable quotes are not verified.
  - Validation: Unit tests for quote validation and rejection/correction behavior.
  - Blocked Condition: None.
  - Files: `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`

- [ ] (03C): Add deterministic duplicate filtering
  - Source of Truth: `docs/plans/Plan_10.md` > `## 3. Scope`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.2 Verification Rules`
  - Source Requirements:
    - Implement deterministic duplicate filtering so repeated chunks are not verified twice.
    - Reject chunks that are duplicated.
  - Details: De-duplicate verified chunks by `chunk_id` first. If duplicate content appears under different chunk IDs, apply a conservative content-normalized duplicate check where practical and keep the stronger or first clearly useful evidence. Record duplicate handling in rejection reasons when it affects output.
  - Dependencies: (03A), (03B).
  - User Action: None.
  - Agent Work: Add duplicate filtering helper and tests for repeated verified chunks.
  - Output: No duplicate verified chunks in Agent 2 success output.
  - Acceptance: A repeated `chunk_id` appears at most once in `verified_chunks`; duplicate evidence is rejected or removed with a reason where possible.
  - Validation: Unit tests for duplicate verified chunks.
  - Blocked Condition: None.
  - Files: `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`

- [ ] (03D): Add basic contradiction and missing-information adjustment
  - Source of Truth: `docs/plans/Plan_10.md` > `## 3. Scope`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.3 Missing Information Rule`
  - Source Requirements:
    - Add basic contradiction check for conflicting dates or mutually incompatible claims when clear from verified chunks.
    - If no verified chunk remains, set `missing_information = true`.
    - Contradictory verified chunks must reduce confidence and set missing information if unresolved.
    - Verified chunks conflict on a date -> `missing_information = true` or lower confidence with contradiction reason.
  - Details: Implement a conservative deterministic check for obvious date conflicts and mutually incompatible short claims. Do not attempt broad natural-language theorem proving. If conflict is unresolved, lower confidence, mark `missing_information = true`, and include safe contradiction wording in a rejection or verification reason.
  - Dependencies: (03B), (03C).
  - User Action: None.
  - Agent Work: Add contradiction helper, no-verified-chunks adjustment, confidence bounds preservation, and tests for date conflict.
  - Output: Contradiction-aware Agent 2 output with safe missing-information behavior.
  - Acceptance: No verified chunks results in `missing_information = true`; clear contradictions are detected or reported; confidence remains in range.
  - Validation: Unit tests for no verified chunks after filtering and conflicting date evidence.
  - Blocked Condition: None.
  - Files: `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`

- [ ] (03E): Preserve final output shape after post-processing
  - Source of Truth: `docs/plans/Plan_10.md` > `## 1. Goal`; `docs/plans/Plan_10.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.4 Agent 2 Output Schema`
  - Source Requirements:
    - Agent 2 returns exactly `verified_chunks`, `rejected_chunks`, `missing_information`, and `confidence`.
    - Agent 2 output is Pydantic-validated.
    - `confidence` is between `0.0` and `1.0`.
  - Details: Validate the final post-processed result with `VerificationAgentOutput` immediately before returning it. Ensure helper metadata or internal reasons do not add extra top-level keys.
  - Dependencies: (03A), (03B), (03C), (03D).
  - User Action: None.
  - Agent Work: Add final validation pass and tests for exact keys after post-processing.
  - Output: Final schema-valid Agent 2 output.
  - Acceptance: Returned object/dict serializes to exactly the required top-level shape.
  - Validation: Unit test for exact serialized output keys.
  - Blocked Condition: None.
  - Files: `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`

### Files or Modules Likely Created or Updated

- `backend/app/agents/verification_agent.py`
- `backend/app/agents/schemas.py` only if schema refinements are needed
- `backend/tests/test_verification_agent.py`

### Required Outputs / Artifacts

- Candidate membership validation.
- Quote faithfulness validation.
- Duplicate verified-chunk filtering.
- Basic contradiction detection.
- Final post-processed Pydantic validation.

### Acceptance Criteria

- Unknown chunk IDs are not accepted.
- Fabricated or untraceable verified quotes are not accepted.
- Duplicate verified chunks are filtered.
- Missing evidence sets `missing_information = true`.
- Clear contradictions are detected or reflected safely.
- Final output still has exactly the Plan 10 shape.

### Required Tests or Validations

- Unknown chunk ID validation failure test.
- Quote mismatch rejection/correction test.
- Duplicate filtering test.
- Conflicting date or incompatible claim test.
- No-verified-chunks missing-information test.
- Exact output key test after post-processing.

### Explicit Non-Goals

- Do not build a full natural-language contradiction engine.
- Do not retrieve additional chunks to resolve conflicts.
- Do not generate final answers or user-facing citations.
- Do not add new database schema fields for contradiction metadata.

## Mandatory Batch04 - Agent Step Logging and Failure Handling

### Goal

Persist Agent 2 success and failure steps to `agent_steps` with safe payloads and controlled error behavior.

### Why this batch exists

Agent 2 must be auditable. Future users and reviewers need to inspect what candidates were checked, which chunks were verified or rejected, and why failures occurred without exposing secrets or fake success.

### Inputs / Dependencies

- Batch02 verification callable
- Batch03 final post-processing behavior
- Existing Plan 2 `agent_steps` table
- Existing `agent_log_service.py` patterns from Plan 9
- `docs/plans/Plan_10.md`
- `docs/plans/Master_Plan.md` `agent_steps` contract

### Tasks

- [ ] (04A): Add Agent 2 success-step logging
  - Source of Truth: `docs/plans/Plan_10.md` > `## 3. Scope`; `docs/plans/Plan_10.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## Table: agent_steps`; `docs/plans/Master_Plan.md` > `### 5.5 Agent Logs / Debug Page`
  - Source Requirements:
    - Log Agent 2 input/output to `agent_steps`.
    - Agent 2 logs success steps.
    - Logs should include Agent 2 verified chunks and Agent 2 rejected chunks.
  - Details: Use a consistent step name such as `agent_2_verification` and agent name such as `verification_agent`, unless existing log service conventions require a different naming pattern. Include safe input and output JSON payloads.
  - Dependencies: Batch02, Batch03, existing agent log service.
  - User Action: User must provide live Supabase setup and a valid `agent_run_id` for live persistence validation.
  - Agent Work: Extend or reuse `agent_log_service.py` so successful Agent 2 runs, including empty-candidate success, write a success log.
  - Output: Agent 2 success `agent_steps` persistence path.
  - Acceptance: Successful verification writes one safe success log when logging dependencies are available; log output includes final verified/rejected/missing/confidence result.
  - Validation: Mocked unit test for success log payload.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live Supabase validation when real Supabase settings, applied schema, or valid `agent_run_id` are missing.
  - Files: `backend/app/services/agent_log_service.py`, `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`, `backend/tests/test_agent_log_service.py` if needed

- [ ] (04B): Add Agent 2 failed-step logging
  - Source of Truth: `docs/plans/Plan_10.md` > `## 8. API Design`; `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## Table: agent_steps`
  - Source Requirements:
    - Log Agent 2 step with status `failed`.
    - ShopAIKey failure logs a failed Agent 2 step and raises `VerificationAgentError`.
    - Invalid LLM JSON is rejected and logged.
    - Unknown chunk IDs in LLM output cause validation failure.
  - Details: Failed logs should include safe input and a safe error summary, not raw provider responses, secrets, stack traces, or excessive private document content. Preserve the original `VerificationAgentError` semantics after attempting to log.
  - Dependencies: (04A), Batch02, Batch03.
  - User Action: User must provide live Supabase setup and a valid `agent_run_id` for live failed-log validation.
  - Agent Work: Wrap provider, JSON parsing, schema validation, unknown-ID, and post-processing validation failures with failed-step logging and controlled re-raise.
  - Output: Agent 2 failed `agent_steps` persistence path.
  - Acceptance: Provider errors, invalid JSON, schema mismatch, and unknown IDs create failed log attempts and raise `VerificationAgentError`.
  - Validation: Mocked unit tests for invalid JSON failed log, provider failure failed log, and unknown-ID failed log.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live Supabase validation when real Supabase settings, applied schema, or valid `agent_run_id` are missing.
  - Files: `backend/app/services/agent_log_service.py`, `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`, `backend/tests/test_agent_log_service.py` if needed

- [ ] (04C): Keep log failures safe and visible
  - Source of Truth: `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`; `docs/plans/Plan_10.md` > `## 15. Reviewer Checklist`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - Agent 2 logs success and failure steps.
    - No hardcoded secrets.
    - No fake success.
    - Backend-only secrets must remain out of frontend code.
  - Details: If log insertion itself fails, expose that condition through existing safe logging/error patterns without converting a failed verification into fake success. Do not leak credentials or raw SQL/provider internals.
  - Dependencies: (04A), (04B), existing agent log service behavior.
  - User Action: None for mocked tests; live log validation requires user-provided setup.
  - Agent Work: Reuse existing log failure handling patterns from Agent 1 where possible, add tests for log insertion failure if existing coverage does not apply to Agent 2.
  - Output: Honest log failure behavior.
  - Acceptance: Verification success is not claimed if required validation failed; log failures are visible in tests or safe warnings; secrets are not logged.
  - Validation: Mocked log insertion failure test or existing service-level coverage updated for Agent 2.
  - Blocked Condition: None for automated mocked validation; `BLOCKED_BY_USER_ACTION` only for live Supabase validation.
  - Files: `backend/app/services/agent_log_service.py`, `backend/app/agents/verification_agent.py`, `backend/tests/test_verification_agent.py`, `backend/tests/test_agent_log_service.py` if needed

### Files or Modules Likely Created or Updated

- `backend/app/services/agent_log_service.py`
- `backend/app/agents/verification_agent.py`
- `backend/tests/test_verification_agent.py`
- `backend/tests/test_agent_log_service.py` if service coverage needs Agent 2 cases

### Required Outputs / Artifacts

- Success log path for Agent 2.
- Failed log path for Agent 2.
- Safe error summaries for provider, JSON, schema, unknown-ID, quote, contradiction, and log failures.
- Mocked logging tests.

### Acceptance Criteria

- Agent 2 logs successful verification output.
- Agent 2 logs failed verification attempts when possible.
- Failure paths raise `VerificationAgentError`.
- Log payloads do not expose provider keys, service role keys, Qdrant keys, stack traces, or raw private data beyond expected safe verification payloads.
- Log insertion failures do not produce fake success.

### Required Tests or Validations

- Mocked success log test.
- Mocked failed log test for invalid JSON.
- Mocked failed log test for ShopAIKey/provider failure.
- Mocked failed log test for unknown chunk ID or validation failure.
- Log insertion failure test if not already covered by reusable service behavior.

### Explicit Non-Goals

- Do not create a public agent log API.
- Do not add frontend log viewer screens.
- Do not modify `agent_steps` table schema.
- Do not fabricate live Supabase validation.

## Mandatory Batch05 - Required Automated Tests

### Goal

Add and run targeted automated tests proving Agent 2 schemas, prompt behavior, LLM validation, deterministic checks, failure handling, and logging meet Plan 10.

### Why this batch exists

Agent 2 is a safety gate. The required behavior must be verified through tests before manual validation or execution reporting can claim the milestone is complete.

### Inputs / Dependencies

- Batch01 through Batch04 implementation
- Existing backend pytest setup
- `docs/plans/Plan_10.md` required test list
- Existing mocked provider/logging test patterns

### Tasks

- [ ] (05A): Add accepted and rejected evidence tests
  - Source of Truth: `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.2 Verification Rules`
  - Source Requirements:
    - Candidate directly states the answer -> appears in `verified_chunks`.
    - Candidate is loosely related -> appears in `rejected_chunks`.
    - Irrelevant chunks are rejected with reasons.
  - Details: Use mocked ShopAIKey responses and candidate fixtures that resemble Agent 1 output. Keep assertions on final post-processed output, not just raw LLM output.
  - Dependencies: Batch02, Batch03.
  - User Action: None.
  - Agent Work: Add tests for direct evidence acceptance and weak evidence rejection.
  - Output: Automated coverage for core accept/reject behavior.
  - Acceptance: Tests fail without correct verified/rejected chunk handling and pass with Plan 10 behavior.
  - Validation: `cd backend` then `pytest tests/test_verification_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_verification_agent.py`

- [ ] (05B): Add missing-information and empty-candidate tests
  - Source of Truth: `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.3 Missing Information Rule`
  - Source Requirements:
    - No candidates -> `missing_information = true`.
    - If no verified chunk remains, set `missing_information = true`.
    - Empty candidates return confidence `0.0`.
  - Details: Include tests proving empty input does not call ShopAIKey and no verified chunks after filtering still sets missing information.
  - Dependencies: Batch02, Batch03.
  - User Action: None.
  - Agent Work: Add empty-candidate and no-verified-result tests.
  - Output: Automated missing-information coverage.
  - Acceptance: Missing-information behavior is deterministic and safe.
  - Validation: `cd backend` then `pytest tests/test_verification_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_verification_agent.py`

- [ ] (05C): Add invalid JSON, unknown ID, and provider failure tests
  - Source of Truth: `docs/plans/Plan_10.md` > `## 8. API Design`; `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`
  - Source Requirements:
    - LLM returns invalid JSON -> `VerificationAgentError` and failed log.
    - LLM returns unknown `chunk_id` -> validation failure.
    - ShopAIKey failure logs a failed Agent 2 step and raises `VerificationAgentError`.
  - Details: Mock the chat helper and log service so these tests do not depend on live provider or database setup.
  - Dependencies: Batch02, Batch03, Batch04.
  - User Action: None.
  - Agent Work: Add tests for invalid JSON, unknown chunk ID, and provider failure with failed-log assertions.
  - Output: Automated failure-handling coverage.
  - Acceptance: Each failure path raises controlled error and attempts safe failed-step logging.
  - Validation: `cd backend` then `pytest tests/test_verification_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_verification_agent.py`

- [ ] (05D): Add contradiction, quote, duplicate, and confidence tests
  - Source of Truth: `docs/plans/Plan_10.md` > `## 9. Implementation Steps`; `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Verified chunks conflict on a date -> `missing_information = true` or lower confidence with contradiction reason.
    - Quotes not found in source content must be rejected or corrected to a source excerpt.
    - Duplicate chunks are not verified twice.
    - `confidence` is between `0.0` and `1.0`.
  - Details: Keep contradiction tests focused on clear, deterministic conflicts such as two incompatible date values. Avoid brittle broad-language assumptions.
  - Dependencies: Batch03.
  - User Action: None.
  - Agent Work: Add tests for contradiction behavior, quote validation, duplicate filtering, and confidence bounds.
  - Output: Automated deterministic safety-check coverage.
  - Acceptance: Tests prove final Agent 2 output is safe after LLM output is post-processed.
  - Validation: `cd backend` then `pytest tests/test_verification_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_verification_agent.py`

- [ ] (05E): Run required targeted automated validation
  - Source of Truth: `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_10.md` > `## 15. Reviewer Checklist`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - Run `cd backend` then `pytest tests/test_verification_agent.py -v`.
    - Tests were actually run.
    - Acceptance criteria passed.
    - No fake success.
  - Details: Run the exact targeted pytest command. If broader agent log service tests were changed, run those too. Report failures honestly and do not mark the batch complete until required tests pass or a blocked status is documented.
  - Dependencies: (05A), (05B), (05C), (05D).
  - User Action: None.
  - Agent Work: Execute targeted tests, capture results, and fix in-scope failures.
  - Output: Test result evidence for Plan 10.
  - Acceptance: Required tests pass, or failures are documented with remaining in-scope work.
  - Validation: `cd backend` then `pytest tests/test_verification_agent.py -v`; plus `pytest tests/test_agent_log_service.py -v` if that file changed.
  - Blocked Condition: None unless local environment lacks required test dependencies; report dependency issue safely instead of claiming success.
  - Files: `backend/tests/test_verification_agent.py`, `backend/tests/test_agent_log_service.py` if changed

### Files or Modules Likely Created or Updated

- `backend/tests/test_verification_agent.py`
- `backend/tests/test_agent_log_service.py` if logging service behavior is extended
- Runtime files from earlier batches only as needed to make tests pass

### Required Outputs / Artifacts

- Automated test coverage for accepted evidence.
- Automated test coverage for rejected evidence.
- Automated test coverage for empty and missing-information behavior.
- Automated test coverage for invalid JSON, unknown IDs, provider failure, logging failure, quote validation, duplicates, contradictions, and confidence bounds.
- Required pytest command output summarized in the execution report.

### Acceptance Criteria

- `backend/tests/test_verification_agent.py` exists and covers all Plan 10 required cases.
- Targeted pytest command was run.
- Tests pass before completion is claimed.
- Mocked tests avoid live ShopAIKey and Supabase dependency unless explicitly performing manual/live validation.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_verification_agent.py -v`
- `pytest tests/test_agent_log_service.py -v` if agent log service tests changed

### Explicit Non-Goals

- Do not rely on live ShopAIKey calls for automated tests.
- Do not fabricate passing test output.
- Do not broaden tests into Agent 3, LangGraph, public chat APIs, or frontend screens.

## Mandatory Batch06 - Manual Validation, Reporting, and Scope Review

### Goal

Run the required manual Agent 1 to Agent 2 smoke check when setup is available, write the execution report, and confirm Plan 10 scope boundaries before reviewer handoff.

### Why this batch exists

Automated tests prove deterministic behavior, but Plan 10 also requires a manual sample check and a clear report of files, commands, test results, known issues, out-of-scope work, and example output.

### Inputs / Dependencies

- Batch01 through Batch05 completed or safely blocked
- Existing processed/indexed/graph-built document data if available
- Valid `agent_run_id` and Agent 1 output if live manual smoke check is attempted
- Real backend `.env` values for ShopAIKey and Supabase if live provider/log checks are attempted
- `docs/plans/Plan_10.md`

### Tasks

- [ ] (06A): Run manual Agent 1 output into Agent 2 when setup is available
  - Source of Truth: `docs/plans/Plan_10.md` > `## 11. Required Tests`; `docs/plans/Plan_10.md` > `## 13. Failure Handling`; `README.md` > `## Configuration`; `README.md` > `## Known Gaps or Unclear Areas`
  - Source Requirements:
    - Run Agent 1 for the sample question.
    - Pass Agent 1 output into Agent 2.
    - Confirm Agent 2 verifies chunks with start date, probation duration, and official work condition.
    - Missing credentials or setup must be reported as blocked, not complete.
  - Details: Use existing backend scripts, tests, or direct callable invocation patterns. If no valid processed/indexed document, `agent_run_id`, Supabase setup, or ShopAIKey credentials are available, report `BLOCKED_BY_USER_ACTION` for live manual validation and rely on automated mocked tests for code behavior.
  - Dependencies: Batch05 passing tests.
  - User Action: User must provide real backend `.env` settings, a valid existing `agent_run_id`, and sample processed/indexed document data for live manual validation.
  - Agent Work: Attempt manual smoke check only when setup is available; otherwise record exact safe blocking reason.
  - Output: Manual Agent 2 validation result or blocked status.
  - Acceptance: Agent 2 verifies relevant sample evidence and rejects irrelevant evidence, or manual validation is explicitly blocked with a safe setup reason.
  - Validation: Direct callable smoke check or documented `BLOCKED_BY_USER_ACTION`.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if required ShopAIKey credentials, Supabase settings, valid `agent_run_id`, or sample processed/indexed candidate data are missing.
  - Files: No runtime files expected; execution report records result

- [ ] (06B): Create execution report with example Agent 2 output
  - Source of Truth: `docs/plans/Plan_10.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_10.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Report files created.
    - Report files modified.
    - Report commands run.
    - Report test results.
    - Report known issues.
    - Report intentionally not implemented out-of-scope work.
    - Include an example Agent 2 output containing verified and rejected chunks.
  - Details: Create the standard report artifact for Plan 10 using the repo's existing reports pattern. Keep example output safe and synthetic if needed; do not include secrets or private raw document content.
  - Dependencies: Batch05, (06A).
  - User Action: None.
  - Agent Work: Write report with accurate commands/results and a safe example output.
  - Output: Plan 10 execution report.
  - Acceptance: Report includes all Plan 10 required sections and does not claim blocked live validation as completed.
  - Validation: Read report before handoff and confirm every required report item is present.
  - Blocked Condition: None.
  - Files: `docs/reports/report_10_execute_agent.md`

- [ ] (06C): Complete scope, secret, and architecture review
  - Source of Truth: `docs/plans/Plan_10.md` > `## 4. Out of Scope`; `docs/plans/Plan_10.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_10.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 18.1 Grounding Rule`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - Scope was followed.
    - Out-of-scope work was not added.
    - No hardcoded secrets.
    - Architecture still matches `docs/plans/Master_Plan.md`.
    - Rejected chunks are not passed as verified evidence.
    - Agent 2 does not generate final answers.
  - Details: Inspect changed files and tests for scope boundaries. Confirm no API route, frontend screen, Agent 3 code, LangGraph workflow, final answer generation, or committed secret was added.
  - Dependencies: Batch05, (06B).
  - User Action: None.
  - Agent Work: Run focused scans or code review checks, update report with scope findings, and update this task tracker only after validations pass or blocks are recorded.
  - Output: Reviewer-ready scope boundary confirmation.
  - Acceptance: Scope review confirms Plan 10 boundaries or documents exact deviations requiring fixes before reviewer handoff.
  - Validation: Git diff review, secret-name scan, and targeted search for out-of-scope route/workflow/Agent 3 additions.
  - Blocked Condition: None.
  - Files: `docs/reports/report_10_execute_agent.md`, `docs/tasks/task_10.md` progress tracker during execution

### Files or Modules Likely Created or Updated

- `docs/reports/report_10_execute_agent.md`
- `docs/tasks/task_10.md` progress tracker during execution
- No runtime files unless test or scope feedback from earlier batches requires fixes

### Required Outputs / Artifacts

- Manual Agent 2 validation result or blocked status.
- Execution report for Plan 10 reviewer handoff.
- Example Agent 2 output with verified and rejected chunks.
- Scope, secret, and architecture boundary confirmation.

### Acceptance Criteria

- Automated tests were run and reported.
- Manual check was completed or safely blocked.
- Success and failure logging behavior is reported honestly.
- Out-of-scope work was not implemented.
- No secrets or fake success appear in the report.
- Example Agent 2 output is included.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_verification_agent.py -v`
- Manual Agent 1 -> Agent 2 smoke check when setup is available.
- Safe `agent_steps` row verification when live Supabase setup is available.
- Scope and secret inspection.

### Explicit Non-Goals

- Do not fabricate live provider, database, or document validation.
- Do not create real provider keys, Supabase projects, Qdrant collections, documents, or agent runs on behalf of the user unless explicitly requested.
- Do not implement public chat, evidence, or agent log screens.
- Do not implement Agent 3, LangGraph, or final answer generation.

## Optional Future Tracks

No optional future tracks are part of the mandatory Plan 10 batch chain.

Agent 3 answer generation, Agent 3 self-check, LangGraph orchestration, `/api/chat/ask`, citation formatting for users, public evidence APIs, public agent log APIs, frontend evidence display, and final answer generation remain future work outside this task file unless a later approved plan explicitly includes them.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05
- Batch05 -> Batch06

Optional future tracks are outside the mandatory dependency chain.

## Global Verification Checklist

- [ ] `docs/plans/Plan_10.md` remained the scope authority.
- [ ] No database schema changes were added.
- [ ] `backend/app/agents/schemas.py` defines Agent 2 input and output schemas.
- [ ] Agent 2 output contains exactly `verified_chunks`, `rejected_chunks`, `missing_information`, and `confidence`.
- [ ] `confidence` is validated between `0.0` and `1.0`.
- [ ] `backend/app/agents/prompts.py` contains the Agent 2 verification prompt.
- [ ] Verification prompt rejects weak, loose, duplicate, contradicted, unclear, or wrong-document chunks.
- [ ] Verification prompt accepts directly useful or simple-reasoning-supporting evidence.
- [ ] Verification prompt requires valid JSON only.
- [ ] `backend/app/agents/verification_agent.py` exposes `run_verification_agent`.
- [ ] Empty candidates return missing information with confidence `0.0` without calling ShopAIKey.
- [ ] Non-empty candidates call ShopAIKey chat completion through backend service code.
- [ ] LLM JSON output is parsed and Pydantic-validated.
- [ ] Unknown chunk IDs from LLM output are not accepted.
- [ ] Verified quotes are faithful excerpts from Agent 1 candidate content.
- [ ] Duplicate verified chunks are filtered.
- [ ] Clear contradictions are detected or reported.
- [ ] No verified evidence sets `missing_information = true`.
- [ ] Agent 2 logs successful verification steps to `agent_steps`.
- [ ] Agent 2 logs failed verification steps when possible.
- [ ] ShopAIKey, invalid JSON, schema validation, unknown-ID, and provider failures raise `VerificationAgentError`.
- [ ] Rejected chunks are not passed as verified evidence.
- [ ] Agent 2 does not generate final answers.
- [ ] Agent 2 does not add citation formatting for users.
- [ ] Agent 2 does not retrieve new chunks beyond Agent 1 candidates.
- [ ] Agent 3 was not implemented.
- [ ] LangGraph workflow was not implemented.
- [ ] No public chat, evidence, or agent log API was added.
- [ ] Backend-only secrets and provider settings stayed out of frontend code.
- [ ] `cd backend` then `pytest tests/test_verification_agent.py -v` was run and reported.
- [ ] Manual Agent 1 -> Agent 2 smoke check was completed or marked `BLOCKED_BY_USER_ACTION` with a safe reason.
- [ ] Execution report includes files created, files modified, commands run, test results, known issues, out-of-scope work, and example Agent 2 output.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [ ] Batch01 - Verification Contracts, Prompt, and Backend-Only Configuration
- [ ] Batch02 - Verification Agent Callable and LLM JSON Validation
- [ ] Batch03 - Deterministic Evidence Safety Checks
- [ ] Batch04 - Agent Step Logging and Failure Handling
- [ ] Batch05 - Required Automated Tests
- [ ] Batch06 - Manual Validation, Reporting, and Scope Review

### Task IDs

#### Batch01

- [x] (01A): Extend agent schemas for Agent 2 verification
- [x] (01B): Enforce confidence validation behavior
- [x] (01C): Add reusable verification prompt rules
- [x] (01D): Confirm ShopAIKey chat configuration boundary

#### Batch02

- [ ] (02A): Create verification agent module and controlled error type
- [ ] (02B): Implement deterministic empty-candidates behavior
- [ ] (02C): Build compact evidence payload and call ShopAIKey chat
- [ ] (02D): Parse and validate LLM JSON response

#### Batch03

- [ ] (03A): Reject or fail unknown returned chunk IDs
- [ ] (03B): Validate verified and rejected quotes against source candidate content
- [ ] (03C): Add deterministic duplicate filtering
- [ ] (03D): Add basic contradiction and missing-information adjustment
- [ ] (03E): Preserve final output shape after post-processing

#### Batch04

- [ ] (04A): Add Agent 2 success-step logging
- [ ] (04B): Add Agent 2 failed-step logging
- [ ] (04C): Keep log failures safe and visible

#### Batch05

- [ ] (05A): Add accepted and rejected evidence tests
- [ ] (05B): Add missing-information and empty-candidate tests
- [ ] (05C): Add invalid JSON, unknown ID, and provider failure tests
- [ ] (05D): Add contradiction, quote, duplicate, and confidence tests
- [ ] (05E): Run required targeted automated validation

#### Batch06

- [ ] (06A): Run manual Agent 1 output into Agent 2 when setup is available
- [ ] (06B): Create execution report with example Agent 2 output
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
- reason: missing ShopAIKey API key, missing Supabase credentials, missing applied migration, missing valid `agent_run_id`, missing Agent 1 candidates, missing processed indexed document, missing provider setup, missing manual setup, or other safe summary

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
