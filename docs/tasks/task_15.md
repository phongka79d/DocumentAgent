# Plan 15 - Agent Logs Debug UI Execution Tasks

## Purpose

Create a detailed execution task file for the approved Agent Logs / Debug UI milestone. This task file guides a future Execution Agent to align the existing logs response with the Plan 15 contract, add typed frontend log access, build raw and structured step inspection components, add direct run lookup and chat-to-logs navigation, preserve secret and scope boundaries, validate the frontend in a browser, and report results for `docs/plans/Plan_15.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_15.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Current project context reviewed: `README.md`
- Current implementation inspected for planning context:
  - `backend/app/schemas/agent_runs.py`
  - `backend/app/api/agent_runs.py`
  - `backend/app/services/agent_run_service.py`
  - `backend/app/services/supabase_service.py`
  - `backend/app/agents/retrieval_agent.py`
  - `backend/app/agents/verification_agent.py`
  - `backend/app/agents/answer_agent.py`
  - `backend/tests/test_agent_runs_api.py`
  - `frontend/package.json`
  - `frontend/src/App.tsx`
  - `frontend/src/api/agentRuns.ts`
  - `frontend/src/pages/ChatPage.tsx`
  - `frontend/src/components/AnswerPanel.tsx`
  - `frontend/src/pages/EvidenceViewerPage.tsx`
  - `frontend/src/types/chat.ts`
- Conflict note: Plan 15 requires each logs step to expose `step_name` and nullable `error_message`, and requires the UI to identify the three named agent steps and display failed-step errors. The mounted Plan 12 endpoint currently returns only `agent_name`, `input`, `output`, `status`, and `created_at`, even though the persisted `agent_steps` rows already contain `step_name` and `error_message`. This task therefore includes a minimal alignment of the existing response schema/service/tests. It does not create a new endpoint, database migration, or backend logging system.
- Runtime payload note: Current successful Agent 3 logs store the self-check under `output.self_check_result`, not `output.self_check`. Structured frontend parsing must support the current persisted field name and may accept `self_check` as a defensive compatibility alias. Raw JSON remains mandatory for every step.

## Source Section Index

- `docs/plans/Plan_15.md` > `## 1. Goal` -> a developer can open a known `agent_run_id` and inspect every persisted agent step.
- `docs/plans/Plan_15.md` > `## 2. Why This Plan Exists` -> intermediate retrieval, verification, generation, self-check, error, and timestamp states must be visible without direct database access or secret exposure.
- `docs/plans/Plan_15.md` > `## 3. Scope` -> frontend API, logs page, run lookup/link, step list/detail, raw JSON, specialized panels, states, route/navigation, build, and manual checks.
- `docs/plans/Plan_15.md` > `## 4. Out of Scope` -> no new logs endpoint, admin run browser, run editing, graph visualization, production observability dashboard, or secret exposure.
- `docs/plans/Plan_15.md` > `## 5. Dependencies` -> Plan 12 logs API is required and Plan 14 chat integration is optional but available in the current project.
- `docs/plans/Plan_15.md` > `## 6. Required Files and Folders` -> expected types, API helper, page, viewers, route, and conditional test file.
- `docs/plans/Plan_15.md` > `## 7. Data Model / Schema Changes` -> no database schema change; target frontend `AgentStep` and `AgentRunLogsResponse` contracts and expected step names.
- `docs/plans/Plan_15.md` > `## 8. API Design` -> existing `GET /api/agent-runs/{agent_run_id}/logs` call and run ID validation.
- `docs/plans/Plan_15.md` > `## 9. Implementation Steps` -> ordered contracts, components, page, chat link, route, states, overflow, tests, and build work.
- `docs/plans/Plan_15.md` > `## 10. Configuration and Environment Variables` -> `VITE_API_BASE_URL` is frontend-safe and backend-only secrets must remain outside the frontend.
- `docs/plans/Plan_15.md` > `## 11. Required Tests` -> frontend build, conditional frontend tests, happy-path manual inspection, and negative manual tests.
- `docs/plans/Plan_15.md` > `## 12. Acceptance Criteria` -> logs page, run lookup, statuses/timestamps, raw JSON, specialized panels, failed-step errors, build, and secret safety.
- `docs/plans/Plan_15.md` > `## 13. Failure Handling` -> missing ID, not found, backend error, empty steps, malformed output, and long JSON behavior.
- `docs/plans/Plan_15.md` > `## 14. Agent Report Requirement` -> report files, commands, tests, known issues, exclusions, and real or mocked run ID usage.
- `docs/plans/Plan_15.md` > `## 15. Reviewer Checklist` -> scope, tests, acceptance, secrets, architecture, debug focus, raw fallback, and score-field accuracy.
- `docs/plans/Master_Plan.md` > `## 2. Tech Stack` > `### Frontend` -> React, TypeScript, frontend styling, and Axios-compatible frontend architecture.
- `docs/plans/Master_Plan.md` > `## 5. Core Features` > `### 5.5 Agent Logs / Debug Page` -> required debug content across all agents, errors, confidence, and timestamps.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.4 Scoring Formula` -> exact retrieval score component names and meaning.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.6 Agent 1 Output Schema` -> `candidates` and retrieval candidate field names.
- `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.4 Agent 2 Output Schema` -> verified/rejected chunks, missing information, and confidence.
- `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.5 Self-Check` -> self-check questions the debug UI must expose.
- `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.6 Agent 3 Output Schema` -> final answer, citations, reasoning, confidence, and self-check fields.
- `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.6 Get Agent Logs` -> existing logs endpoint and base response shape.
- `docs/plans/Master_Plan.md` > `# 14. Frontend Page Plan` > `## 14.5 Agent Logs / Debug Page` -> raw JSON, retrieval, verification, self-check, and error display.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> frontend `VITE_API_BASE_URL` and backend-only private key boundary.
- `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure` -> expected `agentRuns.ts`, `AgentLogsPage.tsx`, and `AgentLogViewer.tsx` locations.
- `docs/plans/Master_Plan.md` > `# 17. Implementation Phases` > `## Phase 10: Frontend UI` -> Agent Logs / Debug Page is part of the frontend MVP.
- `docs/plans/Master_Plan.md` > `# 18. Quality Rules` > `## 18.5 Debuggability Rule` -> every run must be traceable through retrieval, selection/rejection, answer generation, and self-check.
- `docs/plans/Master_Plan.md` > `# 19. MVP Success Criteria` -> frontend must display agent logs while private keys remain backend-only.
- `docs/plans/Master_Plan.md` > `# 21. Non-Goals for MVP` -> no multi-user auth/JWT, admin dashboard, or other non-MVP systems.
- `README.md` > `## Overview` -> Plan 12 logs API and Plan 14 chat/evidence UI are implemented; the logs/debug frontend remains planned.
- `README.md` > `## Architecture` -> existing backend response/service boundaries and routed React/Axios frontend.
- `README.md` > `## Frontend` -> current React 19, Vite, TypeScript, React Router, Axios, plain CSS, routes, and API/type/component organization.
- `README.md` > `## Running the Project` > `### Backend API` -> mounted logs endpoint.
- `README.md` > `## Running the Project` > `### Production Frontend Build` -> current frontend build command.
- `README.md` > `## Testing and Validation` -> no frontend test script currently exists; backend agent-run tests and frontend build commands are available.
- `README.md` > `## Development Notes for AI Agents` -> preserve the frontend API boundary, single-user behavior, safe backend errors, and backend-only secrets.
- `README.md` > `## Known Gaps or Unclear Areas` -> public logs API is mounted while the agent-log/debug frontend remains unimplemented.

