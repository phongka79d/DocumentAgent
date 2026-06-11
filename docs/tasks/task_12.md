# Plan 12 - LangGraph Full QA Workflow Execution Tasks

## Purpose

Create a detailed execution task file for the approved LangGraph full question-answering workflow milestone. This task file guides a future Execution Agent to connect Agent 1, Agent 2, and Agent 3 into one backend workflow, expose `/api/chat/ask`, persist chat messages and agent runs, provide evidence/log retrieval endpoints, add failure handling, run required tests, and report results for `docs/plans/Plan_12.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_12.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Current project context reviewed: `README.md`
- Conflict note: No architecture conflicts were found. `docs/plans/Master_Plan.md` aligns with Plan 12 on LangGraph orchestration order, chat ask response shape, evidence endpoint, logs endpoint, existing table names, backend-only secrets, single-user filtering, and debuggability. `README.md` confirms Agent 1, Agent 2, Agent 3, `agent_steps` logging, retrieval services, Supabase/Qdrant/ShopAIKey integration, and the initial database migration exist, while full agent run orchestration, chat APIs, evidence APIs, logs APIs, and frontend chat remain planned. `docs/plans/Plan_12.md` remains the scope authority for this task file.

## Source Section Index

- `docs/plans/Plan_12.md` > `## 1. Goal` -> full Agent 1 -> Agent 2 -> Agent 3 workflow, persistence, evidence/log retrieval, and testable API result.
- `docs/plans/Plan_12.md` > `## 2. Why This Plan Exists` -> orchestrate separate agents into a reliable backend QA contract before frontend chat.
- `docs/plans/Plan_12.md` > `## 3. Scope` -> required graph, API, persistence, evidence/log endpoints, failure handling, and tests.
- `docs/plans/Plan_12.md` > `## 4. Out of Scope` -> no frontend chat, streaming, conversation memory beyond storage, auth/JWT, multi-user, or document deletion.
- `docs/plans/Plan_12.md` > `## 5. Dependencies` -> completed Plans 9, 10, 11, and existing Plan 2 tables.
- `docs/plans/Plan_12.md` > `## 6. Required Files and Folders` -> expected graph, API, schema, service, router, test, and dependency files.
- `docs/plans/Plan_12.md` > `## 7. Data Model / Schema Changes` -> no table changes, existing tables, chat request/response, and LangGraph state shape.
- `docs/plans/Plan_12.md` > `## 8. API Design` -> `/api/chat/ask`, evidence endpoint, logs endpoint, validation, and error responses.
- `docs/plans/Plan_12.md` > `## 9. Implementation Steps` -> ordered implementation tasks from dependency checks through endpoint and tests.
- `docs/plans/Plan_12.md` > `## 10. Configuration and Environment Variables` -> backend-only `SINGLE_USER_ID`, Supabase settings, and downstream retrieval setting.
- `docs/plans/Plan_12.md` > `## 11. Required Tests` -> workflow tests, API tests, manual API checks, evidence/log checks, and failure checks.
- `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria` -> chat endpoint, run persistence, ordered workflow, step retrieval, messages, evidence, logs, and failed status behavior.
- `docs/plans/Plan_12.md` > `## 13. Failure Handling` -> empty question, unknown documents, agent failures, missing information, and log query failures.
- `docs/plans/Plan_12.md` > `## 14. Agent Report Requirement` -> required execution report contents and response examples.
- `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist` -> scope, tests, secrets, architecture, workflow order, single-user scoping, Agent 3 final answer, and Agent 2 evidence source.
- `docs/plans/Master_Plan.md` > `### 5.3 Chat With Document Page` -> backend must run Agent 1, Agent 2, then Agent 3 for chat.
- `docs/plans/Master_Plan.md` > `### 5.4 Evidence Viewer` -> evidence display needs file name, quoted text, score/status, and reason.
- `docs/plans/Master_Plan.md` > `### 5.5 Agent Logs / Debug Page` -> logs must include retrieval, verification, self-check, answer, confidence, errors, and timestamps.
- `docs/plans/Master_Plan.md` > `## Table: chat_sessions` -> approved chat session fields.
- `docs/plans/Master_Plan.md` > `## Table: chat_messages` -> approved chat message fields.
- `docs/plans/Master_Plan.md` > `## Table: agent_runs` -> approved run persistence fields.
- `docs/plans/Master_Plan.md` > `## Table: agent_steps` -> approved step log fields.
- `docs/plans/Master_Plan.md` > `# 9. Question Answering Workflow` -> required LangGraph order and insufficient evidence rule.
- `docs/plans/Master_Plan.md` > `## 13.4 Ask Question` -> planned `/api/chat/ask` contract.
- `docs/plans/Master_Plan.md` > `## 13.5 Get Evidence` -> planned evidence endpoint contract.
- `docs/plans/Master_Plan.md` > `## 13.6 Get Agent Logs` -> planned logs endpoint contract.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> backend-only environment and frontend secret boundary.
- `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure` -> expected graph, API, schema, service, and test file locations.
- `docs/plans/Master_Plan.md` > `## Phase 9: LangGraph Orchestration` -> workflow, step, run, final answer, and error-log acceptance.
- `docs/plans/Master_Plan.md` > `## 18.1 Grounding Rule` -> final answers must be grounded in verified chunks only.
- `docs/plans/Master_Plan.md` > `## 18.4 Missing Information Rule` -> insufficient evidence must be stated clearly.
- `docs/plans/Master_Plan.md` > `## 18.5 Debuggability Rule` -> every agent run must be traceable.
- `README.md` > `## Overview` -> current implementation status and planned full orchestration/API gap.
- `README.md` > `## Architecture` -> current backend layers and existing Agent 1/2/3 callables.
- `README.md` > `## Data, Storage, and External Services` -> existing Supabase tables, Qdrant behavior, and ShopAIKey boundaries.
- `README.md` > `## Configuration` -> backend `.env` behavior and backend-only setting requirements.
- `README.md` > `## Testing and Validation` -> current pytest conventions and targeted test expectations.
- `README.md` > `Important coordination rules` -> route wiring, secret boundaries, validation, and no fake completion claims.
- `README.md` > `## Known Gaps or Unclear Areas` -> full agent workflow orchestration, chat APIs, evidence APIs, and log APIs remain planned.

## Approved Architecture Summary

Plan 12 approves a backend-only LangGraph QA workflow for the single-user Document QA Agent MVP. The workflow must create an `agent_runs` row, run Agent 1 retrieval, Agent 2 evidence verification, and Agent 3 answer generation/self-check in order, persist each agent step through the existing `agent_steps` path, persist user and assistant chat messages, update the agent run with final answer/confidence or safe failure status, and expose the result through `POST /api/chat/ask`.

The approved graph path is `START -> Agent 1 -> Agent 2 -> Agent 3 -> Self-check -> FINAL`. Agent 3 already owns self-check behavior, so the graph implementation must preserve that logical path without inventing a separate unsupported public agent. Final answers must come from Agent 3 output only. Evidence retrieval must read Agent 2 output from persisted `agent_steps`, not unverified retrieval candidates. Logs retrieval must return ordered persisted steps for one `agent_run_id`.

Plan 12 does not approve database table changes. It uses the existing `chat_sessions`, `chat_messages`, `agent_runs`, and `agent_steps` tables from Plan 2. All run/session/message/document lookups and writes must remain scoped to `SINGLE_USER_ID`. Backend-only secrets and Supabase service role access must stay in backend code. The frontend chat UI, streaming, authentication/JWT, multi-user behavior, document deletion, and conversation memory beyond stored chat messages are explicitly out of scope.

## Global Implementation Rules

