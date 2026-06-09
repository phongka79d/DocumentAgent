# Plan 9 - Agent 1 Retrieval Agent Execution Tasks

## Purpose

Create a detailed execution task file for the approved Agent 1 Retrieval Agent milestone. This task file guides a future Execution Agent to add backend agent schemas, wrap the completed hybrid retrieval service in an Agent 1 callable contract, persist `agent_steps` logs for retrieval success and failure, and verify the required structured candidate output from `docs/plans/Plan_9.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_9.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Current project context reviewed: `README.md`
- Conflict note: No architecture conflicts were found. `docs/plans/Master_Plan.md` aligns with Plan 9 on Agent 1 retrieval, structured candidate output, score visibility, `agent_steps`, backend-only environment variables, and future LangGraph boundaries. `README.md` confirms Plan 8 hybrid retrieval is implemented and that agent workflow/runtime APIs are still planned. `docs/plans/Plan_9.md` remains the scope authority for this task file.

## Source Section Index

- `docs/plans/Plan_9.md` > `## 1. Goal` -> Agent 1 must return structured candidates and log a successful retrieval step.
- `docs/plans/Plan_9.md` > `## 2. Why This Plan Exists` -> Agent 1 wraps hybrid retrieval before evidence verification.
- `docs/plans/Plan_9.md` > `## 3. Scope` -> required schemas, retrieval logic, hybrid integration, JSON output, logging, and tests.
- `docs/plans/Plan_9.md` > `## 4. Out of Scope` -> prohibited Agent 2, Agent 3, LangGraph workflow, chat API, answer generation, and verification.
- `docs/plans/Plan_9.md` > `## 5. Dependencies` -> completed Plan 2 `agent_steps` and completed Plan 8 hybrid retrieval.
- `docs/plans/Plan_9.md` > `## 6. Required Files and Folders` -> required agent package, schemas, retrieval agent, log service, Supabase helper, and tests.
- `docs/plans/Plan_9.md` > `## 7. Data Model / Schema Changes` -> no database schema changes, Agent 1 input/output schema, and agent step log shape.
- `docs/plans/Plan_9.md` > `## 8. API Design` -> no public endpoints and internal `run_retrieval_agent` callable.
- `docs/plans/Plan_9.md` > `## 9. Implementation Steps` -> ordered schema, logging, agent, validation, hybrid retrieval, success log, failure log, and test steps.
- `docs/plans/Plan_9.md` > `## 10. Configuration and Environment Variables` -> backend-only `RETRIEVAL_FINAL_TOP_K`, `SINGLE_USER_ID`, Supabase URL, and service role key requirements.
- `docs/plans/Plan_9.md` > `## 11. Required Tests` -> unit tests, manual check, and negative failure checks.
- `docs/plans/Plan_9.md` > `## 12. Acceptance Criteria` -> callable function, structured schema, score components, sort order, success logs, failure logs, and no verification/answers.
- `docs/plans/Plan_9.md` > `## 13. Failure Handling` -> validation errors, hybrid failures, log insert failures, empty results, and schema mismatch behavior.
- `docs/plans/Plan_9.md` > `## 14. Agent Report Requirement` -> required execution report content and live-vs-mocked log verification.
- `docs/plans/Plan_9.md` > `## 15. Reviewer Checklist` -> scope, tests, acceptance, secrets, architecture, output validation, and failure visibility.
- `docs/plans/Master_Plan.md` > `## Table: agent_steps` -> approved `agent_steps` fields.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.1 Goal` -> Agent 1 retrieval signals.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.2 Retrieval Steps` -> receive question, retrieve, merge, score, sort, and return candidates.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.3 Top-K Settings` -> configurable Top-K values.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.4 Scoring Formula` -> score component meanings and normalized range.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.6 Agent 1 Output Schema` -> required candidate JSON fields.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> backend-only environment variables and frontend secret boundary.
- `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure` -> expected `backend/app/agents` and service locations.
- `README.md` > `### Hybrid Retrieval Configuration, Schemas, Scoring Utilities, Graph Candidates, and API Mode` -> current Plan 8 hybrid retrieval service context.
- `README.md` > `### Data, Storage, and External Services` -> current migration includes `agent_runs` and `agent_steps`.
- `README.md` > `## Known Gaps or Unclear Areas` -> chat agents, agent logs APIs, and LangGraph workflow are not yet implemented.

## Approved Architecture Summary

Plan 9 approves a backend-only Agent 1 Retrieval Agent for the single-user Document QA Agent MVP. Agent 1 is an internal callable layer, not a public API. It receives a user question, a selected document list, and an existing `agent_run_id`; validates that input with Pydantic; calls the completed Plan 8 hybrid retrieval service; converts returned hybrid candidates into the required Agent 1 output schema; validates the output; and persists an `agent_steps` row for the retrieval step.

The Agent 1 output must include `question` and `candidates`. Each candidate must preserve the hybrid retrieval fields `chunk_id`, `document_id`, `file_name`, `content`, `page_number`, `section_title`, `semantic_similarity`, `graph_relevance`, `keyword_overlap`, `metadata_match`, `recency_or_position_score`, `final_score`, and `retrieval_reason`. Candidate ordering must remain sorted by `final_score` as returned by hybrid retrieval.