## Approved Architecture Summary

Plan 15 extends the existing React 19, TypeScript, Vite, React Router, Axios, and plain CSS frontend. All log requests must use the existing `frontend/src/api/client.ts` Axios instance and `VITE_API_BASE_URL`; the browser must call only the mounted FastAPI route `GET /api/agent-runs/{agent_run_id}/logs`.

The existing endpoint and persistence layer remain authoritative infrastructure. No new route, table, migration, provider call, or logging pipeline is approved. A narrow response-contract repair is required because persisted rows include `step_name` and `error_message`, but `AgentRunLogStepResponse` currently drops them. The aligned public step contract is:

```ts
export type AgentStep = {
  agent_name: string;
  step_name: string;
  input: unknown;
  output: unknown;
  status: "success" | "failed";
  created_at: string;
  error_message: string | null;
};
```

The backend must continue returning steps in chronological persistence order. The frontend must preserve that order and identify recognized panels primarily by `step_name`:

```text
agent_1_retrieval
agent_2_verification
agent_3_answer_self_check
```

Structured panels are convenience views over persisted JSON, not replacements for it. Every selected step must always show raw `input` and raw `output`. If a specialized panel cannot recognize or validate a payload, the page must remain usable and raw JSON must still render.

Current persisted successful payloads establish the runtime parsing targets:

- Agent 1 output: `question` and `candidates`; each candidate may include `chunk_id`, `document_id`, `file_name`, `content`, page/section metadata, `semantic_similarity`, `graph_relevance`, `keyword_overlap`, `metadata_match`, `recency_or_position_score`, `final_score`, and `retrieval_reason`.
- Agent 2 output: `verified_chunks`, `rejected_chunks`, `missing_information`, and `confidence`.
- Agent 3 output: `draft_answer`, `self_check_result`, `final_answer`, `citations`, `reasoning_summary`, `confidence`, and `errors`. Failed steps may instead contain an `error` object.

The UI is a developer debug surface, not an admin dashboard. It supports direct lookup of one known run ID and a link from the latest chat answer. It must not browse all runs, mutate logs, reveal environment variables/prompts/secrets, call Supabase/Qdrant/ShopAIKey directly, or introduce authentication, graph visualization, or production observability tooling.

The current frontend has no `test` script or testing libraries. Frontend UI tests are conditional on real test infrastructure already being present when execution begins. The mandatory frontend automated check is `npm run build`. Because the task includes a narrow backend response alignment, the targeted backend agent-run tests are also mandatory.

## Global Implementation Rules

- Treat `docs/plans/Plan_15.md` as the primary authority for scope, component responsibilities, UI states, validation, acceptance, failure handling, and reviewer checks.
- Use `docs/plans/Master_Plan.md` only to clarify the approved debug content, exact Agent 1/2/3 output fields, existing endpoint, frontend structure, secret boundary, and MVP non-goals.
- Use `README.md` and inspected code only to understand the current implementation state and avoid stale assumptions.
- Keep the backend change limited to exposing persisted `step_name` and nullable `error_message` through the existing logs response and updating focused tests. Do not add a route, table, migration, logging write path, new status, or agent behavior.
- Preserve single-user ownership checks and safe error mapping in the existing agent-run service and route.
- Use the existing frontend `apiClient`; do not introduce a second HTTP client or hardcode a backend origin.
- Keep `VITE_API_BASE_URL` as the only required frontend runtime setting.
- Never read, render, log, bundle, or expose `SUPABASE_SERVICE_ROLE_KEY`, `QDRANT_API_KEY`, `SHOPAIKEY_API_KEY`, provider prompts, backend environment dumps, stack traces, or raw backend exception objects.
- Do not call Supabase, Qdrant, ShopAIKey, or any provider directly from the frontend.
- Encode `agent_run_id` before placing it in the request path.
- Validate a submitted run ID as a non-empty UUID before issuing the logs request.
- Preserve backend-returned chronological step order. Do not sort by display labels or assume exactly three steps.
- Use `step_name` as the primary recognized-step discriminator. A defensive `agent_name` fallback may support legacy/malformed data, but it must not hide the contract mismatch.
- Keep raw JSON input and output visible for every step, including recognized, failed, malformed, and future unknown steps.
- Format JSON with stable indentation. Preserve booleans, numbers, nulls, arrays, and nested objects without stringifying them into misleading display values.
- Ensure JSON blocks wrap where appropriate and provide contained horizontal scrolling for unbreakable long tokens without causing page-level horizontal overflow.
- Parse specialized panels defensively using type guards or small focused normalization helpers. Do not use unchecked casts or `any`.
- Agent 1 score labels must map to the actual fields `semantic_similarity`, `graph_relevance`, `keyword_overlap`, `metadata_match`, `recency_or_position_score`, and `final_score`.
- Do not re-score, rerank, or alter Agent 1 candidates in the frontend.
- Agent 2 display must keep verified and rejected chunks distinct and show `missing_information` and `confidence`.
- Agent 3 display must support the current `self_check_result` field, may accept `self_check` as a compatibility alias, and must show the persisted final answer when present.
- Show status and failure through visible text and structure, not color alone.
- Display nullable `error_message` for failed steps when present. If it is absent, preserve the failed status and inspectable raw output without inventing an error.
- Use safe, actionable page errors for invalid IDs, not-found runs, connection failures, and backend failures.
- Avoid stale-response races when the route parameter or submitted run ID changes during a request.
- Preserve existing upload, documents, chat, and evidence routes and behavior.
- Add chat-to-logs access only for a real returned `agent_run_id`; do not fabricate IDs or retain a link for an answer that has been replaced.
- Preserve the current plain CSS approach in `frontend/src/styles.css`; do not add Tailwind, a component library, state-management library, data-fetching library, formatter, linter, or test framework solely for this plan.
- Treat frontend tests as conditional. Do not create broad test infrastructure just to make `npm test` exist and do not fabricate a test result.
- Update task and batch progress only after acceptance and validation are satisfied or an allowed blocked condition is recorded.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable Python, React, and TypeScript.
- Use descriptive names for response fields, types, guards, components, props, state, handlers, routes, styles, and tests.
- Keep functions, components, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow the existing FastAPI/Pydantic/pytest and React 19/Vite/Axios/React Router/strict TypeScript conventions.
- Use clear Python and TypeScript typing; narrow `unknown` before reading nested JSON.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values.
- Add comments only for non-obvious contract compatibility, stale-request handling, or defensive payload parsing.
- Keep frontend code free of backend-only secrets and backend-only configuration names except in explicit scope-audit commands.
- Avoid adding formatters, linters, frameworks, libraries, or architecture changes outside Plan 15 unless already present or explicitly approved.

## Batch Map

- Batch01 - Existing Logs Contract and Frontend API Boundary
- Batch02 - Raw JSON and Specialized Step Panels
- Batch03 - Agent Step List and Detail Viewer
- Batch04 - Logs Page Lookup and Chat Integration
- Batch05 - Routing, Navigation, Styling, and Scope Hardening
- Batch06 - Automated and Manual Validation, Reporting, and Handoff