- Keep `docs/plans/Plan_12.md` as the source of truth for scope, API contracts, workflow order, persistence, validation, tests, failure handling, and out-of-scope boundaries.
- Use `docs/plans/Master_Plan.md` only to clarify the target LangGraph architecture, table meanings, API shapes, grounding/debuggability rules, and expected project structure.
- Use `README.md` only to understand current code state: Agent 1, Agent 2, Agent 3, `agent_steps` logging, retrieval services, Supabase/Qdrant/ShopAIKey helpers, and migrations exist, but full orchestration and public chat/evidence/log APIs do not.
- Depend on completed Plan 9 Agent 1, Plan 10 Agent 2, Plan 11 Agent 3, and Plan 2 database tables; do not reimplement retrieval, verification, answer generation, or database migrations unless required to integrate the approved workflow.
- Do not add or modify database table schemas in this plan.
- Register new FastAPI routers in `backend/app/main.py`; creating route files alone is not enough.
- Validate all selected `document_ids` before workflow execution and ensure every selected document belongs to `SINGLE_USER_ID`.
- Keep all `chat_sessions`, `chat_messages`, `agent_runs`, `agent_steps`, and document access scoped by `SINGLE_USER_ID`.
- Persist a user message before workflow execution and an assistant message after successful final answer generation.
- Create `agent_runs` with status `running` before invoking the graph; update to `success` or `failed` with safe public details.
- Evidence endpoint must read Agent 2 verification output from `agent_steps`; it must not return unverified Agent 1 candidates as verified evidence.
- Logs endpoint must read all `agent_steps` for the run ordered by `created_at`.
- Empty questions, invalid document selections, unknown sessions, agent failures, log query failures, and missing-information outcomes must map to controlled responses without leaking secrets, raw provider errors, or stack traces.
- Use `.env.example` for placeholder names only and never commit real secrets.
- Do not implement frontend chat UI, streaming responses, JWT/auth, multi-user support, document deletion, or conversation memory beyond stored messages.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, schemas, settings, services, routers, tests, and errors.
- Keep functions, services, graph nodes, schemas, and route handlers focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, LangGraph, service-layer, and provider-client conventions already present in the backend.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless Plan 12 explicitly requires them.
- Add comments only where they clarify a non-obvious workflow, persistence, error mapping, or serialization decision.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Avoid adding formatters, linters, frameworks, or architecture changes outside Plan 12 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Workflow Contracts, Dependencies, and API Schemas
- Batch02 - Chat and Agent Run Persistence Services
- Batch03 - LangGraph Workflow Orchestration
- Batch04 - Public Chat, Evidence, and Logs APIs
- Batch05 - Failure Handling and Single-User Safety
- Batch06 - Required Automated Tests
- Batch07 - Manual Validation, Reporting, and Scope Review

## Mandatory Batch01 - Workflow Contracts, Dependencies, and API Schemas

### Goal

Prepare the backend contracts required by the full QA workflow before persistence, graph orchestration, and public routes are wired.

### Why this batch exists

The workflow must have stable request/response schemas, graph state shape, dependency availability, and output contracts before the Execution Agent connects long-running persistence and agent orchestration behavior.

### Inputs / Dependencies

- `docs/plans/Plan_12.md`
- `docs/plans/Master_Plan.md`
- `README.md`
- Completed Plan 9 Agent 1 callable and schemas
- Completed Plan 10 Agent 2 callable and schemas
- Completed Plan 11 Agent 3 callable and schemas
- Existing Plan 2 tables from `backend/app/db/migrations/001_initial_schema.sql`

### Tasks

- [ ] (01A): Confirm LangGraph dependency and backend import boundary
  - Source of Truth: `docs/plans/Plan_12.md` > `## 3. Scope`; `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## Phase 9: LangGraph Orchestration`
  - Source Requirements:
    - Create LangGraph workflow in `backend/app/agents/graph.py`.
    - Add LangGraph dependency if not already present.
    - Workflow must connect Agent 1, Agent 2, and Agent 3.
  - Details: Inspect `backend/requirements.txt` and current imports. Add the LangGraph package only if missing. Keep the dependency backend-only and avoid changing unrelated dependencies.
  - Dependencies: Completed Plans 9, 10, and 11.
  - User Action: None.
  - Agent Work: Verify dependency availability, update `backend/requirements.txt` if needed, and prepare imports for `backend/app/agents/graph.py`.
  - Output: LangGraph dependency ready for backend workflow code.
  - Acceptance: Backend can import the LangGraph workflow primitives required by the implementation.
  - Validation: Run a targeted import smoke check or include dependency import in workflow tests.
  - Blocked Condition: None unless package installation or dependency resolution fails locally; report the exact dependency issue safely.
  - Files: `backend/requirements.txt`, `backend/app/agents/graph.py`

- [ ] (01B): Add chat API request and response schemas
  - Source of Truth: `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Master_Plan.md` > `## 13.4 Ask Question`
  - Source Requirements:
    - `backend/app/schemas/chat.py` contains chat request and answer response schemas.
    - Request includes nullable or omitted `session_id`, non-empty `question`, and `document_ids`.
    - Response includes `answer`, `confidence`, `citations`, and `agent_run_id`.
  - Details: Use Pydantic schemas consistent with existing backend API schema style. Validate UUID fields where the current codebase expects UUIDs, and keep public response names exactly aligned with Plan 12.
  - Dependencies: None.
  - User Action: None.
  - Agent Work: Create or extend chat schemas for `/api/chat/ask`, citation response objects, and response serialization.
  - Output: Typed chat request and answer response models.
  - Acceptance: Empty or whitespace-only questions can be rejected; `document_ids` are UUID-validated; response model matches Plan 12 field names.
  - Validation: Schema tests in `backend/tests/test_chat_api.py` or direct route tests once Batch06 exists.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/chat.py`, `backend/tests/test_chat_api.py`

- [ ] (01C): Add agent run evidence and logs response schemas
  - Source of Truth: `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Master_Plan.md` > `## 13.5 Get Evidence`; `docs/plans/Master_Plan.md` > `## 13.6 Get Agent Logs`
  - Source Requirements:
    - `backend/app/schemas/agent_runs.py` contains evidence and logs response schemas.
    - Evidence response contains `verified_chunks` and `rejected_chunks`.
    - Logs response contains `agent_run_id` and ordered step entries.
  - Details: Reuse existing Agent 2 verification schema shapes when practical. Logs must expose safe JSON-serializable inputs/outputs/status/timestamps without leaking backend secrets or stack traces.
  - Dependencies: Completed Plan 10 schemas and existing `agent_steps` table contract.
  - User Action: None.
  - Agent Work: Create response models for evidence and logs endpoints, including step output objects.
  - Output: Typed agent run evidence and logs response models.
  - Acceptance: Evidence and logs route handlers can return validated response bodies matching Plan 12.
  - Validation: API tests in `backend/tests/test_agent_runs_api.py`.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/agent_runs.py`, `backend/tests/test_agent_runs_api.py`

- [ ] (01D): Define workflow state schema and graph callable contract
  - Source of Truth: `docs/plans/Plan_12.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 9. Question Answering Workflow`
  - Source Requirements:
    - LangGraph state includes `agent_run_id`, `session_id`, `question`, `document_ids`, `retrieval`, `verification`, `answer`, and `error`.
    - Implement `run_qa_workflow(question, document_ids, session_id=None)`.
    - Compile graph with Agent 1, Agent 2, and Agent 3 in order.
  - Details: Define a typed state model or TypedDict in `backend/app/agents/graph.py` that can carry existing Agent 1, Agent 2, and Agent 3 outputs without lossy conversions. Keep state internal to the backend workflow.
  - Dependencies: (01A), completed agent callable contracts.
  - User Action: None.
  - Agent Work: Add workflow state shape and a public backend callable signature for `run_qa_workflow`.
  - Output: Stable internal workflow contract ready for graph implementation.
  - Acceptance: Workflow tests can construct state and assert transitions with mocked agents.
  - Validation: `cd backend` then `pytest tests/test_langgraph_workflow.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/graph.py`, `backend/tests/test_langgraph_workflow.py`

- [ ] (01E): Confirm out-of-scope and backend-only boundaries before implementation
  - Source of Truth: `docs/plans/Plan_12.md` > `## 4. Out of Scope`; `docs/plans/Plan_12.md` > `## 10. Configuration and Environment Variables`; `README.md` > `Important coordination rules`; `README.md` > `## Known Gaps or Unclear Areas`
  - Source Requirements:
    - Do not build frontend chat UI.
    - Do not add streaming responses, JWT/auth, multi-user support, document deletion, or extra conversation memory.
    - Keep `SINGLE_USER_ID`, Supabase service role, and provider credentials backend-only.
  - Details: Treat this as an implementation guardrail. If the Execution Agent discovers nearby frontend or auth code, it must leave it unchanged unless Plan 12 directly requires a backend integration point.
  - Dependencies: None.
  - User Action: None.
  - Agent Work: Review planned files and record boundaries in the execution report.
  - Output: Explicit scope guardrails for later batches.
  - Acceptance: Later implementation touches only Plan 12 backend workflow/API/test/report/task artifacts.
  - Validation: Scope review in Batch07.
  - Blocked Condition: None.
  - Files: `docs/reports/report_12_execute_agent.md`

### Files or Modules Likely Created or Updated

- `backend/requirements.txt`
- `backend/app/schemas/chat.py`
- `backend/app/schemas/agent_runs.py`
- `backend/app/agents/graph.py`
- `backend/tests/test_langgraph_workflow.py`
- `backend/tests/test_chat_api.py`
- `backend/tests/test_agent_runs_api.py`

### Required Outputs / Artifacts

- LangGraph dependency confirmed or added.
- Chat request/response schemas.
- Agent run evidence/log response schemas.
- Internal workflow state and callable contract.
- Explicit scope boundaries for the execution report.

### Acceptance Criteria