The agent step log must use `step_name = "agent_1_retrieval"` and `agent_name = "retrieval_agent"`, store safe JSON input/output payloads, and report `status = "success"` or `status = "failed"` with a safe error message. Log insertion helpers may be added to `supabase_service.py`, but Plan 9 does not allow database schema changes.

Failure handling is part of the architecture. Invalid input must fail before retrieval. Hybrid retrieval failures must create a failed agent step log when possible and re-raise a controlled `RetrievalAgentError`. Agent log insert failures must be logged safely and must not erase the original retrieval failure context. Empty retrieval results are valid successful output with `candidates: []`.

Plan 9 explicitly does not implement Agent 2 evidence verification, Agent 3 answer generation, LangGraph orchestration, `/api/chat/ask`, final answers, public agent log APIs, or verified chunk marking.

## Global Implementation Rules

- Keep `docs/plans/Plan_9.md` as the source of truth for scope, validations, failure handling, and out-of-scope boundaries.
- Use `docs/plans/Master_Plan.md` only to clarify the broader Agent 1 contract, `agent_steps` fields, environment variable boundaries, and expected package locations.
- Use `README.md` only to understand the current implementation state, especially completed hybrid retrieval and missing agent workflow APIs.
- Depend on completed Plan 2 `agent_steps` schema and completed Plan 8 hybrid retrieval behavior; do not reimplement hybrid retrieval, graph retrieval, semantic retrieval, Qdrant search, or scoring.
- Do not add database migrations or modify the `agent_steps` table schema.
- Do not create public chat, agent, evidence, or final answer APIs in this plan.
- Do not implement LangGraph orchestration in this plan.
- Do not implement Agent 2 verification or Agent 3 answer generation.
- Do not mark chunks as verified from Agent 1.
- Do not expose backend-only values to frontend code.
- Use `.env.example` for placeholder names only and never commit real secrets.
- Preserve single-user filtering through existing service dependencies and Supabase helpers.
- Keep agent input, output, and log payloads JSON-serializable and Pydantic-validated before persistence where applicable.
- Write safe errors that do not expose provider keys, Supabase service role values, SQL payloads, stack traces, or private document content beyond expected retrieval output.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, schemas, settings, services, tests, and errors.
- Keep functions, services, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, Supabase Python client, and service-layer conventions already present in the backend.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless Plan 9 explicitly requires them.
- Add comments only where they clarify a non-obvious error-handling, serialization, or logging decision.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Avoid adding formatters, linters, frameworks, or architecture changes outside Plan 9 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Agent Package, Schemas, and Configuration Boundary
- Batch02 - Agent Step Logging Service
- Batch03 - Retrieval Agent Callable and Failure Handling
- Batch04 - Required Automated Tests
- Batch05 - Manual Validation, Reporting, and Scope Review

## Mandatory Batch01 - Agent Package, Schemas, and Configuration Boundary

### Goal

Prepare the backend agent package and Pydantic contracts required by Agent 1.

### Why this batch exists

The retrieval agent cannot safely call hybrid retrieval or persist logs until the input, candidate, output, and configuration boundaries are explicit and validated.

### Inputs / Dependencies

- `docs/plans/Plan_9.md`
- `docs/plans/Master_Plan.md`
- Current backend Pydantic schema conventions
- Completed Plan 8 hybrid retrieval schema fields
- Existing backend settings and `.env.example`

### Tasks