## Mandatory Batch01 - Existing Logs Contract and Frontend API Boundary

### Goal

Expose the complete persisted logs contract through the existing backend endpoint and create the typed frontend API boundary required by the debug UI.

### Why this batch exists

The UI cannot reliably recognize named agent steps or display failed-step messages while the current response drops `step_name` and `error_message`. Frontend components also need a typed, safe logs request before page work begins.

### Inputs / Dependencies

- `docs/plans/Plan_15.md`
- `docs/plans/Master_Plan.md`
- `README.md`
- Completed Plan 12 logs endpoint and persistence
- Existing `backend/app/schemas/agent_runs.py`
- Existing `backend/app/services/agent_run_service.py`
- Existing `backend/tests/test_agent_runs_api.py`
- Existing `frontend/src/api/client.ts`
- Existing `frontend/src/api/agentRuns.ts`

### Tasks

- [x] (01A): Align the existing logs response with persisted step metadata
  - Source of Truth: `docs/plans/Plan_15.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_15.md` > `## 8. API Design`; `docs/plans/Plan_15.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_15.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Each frontend log step requires `step_name` and optional `error_message`.
    - Failed steps must expose their error messages.
    - The existing logs endpoint must be used rather than creating a new backend API.
  - Details: Repair the existing response boundary so the endpoint returns metadata already persisted in `agent_steps`. This is a contract alignment, not a new logs implementation.
  - Dependencies: Completed Plan 12 agent-run logs endpoint and existing `agent_steps` persistence fields.
  - User Action: None.
  - Agent Work: Add required non-empty `step_name` and nullable `error_message` fields to `AgentRunLogStepResponse`; map both fields in `_log_step_response`; preserve existing `agent_name`, JSON input/output, success/failed status, timestamp, order, ownership checks, and safe errors; update focused service and route tests for successful and failed steps.
  - Output: Existing `GET /api/agent-runs/{agent_run_id}/logs` returns the complete Plan 15 step contract.
  - Acceptance: A response step contains `step_name`, `agent_name`, `input`, `output`, `status`, `created_at`, and `error_message`; failed-step tests prove the safe error is returned; no migration, new endpoint, or logging-write change is introduced.
  - Validation: From `backend/`, run `pytest tests/test_agent_runs_api.py -v`; inspect the route response serialization and diff for scope.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/agent_runs.py`, `backend/app/services/agent_run_service.py`, `backend/tests/test_agent_runs_api.py`

- [x] (01B): Define frontend agent-run log types
  - Source of Truth: `docs/plans/Plan_15.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_15.md` > `## 7. Data Model / Schema Changes`
  - Source Requirements:
    - Create `frontend/src/types/agentRuns.ts`.
    - Define `AgentStep` and `AgentRunLogsResponse`.
    - Support the named Agent 1, Agent 2, and Agent 3 steps while allowing future string values safely.
  - Details: Create the frontend contracts for the aligned logs response without moving existing chat/evidence types unnecessarily.
  - Dependencies: (01A) target response contract.
  - User Action: None.
  - Agent Work: Add typed log response definitions with `input` and `output` as `unknown`, success/failed status typing, ISO timestamp string, nullable error, and recognized step-name constants or a narrow union plus string compatibility where useful.
  - Output: Shared typed log contracts for the API client and UI.
  - Acceptance: Types represent every aligned backend response field, do not use `any`, and do not incorrectly require specialized Agent 1/2/3 payloads for unknown or malformed steps.
  - Validation: Run the frontend TypeScript build in Batch06; inspect type imports and verify no circular dependency with `types/chat.ts`.
  - Blocked Condition: None.
  - Files: `frontend/src/types/agentRuns.ts`

- [x] (01C): Extend the agent-runs API client with logs lookup
  - Source of Truth: `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_15.md` > `## 8. API Design`; `docs/plans/Plan_15.md` > `## 10. Configuration and Environment Variables`
  - Source Requirements:
    - Add `getAgentRunLogs(agentRunId)`.
    - Call `GET /api/agent-runs/{agent_run_id}/logs`.
    - Use `VITE_API_BASE_URL` through the existing frontend API client.
    - Do not expose secrets.
  - Details: Extend the existing evidence-oriented agent-runs module without breaking `getAgentRunEvidence`.
  - Dependencies: (01B), existing `frontend/src/api/agentRuns.ts`.
  - User Action: None.
  - Agent Work: Add an encoded logs request returning `AgentRunLogsResponse`; keep or refine safe error mapping so evidence and logs failures have truthful generic messages; preserve backend `detail` strings such as not-found; avoid exposing raw Axios errors.
  - Output: Typed `getAgentRunLogs` frontend API helper.
  - Acceptance: The helper uses `apiClient`, encodes the run ID, calls only the existing `/logs` route, returns typed data, and leaves evidence loading behavior intact.
  - Validation: Run `npm run build` in Batch06; inspect request paths and safe error mapping; run frontend tests only if a real runner exists.
  - Blocked Condition: None.
  - Files: `frontend/src/api/agentRuns.ts`, `frontend/src/types/agentRuns.ts`

### Files or Modules Likely Created or Updated

- `backend/app/schemas/agent_runs.py`
- `backend/app/services/agent_run_service.py`
- `backend/tests/test_agent_runs_api.py`
- `frontend/src/types/agentRuns.ts`
- `frontend/src/api/agentRuns.ts`

### Required Outputs / Artifacts

- Aligned existing logs response with `step_name` and `error_message`.
- Focused backend regression coverage.
- Typed frontend logs contracts.
- Typed, encoded logs API helper with safe errors.

### Acceptance Criteria

- Existing logs endpoint returns persisted step name and nullable error message.
- Existing ownership and safe error behavior remains intact.
- No new endpoint, migration, table, or logging pipeline is added.
- Frontend has no hardcoded backend URL or secret.
- Evidence API behavior still compiles and remains unchanged.

### Required Tests or Validations

- `cd backend && pytest tests/test_agent_runs_api.py -v`
- `cd frontend && npm run build` in Batch06
- Frontend tests only if configured
- Diff inspection for endpoint/schema scope

### Explicit Non-Goals

- Changing how agent steps are written.
- Adding new agent statuses.
- Returning all agent runs.
- Changing chat, evidence, retrieval, verification, or answer behavior.

## Mandatory Batch02 - Raw JSON and Specialized Step Panels

### Goal

Build defensive, reusable components that always expose raw step data and add readable Agent 1, Agent 2, and Agent 3 summaries when recognized payloads are present.

### Why this batch exists

The debug page must make complex persisted JSON readable while remaining resilient to unknown, partial, failed, or malformed payloads.

### Inputs / Dependencies

- Completed Batch01 frontend types
- Current persisted Agent 1, Agent 2, and Agent 3 output shapes
- Existing frontend plain CSS conventions

### Tasks