- Schema field names match Plan 12 API contracts.
- Workflow state can carry all required IDs, inputs, intermediate agent outputs, final answer, and errors.
- No frontend, auth, streaming, document deletion, or schema migration work is introduced.

### Required Tests or Validations

- Targeted schema/API tests once Batch06 is implemented.
- Targeted LangGraph workflow tests once Batch06 is implemented.
- Import smoke check for LangGraph primitives.

### Explicit Non-Goals

- Do not implement route handlers in Batch01 beyond what is needed for schema import compatibility.
- Do not call live agents, Supabase, Qdrant, or ShopAIKey in schema tests.
- Do not implement frontend screens.

## Mandatory Batch02 - Chat and Agent Run Persistence Services

### Goal

Implement the service-layer persistence needed to create or fetch sessions, store chat messages, create/update agent runs, validate selected documents, and retrieve evidence/log data.

### Why this batch exists

The graph and API must persist all required state safely and consistently. Centralizing persistence behind service helpers keeps route handlers and graph nodes thin and preserves single-user filtering.

### Inputs / Dependencies

- Batch01 schemas and contracts
- Existing Supabase service patterns
- Existing Plan 2 tables: `chat_sessions`, `chat_messages`, `agent_runs`, `agent_steps`
- Existing document ownership metadata in `documents`
- Existing Agent 1/2/3 step logging behavior

### Tasks

- [ ] (02A): Add Supabase helpers for chat sessions and messages
  - Source of Truth: `docs/plans/Plan_12.md` > `## 3. Scope`; `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Master_Plan.md` > `## Table: chat_sessions`; `docs/plans/Master_Plan.md` > `## Table: chat_messages`
  - Source Requirements:
    - Add chat session and message persistence.
    - Use existing `chat_sessions` and `chat_messages` tables.
    - If `session_id` is omitted, create a new chat session.
  - Details: Extend `backend/app/services/supabase_service.py` with helper methods for creating sessions, fetching sessions for `SINGLE_USER_ID`, and inserting user/assistant messages with metadata.
  - Dependencies: Existing Supabase service conventions.
  - User Action: None.
  - Agent Work: Add safe, testable persistence helper contracts without committing secrets.
  - Output: Supabase service methods for chat session/message persistence.
  - Acceptance: Helpers always include `SINGLE_USER_ID` ownership and return normalized data needed by `chat_service.py`.
  - Validation: Mocked service tests through `backend/tests/test_chat_api.py` or dedicated service tests if current repo patterns support them.
  - Blocked Condition: None.
  - Files: `backend/app/services/supabase_service.py`, backend tests

- [ ] (02B): Add Supabase helpers for agent runs and agent steps lookup
  - Source of Truth: `docs/plans/Plan_12.md` > `## 3. Scope`; `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Master_Plan.md` > `## Table: agent_runs`; `docs/plans/Master_Plan.md` > `## Table: agent_steps`
  - Source Requirements:
    - Persist `agent_runs`.
    - Persist and retrieve `agent_steps` from each agent.
    - Add helpers for `agent_runs` and `agent_steps` queries.
  - Details: Add helper methods for inserting an agent run, updating success/failure, fetching a run for `SINGLE_USER_ID`, and listing ordered steps for a run. Preserve existing Agent 1/2/3 log insertion path unless a small compatible adapter is required.
  - Dependencies: Existing `agent_steps` logging service and Supabase service.
  - User Action: None.
  - Agent Work: Implement backend persistence helper methods with safe error surfaces.
  - Output: Supabase service methods for run lifecycle and step lookup.
  - Acceptance: Run and step helpers scope by `SINGLE_USER_ID`; ordered step lookup is deterministic by `created_at`.
  - Validation: Mocked tests for run creation/update and step lookup behavior.
  - Blocked Condition: None.
  - Files: `backend/app/services/supabase_service.py`, backend tests

- [ ] (02C): Create chat service for session and message orchestration
  - Source of Truth: `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - `chat_service.py` handles chat session, chat message, and agent run persistence.
    - Create or fetch chat sessions.
    - Persist user and assistant messages.
  - Details: Implement service functions that validate an optional `session_id`, create a session when omitted, persist the user question before workflow execution, and persist assistant content after successful workflow completion.
  - Dependencies: (02A), (02B).
  - User Action: None.
  - Agent Work: Create `backend/app/services/chat_service.py` using Supabase helper boundaries and typed schemas.
  - Output: Chat persistence orchestration service.
  - Acceptance: Existing session lookup returns 404-safe failure if not owned by `SINGLE_USER_ID`; omitted session creates a new session; user/assistant messages are stored with safe metadata.
  - Validation: Mocked route or service tests in `backend/tests/test_chat_api.py`.
  - Blocked Condition: None.
  - Files: `backend/app/services/chat_service.py`, `backend/tests/test_chat_api.py`

- [ ] (02D): Create agent run service for lifecycle, evidence, and logs
  - Source of Truth: `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - `agent_run_service.py` handles run creation, update, evidence lookup, and logs lookup.
    - Create `agent_runs` row with status `running` before graph invocation.
    - Mark run `success` with final answer/confidence or `failed` with safe error.
    - Evidence endpoint reads Agent 2 output from `agent_steps`.
  - Details: Encapsulate status transitions and evidence extraction so route handlers do not parse raw step rows directly. Evidence lookup must identify the Agent 2 verification step by step name or agent name matching existing logging conventions.
  - Dependencies: (02B), completed Agent 2 logging behavior.
  - User Action: None.
  - Agent Work: Create lifecycle and lookup service methods with controlled errors for not-found, invalid step data, and dependency failure cases.
  - Output: Agent run service ready for graph and API use.
  - Acceptance: Service can create/update runs, fetch evidence from Agent 2 output, and fetch ordered logs for one owned run.
  - Validation: Mocked tests in `backend/tests/test_agent_runs_api.py` and workflow tests.
  - Blocked Condition: None.
  - Files: `backend/app/services/agent_run_service.py`, `backend/tests/test_agent_runs_api.py`

- [ ] (02E): Add selected document ownership validation
  - Source of Truth: `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Plan_12.md` > `## 13. Failure Handling`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - `document_ids` must be valid UUIDs.
    - All selected documents must belong to `SINGLE_USER_ID`.
    - Unknown selected document returns 404 or 400 before workflow starts.
  - Details: Add a helper in the appropriate service layer to validate all selected document IDs before creating or invoking the agent workflow. Reuse existing document metadata helpers where possible.
  - Dependencies: Existing document metadata persistence.
  - User Action: None.
  - Agent Work: Add document ownership lookup and validation behavior.
  - Output: Safe pre-workflow selected document validation.
  - Acceptance: Invalid/missing documents fail before agent run execution; selected documents are constrained to `SINGLE_USER_ID`.
  - Validation: API tests for unknown document and not-owned document behavior.
  - Blocked Condition: None.
  - Files: `backend/app/services/chat_service.py`, `backend/app/services/supabase_service.py`, `backend/tests/test_chat_api.py`

- [ ] (02F): Define controlled service errors for API mapping
  - Source of Truth: `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Plan_12.md` > `## 13. Failure Handling`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - Empty question returns 400.
    - Unknown session returns 404.
    - Workflow failure returns 500.
    - Log query failure returns 500 with safe public message.
  - Details: Add small typed exceptions or reuse existing project exception patterns so API routes can map validation, not-found, dependency, and workflow failures without broad exception leaks.
  - Dependencies: (02C), (02D), (02E).
  - User Action: None.
  - Agent Work: Add controlled error types and safe messages for chat and agent run services.
  - Output: Predictable service error taxonomy.
  - Acceptance: Route handlers can map errors to Plan 12 HTTP responses without exposing raw provider/database details.
  - Validation: API error-path tests.
  - Blocked Condition: None.
  - Files: `backend/app/services/chat_service.py`, `backend/app/services/agent_run_service.py`, backend tests

### Files or Modules Likely Created or Updated

- `backend/app/services/supabase_service.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/agent_run_service.py`
- `backend/tests/test_chat_api.py`
- `backend/tests/test_agent_runs_api.py`
- Related service tests if current repo patterns require them

### Required Outputs / Artifacts

- Chat session/message persistence helpers.
- Agent run lifecycle helpers.
- Evidence and logs lookup helpers.
- Selected document ownership validation.
- Controlled service errors for API mapping.

### Acceptance Criteria

- All persistence helpers scope data by `SINGLE_USER_ID`.
- User question and assistant answer persistence can be coordinated around the workflow.
- Agent runs can transition from `running` to `success` or `failed`.
- Evidence lookup is based on Agent 2 persisted step output.
- Logs lookup returns ordered persisted steps.

### Required Tests or Validations

- Mocked chat API/service tests for session creation, existing session, message writes, and document validation.
- Mocked agent run API/service tests for run lifecycle, evidence lookup, logs lookup, and not-found cases.