- [x] (01A): Create backend agents package
  - Source of Truth: `docs/plans/Plan_9.md` > `## 3. Scope`; `docs/plans/Plan_9.md` > `## 6. Required Files and Folders`; `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure`
  - Source Requirements:
    - Add shared agent schemas.
    - Create `backend/app/agents/__init__.py`.
    - Keep Agent 1 implementation under `backend/app/agents/retrieval_agent.py`.
  - Details: Establish the `backend/app/agents` package using the repo's existing package style. Avoid adding Agent 2, Agent 3, LangGraph, or API modules.
  - Dependencies: None.
  - User Action: None.
  - Agent Work: Create the package marker and prepare imports only where needed for Agent 1.
  - Output: Importable backend agent package.
  - Acceptance: `backend/app/agents` imports without side effects; no public API route is added; no Agent 2/Agent 3 files are created.
  - Validation: Run a targeted import check from `backend`, such as importing `app.agents`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/__init__.py`

- [x] (01B): Define shared Agent 1 Pydantic schemas
  - Source of Truth: `docs/plans/Plan_9.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_9.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.6 Agent 1 Output Schema`
  - Source Requirements:
    - Define `RetrievalAgentInput`, `RetrievalCandidate`, and `RetrievalAgentOutput`.
    - Agent input includes `agent_run_id`, `question`, and `document_ids`.
    - Agent output includes `question` and structured `candidates`.
    - Candidate schema must include all hybrid retrieval score fields and `retrieval_reason`.
  - Details: Use Pydantic validation compatible with the backend's current Pydantic version. Validate UUID-like fields consistently with existing schemas. Keep score fields normalized by trusting or validating Plan 8 hybrid output as appropriate.
  - Dependencies: (01A), completed Plan 8 candidate schema fields.
  - User Action: None.
  - Agent Work: Add schemas to `backend/app/agents/schemas.py`, export only useful symbols, and avoid duplicating large retrieval logic.
  - Output: Typed Agent 1 input, candidate, and output models.
  - Acceptance: Input rejects malformed `agent_run_id`, empty or invalid questions where required, and invalid document IDs; output validates every required candidate field; `candidates: []` is valid.
  - Validation: Add or run schema import/validation tests once Batch04 test files exist; run a direct Pydantic smoke check in this batch if tests are not present yet.
  - Blocked Condition: None.
  - Files: `backend/app/agents/schemas.py`, `backend/app/agents/__init__.py`

- [x] (01C): Confirm backend-only retrieval and persistence configuration boundary
  - Source of Truth: `docs/plans/Plan_9.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.3 Top-K Settings`; `docs/plans/Master_Plan.md` > `# 15. Environment Variables`; `README.md` > `### Hybrid Retrieval Configuration, Schemas, Scoring Utilities, Graph Candidates, and API Mode`
  - Source Requirements:
    - `RETRIEVAL_FINAL_TOP_K` is the default number of candidate chunks Agent 1 returns.
    - `SINGLE_USER_ID`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY` remain backend-only.
    - Real secret values must not be committed or exposed to frontend code.
  - Details: Reuse existing settings and `.env.example` values from Plan 8 when present. Only update configuration if Agent 1 needs a missing setting or placeholder. Do not add frontend variables.
  - Dependencies: Completed Plan 8 backend configuration.
  - User Action: User must provide real Supabase settings in `backend/.env` for live agent step persistence checks.
  - Agent Work: Confirm or add safe backend-only placeholders and ensure Agent 1 resolves final Top-K through backend settings or the hybrid retrieval service contract.
  - Output: Verified backend-only configuration boundary for Agent 1.
  - Acceptance: `RETRIEVAL_FINAL_TOP_K`, `SINGLE_USER_ID`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY` are documented or configured backend-only; frontend files do not contain backend-only secrets or retrieval settings.
  - Validation: Run backend config/import tests or targeted settings import; scan frontend for backend-only variable names.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live Supabase persistence validation when real Supabase settings are missing.
  - Files: `backend/app/core/config.py`, `backend/.env.example`, frontend env files only for inspection

### Files or Modules Likely Created or Updated

- `backend/app/agents/__init__.py`
- `backend/app/agents/schemas.py`
- `backend/app/core/config.py` only if required settings are missing
- `backend/.env.example` only if safe placeholders are missing

### Required Outputs / Artifacts

- Importable `backend/app/agents` package.
- Pydantic Agent 1 input, candidate, and output schemas.
- Confirmed backend-only final Top-K and Supabase persistence configuration boundary.

### Acceptance Criteria

- Agent 1 schemas match Plan 9 required input and output shape.
- Candidate schema includes every required retrieval score component.
- Empty candidate output is schema-valid.
- Backend-only settings remain out of frontend code.
- No runtime retrieval agent logic is implemented before schema contracts are ready.

### Required Tests or Validations

- Backend import check for `app.agents` and `app.agents.schemas`.
- Direct Pydantic schema validation smoke check or targeted schema tests.
- Backend settings import/config validation.
- Frontend scan for backend-only settings and provider secrets.

### Explicit Non-Goals

- Do not implement `run_retrieval_agent` in this batch.
- Do not write `agent_steps` rows in this batch.
- Do not add public API routes.
- Do not implement Agent 2, Agent 3, or LangGraph.

## Mandatory Batch02 - Agent Step Logging Service

### Goal

Add the backend service boundary for writing Agent 1 step logs to `agent_steps`.

### Why this batch exists

Agent 1 completion is only traceable when success and failure inputs/outputs are safely persisted through a focused logging service.

### Inputs / Dependencies

- Batch01 schemas and configuration boundary
- Completed Plan 2 `agent_steps` table
- Existing `supabase_service.py` helper patterns
- `docs/plans/Plan_9.md`
- `docs/plans/Master_Plan.md` `agent_steps` table contract

### Tasks

- [x] (02A): Add Supabase helper for inserting agent step logs
  - Source of Truth: `docs/plans/Plan_9.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_9.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Master_Plan.md` > `## Table: agent_steps`
  - Source Requirements:
    - `backend/app/services/supabase_service.py` may add a helper for inserting agent step logs if not already present.
    - Agent step rows include `agent_run_id`, `step_name`, `agent_name`, `input`, `output`, `status`, and nullable `error_message`.
    - No database schema changes are required.
  - Details: Follow existing Supabase service conventions for inserts, safe exceptions, and dependency injection or test mocking. Keep JSON payloads serializable.
  - Dependencies: Existing Supabase service and Plan 2 migration.
  - User Action: User must have applied the existing migration for live persistence validation.
  - Agent Work: Add a narrow insert helper or reuse an existing one if it already exists. Do not broaden Supabase service into workflow orchestration.
  - Output: Supabase helper that inserts one `agent_steps` row.
  - Acceptance: Helper builds the exact row shape required by Plan 9 and Master Plan; no schema migration is added; tests can mock the helper.
  - Validation: Unit test with mocked Supabase client or service boundary; live validation only after user setup is available.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live database insert checks if Supabase credentials, migration, or a valid `agent_run_id` are unavailable.
  - Files: `backend/app/services/supabase_service.py`, `backend/tests/test_supabase_service.py` if adding direct helper tests