- [x] (02A): Build the reusable raw JSON viewer
  - Source of Truth: `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_15.md` > `## 9. Implementation Steps`; `docs/plans/Plan_15.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Display raw JSON input and output for every step.
    - Use readable formatted JSON.
    - Long JSON must remain readable and not break the layout.
  - Details: Create a generic read-only JSON display that handles any JSON-compatible or malformed frontend value safely.
  - Dependencies: (01B).
  - User Action: None.
  - Agent Work: Implement `JsonViewer.tsx` with stable indentation, accessible labeling, a safe fallback for values that cannot be serialized, and class hooks for wrapping/contained horizontal scrolling.
  - Output: Reusable raw JSON component.
  - Acceptance: Objects, arrays, strings, numbers, booleans, null, and unexpected values render without throwing; content remains selectable and no edit controls are present.
  - Validation: Component tests only if a runner exists; otherwise compile and manually inspect representative nested/long payloads in Batch06.
  - Blocked Condition: None.
  - Files: `frontend/src/components/JsonViewer.tsx`, `frontend/src/styles.css`

- [x] (02B): Build the Agent 1 retrieval score table
  - Source of Truth: `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 9. Implementation Steps`; `docs/plans/Plan_15.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.4 Scoring Formula`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.6 Agent 1 Output Schema`
  - Source Requirements:
    - Read Agent 1 candidates from step output.
    - Show chunk ID, file name, semantic similarity, graph relevance, keyword overlap, metadata match, position score, and final score.
    - Score fields must match Agent 1 output names.
  - Details: Present the persisted candidate ranking without recomputing or reordering it.
  - Dependencies: (01B), (02A).
  - User Action: None.
  - Agent Work: Add defensive candidate parsing from `output.candidates`; render the actual fields `semantic_similarity`, `graph_relevance`, `keyword_overlap`, `metadata_match`, `recency_or_position_score`, and `final_score`; include chunk/file identity and a clear unavailable/empty state for missing candidates.
  - Output: `RetrievalScoreTable` specialized debug panel.
  - Acceptance: Candidate rows preserve API order; numeric zero is not mistaken for missing; absent fields display a neutral unavailable value; malformed candidates do not crash or suppress raw JSON.
  - Validation: Compile, inspect against a real Agent 1 log in Batch06, and add focused tests only if existing test infrastructure supports them.
  - Blocked Condition: None.
  - Files: `frontend/src/components/RetrievalScoreTable.tsx`, `frontend/src/styles.css`

- [x] (02C): Build the Agent 2 verification result panel
  - Source of Truth: `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 11. Agent 2: Evidence Verification Agent` > `## 11.4 Agent 2 Output Schema`
  - Source Requirements:
    - Display `verified_chunks`, `rejected_chunks`, `missing_information`, and `confidence`.
    - Keep verification results readable.
  - Details: Build a debug-focused Agent 2 summary that retains internal identifiers when present because this page is explicitly for developers.
  - Dependencies: (01B), (02A).
  - User Action: None.
  - Agent Work: Parse Agent 2 output defensively; show verified and rejected groups with counts, chunk/file identity, quote, page/reason fields when present, missing-information boolean, and confidence including zero; provide empty/malformed states.
  - Output: `VerificationResultPanel` specialized debug panel.
  - Acceptance: Verified and rejected chunks are structurally distinct; missing information and confidence use visible labels; malformed sections do not crash and raw JSON remains available.
  - Validation: Compile and inspect against a real Agent 2 log in Batch06; tests are conditional on existing infrastructure.
  - Blocked Condition: None.
  - Files: `frontend/src/components/VerificationResultPanel.tsx`, `frontend/src/styles.css`

- [x] (02D): Build the Agent 3 answer and self-check panel
  - Source of Truth: `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.5 Self-Check`; `docs/plans/Master_Plan.md` > `# 12. Agent 3: Answer Generation and Self-Check Agent` > `## 12.6 Agent 3 Output Schema`
  - Source Requirements:
    - Display the final answer and Agent 3 self-check booleans.
    - Make answer generation and self-check traceable.
  - Details: Support the current persisted `self_check_result` key while remaining compatible with a `self_check` payload if encountered.
  - Dependencies: (01B), (02A).
  - User Action: None.
  - Agent Work: Parse and display `final_answer`, optional draft answer summary, confidence, reasoning summary, citations count/details where useful, and the self-check fields `uses_only_verified_chunks`, `has_citation`, `has_unsupported_claims`, and `is_ready`; show explicit true/false text.
  - Output: `SelfCheckPanel` specialized Agent 3 debug panel.
  - Acceptance: Current `self_check_result` logs render correctly; false values remain visible; missing/malformed self-check data shows a neutral state; raw output remains available.
  - Validation: Compile and inspect against a real Agent 3 log in Batch06; tests are conditional on existing infrastructure.
  - Blocked Condition: None.
  - Files: `frontend/src/components/SelfCheckPanel.tsx`, `frontend/src/styles.css`

### Files or Modules Likely Created or Updated

- `frontend/src/components/JsonViewer.tsx`
- `frontend/src/components/RetrievalScoreTable.tsx`
- `frontend/src/components/VerificationResultPanel.tsx`
- `frontend/src/components/SelfCheckPanel.tsx`
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- Safe raw JSON rendering.
- Agent 1 score table using actual field names.
- Agent 2 verified/rejected/missing/confidence panel.
- Agent 3 final answer and self-check panel.

### Acceptance Criteria

- Specialized panels never replace or block raw JSON access.
- Unknown, absent, or malformed payload fields do not crash.
- Numeric zero and boolean false render correctly.
- Internal chunk IDs are allowed only in this debug context.
- No frontend re-scoring, verification, or self-check logic is introduced.

### Required Tests or Validations

- `cd frontend && npm run build` in Batch06
- Conditional component tests if configured
- Manual inspection against real Agent 1, Agent 2, and Agent 3 logs
- Long-content and malformed-payload checks

### Explicit Non-Goals

- Editing JSON.
- Download/export.
- Client-side reranking or verification.
- Graph visualization.
- Replacing the evidence viewer.

## Mandatory Batch03 - Agent Step List and Detail Viewer

### Goal

Create the combined logs workspace with an ordered selectable step list, a resilient detail panel, specialized recognized-step views, raw input/output, and visible failure metadata.

### Why this batch exists

Developers need to move through every persisted step and correlate identity, status, timestamp, errors, structured summaries, and raw payloads in one place.

### Inputs / Dependencies

- Completed Batch01 contracts
- Completed Batch02 display components
- Chronologically ordered `AgentRunLogsResponse.steps`

### Tasks