### Explicit Non-Goals

- Do not add database migrations or table schema changes.
- Do not store conversation memory beyond the Plan 12 chat message rows.
- Do not change existing Agent 1/2/3 core behavior except for integration compatibility.

## Mandatory Batch03 - LangGraph Workflow Orchestration

### Goal

Implement `backend/app/agents/graph.py` so one backend callable creates an agent run, invokes Agent 1, Agent 2, and Agent 3 in the required order, persists run status, and returns the final answer contract.

### Why this batch exists

Plan 12's central milestone is the full backend QA workflow. The graph must prove that existing agent callables work together and that agent run state is persisted correctly across success, insufficient-evidence, and failure paths.

### Inputs / Dependencies

- Batch01 workflow state and schema contracts
- Batch02 persistence services
- Existing `run_retrieval_agent`
- Existing `run_verification_agent`
- Existing `run_answer_agent`
- Existing `agent_steps` logging behavior

### Tasks

- [ ] (03A): Implement LangGraph node for Agent 1 retrieval
  - Source of Truth: `docs/plans/Plan_12.md` > `## 1. Goal`; `docs/plans/Plan_12.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 9. Question Answering Workflow`
  - Source Requirements:
    - Workflow runs Agent 1 first.
    - State includes `retrieval`.
    - Agent steps are persisted.
  - Details: Create a graph node that calls the existing Agent 1 retrieval callable using the current agent input schema. Pass `agent_run_id`, question, and selected `document_ids` as required by the existing callable.
  - Dependencies: Batch01, existing Agent 1 callable.
  - User Action: None.
  - Agent Work: Add Agent 1 graph node and state update behavior.
  - Output: State transition from question/document IDs to retrieval output.
  - Acceptance: Mocked workflow test proves Agent 1 is called before Agent 2 and its output is stored in state.
  - Validation: `cd backend` then `pytest tests/test_langgraph_workflow.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/graph.py`, `backend/tests/test_langgraph_workflow.py`

- [ ] (03B): Implement LangGraph node for Agent 2 verification
  - Source of Truth: `docs/plans/Plan_12.md` > `## 1. Goal`; `docs/plans/Plan_12.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 9. Question Answering Workflow`
  - Source Requirements:
    - Workflow runs Agent 2 after Agent 1.
    - State includes `verification`.
    - Agent 2 missing information still allows Agent 3 safe answer behavior.
  - Details: Create a graph node that converts Agent 1 output into the existing Agent 2 verification callable input without dropping candidate evidence fields needed by Agent 2.
  - Dependencies: (03A), existing Agent 2 callable.
  - User Action: None.
  - Agent Work: Add Agent 2 graph node and state update behavior.
  - Output: State transition from retrieval output to verification output.
  - Acceptance: Mocked workflow test proves Agent 2 receives Agent 1 output and updates state before Agent 3.
  - Validation: `cd backend` then `pytest tests/test_langgraph_workflow.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/graph.py`, `backend/tests/test_langgraph_workflow.py`

- [ ] (03C): Implement LangGraph node for Agent 3 answer and self-check
  - Source of Truth: `docs/plans/Plan_12.md` > `## 1. Goal`; `docs/plans/Plan_12.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `# 9. Question Answering Workflow`
  - Source Requirements:
    - Workflow runs Agent 3 after Agent 2.
    - Agent 3 contains the self-check, matching `START -> Agent 1 -> Agent 2 -> Agent 3 -> Self-check -> FINAL`.
    - Final answers come from Agent 3 output.
  - Details: Create a graph node that passes Agent 2 verification output to the existing Agent 3 answer callable. Do not bypass Agent 3 self-check or synthesize the final answer in the graph layer.
  - Dependencies: (03B), existing Agent 3 callable.
  - User Action: None.
  - Agent Work: Add Agent 3 graph node and state update behavior.
  - Output: State transition from verification output to final answer output.
  - Acceptance: Mocked workflow test proves final response comes from Agent 3 output and self-check path is represented through Agent 3.
  - Validation: `cd backend` then `pytest tests/test_langgraph_workflow.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/graph.py`, `backend/tests/test_langgraph_workflow.py`

- [ ] (03D): Compile graph in required order
  - Source of Truth: `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `# 9. Question Answering Workflow`
  - Source Requirements:
    - Define LangGraph workflow `START -> Agent 1 -> Agent 2 -> Agent 3 -> Self-check -> FINAL`.
    - Compile graph with order `START -> Agent 1 -> Agent 2 -> Agent 3 -> FINAL`.
    - Workflow runs Agent 1, Agent 2, and Agent 3 in order.
  - Details: Use LangGraph primitives to connect nodes sequentially. If Agent 3 self-check is internal to `run_answer_agent`, document the logical self-check in code/test naming without adding unsupported extra public behavior.
  - Dependencies: (03A), (03B), (03C).
  - User Action: None.
  - Agent Work: Build and compile the graph and expose a reusable graph runner.
  - Output: Compiled LangGraph workflow.
  - Acceptance: Workflow tests assert call order and state flow across all three agents.
  - Validation: `cd backend` then `pytest tests/test_langgraph_workflow.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/graph.py`, `backend/tests/test_langgraph_workflow.py`

- [ ] (03E): Implement `run_qa_workflow` lifecycle orchestration
  - Source of Truth: `docs/plans/Plan_12.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Implement `run_qa_workflow(question, document_ids, session_id=None)`.
    - Create `agent_runs` row with status `running` before invoking graph.
    - On success, update `agent_runs` with status `success`, final answer, and confidence.
    - On failure, update `agent_runs` with status `failed` and error message.
  - Details: Coordinate agent run creation/update through `agent_run_service.py`. Ensure failure after run creation always attempts to mark the run failed with a safe error message.
  - Dependencies: Batch02, (03D).
  - User Action: None.
  - Agent Work: Implement orchestration wrapper and return a response-ready workflow result.
  - Output: Backend callable that executes the full QA workflow and persists run lifecycle.
  - Acceptance: One workflow call creates one run, updates success/failure, and returns Agent 3 final answer fields plus `agent_run_id`.
  - Validation: Mocked workflow lifecycle tests in `backend/tests/test_langgraph_workflow.py`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/graph.py`, `backend/tests/test_langgraph_workflow.py`

- [ ] (03F): Preserve insufficient-evidence behavior through the workflow
  - Source of Truth: `docs/plans/Plan_12.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `# 9. Question Answering Workflow`; `docs/plans/Master_Plan.md` > `## 18.4 Missing Information Rule`
  - Source Requirements:
    - Agent 2 missing information should still allow Agent 3 to return safe insufficient-evidence answer.
    - If evidence is insufficient, the system must say so clearly.
  - Details: Ensure the graph does not treat Agent 2 `missing_information=true` as a workflow failure. Agent 3 should receive the verification output and return its safe insufficient-evidence response.
  - Dependencies: (03B), (03C), existing Agent 3 insufficient-evidence behavior.
  - User Action: None.
  - Agent Work: Add state handling and tests for the missing-information path.
  - Output: Safe insufficient-evidence workflow path.
  - Acceptance: Workflow returns a safe answer and marks run success when Agent 3 successfully handles missing information.
  - Validation: Mocked workflow test for Agent 2 missing-information true.
  - Blocked Condition: None.
  - Files: `backend/app/agents/graph.py`, `backend/tests/test_langgraph_workflow.py`

### Files or Modules Likely Created or Updated

- `backend/app/agents/graph.py`
- `backend/tests/test_langgraph_workflow.py`
- `backend/app/services/agent_run_service.py` if lifecycle adjustments are needed

### Required Outputs / Artifacts

- Compiled LangGraph workflow.
- `run_qa_workflow(question, document_ids, session_id=None)` backend callable.
- Sequential node handling for Agent 1, Agent 2, and Agent 3.
- Success, failure, and insufficient-evidence lifecycle behavior.

### Acceptance Criteria