- [x] (02B): Implement focused agent log service
  - Source of Truth: `docs/plans/Plan_9.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_9.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_9.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Create `backend/app/services/agent_log_service.py`.
    - Implement `log_agent_step(agent_run_id, step_name, agent_name, input_payload, output_payload, status, error_message=None)`.
    - Agent 1 uses `step_name = "agent_1_retrieval"` and `agent_name = "retrieval_agent"`.
  - Details: Keep this service generic enough for one step log, but do not implement the full agent workflow or agent run lifecycle. Ensure payload serialization does not mutate caller data.
  - Dependencies: (02A), Batch01 schemas.
  - User Action: None for mocked tests.
  - Agent Work: Add log service function, simple validation for status values if appropriate, and safe conversion for Pydantic models to JSON-compatible dicts.
  - Output: Reusable agent step logging helper.
  - Acceptance: Agent log service can write success and failed rows through the Supabase helper; it accepts Pydantic models or dictionaries; it does not print or expose secrets.
  - Validation: Unit tests with mocked Supabase helper for success and failed log calls.
  - Blocked Condition: None for mocked tests; `BLOCKED_BY_USER_ACTION` only for live persistence checks.
  - Files: `backend/app/services/agent_log_service.py`, `backend/app/services/__init__.py` if needed, `backend/tests/test_retrieval_agent.py` or dedicated service tests

- [x] (02C): Define safe log failure behavior
  - Source of Truth: `docs/plans/Plan_9.md` > `## 13. Failure Handling`; `docs/plans/Plan_9.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Agent log insert failure must be logged.
    - Agent log insert failure should not silently erase retrieval failure context.
    - Failures must be visible in logs.
  - Details: Decide how `agent_log_service` signals insert failures to `retrieval_agent` while preserving the original retrieval outcome. Use existing backend logging patterns.
  - Dependencies: (02B), existing backend logging setup.
  - User Action: None.
  - Agent Work: Implement safe logging of log-insert failures and document how the retrieval agent should behave when logging fails after a successful or failed retrieval attempt.
  - Output: Deterministic failure behavior for agent step log persistence.
  - Acceptance: Tests prove original retrieval failures remain visible even if log insertion also fails; success-path log failure is visible and handled according to the chosen safe behavior.
  - Validation: Mock log insertion failure in tests and assert safe error/log behavior.
  - Blocked Condition: None.
  - Files: `backend/app/services/agent_log_service.py`, `backend/app/agents/retrieval_agent.py` once Batch03 exists, tests

### Files or Modules Likely Created or Updated

- `backend/app/services/supabase_service.py`
- `backend/app/services/agent_log_service.py`
- `backend/app/services/__init__.py` if needed
- `backend/tests/test_supabase_service.py`
- `backend/tests/test_retrieval_agent.py` or dedicated agent log service tests

### Required Outputs / Artifacts

- Supabase insert helper for `agent_steps`.
- Focused `log_agent_step` service.
- Safe behavior for log insertion failures.

### Acceptance Criteria

- Success and failed retrieval steps can be represented with the required `agent_steps` shape.
- Log payloads are JSON-compatible and safe.
- No database migration is introduced.
- Log insertion failures are visible and do not erase original retrieval failure context.

### Required Tests or Validations

- Mocked Supabase helper tests.
- Mocked `agent_log_service` success and failure tests.
- Backend import checks for the new service.

### Explicit Non-Goals

- Do not create or manage full `agent_runs` lifecycle in this batch.
- Do not add public agent log APIs.
- Do not implement Agent 1 retrieval logic before the logging boundary is ready.
- Do not perform live database validation unless required local credentials and rows are available.

## Mandatory Batch03 - Retrieval Agent Callable and Failure Handling

### Goal

Implement the internal Agent 1 callable that validates input, calls hybrid retrieval, returns structured output, and logs success or failure.

### Why this batch exists

Plan 9's core deliverable is a workflow-compatible retrieval agent wrapper around the completed hybrid retrieval service, not another retrieval implementation.

### Inputs / Dependencies

- Batch01 Agent 1 schemas
- Batch02 agent log service
- Completed Plan 8 `backend/app/services/hybrid_retrieval_service.py`
- Existing backend settings for `RETRIEVAL_FINAL_TOP_K`
- `docs/plans/Plan_9.md`

### Tasks