- [x] (03A): Build the ordered agent step list and selection state
  - Source of Truth: `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_15.md` > `## 9. Implementation Steps`; `docs/plans/Plan_15.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Show agent name, step name, status, timestamp, and error indicator.
    - Allow a developer to inspect every persisted step.
  - Details: Create the navigation side of `AgentLogViewer` while preserving server order and supporting duplicate or unknown step names.
  - Dependencies: Batch01.
  - User Action: None.
  - Agent Work: Render every step as a keyboard-operable selectable control; track selection by stable list position plus step metadata rather than assuming unique names; select the first step by default when available; reset safely when a new run response arrives.
  - Output: Ordered, accessible agent step list.
  - Acceptance: Every response step is visible in original order; selected state, success/failed text, timestamp, and error presence are clear; duplicate/unknown steps remain selectable.
  - Validation: Compile; keyboard and real-log checks in Batch06; conditional component tests if configured.
  - Blocked Condition: None.
  - Files: `frontend/src/components/AgentLogViewer.tsx`, `frontend/src/styles.css`

- [x] (03B): Build the selected-step detail panel and recognized-step dispatch
  - Source of Truth: `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_15.md` > `## 9. Implementation Steps`; `docs/plans/Plan_15.md` > `## 13. Failure Handling`; `docs/plans/Plan_15.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Show specialized panels for recognized steps.
    - Show raw JSON for every step.
    - Malformed output must still render in raw JSON.
  - Details: Compose Batch02 components beneath selected-step metadata without making specialized parsing a failure boundary.
  - Dependencies: (03A), Batch02.
  - User Action: None.
  - Agent Work: Dispatch by `step_name` to Agent 1, Agent 2, or Agent 3 panels; optionally use a documented `agent_name` compatibility fallback; render status, timestamp, and nullable `error_message`; always render separately labeled raw input and output viewers.
  - Output: Full selected-step detail experience.
  - Acceptance: Recognized successful steps show their structured panel plus raw input/output; failed and unknown steps show metadata/errors plus raw input/output; a specialized parser failure cannot blank the detail panel.
  - Validation: Compile; inspect all three real step types, an unknown step fixture if tests exist, and failed/malformed payload behavior in Batch06.
  - Blocked Condition: None.
  - Files: `frontend/src/components/AgentLogViewer.tsx`, Batch02 component imports, `frontend/src/styles.css`

- [x] (03C): Add viewer empty-state, formatting, and accessibility behavior
  - Source of Truth: `docs/plans/Plan_15.md` > `## 11. Required Tests`; `docs/plans/Plan_15.md` > `## 13. Failure Handling`; `docs/plans/Plan_15.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Empty steps show an empty state.
    - Long JSON and quotes do not overflow.
    - Debug information remains readable.
  - Details: Complete viewer-level semantics and layout behavior before page integration.
  - Dependencies: (03A), (03B).
  - User Action: None.
  - Agent Work: Add a clear no-steps state; use appropriate headings, lists, status/error announcements, focus-visible styles, and responsive list/detail behavior; ensure timestamps use a readable format while raw values remain available in data.
  - Output: Accessible, resilient `AgentLogViewer`.
  - Acceptance: Zero steps does not render a broken selection panel; keyboard focus is visible; status is not color-only; long content stays within the workspace at desktop and narrow widths.
  - Validation: Manual keyboard, empty-state, and overflow checks in Batch06; conditional tests if configured.
  - Blocked Condition: None.
  - Files: `frontend/src/components/AgentLogViewer.tsx`, `frontend/src/styles.css`

### Files or Modules Likely Created or Updated

- `frontend/src/components/AgentLogViewer.tsx`
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- Ordered selectable step list.
- Selected-step metadata and error display.
- Recognized Agent 1/2/3 structured panel dispatch.
- Raw input/output for every step.
- Empty, unknown, failed, and malformed-step resilience.

### Acceptance Criteria

- Every returned step is selectable and inspectable.
- Step status and timestamp are visible.
- Failed steps show nullable errors when present.
- Raw JSON is always available.
- Unknown step names do not disappear.
- Viewer is keyboard-usable and responsive.

### Required Tests or Validations

- `cd frontend && npm run build` in Batch06
- Conditional viewer tests if configured
- Manual keyboard selection
- Real three-step run inspection
- Empty, unknown, failed, malformed, and long-content checks where fixtures or real data are available

### Explicit Non-Goals

- Timeline graph.
- Step mutation or retry.
- Run deletion.
- Cross-run comparison.

## Mandatory Batch04 - Logs Page Lookup and Chat Integration

### Goal

Create the Agent Logs page with validated direct run lookup and connect the latest chat answer to its logs.

### Why this batch exists

Plan 15 must work both when a developer already knows a run ID and when a run has just been produced by the existing chat workflow.

### Inputs / Dependencies

- Completed Batch01 API client
- Completed Batch03 viewer
- Existing Plan 14 `ChatPage` and returned `agent_run_id`
- Existing React Router application

### Tasks

- [x] (04A): Build the Agent Logs page lookup and load state machine
  - Source of Truth: `docs/plans/Plan_15.md` > `## 1. Goal`; `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_15.md` > `## 8. API Design`; `docs/plans/Plan_15.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Provide an agent run ID input.
    - Block missing IDs and validate UUID format if format validation is used.
    - Show loading, not-found, empty, and backend error states.
  - Details: Build a page-level form and explicit request states around `getAgentRunLogs`.
  - Dependencies: (01C), Batch03.
  - User Action: None.
  - Agent Work: Create `AgentLogsPage.tsx`; keep input text controlled; trim and validate UUID before request; prevent duplicate submit while loading; distinguish idle, loading, success, empty-response, and error states; render `AgentLogViewer` only for a successful response; ignore stale responses after a new lookup.
  - Output: Direct run lookup page.
  - Acceptance: No request is sent for blank/invalid IDs; valid IDs load the requested run; not-found/backend/connection messages are safe; an empty steps array shows a truthful empty state.
  - Validation: Compile; manual valid/invalid/not-found/backend failure checks in Batch06; conditional tests if configured.
  - Blocked Condition: None.
  - Files: `frontend/src/pages/AgentLogsPage.tsx`, `frontend/src/api/agentRuns.ts`, `frontend/src/types/agentRuns.ts`

- [x] (04B): Support direct route parameter loading and shareable run URLs
  - Source of Truth: `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 9. Implementation Steps`; `docs/plans/Plan_15.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Support an ID input or links from chat results.
    - Support optional route parameter behavior.
    - User can load logs by `agent_run_id`.
  - Details: Keep the route and input synchronized without request loops or stale data.
  - Dependencies: (04A).
  - User Action: None.
  - Agent Work: Read optional `agentRunId` from React Router; prefill and auto-load valid direct IDs; navigate submitted lookups to `/agent-logs/{encoded-id}`; preserve `/agent-logs` as the empty lookup page; handle invalid route values with validation instead of a backend call.
  - Output: Direct and shareable Agent Logs URLs.
  - Acceptance: Opening a valid direct URL loads exactly once; submitting a new ID updates the URL and data; returning to the base route gives a clean lookup state.
  - Validation: Manual route reload, base route, valid param, invalid param, and changed-param checks in Batch06.
  - Blocked Condition: None.
  - Files: `frontend/src/pages/AgentLogsPage.tsx`, `frontend/src/App.tsx`

- [x] (04C): Link the latest chat answer to its agent logs
  - Source of Truth: `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 5. Dependencies`; `docs/plans/Plan_15.md` > `## 9. Implementation Steps`; `docs/plans/Plan_15.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Add links from chat results when Plan 14 components are present.
    - Use the last returned `agent_run_id`.
  - Details: Add a route-aware debug action to the current successful answer area without changing chat submission or evidence loading.
  - Dependencies: (04B), completed Plan 14 chat page.
  - User Action: None.
  - Agent Work: Add an `Inspect agent logs` link/button for `latestResponse.agent_run_id` using React Router navigation; place it near answer/evidence actions; ensure it updates when a new answer replaces the old response and is absent before a successful answer.
  - Output: Chat-to-logs navigation for the latest real run.
  - Acceptance: Successful chat results link to the matching encoded run URL; no fabricated or stale run ID is used; existing answer, citation, and evidence behavior remains intact.
  - Validation: Build and perform a real chat-to-logs browser flow in Batch06.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only if live chat prerequisites or a ready document are unavailable for manual validation; implementation itself is not blocked.
  - Files: `frontend/src/pages/ChatPage.tsx`, optionally `frontend/src/components/AnswerPanel.tsx`, `frontend/src/styles.css`