- Workflow order is Agent 1, then Agent 2, then Agent 3.
- Agent run is created before graph execution.
- Agent run status is updated to `success` or `failed`.
- Final answer and confidence are stored from Agent 3 output.
- Agent 2 missing information produces safe Agent 3 output instead of graph failure.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_langgraph_workflow.py -v`

### Explicit Non-Goals

- Do not add streaming or async background workflow behavior unless already required by existing app patterns.
- Do not implement a new answer generator in the graph layer.
- Do not change Agent 1/2/3 standalone contracts beyond small integration adapters.

## Mandatory Batch04 - Public Chat, Evidence, and Logs APIs

### Goal

Expose the full workflow through backend API routes and register those routes in the FastAPI application.

### Why this batch exists

Plan 12 is testable only when an API request can run the workflow and when evidence/log data can be retrieved by `agent_run_id`.

### Inputs / Dependencies

- Batch01 schemas
- Batch02 services
- Batch03 workflow callable
- Existing FastAPI router patterns
- Existing `backend/app/main.py` application factory

### Tasks

- [ ] (04A): Implement `POST /api/chat/ask`
  - Source of Truth: `docs/plans/Plan_12.md` > `## 1. Goal`; `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 13.4 Ask Question`
  - Source Requirements:
    - Add `POST /api/chat/ask`.
    - Request body includes nullable `session_id`, `question`, and `document_ids`.
    - Response body includes `answer`, `confidence`, `citations`, and `agent_run_id`.
    - One question creates an `agent_runs` row and stores messages.
  - Details: Create `backend/app/api/chat.py` with a thin FastAPI route that validates request schema, delegates session/message setup and document validation to services, runs `run_qa_workflow`, and returns the response schema.
  - Dependencies: Batch02, Batch03.
  - User Action: None.
  - Agent Work: Implement chat route and error mapping.
  - Output: Working `/api/chat/ask` route module.
  - Acceptance: API test can post a question and receive the expected response shape with `agent_run_id`.
  - Validation: `cd backend` then `pytest tests/test_chat_api.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/api/chat.py`, `backend/tests/test_chat_api.py`

- [ ] (04B): Register chat router in FastAPI app
  - Source of Truth: `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - `backend/app/main.py` includes chat router.
    - Adding a router file alone does not expose it.
  - Details: Follow existing router registration style in `backend/app/main.py`. Use `/api/chat` prefix if route path is defined as `/ask`, or define path consistently so the final mounted URL is `/api/chat/ask`.
  - Dependencies: (04A).
  - User Action: None.
  - Agent Work: Wire chat router into app creation.
  - Output: Mounted chat API route.
  - Acceptance: FastAPI route exists at `POST /api/chat/ask` in tests.
  - Validation: Route-level API test in `backend/tests/test_chat_api.py`.
  - Blocked Condition: None.
  - Files: `backend/app/main.py`, `backend/tests/test_chat_api.py`

- [ ] (04C): Implement `GET /api/agent-runs/{agent_run_id}/evidence`
  - Source of Truth: `docs/plans/Plan_12.md` > `## 1. Goal`; `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 13.5 Get Evidence`
  - Source Requirements:
    - Add evidence endpoint by `agent_run_id`.
    - Response contains `verified_chunks` and `rejected_chunks`.
    - Evidence endpoint reads Agent 2 output from `agent_steps`, not unverified retrieval candidates.
    - Missing run returns 404 for `SINGLE_USER_ID`.
  - Details: Create `backend/app/api/agent_runs.py` and delegate evidence lookup to `agent_run_service.py`. Keep response payload close to Agent 2 output while preserving safe serialization.
  - Dependencies: Batch02 evidence lookup service.
  - User Action: None.
  - Agent Work: Implement evidence route and not-found/error mapping.
  - Output: Working evidence endpoint.
  - Acceptance: API test returns verified/rejected chunks from mocked Agent 2 step output and returns 404 for unknown run.
  - Validation: `cd backend` then `pytest tests/test_agent_runs_api.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/api/agent_runs.py`, `backend/tests/test_agent_runs_api.py`

- [ ] (04D): Implement `GET /api/agent-runs/{agent_run_id}/logs`
  - Source of Truth: `docs/plans/Plan_12.md` > `## 1. Goal`; `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## 13.6 Get Agent Logs`; `docs/plans/Master_Plan.md` > `## 18.5 Debuggability Rule`
  - Source Requirements:
    - Add logs endpoint by `agent_run_id`.
    - Response contains `agent_run_id` and ordered `steps`.
    - Logs endpoint reads all `agent_steps` for the run ordered by `created_at`.
  - Details: Delegate ordered step lookup to `agent_run_service.py`. Ensure raw inputs/outputs are JSON-serializable and safe for debug use.
  - Dependencies: Batch02 logs lookup service.
  - User Action: None.
  - Agent Work: Implement logs route and error mapping.
  - Output: Working logs endpoint.
  - Acceptance: API test returns steps in `created_at` order and includes agent name, input, output, status, and timestamp.
  - Validation: `cd backend` then `pytest tests/test_agent_runs_api.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/api/agent_runs.py`, `backend/tests/test_agent_runs_api.py`

- [ ] (04E): Register agent run router in FastAPI app
  - Source of Truth: `docs/plans/Plan_12.md` > `## 6. Required Files and Folders`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - `backend/app/main.py` includes `agent_runs` router.
    - Evidence and logs endpoints are reachable under `/api/agent-runs`.
  - Details: Follow existing app routing style and ensure final route paths are exactly `/api/agent-runs/{agent_run_id}/evidence` and `/api/agent-runs/{agent_run_id}/logs`.
  - Dependencies: (04C), (04D).
  - User Action: None.
  - Agent Work: Wire agent run router into app creation.
  - Output: Mounted evidence and logs APIs.
  - Acceptance: FastAPI route tests can call both endpoints through the application.
  - Validation: Route-level tests in `backend/tests/test_agent_runs_api.py`.
  - Blocked Condition: None.
  - Files: `backend/app/main.py`, `backend/tests/test_agent_runs_api.py`

### Files or Modules Likely Created or Updated

- `backend/app/api/chat.py`
- `backend/app/api/agent_runs.py`
- `backend/app/main.py`
- `backend/tests/test_chat_api.py`
- `backend/tests/test_agent_runs_api.py`

### Required Outputs / Artifacts

- Mounted `POST /api/chat/ask`.
- Mounted `GET /api/agent-runs/{agent_run_id}/evidence`.
- Mounted `GET /api/agent-runs/{agent_run_id}/logs`.
- API responses matching Plan 12 schemas.

### Acceptance Criteria

- `/api/chat/ask` exists and returns final answer, confidence, citations, and `agent_run_id`.
- Evidence endpoint returns Agent 2 verified and rejected chunks.
- Logs endpoint returns ordered agent steps.
- Unknown run/session cases return safe not-found errors.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_chat_api.py tests/test_agent_runs_api.py -v`

### Explicit Non-Goals

- Do not build frontend pages for chat, evidence, or logs.
- Do not add streaming endpoints.
- Do not expose backend-only secrets or service-role behavior through responses.

## Mandatory Batch05 - Failure Handling and Single-User Safety

### Goal

Harden validation, failure paths, and single-user data boundaries across workflow, persistence, and API routes.

### Why this batch exists

The full workflow crosses agents, persistence, and API routes. Failure behavior must be explicit so the API does not return fake success, leak internals, or read/write another user's data.

### Inputs / Dependencies

- Batch02 services
- Batch03 workflow
- Batch04 APIs
- Existing settings and `SINGLE_USER_ID` behavior
- Existing Agent 1/2/3 controlled error behavior

### Tasks

- [ ] (05A): Enforce chat request validation and selected-document errors
  - Source of Truth: `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Plan_12.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Empty question returns HTTP 400.
    - Selected document list is empty returns HTTP 400 if explicit selection is required.
    - Unknown selected document returns HTTP 404 or HTTP 400 before workflow starts.
    - `document_ids` must be valid UUIDs.
  - Details: Map validation errors consistently. If the implementation requires explicit document selection, enforce non-empty `document_ids` before workflow start. Do not create an agent run for invalid requests that fail before workflow execution.
  - Dependencies: Batch04 chat API.
  - User Action: None.
  - Agent Work: Add validation behavior and tests for request failures.
  - Output: Safe pre-workflow validation.
  - Acceptance: Invalid requests return controlled errors and do not invoke agents.
  - Validation: `cd backend` then `pytest tests/test_chat_api.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/api/chat.py`, `backend/app/services/chat_service.py`, `backend/tests/test_chat_api.py`

- [ ] (05B): Enforce session, document, run, message, and step scoping by `SINGLE_USER_ID`
  - Source of Truth: `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Plan_12.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - All selected documents must belong to `SINGLE_USER_ID`.
    - Unknown `session_id` not found for `SINGLE_USER_ID` returns 404.
    - Reviewer must confirm all run/session/message queries are scoped by `SINGLE_USER_ID`.
  - Details: Audit query helpers and service calls for ownership filters. Agent step lookup should be tied to an agent run that belongs to `SINGLE_USER_ID`, not only to a raw run ID.
  - Dependencies: Batch02, Batch04.
  - User Action: None.
  - Agent Work: Add or tighten filters, tests, and report notes for single-user scoping.
  - Output: Single-user-safe persistence and retrieval behavior.
  - Acceptance: Tests prove not-owned session/document/run data is not accepted or returned.
  - Validation: API/service tests and scope review in Batch07.
  - Blocked Condition: None.
  - Files: `backend/app/services/supabase_service.py`, `backend/app/services/chat_service.py`, `backend/app/services/agent_run_service.py`, backend tests

- [ ] (05C): Mark agent failures as failed runs with safe errors
  - Source of Truth: `docs/plans/Plan_12.md` > `## 9. Implementation Steps`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_12.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Agent 1 failure marks run failed.
    - Agent 2 failure marks run failed.
    - Agent 3 failure marks run failed.
    - Workflow failure returns HTTP 500.
    - Errors mark the agent run as `failed`.
  - Details: Ensure exceptions after run creation update status to `failed` with a safe summary. Preserve existing per-agent failed step logging when the agent callable provides it.
  - Dependencies: Batch03.
  - User Action: None.
  - Agent Work: Add failure handling and tests for each agent failure path.
  - Output: Controlled workflow failure behavior.
  - Acceptance: Mocked Agent 1/2/3 failures all result in failed agent run status and safe API failure response.
  - Validation: `cd backend` then `pytest tests/test_langgraph_workflow.py tests/test_chat_api.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/agents/graph.py`, `backend/app/api/chat.py`, backend tests