- [x] (03A): Create retrieval agent module and controlled error type
  - Source of Truth: `docs/plans/Plan_9.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_9.md` > `## 8. API Design`; `docs/plans/Plan_9.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Create `backend/app/agents/retrieval_agent.py`.
    - Internal callable is `run_retrieval_agent(input: RetrievalAgentInput) -> RetrievalAgentOutput`.
    - Retrieval failures re-raise a controlled `RetrievalAgentError`.
  - Details: Keep the module backend-only and service-level. Do not mount a router. Use dependency imports that tests can patch cleanly.
  - Dependencies: Batch01.
  - User Action: None.
  - Agent Work: Add module, error type, constants for `agent_1_retrieval` and `retrieval_agent`, and a callable skeleton ready for implementation.
  - Output: Importable retrieval agent module.
  - Acceptance: Module imports cleanly; no public endpoint is added; error type is available for workflow layers.
  - Validation: Direct import check or targeted tests.
  - Blocked Condition: None.
  - Files: `backend/app/agents/retrieval_agent.py`, `backend/app/agents/__init__.py`

- [x] (03B): Implement input validation and hybrid retrieval call
  - Source of Truth: `docs/plans/Plan_9.md` > `## 8. API Design`; `docs/plans/Plan_9.md` > `## 9. Implementation Steps`; `docs/plans/Plan_9.md` > `## 10. Configuration and Environment Variables`; `README.md` > `### Hybrid Retrieval Configuration, Schemas, Scoring Utilities, Graph Candidates, and API Mode`
  - Source Requirements:
    - Validate input with Pydantic.
    - Call `retrieve_hybrid(question, document_ids, final_top_k)`.
    - Use `RETRIEVAL_FINAL_TOP_K` as the default number of candidate chunks Agent 1 returns.
  - Details: Accept either a `RetrievalAgentInput` instance or raw input data only if the implementation clearly validates through `RetrievalAgentInput`. Do not bypass existing hybrid retrieval validation or selected document filtering.
  - Dependencies: (03A), Batch01 schemas, completed Plan 8 hybrid retrieval.
  - User Action: None.
  - Agent Work: Resolve final Top-K from settings or through the hybrid service default, call hybrid retrieval with question and document IDs, and preserve returned order.
  - Output: Agent 1 can retrieve candidate data through Plan 8 service.
  - Acceptance: Hybrid retrieval is called exactly through the approved service boundary; selected document IDs are passed through; invalid input fails before retrieval.
  - Validation: Mocked test proving hybrid retrieval call arguments and invalid input behavior.
  - Blocked Condition: None.
  - Files: `backend/app/agents/retrieval_agent.py`, tests

- [x] (03C): Convert hybrid candidates into validated Agent 1 output and log success
  - Source of Truth: `docs/plans/Plan_9.md` > `## 1. Goal`; `docs/plans/Plan_9.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_9.md` > `## 9. Implementation Steps`; `docs/plans/Plan_9.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Convert retrieval candidates into `RetrievalCandidate` models.
    - Validate the output model before returning.
    - Write an `agent_steps` row with status `success` after output validation.
    - Candidate chunks are sorted by `final_score` as returned by hybrid retrieval.
  - Details: Preserve all required candidate fields and score components. If optional or nullable fields are allowed, keep the schema behavior explicit and tested. Log the validated input and output safely.
  - Dependencies: (03B), Batch02 log service.
  - User Action: None for mocked tests.
  - Agent Work: Build `RetrievalAgentOutput`, log success through `log_agent_step`, and return the validated model.
  - Output: Successful Agent 1 run returns structured output and writes a success log.
  - Acceptance: Output matches required JSON schema; success log uses `step_name = "agent_1_retrieval"`, `agent_name = "retrieval_agent"`, `status = "success"`, safe input payload, and validated output payload.
  - Validation: Mocked success-path test asserting output schema, candidate fields, ordering preservation, and log call payload.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live database log verification when required Supabase setup is missing.
  - Files: `backend/app/agents/retrieval_agent.py`, tests

- [x] (03D): Implement retrieval failure handling and failed-step logging
  - Source of Truth: `docs/plans/Plan_9.md` > `## 8. API Design`; `docs/plans/Plan_9.md` > `## 9. Implementation Steps`; `docs/plans/Plan_9.md` > `## 13. Failure Handling`; `docs/plans/Plan_9.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - If retrieval fails, write an `agent_steps` row with status `failed` and a safe error message.
    - Re-raise a controlled `RetrievalAgentError` for the workflow layer to handle later.
    - Agent log insert failure must be logged and must not silently erase retrieval failure context.
  - Details: Wrap hybrid retrieval dependency errors without leaking provider, Qdrant, Supabase, or stack-trace details. Preserve validation errors for invalid input before retrieval, as Plan 9 requires.
  - Dependencies: (03B), Batch02 safe log behavior.
  - User Action: None.
  - Agent Work: Add failure branch, safe error mapping, failed-step log call, and controlled re-raise.
  - Output: Deterministic Agent 1 failure behavior.
  - Acceptance: Retrieval exceptions produce a failed log entry and `RetrievalAgentError`; log insertion failures are visible; invalid input raises validation before retrieval and does not create fake success.
  - Validation: Mocked failure tests for hybrid retrieval exception, log insertion failure, and invalid input.
  - Blocked Condition: None.
  - Files: `backend/app/agents/retrieval_agent.py`, `backend/app/services/agent_log_service.py`, tests

### Files or Modules Likely Created or Updated

- `backend/app/agents/retrieval_agent.py`
- `backend/app/agents/__init__.py`
- `backend/app/agents/schemas.py`
- `backend/app/services/agent_log_service.py`
- `backend/tests/test_retrieval_agent.py`

### Required Outputs / Artifacts