### Files or Modules Likely Created or Updated

- `frontend/src/pages/AgentLogsPage.tsx`
- `frontend/src/pages/ChatPage.tsx`
- Optional `frontend/src/components/AnswerPanel.tsx`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- Agent Logs lookup form and state handling.
- Direct `/agent-logs/{agent_run_id}` loading behavior.
- Base `/agent-logs` lookup behavior.
- Latest chat answer link to matching logs.

### Acceptance Criteria

- Blank and invalid IDs are blocked locally.
- Valid IDs load through the typed API helper.
- Direct URLs are shareable and reloadable.
- Stale requests do not replace a newer lookup.
- Chat link uses the latest actual `agent_run_id`.
- Existing chat/evidence behavior is preserved.

### Required Tests or Validations

- `cd frontend && npm run build` in Batch06
- Conditional page tests if configured
- Manual base route, direct route, invalid ID, changed ID, and chat-link checks

### Explicit Non-Goals

- Run history.
- Search or filtering across runs.
- Session browser.
- Automatic polling.
- Re-running failed steps.

## Mandatory Batch05 - Routing, Navigation, Styling, and Scope Hardening

### Goal

Mount the Agent Logs experience in the application shell, complete responsive/accessibility styling, and prove the implementation remains a read-only debug page within Plan 15 scope.

### Why this batch exists

The feature is incomplete until it is reachable, usable at narrow widths, safe around long JSON, and audited against secret and admin-dashboard scope creep.

### Inputs / Dependencies

- Completed Batch01 through Batch04
- Existing `frontend/src/App.tsx`
- Existing `frontend/src/styles.css`
- Existing Upload, Documents, Chat, and Evidence routes

### Tasks

- [ ] (05A): Mount Agent Logs routes and primary navigation
  - Source of Truth: `docs/plans/Plan_15.md` > `## 3. Scope`; `docs/plans/Plan_15.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_15.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure`
  - Source Requirements:
    - Add route and navigation for Agent Logs.
    - Preserve the existing frontend application structure.
  - Details: Expose both the lookup and direct-ID routes through the existing React Router shell.
  - Dependencies: (04B).
  - User Action: None.
  - Agent Work: Add an Agent Logs `NavLink`; mount `/agent-logs` and `/agent-logs/:agentRunId`; preserve `/upload`, `/documents`, `/chat`, `/evidence/:agentRunId`, root redirect, and unknown-route behavior.
  - Output: Reachable Agent Logs page and active navigation state.
  - Acceptance: Navigation uses client-side routing; base and direct routes render; existing routes still work; unknown routes do not accidentally expose a run.
  - Validation: Build and manual route/navigation checks in Batch06.
  - Blocked Condition: None.
  - Files: `frontend/src/App.tsx`