- [ ] (05D): Handle evidence and logs lookup failures safely
  - Source of Truth: `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Plan_12.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## 18.5 Debuggability Rule`
  - Source Requirements:
    - Missing agent run returns 404 for `SINGLE_USER_ID`.
    - Agent step log query failure returns HTTP 500 with safe public message.
    - Developers must inspect run steps without leaking internals.
  - Details: Distinguish not-found from dependency/query failure. Keep public error messages safe and avoid exposing Supabase raw errors.
  - Dependencies: Batch04 agent run APIs.
  - User Action: None.
  - Agent Work: Add error mapping and tests for evidence/log not-found and query-failure cases.
  - Output: Safe debug endpoint error behavior.
  - Acceptance: Not-found is 404; dependency failure is 500 with safe message.
  - Validation: `cd backend` then `pytest tests/test_agent_runs_api.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/api/agent_runs.py`, `backend/app/services/agent_run_service.py`, `backend/tests/test_agent_runs_api.py`

- [ ] (05E): Prevent secret and private implementation leakage
  - Source of Truth: `docs/plans/Plan_12.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `# 15. Environment Variables`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - No hardcoded secrets.
    - Backend-only settings must not be exposed to frontend.
    - Supabase service role and provider keys remain backend-only.
  - Details: Inspect new code and tests for hardcoded secret values, raw `.env` reads outside existing settings patterns, and accidental frontend exposure.
  - Dependencies: Batches 01 through 04.
  - User Action: None.
  - Agent Work: Run focused scans or code review checks and document findings in the execution report.
  - Output: Secret-boundary confirmation.
  - Acceptance: No new hardcoded secrets or frontend secret references exist.
  - Validation: Secret-name scan and git diff review in Batch07.
  - Blocked Condition: None.
  - Files: `docs/reports/report_12_execute_agent.md`, changed backend files

### Files or Modules Likely Created or Updated

- `backend/app/agents/graph.py`
- `backend/app/api/chat.py`
- `backend/app/api/agent_runs.py`
- `backend/app/services/chat_service.py`
- `backend/app/services/agent_run_service.py`
- `backend/app/services/supabase_service.py`
- `backend/tests/test_langgraph_workflow.py`
- `backend/tests/test_chat_api.py`
- `backend/tests/test_agent_runs_api.py`

### Required Outputs / Artifacts

- Safe validation and error mapping.
- Failed-run lifecycle behavior for Agent 1/2/3 failures.
- Single-user scoping across all new persistence and lookup behavior.
- Secret-boundary review result.

### Acceptance Criteria

- Invalid chat inputs fail before workflow execution.
- Not-owned or unknown sessions/documents/runs are rejected.
- Agent failures mark runs failed and do not claim success.
- Evidence/log lookup failures are safe and correctly mapped.
- No backend-only secrets are exposed.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_langgraph_workflow.py tests/test_chat_api.py tests/test_agent_runs_api.py -v`
- Focused scan for secret names and out-of-scope frontend changes.

### Explicit Non-Goals

- Do not hide failed workflow status by returning a successful answer.
- Do not bypass `SINGLE_USER_ID` for convenience in tests or services.
- Do not include raw provider, Supabase, Qdrant, or stack trace details in public API errors.

## Mandatory Batch06 - Required Automated Tests

### Goal

Add and run the required mocked workflow and API tests for Plan 12.

### Why this batch exists

Plan 12 explicitly requires deterministic workflow tests, chat API tests, evidence/log API tests, and failure-path tests. Completion cannot be claimed without running the required validations or documenting a real blocker.

### Inputs / Dependencies

- Batch01 through Batch05 implementation
- Existing backend pytest patterns
- Mockable Agent 1/2/3 callables
- Mockable Supabase service boundaries

### Tasks

- [ ] (06A): Add LangGraph workflow success-order tests
  - Source of Truth: `docs/plans/Plan_12.md` > `## 11. Required Tests`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Add tests with mocked agent functions so workflow behavior is deterministic.
    - Confirm workflow order matches `START -> Agent 1 -> Agent 2 -> Agent 3 -> Self-check -> FINAL`.
    - One question creates an `agent_runs` row and logs each agent step.
  - Details: Mock Agent 1, Agent 2, Agent 3, and persistence boundaries. Assert call order, state transitions, final answer source, run creation, success update, and response fields.
  - Dependencies: Batch03.
  - User Action: None.
  - Agent Work: Add deterministic workflow success tests.
  - Output: Workflow order and success lifecycle coverage.
  - Acceptance: Tests prove the full graph runs in required order and returns Agent 3 final answer.
  - Validation: `cd backend` then `pytest tests/test_langgraph_workflow.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_langgraph_workflow.py`

- [ ] (06B): Add LangGraph workflow failure and insufficient-evidence tests
  - Source of Truth: `docs/plans/Plan_12.md` > `## 11. Required Tests`; `docs/plans/Plan_12.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Add error-path tests for Agent 1, Agent 2, and Agent 3 failures.
    - Mock Agent 2 `missing_information=true` and confirm safe answer.
    - Mock Agent 3 failure and confirm `agent_runs.status = failed`.
  - Details: Cover all required failure paths separately. Confirm missing information is not treated as graph failure when Agent 3 returns a safe answer.
  - Dependencies: Batch03, Batch05.
  - User Action: None.
  - Agent Work: Add workflow error-path and missing-information tests.
  - Output: Failure lifecycle coverage.
  - Acceptance: Agent failures mark runs failed; missing information returns safe successful output when Agent 3 handles it.
  - Validation: `cd backend` then `pytest tests/test_langgraph_workflow.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_langgraph_workflow.py`

- [ ] (06C): Add `/api/chat/ask` API tests
  - Source of Truth: `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Plan_12.md` > `## 11. Required Tests`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_12.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Tests `/api/chat/ask`.
    - Response includes `answer`, `confidence`, `citations`, and `agent_run_id`.
    - Empty question, empty selected document list if required, unknown session, and workflow failure are handled.
    - User and assistant messages are stored.
  - Details: Use FastAPI test client and mocks for workflow/service dependencies. Avoid live Supabase, Qdrant, or ShopAIKey calls.
  - Dependencies: Batch04, Batch05.
  - User Action: None.
  - Agent Work: Add chat API success and error tests.
  - Output: API coverage for chat route.
  - Acceptance: Tests prove response shape, route mounting, service delegation, message persistence, and error mapping.
  - Validation: `cd backend` then `pytest tests/test_chat_api.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_chat_api.py`

- [ ] (06D): Add evidence and logs API tests
  - Source of Truth: `docs/plans/Plan_12.md` > `## 8. API Design`; `docs/plans/Plan_12.md` > `## 11. Required Tests`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Tests evidence and logs endpoints.
    - Evidence endpoint returns verified and rejected chunks.
    - Logs endpoint returns each agent step.
    - Evidence endpoint reads Agent 2 output, not unverified retrieval candidates.
  - Details: Mock agent run service or Supabase rows to include Agent 1, Agent 2, and Agent 3 steps. Assert evidence is extracted only from Agent 2 verification output and logs are ordered.
  - Dependencies: Batch04, Batch05.
  - User Action: None.
  - Agent Work: Add agent run API success and error tests.
  - Output: API coverage for evidence and logs endpoints.
  - Acceptance: Tests prove route mounting, not-found behavior, safe query failure handling, evidence source, and ordered logs.
  - Validation: `cd backend` then `pytest tests/test_agent_runs_api.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_agent_runs_api.py`