- Internal `run_retrieval_agent` callable.
- Controlled `RetrievalAgentError`.
- Structured Agent 1 output model.
- Success and failed `agent_steps` log behavior.

### Acceptance Criteria

- Agent 1 has a clear callable function.
- Agent 1 output matches the required structured JSON schema.
- Candidate chunks include all retrieval score components.
- Candidate chunks remain sorted by `final_score` as returned by hybrid retrieval.
- Agent 1 logs successful runs to `agent_steps`.
- Agent 1 logs failed runs to `agent_steps`.
- Agent 1 does not verify evidence or generate answers.

### Required Tests or Validations

- Mocked callable success test.
- Mocked output validation test.
- Mocked failure and failed-log tests.
- Import check for `app.agents.retrieval_agent`.

### Explicit Non-Goals

- Do not implement Agent 2 verification.
- Do not implement Agent 3 answer generation.
- Do not build LangGraph workflow.
- Do not create `/api/chat/ask`.
- Do not generate final answers.
- Do not mark chunks as verified.

## Mandatory Batch04 - Required Automated Tests

### Goal

Add and run the required automated tests for Agent 1 schema, success, empty result, and failure behavior.

### Why this batch exists

Agent 1 must be proven through deterministic tests before any manual database or workflow checks can be trusted.

### Inputs / Dependencies

- Batch01 through Batch03 implementation
- `docs/plans/Plan_9.md`
- Existing pytest structure under `backend/tests`
- Mockable Plan 8 hybrid retrieval and agent log service boundaries

### Tasks

- [ ] (04A): Add Agent 1 schema validation tests
  - Source of Truth: `docs/plans/Plan_9.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_9.md` > `## 9. Implementation Steps`; `docs/plans/Plan_9.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Agent 1 input and output must be Pydantic-validated.
    - Invalid input raises validation error before retrieval.
    - Candidate schema mismatch must fail before the workflow proceeds.
  - Details: Test valid input, malformed IDs, empty/invalid question behavior, valid empty candidates, and missing candidate score fields.
  - Dependencies: Batch01 schemas.
  - User Action: None.
  - Agent Work: Add focused schema tests in `backend/tests/test_retrieval_agent.py` or a dedicated schema test file.
  - Output: Tests covering input/output schema boundaries.
  - Acceptance: Invalid input cannot call retrieval; invalid candidate output is rejected; empty candidates remain valid.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_retrieval_agent.py`, `backend/app/agents/schemas.py`

- [ ] (04B): Add successful retrieval and success-log tests
  - Source of Truth: `docs/plans/Plan_9.md` > `## 1. Goal`; `docs/plans/Plan_9.md` > `## 9. Implementation Steps`; `docs/plans/Plan_9.md` > `## 11. Required Tests`; `docs/plans/Plan_9.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Add tests that mock hybrid retrieval and agent logging.
    - Agent 1 produces required JSON candidate schema.
    - Agent 1 records a successful `agent_steps` row for retrieval.
    - Candidate chunks are sorted by `final_score` as returned by hybrid retrieval.
  - Details: Mock `retrieve_hybrid` with deterministic candidates containing every score field. Assert the returned model and log payload include the required fields and exact status.
  - Dependencies: Batch03 success path.
  - User Action: None.
  - Agent Work: Add success test coverage and keep it independent from live Supabase, Qdrant, and ShopAIKey.
  - Output: Passing success-path Agent 1 tests.
  - Acceptance: Tests prove the callable returns structured output and calls `log_agent_step` with success after output validation.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_retrieval_agent.py`

- [ ] (04C): Add empty result and retrieval failure tests
  - Source of Truth: `docs/plans/Plan_9.md` > `## 11. Required Tests`; `docs/plans/Plan_9.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_9.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Empty results return `candidates: []` with status `success`.
    - Retrieval exceptions produce a failed log entry.
    - Retrieval exceptions raise `RetrievalAgentError`.
  - Details: Test the empty candidate path separately from failure. Mock hybrid retrieval failure and assert failed-step log shape, safe error message, and controlled exception.
  - Dependencies: Batch03 failure handling.
  - User Action: None.
  - Agent Work: Add tests for empty results, hybrid retrieval failure, and log failure preservation.
  - Output: Passing tests for empty success and failure behavior.
  - Acceptance: Empty results are not treated as failure; retrieval failure is visible in logs and surfaces as `RetrievalAgentError`.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_agent.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_retrieval_agent.py`