- [ ] (05B): Complete responsive, overflow-safe, and accessible debug styling
  - Source of Truth: `docs/plans/Plan_15.md` > `## 9. Implementation Steps`; `docs/plans/Plan_15.md` > `## 11. Required Tests`; `docs/plans/Plan_15.md` > `## 13. Failure Handling`; `docs/plans/Plan_15.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Long JSON and quotes must not overflow the page.
    - Step list/detail and status/error information must remain readable.
    - Manual UI checks are required.
  - Details: Fit the debug workspace into the current compact application visual language.
  - Dependencies: Batch02 through (05A).
  - User Action: None.
  - Agent Work: Add desktop list/detail layout, narrow single-column behavior, contained table/JSON scrolling, long-token handling, visible focus, selected-step styling, status/error text, loading/empty panels, readable tables/cards, and touch-friendly controls.
  - Output: Production-ready Agent Logs styling.
  - Acceptance: No page-level horizontal overflow at 320px, 375px, or desktop widths; JSON/table overflow is contained; controls remain usable; status and selection are not color-only.
  - Validation: Manual responsive, keyboard, zoom/long-content checks in Batch06.
  - Blocked Condition: None.
  - Files: `frontend/src/styles.css`, Agent Logs page/components only when markup adjustments are required

- [ ] (05C): Perform Plan 15 secret, endpoint, and scope hardening
  - Source of Truth: `docs/plans/Plan_15.md` > `## 2. Why This Plan Exists`; `docs/plans/Plan_15.md` > `## 4. Out of Scope`; `docs/plans/Plan_15.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_15.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `# 21. Non-Goals for MVP`
  - Source Requirements:
    - Do not expose backend environment variables or secrets.
    - Do not add an admin dashboard, multi-user run browser, editing, graph visualization, or production observability dashboard.
    - Keep the page debug-focused.
  - Details: Audit the completed implementation and remove accidental scope expansion before final validation.
  - Dependencies: Batch01 through (05B).
  - User Action: None.
  - Agent Work: Inspect/search the diff for new run-list endpoints, direct provider/Supabase/Qdrant calls, backend-only env names, prompt/environment display, auth/JWT, mutation controls, polling, graph/observability libraries, hardcoded origins, and unrelated backend changes.
  - Output: Scope-hardened Plan 15 implementation with recorded audit evidence.
  - Acceptance: Runtime changes are limited to the existing logs response alignment and approved frontend files; the page loads one known run only and remains read-only.
  - Validation: Record exact scope-search commands and results in the execution report.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/agent_runs.py`, `backend/app/services/agent_run_service.py`, `backend/tests/test_agent_runs_api.py`, `frontend/src/**`

### Files or Modules Likely Created or Updated

- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- Plan 15 frontend page/components
- Plan 15 backend contract files from Batch01

### Required Outputs / Artifacts

- Agent Logs primary navigation.
- Base and direct routes.
- Responsive and accessible debug workspace.
- Secret/endpoint/scope audit evidence.

### Acceptance Criteria

- Agent Logs is reachable through navigation.
- Existing application routes remain intact.
- UI is usable from 320px through desktop.
- Raw JSON and tables do not cause page overflow.
- No admin browser, mutation, auth, graph visualization, observability platform, direct provider call, hardcoded backend URL, or secret display is added.

### Required Tests or Validations

- `cd frontend && npm run build` in Batch06
- Manual route, navigation, keyboard, and responsive checks
- Scope-search commands
- Git diff review

### Explicit Non-Goals

- Design-system migration.
- New CSS framework.
- Admin navigation.
- Run management actions.
- Backend observability integrations.

## Mandatory Batch06 - Automated and Manual Validation, Reporting, and Handoff

### Goal

Prove the aligned endpoint and Agent Logs frontend satisfy Plan 15 with real evidence where available, accurately report blocked scenarios, and prepare a traceable reviewer handoff.

### Why this batch exists

Plan 15 explicitly requires build/test commands, real or mocked run disclosure, happy-path inspection of all three agents, negative cases, failed-run visibility, and an execution report. This batch prevents unsupported completion claims.

### Inputs / Dependencies

- Completed Batch01 through Batch05
- Configured backend and frontend dependencies
- A known real `agent_run_id` with persisted Agent 1, Agent 2, and Agent 3 steps for full happy-path validation
- A failed run ID or safe failure fixture for failed-step validation where available

### Tasks

- [ ] (06A): Run mandatory automated validation
  - Source of Truth: `docs/plans/Plan_15.md` > `## 11. Required Tests`; `docs/plans/Plan_15.md` > `## 12. Acceptance Criteria`; `README.md` > `## Testing and Validation`
  - Source Requirements:
    - Run the frontend production build.
    - Run frontend tests if configured.
    - Prove the existing logs endpoint alignment.
  - Details: Run fresh validation after all implementation changes and report absent test infrastructure accurately.
  - Dependencies: Batch01 through Batch05.
  - User Action: None.
  - Agent Work: Run targeted backend agent-run tests; inspect `frontend/package.json`; run `npm run build`; run `npm test` only if a real test script exists at execution time; run any focused frontend tests added under existing infrastructure.
  - Output: Recorded automated validation evidence.
  - Acceptance: Targeted backend tests pass; frontend build passes; frontend test status is truthfully reported as passed, failed, or not configured.
  - Validation: `cd backend && pytest tests/test_agent_runs_api.py -v`; `cd frontend && npm run build`; conditional `npm test`.
  - Blocked Condition: None unless dependencies cannot be installed or accessed without user-controlled setup; missing frontend test infrastructure is not a blocker.
  - Files: `docs/reports/report_15_execute_agent.md` during execution reporting

- [ ] (06B): Perform real happy-path Agent Logs browser validation
  - Source of Truth: `docs/plans/Plan_15.md` > `## 1. Goal`; `docs/plans/Plan_15.md` > `## 11. Required Tests`; `docs/plans/Plan_15.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_15.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Open a known run ID and inspect all persisted steps.
    - Confirm Agent 1 scores, Agent 2 verification, Agent 3 self-check, and raw JSON.
    - Report whether a real or mocked run ID was used.
  - Details: Validate the full developer workflow through the browser against the mounted backend.
  - Dependencies: (06A), running backend/frontend, known run with three persisted steps.
  - User Action: User must provide or permit creation of a real run through the existing chat workflow if no suitable persisted run exists.
  - Agent Work: Open Agent Logs; load the run directly and through the input; inspect step ordering/status/timestamps; open each Agent 1/2/3 step; verify actual score fields, verified/rejected/missing/confidence data, final answer/self-check, and raw input/output; use the chat `Inspect agent logs` link and confirm it opens the matching run.
  - Output: Happy-path browser validation result with real/mocked status.
  - Acceptance: A developer can inspect every persisted step; all required specialized panels and raw JSON are visible; chat-to-logs navigation uses the same `agent_run_id`.
  - Validation: Browser notes and screenshots where useful; compare visible IDs/fields with the API response without exposing secrets.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if no suitable run exists, provider/backend credentials or ready document data are unavailable, or the required browser surface is unavailable.
  - Files: `docs/reports/report_15_execute_agent.md` during execution reporting

- [ ] (06C): Perform negative, failed-run, malformed-data, and responsive checks
  - Source of Truth: `docs/plans/Plan_15.md` > `## 11. Required Tests`; `docs/plans/Plan_15.md` > `## 13. Failure Handling`; `docs/plans/Plan_15.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Invalid ID shows validation or not-found feedback.
    - Backend failure shows a safe error.
    - Failed runs show error messages.
    - Empty and malformed output remain readable.
    - Long JSON does not break layout.
  - Details: Validate required failure and resilience states without corrupting real run data.
  - Dependencies: Batch01 through Batch05, browser access.
  - User Action: User must provide a failed run ID only if no safe local fixture or existing failed run is available.
  - Agent Work: Test blank ID, malformed UUID, valid not-found UUID, backend connection failure, empty steps, failed step with `error_message`, unknown/malformed structured output with raw fallback where safely testable, keyboard selection/focus, long JSON/tables, and 320px/375px/desktop layouts.
  - Output: Negative and resilience validation result.
  - Acceptance: Local validation blocks invalid requests; safe backend errors render; failed status/error is visible; empty/malformed data does not crash; raw JSON remains available; no page-level overflow occurs.
  - Validation: Browser/manual notes, conditional component fixtures if a test runner exists, and exact blocked reasons for scenarios that cannot be produced safely.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for failed/empty/malformed live scenarios requiring unavailable user-controlled data or browser access; all locally reproducible validation must still run.
  - Files: `docs/reports/report_15_execute_agent.md` during execution reporting

- [ ] (06D): Write the execution report and reviewer handoff
  - Source of Truth: `docs/plans/Plan_15.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_15.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Report files created/modified, commands, tests, known issues, and intentional exclusions.
    - State whether a real or mocked run ID was used.
    - Give the reviewer evidence for scope, acceptance, raw fallback, secrets, and score fields.
  - Details: Consolidate task-by-task implementation and validation evidence for review.
  - Dependencies: (06A), (06B), (06C), scope audit.
  - User Action: None.
  - Agent Work: Create or append `docs/reports/report_15_execute_agent.md` with completed/partial/blocked task IDs, changed files, command results, browser results, real/mocked run disclosure, contract-alignment rationale, known issues, residual validation gaps, scope exclusions, and reviewer notes.
  - Output: Plan 15 execution report ready for review.
  - Acceptance: Every claimed acceptance criterion is traceable to a test, browser result, inspection, or explicit blocked status; no blocked scenario is reported as passed.
  - Validation: Review report completeness against Plan 15 sections 14 and 15 and this task file's completion template.
  - Blocked Condition: None.
  - Files: `docs/reports/report_15_execute_agent.md`

### Files or Modules Likely Created or Updated

- `docs/reports/report_15_execute_agent.md`
- `frontend/src/pages/AgentLogsPage.test.tsx` only if a real frontend test runner exists
- No runtime source files should change in this batch except focused fixes required by failed validation
- Conditional frontend test files only when a real test runner exists

### Required Outputs / Artifacts

- Passing targeted backend agent-run test result.
- Passing frontend production build.
- Accurate frontend test status.
- Happy-path real/mocked logs inspection status.
- Negative, failed-run, malformed, keyboard, and responsive status.
- Scope-hardening evidence.
- Complete execution report and reviewer handoff.

### Acceptance Criteria

- Backend logs response contract tests pass.
- Frontend build passes.
- Frontend tests are run only when configured.
- Real or mocked run usage is disclosed.
- Agent 1, Agent 2, Agent 3, raw JSON, status, timestamp, and error behavior are validated or explicitly blocked.
- Invalid/not-found/backend failure states are checked.
- 320px, 375px, and desktop layouts are checked.
- Report includes changed files, commands, results, known issues, intentional exclusions, and reviewer evidence.

### Required Tests or Validations

- `cd backend && pytest tests/test_agent_runs_api.py -v`
- `cd frontend && npm run build`
- `cd frontend && npm test` only if a real test script exists
- Browser happy-path logs inspection
- Browser invalid/not-found/backend failure checks
- Browser failed/empty/malformed checks where data is safely available
- Browser keyboard and responsive checks
- Secret/endpoint/scope searches

### Explicit Non-Goals

- Fabricating successful browser evidence.
- Mutating production run data to create an error state.
- Adding a test framework during final validation.
- Expanding backend or frontend scope to fix unrelated failures.
- Committing before the orchestrator reaches the appropriate commit gate.

## Optional Future Tracks

Plan 15 approves no optional implementation track inside this task. The following items remain outside the mandatory chain and require separate plans before work begins:

- Admin or multi-user run browser.
- Agent run or step editing, deletion, retry, or replay.
- Graph visualization.
- Production observability dashboards, tracing vendors, or metrics platforms.
- Streaming/polling live step updates.
- Cross-run comparison, search, export, or retention management.
- A new frontend testing framework when separately approved.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05
- Batch05 -> Batch06

Optional future tracks are outside the mandatory dependency chain.

## Global Verification Checklist

- [ ] `docs/plans/Plan_15.md` remained the primary scope authority.
- [ ] The existing logs endpoint was aligned rather than duplicated.
- [ ] No database migration or new table was added.
- [ ] `AgentRunLogStepResponse` exposes `step_name` and nullable `error_message`.
- [ ] Existing agent-run ownership and safe backend errors remain intact.
- [ ] Backend steps remain chronologically ordered.
- [ ] Targeted `test_agent_runs_api.py` validation passes.
- [ ] `frontend/src/types/agentRuns.ts` defines the complete logs contract without `any`.
- [ ] `getAgentRunLogs` uses the existing Axios `apiClient`.
- [ ] The run ID path segment is encoded.
- [ ] `VITE_API_BASE_URL` remains the only required frontend runtime setting.
- [ ] No hardcoded backend origin is introduced.
- [ ] No frontend code calls Supabase, Qdrant, ShopAIKey, or another provider directly.
- [ ] No backend-only key, environment dump, prompt, stack trace, or raw exception is displayed.
- [ ] Blank run IDs are blocked before a request.
- [ ] Malformed UUIDs are blocked before a request.
- [ ] Valid not-found IDs show a safe clear message.
- [ ] Backend connection/service failures show safe clear messages.
- [ ] Stale responses cannot replace a newer run lookup.
- [ ] Base `/agent-logs` route works.
- [ ] Direct `/agent-logs/:agentRunId` route works.
- [ ] Submitted run IDs update the route.
- [ ] Agent Logs is present in primary navigation.
- [ ] Existing upload, documents, chat, and evidence routes still work.
- [ ] Chat exposes logs only after a successful response with a real `agent_run_id`.
- [ ] Chat logs link opens the matching run.
- [ ] Every returned step appears in original order.
- [ ] Duplicate and unknown steps remain selectable.
- [ ] Step list shows agent name, step name, status, timestamp, and error indication.
- [ ] Failed steps display nullable `error_message` when present.
- [ ] Status and errors are not communicated by color alone.
- [ ] Raw input JSON is visible for every selected step.
- [ ] Raw output JSON is visible for every selected step.
- [ ] Raw JSON renders objects, arrays, primitives, nulls, and malformed/unexpected values safely.
- [ ] Specialized panels never suppress raw JSON.
- [ ] Agent 1 panel reads `output.candidates`.
- [ ] Agent 1 panel uses `semantic_similarity`.
- [ ] Agent 1 panel uses `graph_relevance`.
- [ ] Agent 1 panel uses `keyword_overlap`.
- [ ] Agent 1 panel uses `metadata_match`.
- [ ] Agent 1 panel uses `recency_or_position_score`.
- [ ] Agent 1 panel uses `final_score`.
- [ ] Agent 1 candidates preserve backend order and are not re-scored.
- [ ] Agent 2 panel separates verified and rejected chunks.
- [ ] Agent 2 panel shows `missing_information`.
- [ ] Agent 2 panel shows confidence, including zero.
- [ ] Agent 3 panel shows the final answer when present.
- [ ] Agent 3 panel reads current `self_check_result` data.
- [ ] Agent 3 compatibility with `self_check` does not hide malformed data.
- [ ] Boolean false values are displayed explicitly.
- [ ] Unknown/malformed structured outputs still show raw JSON.
- [ ] Empty step arrays show a clear empty state.
- [ ] Long JSON, quotes, IDs, file names, and tables do not cause page-level overflow.
- [ ] JSON/table overflow remains contained and usable.
- [ ] Keyboard focus is visible.
- [ ] Step selection is keyboard-operable.
- [ ] UI works at 320px, 375px, and desktop widths.
- [ ] No run list, admin dashboard, auth/JWT, mutation controls, graph visualization, production observability tooling, or polling was added.
- [ ] No unrelated backend agent behavior or frontend feature was changed.
- [ ] `npm run build` passes.
- [ ] Frontend tests were run only if a real test command exists.
- [ ] Absence of frontend test infrastructure was reported accurately when applicable.
- [ ] Manual validation states whether the run ID was real or mocked.
- [ ] Manual happy-path Agent 1/2/3 and raw JSON inspection passed or was marked `BLOCKED_BY_USER_ACTION`.
- [ ] Negative, failed-run, malformed, keyboard, and responsive checks passed or were accurately marked blocked.
- [ ] Execution report contains files, commands, results, known issues, exclusions, run-ID provenance, and reviewer notes.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [x] Batch01 - Existing Logs Contract and Frontend API Boundary
- [x] Batch02 - Raw JSON and Specialized Step Panels
- [x] Batch03 - Agent Step List and Detail Viewer
- [x] Batch04 - Logs Page Lookup and Chat Integration
- [ ] Batch05 - Routing, Navigation, Styling, and Scope Hardening
- [ ] Batch06 - Automated and Manual Validation, Reporting, and Handoff

### Task IDs

#### Batch01

- [x] (01A): Align the existing logs response with persisted step metadata
- [x] (01B): Define frontend agent-run log types
- [x] (01C): Extend the agent-runs API client with logs lookup

#### Batch02

- [x] (02A): Build the reusable raw JSON viewer
- [x] (02B): Build the Agent 1 retrieval score table
- [x] (02C): Build the Agent 2 verification result panel
- [x] (02D): Build the Agent 3 answer and self-check panel

#### Batch03

- [x] (03A): Build the ordered agent step list and selection state
- [x] (03B): Build the selected-step detail panel and recognized-step dispatch
- [x] (03C): Add viewer empty-state, formatting, and accessibility behavior

#### Batch04

- [x] (04A): Build the Agent Logs page lookup and load state machine
- [x] (04B): Support direct route parameter loading and shareable run URLs
- [x] (04C): Link the latest chat answer to its agent logs

#### Batch05

- [ ] (05A): Mount Agent Logs routes and primary navigation
- [ ] (05B): Complete responsive, overflow-safe, and accessible debug styling
- [ ] (05C): Perform Plan 15 secret, endpoint, and scope hardening

#### Batch06

- [ ] (06A): Run mandatory automated validation
- [ ] (06B): Perform real happy-path Agent Logs browser validation
- [ ] (06C): Perform negative, failed-run, malformed-data, and responsive checks
- [ ] (06D): Write the execution report and reviewer handoff

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
- reason: missing real agent run, missing failed-run fixture, unavailable ready document, unavailable backend/provider setup, unavailable browser surface, or other safe summary

#### Validation Responsibility
- user-provided setup confirmed: yes / no / not required
- agent validation run after setup: yes / no
- validation command: result

#### Agent Run Validation Source
- run type: real / mocked / not required
- run ID: redacted or safe non-secret identifier
- required steps present: Agent 1 / Agent 2 / Agent 3 / other

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

Future execution agents must not claim completion unless the required tests, build, browser checks, and acceptance criteria are satisfied or explicitly recorded as blocked. They must never include secrets, private environment values, provider payload credentials, or unredacted sensitive debug content in reports.