- [ ] (06E): Run required targeted automated validation
  - Source of Truth: `docs/plans/Plan_12.md` > `## 11. Required Tests`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`; `README.md` > `## Testing and Validation`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - Run `cd backend` then `pytest tests/test_langgraph_workflow.py -v`.
    - Run `cd backend` then `pytest tests/test_chat_api.py tests/test_agent_runs_api.py -v`.
    - Tests were actually run.
    - No fake success.
  - Details: Execute the exact required targeted commands. If shared services, schemas, or existing agent behavior changed, run related targeted tests too. Report failures honestly and do not mark completion unless required tests pass or a blocked status is documented.
  - Dependencies: (06A), (06B), (06C), (06D).
  - User Action: None.
  - Agent Work: Run required tests, capture results, and fix in-scope failures.
  - Output: Test result evidence for Plan 12.
  - Acceptance: Required tests pass, or failures are documented with remaining in-scope work.
  - Validation: `cd backend` then `pytest tests/test_langgraph_workflow.py -v`; `cd backend` then `pytest tests/test_chat_api.py tests/test_agent_runs_api.py -v`.
  - Blocked Condition: None unless local environment lacks required test dependencies; report dependency issue safely instead of claiming success.
  - Files: `backend/tests/test_langgraph_workflow.py`, `backend/tests/test_chat_api.py`, `backend/tests/test_agent_runs_api.py`, related backend test files if touched

### Files or Modules Likely Created or Updated

- `backend/tests/test_langgraph_workflow.py`
- `backend/tests/test_chat_api.py`
- `backend/tests/test_agent_runs_api.py`
- Runtime files from earlier batches only as needed to make tests pass

### Required Outputs / Artifacts

- Deterministic mocked LangGraph workflow tests.
- `/api/chat/ask` tests.
- Evidence endpoint tests.
- Logs endpoint tests.
- Agent 1/2/3 failure tests.
- Missing-information safe answer tests.
- Required pytest command output summarized in the execution report.

### Acceptance Criteria

- Required test files exist.
- Required targeted pytest commands were run.
- Tests pass before completion is claimed.
- Mocked tests avoid live ShopAIKey, Supabase, and Qdrant dependency unless explicitly performing manual/live validation.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_langgraph_workflow.py -v`
- `pytest tests/test_chat_api.py tests/test_agent_runs_api.py -v`
- Related targeted backend tests if shared schemas/services/agent behavior changed

### Explicit Non-Goals

- Do not rely on live provider/database/vector services for automated tests.
- Do not fabricate passing test output.
- Do not broaden tests into frontend UI, auth, streaming, document deletion, or conversation memory.

## Mandatory Batch07 - Manual Validation, Reporting, and Scope Review

### Goal

Run the required manual API checks when setup is available, write the execution report, and confirm Plan 12 scope boundaries before reviewer handoff.

### Why this batch exists

Automated tests prove deterministic behavior, but Plan 12 also requires manual chat/evidence/log checks and a clear execution report showing files, commands, test results, known issues, out-of-scope work, and example successful response shapes.

### Inputs / Dependencies

- Batch01 through Batch06 completed or safely blocked
- Running backend when manual API checks are attempted
- Real backend `.env` values for Supabase, Qdrant, and ShopAIKey only if live workflow validation is attempted
- At least one ready/indexed selected document ID only if live end-to-end API validation is attempted
- Valid `agent_run_id` from a successful chat request for evidence/log checks

### Tasks

- [ ] (07A): Run manual `/api/chat/ask` check when setup is available
  - Source of Truth: `docs/plans/Plan_12.md` > `## 11. Required Tests`; `docs/plans/Plan_12.md` > `## 14. Agent Report Requirement`; `README.md` > `## Configuration`; `README.md` > `## Known Gaps or Unclear Areas`
  - Source Requirements:
    - Manual API check posts to `/api/chat/ask`.
    - Report the shape of one successful `/api/chat/ask` response.
    - One API request creates an `agent_runs` row and returns a grounded final answer.
  - Details: Use the Plan 12 curl shape or an equivalent local HTTP client only when the backend can run with valid service settings and a ready selected document. Do not create fake document IDs or fake provider/database success.
  - Dependencies: Batch06 passing tests.
  - User Action: User must provide valid backend `.env` values and a ready/indexed `document_id` if live validation is required and not already available.
  - Agent Work: Attempt manual chat API check when setup is available; otherwise record `BLOCKED_BY_USER_ACTION` with a safe reason.
  - Output: Manual chat validation result or blocked status.
  - Acceptance: Successful response includes `answer`, `confidence`, `citations`, and `agent_run_id`, or manual validation is explicitly blocked with a safe setup reason.
  - Validation: `curl -X POST http://localhost:8000/api/chat/ask ...` or documented `BLOCKED_BY_USER_ACTION`.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if required backend secrets, service setup, running backend, ready indexed document, or valid selected `document_id` are missing.
  - Files: `docs/reports/report_12_execute_agent.md`

- [ ] (07B): Run manual evidence and logs checks when setup is available
  - Source of Truth: `docs/plans/Plan_12.md` > `## 11. Required Tests`; `docs/plans/Plan_12.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Run evidence/log checks by `agent_run_id`.
    - Report the shape of one verified logs response.
    - Evidence endpoint reads Agent 2 output, not unverified retrieval candidates.
  - Details: Use the `agent_run_id` from a real successful chat request when available. Verify evidence contains Agent 2 verified/rejected chunk output and logs contain ordered agent steps.
  - Dependencies: (07A), Batch06 passing tests.
  - User Action: User must provide or allow creation of a valid `agent_run_id` if live validation is required and not already available.
  - Agent Work: Attempt manual evidence/log API checks when setup is available; otherwise record `BLOCKED_BY_USER_ACTION`.
  - Output: Manual evidence/log validation result or blocked status.
  - Acceptance: Evidence and logs endpoints return expected shapes, or manual validation is explicitly blocked with a safe setup reason.
  - Validation: `curl http://localhost:8000/api/agent-runs/<agent_run_id>/evidence`; `curl http://localhost:8000/api/agent-runs/<agent_run_id>/logs`.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if no valid `agent_run_id`, backend service setup, or live data is available.
  - Files: `docs/reports/report_12_execute_agent.md`

- [ ] (07C): Create execution report with required Plan 12 contents
  - Source of Truth: `docs/plans/Plan_12.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Report files created.
    - Report files modified.
    - Report commands run.
    - Report test results.
    - Report known issues.
    - Report intentionally not implemented out-of-scope work.
    - Include shape of one successful `/api/chat/ask` response.
    - Include shape of one verified logs response.
  - Details: Create the standard report artifact for Plan 12 using the repo's existing reports pattern. Keep examples safe and synthetic if manual live validation is blocked; label synthetic examples clearly.
  - Dependencies: Batch06, (07A), (07B).
  - User Action: None.
  - Agent Work: Write report with accurate commands/results, artifacts, manual check status, and safe examples.
  - Output: Plan 12 execution report.
  - Acceptance: Report includes all Plan 12 required sections and does not claim blocked live validation as completed.
  - Validation: Read report before handoff and confirm every required report item is present.
  - Blocked Condition: None.
  - Files: `docs/reports/report_12_execute_agent.md`

- [ ] (07D): Complete scope, secret, and architecture review
  - Source of Truth: `docs/plans/Plan_12.md` > `## 4. Out of Scope`; `docs/plans/Plan_12.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_12.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## Phase 9: LangGraph Orchestration`; `README.md` > `Important coordination rules`
  - Source Requirements:
    - Scope was followed.
    - Out-of-scope work was not added.
    - Tests were actually run.
    - Acceptance criteria passed.
    - No hardcoded secrets.
    - Architecture still matches `docs/plans/Master_Plan.md`.
    - Workflow order matches `START -> Agent 1 -> Agent 2 -> Agent 3 -> Self-check -> FINAL`.
    - All run/session/message queries are scoped by `SINGLE_USER_ID`.
    - Final answers come from Agent 3 output.
    - Evidence endpoint reads Agent 2 output, not unverified retrieval candidates.
  - Details: Inspect changed files and tests for scope boundaries. Confirm no frontend chat UI, streaming, auth/JWT, multi-user behavior, document deletion, database migration, or extra conversation memory was added.
  - Dependencies: Batch06, (07C).
  - User Action: None.
  - Agent Work: Run focused scans or code review checks, update report with scope findings, and update this task tracker only after validations pass or blocks are recorded.
  - Output: Reviewer-ready scope boundary confirmation.
  - Acceptance: Scope review confirms Plan 12 boundaries or documents exact deviations requiring fixes before reviewer handoff.
  - Validation: Git diff review, secret-name scan, route registration check, workflow order test review, and targeted search for out-of-scope additions.
  - Blocked Condition: None.
  - Files: `docs/reports/report_12_execute_agent.md`, `docs/tasks/task_12.md` progress tracker during execution

### Files or Modules Likely Created or Updated

- `docs/reports/report_12_execute_agent.md`
- `docs/tasks/task_12.md` progress tracker during execution
- No runtime files unless test or scope feedback from earlier batches requires fixes

### Required Outputs / Artifacts