- [ ] (04D): Run required targeted automated validation
  - Source of Truth: `docs/plans/Plan_9.md` > `## 11. Required Tests`; `docs/plans/Plan_9.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_9.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Run `cd backend` then `pytest tests/test_retrieval_agent.py -v`.
    - Verify tests were actually run.
    - Confirm no hardcoded secrets and no fake success.
  - Details: Run the required Plan 9 test command after all Agent 1 tests exist. Also run adjacent tests if changed files touch shared config, Supabase service, or hybrid retrieval contracts.
  - Dependencies: (04A), (04B), (04C).
  - User Action: None.
  - Agent Work: Run targeted tests, report exact commands and results, and inspect changed files for secret exposure or out-of-scope additions.
  - Output: Recorded automated validation evidence.
  - Acceptance: Required tests pass or failures are reported honestly with cause; any additional changed shared-service tests pass where applicable.
  - Validation: `cd backend` then `pytest tests/test_retrieval_agent.py -v`; optional adjacent tests such as `pytest tests/test_supabase_service.py tests/test_config.py tests/test_hybrid_retrieval_service.py -v` if those areas changed.
  - Blocked Condition: None.
  - Files: `backend/tests/test_retrieval_agent.py`, any changed implementation files

### Files or Modules Likely Created or Updated

- `backend/tests/test_retrieval_agent.py`
- `backend/tests/test_supabase_service.py` if Supabase helper tests are needed
- Implementation files from Batch01 through Batch03 if test feedback requires fixes

### Required Outputs / Artifacts

- Unit tests for schema validation.
- Unit tests for success output and success logging.
- Unit tests for empty candidate success.
- Unit tests for retrieval failure and failed logging.
- Recorded test command results.

### Acceptance Criteria

- `pytest tests/test_retrieval_agent.py -v` passes from `backend`.
- Tests do not require live Supabase, Qdrant, or ShopAIKey.
- Tests prove success, empty result, and retrieval failure behavior.
- Tests prove output and candidate schema validation.
- No hardcoded secrets or out-of-scope workflow logic are introduced.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_retrieval_agent.py -v`
- Adjacent tests for any changed shared service or configuration file.
- Secret and frontend boundary inspection.

### Explicit Non-Goals

- Do not run live provider calls in automated tests.
- Do not fabricate live `agent_steps` success.
- Do not add frontend tests for Agent 1.
- Do not test Agent 2, Agent 3, LangGraph, or final chat API behavior.

## Mandatory Batch05 - Manual Validation, Reporting, and Scope Review

### Goal

Complete the manual Agent 1 smoke check when setup is available and produce the required execution report for reviewer handoff.

### Why this batch exists

Plan 9 requires future execution agents to state whether `agent_steps` persistence was verified through a live database or mocked tests, and to report out-of-scope boundaries clearly.

### Inputs / Dependencies

- Batch01 through Batch04 implementation and tests
- Existing `agent_runs` row or another valid `agent_run_id`
- Processed and indexed documents suitable for hybrid retrieval
- Supabase credentials and applied migration for live log checks
- `docs/plans/Plan_9.md`

### Tasks

- [ ] (05A): Run manual Agent 1 smoke check when live setup is available
  - Source of Truth: `docs/plans/Plan_9.md` > `## 11. Required Tests`; `docs/plans/Plan_9.md` > `## 13. Failure Handling`; `docs/plans/Plan_9.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Create or reuse an `agent_run_id`.
    - Call `run_retrieval_agent` with a question and selected document IDs.
    - Confirm output contains candidates with all score fields.
    - Confirm `agent_steps` contains one `agent_1_retrieval` row.
    - Report whether the row was verified through a live database or mocked test.
  - Details: Use existing local processed/indexed/graph-built data only if available. Do not fabricate `agent_run_id`, provider credentials, or document rows. Do not include secrets or private document content in the report.
  - Dependencies: Batch03 callable, Batch04 automated tests.
  - User Action: User must provide or confirm a valid `agent_run_id`, Supabase setup, and selected processed/indexed document IDs if not already available locally.
  - Agent Work: Run service-level manual check, verify output shape and log row, or document a `BLOCKED_BY_USER_ACTION` status with a safe reason.
  - Output: Manual Agent 1 validation result or documented blocked status.
  - Acceptance: Manual check confirms candidate score fields and one `agent_1_retrieval` row, or the report safely explains why live verification is blocked.
  - Validation: Service-level invocation of `run_retrieval_agent` and safe Supabase row lookup; mocked validation evidence remains separate from live verification.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if a valid `agent_run_id`, live Supabase credentials, applied migration, indexed documents, or provider setup is missing.
  - Files: No required file changes beyond execution report; optional smoke script only if the repo already uses that pattern.

- [ ] (05B): Complete execution report and scope boundary review
  - Source of Truth: `docs/plans/Plan_9.md` > `## 4. Out of Scope`; `docs/plans/Plan_9.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_9.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_9.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Report files created, files modified, commands run, test results, known issues, and intentionally out-of-scope work.
    - Include whether `agent_steps` was verified through a live database or mocked test.
    - Reviewer must verify scope, tests, acceptance, secrets, architecture, output validation, and failures visible in logs.
  - Details: Prepare a concise report in the repo's established execution-report location. Do not mark manual live validation complete unless it was actually performed.
  - Dependencies: (05A), Batch04 test results.
  - User Action: None unless manual validation remains blocked.
  - Agent Work: Create or append the Plan 9 execution report, summarize automated and manual validation evidence, and document out-of-scope confirmations.
  - Output: Execution report ready for reviewer handoff.
  - Acceptance: Report includes required fields, exact test command results, live-vs-mocked `agent_steps` status, known issues, out-of-scope confirmations, and safe handoff notes.
  - Validation: Review report against Plan 9 Agent Report Requirement and Reviewer Checklist.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for manual validation items requiring user-provided setup; reporting itself is not blocked.
  - Files: `docs/reports/report_9_execute_agent.md`, `docs/tasks/task_9.md` progress tracker during execution

### Files or Modules Likely Created or Updated

- `docs/reports/report_9_execute_agent.md`
- `docs/tasks/task_9.md` progress tracker during execution
- No runtime files unless test feedback from earlier batches requires fixes

### Required Outputs / Artifacts

- Manual Agent 1 validation result or blocked status.
- Live-vs-mocked `agent_steps` verification statement.
- Execution report for Plan 9 reviewer handoff.
- Scope boundary confirmation.

### Acceptance Criteria

- Automated tests were run and reported.
- Manual check was completed or safely blocked.
- Success and failure logging behavior is reported honestly.
- Out-of-scope work was not implemented.
- No secrets or fake success appear in the report.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_retrieval_agent.py -v`
- Manual `run_retrieval_agent` smoke check when setup is available.
- Safe `agent_steps` row verification when live Supabase setup is available.
- Scope and secret inspection.

### Explicit Non-Goals

- Do not fabricate live database validation.
- Do not create real provider keys, Supabase projects, Qdrant collections, documents, or agent runs on behalf of the user unless explicitly requested.
- Do not implement public chat, evidence, or agent log screens.
- Do not implement Agent 2, Agent 3, LangGraph, or final answer generation.

## Optional Future Tracks

No optional future tracks are part of the mandatory Plan 9 batch chain.

Agent 2 evidence verification, Agent 3 answer generation, LangGraph orchestration, `/api/chat/ask`, public agent log APIs, frontend evidence display, and verified chunk marking remain future work outside this task file unless a later approved plan explicitly includes them.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05

Optional future tracks are outside the mandatory dependency chain.

## Global Verification Checklist

- [ ] `docs/plans/Plan_9.md` remained the scope authority.
- [ ] No database schema changes were added.
- [ ] `backend/app/agents/__init__.py` was created.
- [ ] `backend/app/agents/schemas.py` defines Agent 1 input, candidate, and output schemas.
- [ ] `backend/app/agents/retrieval_agent.py` exposes `run_retrieval_agent`.
- [ ] `run_retrieval_agent` validates input with Pydantic before retrieval.
- [ ] Agent 1 calls the existing Plan 8 hybrid retrieval service instead of reimplementing retrieval.
- [ ] `RETRIEVAL_FINAL_TOP_K` is used or preserved as the Agent 1 default final candidate count.
- [ ] Agent 1 output includes all required candidate score components.
- [ ] Candidate ordering by `final_score` is preserved from hybrid retrieval.
- [ ] Successful runs write an `agent_steps` row with `step_name = "agent_1_retrieval"`.
- [ ] Failed retrieval runs write a failed `agent_steps` row when possible.
- [ ] Retrieval failures raise controlled `RetrievalAgentError`.
- [ ] Invalid input raises validation error before retrieval.
- [ ] Empty retrieval results return `candidates: []` with success status.
- [ ] Agent log insertion failure is visible and does not erase retrieval failure context.
- [ ] No Agent 2 verification logic was implemented.
- [ ] No Agent 3 answer generation logic was implemented.
- [ ] No LangGraph workflow was implemented.
- [ ] No `/api/chat/ask` endpoint was created.
- [ ] No final answer generation was added.
- [ ] Agent 1 does not mark chunks as verified.
- [ ] Backend-only secrets and provider settings stayed out of frontend code.
- [ ] `cd backend` then `pytest tests/test_retrieval_agent.py -v` was run and reported.
- [ ] Manual Agent 1 smoke check was completed or marked `BLOCKED_BY_USER_ACTION` with a safe reason.
- [ ] Execution report states whether `agent_steps` was verified through live database or mocked tests.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [x] Batch01 - Agent Package, Schemas, and Configuration Boundary
- [x] Batch02 - Agent Step Logging Service
- [x] Batch03 - Retrieval Agent Callable and Failure Handling
- [ ] Batch04 - Required Automated Tests
- [ ] Batch05 - Manual Validation, Reporting, and Scope Review

### Task IDs

#### Batch01

- [x] (01A): Create backend agents package
- [x] (01B): Define shared Agent 1 Pydantic schemas
- [x] (01C): Confirm backend-only retrieval and persistence configuration boundary

#### Batch02

- [x] (02A): Add Supabase helper for inserting agent step logs
- [x] (02B): Implement focused agent log service
- [x] (02C): Define safe log failure behavior

#### Batch03

- [x] (03A): Create retrieval agent module and controlled error type
- [x] (03B): Implement input validation and hybrid retrieval call
- [x] (03C): Convert hybrid candidates into validated Agent 1 output and log success
- [x] (03D): Implement retrieval failure handling and failed-step logging

#### Batch04

- [ ] (04A): Add Agent 1 schema validation tests
- [ ] (04B): Add successful retrieval and success-log tests
- [ ] (04C): Add empty result and retrieval failure tests
- [ ] (04D): Run required targeted automated validation

#### Batch05

- [ ] (05A): Run manual Agent 1 smoke check when live setup is available
- [ ] (05B): Complete execution report and scope boundary review

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
- reason: missing API key, missing Supabase credentials, missing applied migration, missing valid `agent_run_id`, missing processed indexed document, missing provider setup, missing manual setup, or other safe summary

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