- Manual chat API validation result or blocked status.
- Manual evidence/log validation result or blocked status.
- Execution report for Plan 12 reviewer handoff.
- Successful `/api/chat/ask` response shape.
- Verified logs response shape.
- Scope, secret, and architecture boundary confirmation.

### Acceptance Criteria

- Automated tests were run and reported.
- Manual checks were completed or safely blocked.
- Successful response examples are included safely.
- Evidence/log behavior is reported honestly.
- Out-of-scope work was not implemented.
- No secrets or fake success appear in the report.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_langgraph_workflow.py -v`
- `pytest tests/test_chat_api.py tests/test_agent_runs_api.py -v`
- Manual `/api/chat/ask` check when setup is available.
- Manual evidence/log endpoint checks when setup is available.
- Scope and secret inspection.

### Explicit Non-Goals

- Do not fabricate live provider, database, vector, document, or agent run validation.
- Do not create real provider keys, Supabase projects, Qdrant collections, documents, or agent runs on behalf of the user unless explicitly requested.
- Do not implement frontend chat, evidence viewer, or agent logs UI.
- Do not implement streaming, auth/JWT, multi-user support, document deletion, or conversation memory beyond stored messages.

## Optional Future Tracks

No optional future tracks are part of the mandatory Plan 12 batch chain.

Frontend chat UI, frontend evidence viewer, frontend agent logs/debug page, streaming responses, authentication/JWT, multi-user support, document deletion, conversation memory beyond stored messages, live rerank provider calls, and richer graph/debug visualization remain outside this task file unless a later approved plan explicitly includes them.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05
- Batch05 -> Batch06
- Batch06 -> Batch07

Optional future tracks are outside the mandatory dependency chain.

## Global Verification Checklist

- [ ] `docs/plans/Plan_12.md` remained the scope authority.
- [ ] No database schema changes or migrations were added.
- [ ] LangGraph dependency is present only if needed.
- [ ] `backend/app/agents/graph.py` exists.
- [ ] Workflow state includes `agent_run_id`, `session_id`, `question`, `document_ids`, `retrieval`, `verification`, `answer`, and `error`.
- [ ] `run_qa_workflow(question, document_ids, session_id=None)` exists.
- [ ] Workflow order is Agent 1, then Agent 2, then Agent 3.
- [ ] Agent 3 self-check remains part of the logical workflow path.
- [ ] Final answers come from Agent 3 output.
- [ ] Agent 2 missing information returns safe Agent 3 insufficient-evidence output.
- [ ] `agent_runs` row is created with status `running` before graph invocation.
- [ ] Successful workflow updates `agent_runs.status` to `success`.
- [ ] Successful workflow stores final answer and confidence on `agent_runs`.
- [ ] Failed Agent 1 workflow updates `agent_runs.status` to `failed`.
- [ ] Failed Agent 2 workflow updates `agent_runs.status` to `failed`.
- [ ] Failed Agent 3 workflow updates `agent_runs.status` to `failed`.
- [ ] User question is stored in `chat_messages`.
- [ ] Assistant answer is stored in `chat_messages`.
- [ ] Omitted `session_id` creates a chat session.
- [ ] Unknown `session_id` for `SINGLE_USER_ID` returns 404.
- [ ] Empty question returns 400.
- [ ] `document_ids` are UUID-validated.
- [ ] Selected documents are validated before workflow execution.
- [ ] Selected document queries are scoped by `SINGLE_USER_ID`.
- [ ] Run queries are scoped by `SINGLE_USER_ID`.
- [ ] Session queries are scoped by `SINGLE_USER_ID`.
- [ ] Message writes use `SINGLE_USER_ID`.
- [ ] Step lookup is tied to an owned agent run.
- [ ] `backend/app/api/chat.py` exposes `POST /api/chat/ask`.
- [ ] Chat router is mounted in `backend/app/main.py`.
- [ ] Chat response includes `answer`, `confidence`, `citations`, and `agent_run_id`.
- [ ] `backend/app/api/agent_runs.py` exposes evidence and logs endpoints.
- [ ] Agent run router is mounted in `backend/app/main.py`.
- [ ] Evidence endpoint returns `verified_chunks` and `rejected_chunks`.
- [ ] Evidence endpoint reads Agent 2 output from `agent_steps`.
- [ ] Evidence endpoint does not use unverified Agent 1 candidates as verified evidence.
- [ ] Logs endpoint returns `agent_run_id` and ordered `steps`.
- [ ] Logs endpoint orders steps by `created_at`.
- [ ] Agent step log query failure returns 500 with a safe public message.
- [ ] Public API errors do not expose raw provider, Supabase, Qdrant, stack trace, or secret values.
- [ ] No frontend chat UI was implemented.
- [ ] No streaming response behavior was implemented.
- [ ] No authentication/JWT or multi-user support was implemented.
- [ ] No document deletion was implemented.
- [ ] No conversation memory beyond storing messages was implemented.
- [ ] Backend-only secrets and provider settings stayed out of frontend code.
- [ ] `cd backend` then `pytest tests/test_langgraph_workflow.py -v` was run and reported.
- [ ] `cd backend` then `pytest tests/test_chat_api.py tests/test_agent_runs_api.py -v` was run and reported.
- [ ] Manual `/api/chat/ask` check was completed or marked `BLOCKED_BY_USER_ACTION` with a safe reason.
- [ ] Manual evidence/log endpoint checks were completed or marked `BLOCKED_BY_USER_ACTION` with a safe reason.
- [ ] Execution report includes files created, files modified, commands run, test results, known issues, out-of-scope work, one successful chat response shape, and one verified logs response shape.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [ ] Batch01 - Workflow Contracts, Dependencies, and API Schemas
- [ ] Batch02 - Chat and Agent Run Persistence Services
- [ ] Batch03 - LangGraph Workflow Orchestration
- [ ] Batch04 - Public Chat, Evidence, and Logs APIs
- [ ] Batch05 - Failure Handling and Single-User Safety
- [ ] Batch06 - Required Automated Tests
- [ ] Batch07 - Manual Validation, Reporting, and Scope Review

### Task IDs

#### Batch01

- [ ] (01A): Confirm LangGraph dependency and backend import boundary
- [ ] (01B): Add chat API request and response schemas
- [ ] (01C): Add agent run evidence and logs response schemas
- [ ] (01D): Define workflow state schema and graph callable contract
- [ ] (01E): Confirm out-of-scope and backend-only boundaries before implementation

#### Batch02

- [ ] (02A): Add Supabase helpers for chat sessions and messages
- [ ] (02B): Add Supabase helpers for agent runs and agent steps lookup
- [ ] (02C): Create chat service for session and message orchestration
- [ ] (02D): Create agent run service for lifecycle, evidence, and logs
- [ ] (02E): Add selected document ownership validation
- [ ] (02F): Define controlled service errors for API mapping

#### Batch03

- [ ] (03A): Implement LangGraph node for Agent 1 retrieval
- [ ] (03B): Implement LangGraph node for Agent 2 verification
- [ ] (03C): Implement LangGraph node for Agent 3 answer and self-check
- [ ] (03D): Compile graph in required order
- [ ] (03E): Implement `run_qa_workflow` lifecycle orchestration
- [ ] (03F): Preserve insufficient-evidence behavior through the workflow

#### Batch04

- [ ] (04A): Implement `POST /api/chat/ask`
- [ ] (04B): Register chat router in FastAPI app
- [ ] (04C): Implement `GET /api/agent-runs/{agent_run_id}/evidence`
- [ ] (04D): Implement `GET /api/agent-runs/{agent_run_id}/logs`
- [ ] (04E): Register agent run router in FastAPI app

#### Batch05

- [ ] (05A): Enforce chat request validation and selected-document errors
- [ ] (05B): Enforce session, document, run, message, and step scoping by `SINGLE_USER_ID`
- [ ] (05C): Mark agent failures as failed runs with safe errors
- [ ] (05D): Handle evidence and logs lookup failures safely
- [ ] (05E): Prevent secret and private implementation leakage

#### Batch06

- [ ] (06A): Add LangGraph workflow success-order tests
- [ ] (06B): Add LangGraph workflow failure and insufficient-evidence tests
- [ ] (06C): Add `/api/chat/ask` API tests
- [ ] (06D): Add evidence and logs API tests
- [ ] (06E): Run required targeted automated validation

#### Batch07

- [ ] (07A): Run manual `/api/chat/ask` check when setup is available
- [ ] (07B): Run manual evidence and logs checks when setup is available
- [ ] (07C): Create execution report with required Plan 12 contents
- [ ] (07D): Complete scope, secret, and architecture review

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
- reason: missing backend `.env`, missing Supabase credentials, missing Qdrant credentials, missing ShopAIKey API key, missing ready indexed document, missing selected `document_id`, missing valid `agent_run_id`, backend not running for manual validation, missing manual setup, or other safe summary

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
