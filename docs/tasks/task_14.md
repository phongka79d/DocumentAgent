# Plan 14 - Frontend Chat and Evidence Viewer Execution Tasks

## Purpose

Create a detailed execution task file for the approved frontend chat and evidence viewer milestone. This task file guides a future Execution Agent to add typed chat/evidence API clients, ready-document selection, question input, answer/confidence/citation display, evidence inspection for verified and rejected chunks, route/navigation updates, frontend validation, manual browser checks, and execution reporting for `docs/plans/Plan_14.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_14.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Current project context reviewed: `README.md`
- Current frontend files inspected for planning context: `frontend/package.json`, `frontend/src/App.tsx`, `frontend/src/api/client.ts`, `frontend/src/api/documents.ts`, `frontend/src/types/documents.ts`, and the current `frontend/src/` tree.
- Conflict note: No blocking architecture conflict was found. Plan 14 narrows the broader master-plan frontend phase to chat and evidence viewing only. The master plan includes an agent logs/debug page, but Plan 14 explicitly excludes agent logs/debug UI, so logs UI and calls to the public logs endpoint are not part of this task. The current frontend uses React Router, Axios, TypeScript, Vite, and plain `styles.css`; this task does not require adding Tailwind, TanStack Query, a new component framework, backend APIs, database schema changes, authentication, or streaming.

## Source Section Index

- `docs/plans/Plan_14.md` > `## 1. Goal` -> chat page must select ready documents, ask through `/api/chat/ask`, show answer, confidence, citations, and open evidence by returned `agent_run_id`.
- `docs/plans/Plan_14.md` > `## 2. Why This Plan Exists` -> expose document QA and verified-evidence inspection now that backend workflow is complete.
- `docs/plans/Plan_14.md` > `## 3. Scope` -> chat client, agent-run evidence client, selector, question form, answer, confidence, citations, evidence viewer, states, tests, and build checks.
- `docs/plans/Plan_14.md` > `## 4. Out of Scope` -> no agent logs/debug UI, streaming, broad session history, prompt/API key exposure, evidence editing, or authentication.
- `docs/plans/Plan_14.md` > `## 5. Dependencies` -> Plan 12 and Plan 13 completion plus at least one ready document for meaningful manual testing.
- `docs/plans/Plan_14.md` > `## 6. Required Files and Folders` -> expected frontend API, type, page, component, route, and optional test files.
- `docs/plans/Plan_14.md` > `## 7. Data Model / Schema Changes` -> no backend schema changes; frontend chat request/response and evidence response types.
- `docs/plans/Plan_14.md` > `## 8. API Design` -> existing chat and evidence endpoints plus frontend validation rules.
- `docs/plans/Plan_14.md` > `## 9. Implementation Steps` -> ordered type, API, component, page, route, error handling, test, and build work.
- `docs/plans/Plan_14.md` > `## 10. Configuration and Environment Variables` -> `VITE_API_BASE_URL` only; no private provider keys in frontend env.
- `docs/plans/Plan_14.md` > `## 11. Required Tests` -> frontend build, conditional frontend tests, happy-path manual UI test, and negative manual UI tests.
- `docs/plans/Plan_14.md` > `## 12. Acceptance Criteria` -> reachable chat page, ready-document selection, question submission, answer/confidence/citations, evidence viewer, build, and no logs UI.
- `docs/plans/Plan_14.md` > `## 13. Failure Handling` -> no-ready-documents, empty-question, backend chat failure, evidence failure, missing citations, and long text wrapping.
- `docs/plans/Plan_14.md` > `## 14. Agent Report Requirement` -> files, commands, tests, issues, intentional exclusions, and manual test status.
- `docs/plans/Plan_14.md` > `## 15. Reviewer Checklist` -> scope, tests, acceptance, secrets, architecture, ready-only selection, citations, evidence separation, and responsive UI.
- `docs/plans/Master_Plan.md` > `## 2. Tech Stack` > `### Frontend` -> React, TypeScript, frontend styling, and Axios-compatible target stack.
- `docs/plans/Master_Plan.md` > `## 3. Authentication Policy` -> single-user MVP, no JWT, backend-only secrets, and all agent execution through backend.
- `docs/plans/Master_Plan.md` > `## 5. Core Features` > `### 5.3 Chat With Document Page` -> select documents and ask a question through backend workflow.
- `docs/plans/Master_Plan.md` > `## 5. Core Features` > `### 5.4 Evidence Viewer` -> inspect evidence used in the final answer.
- `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.4 Ask Question` -> chat request and response shape.
- `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.5 Get Evidence` -> agent-run evidence endpoint shape.
- `docs/plans/Master_Plan.md` > `# 14. Frontend Page Plan` > `## 14.3 Chat With Document Page` -> answer, confidence, citations, and evidence access.
- `docs/plans/Master_Plan.md` > `# 14. Frontend Page Plan` > `## 14.4 Evidence Viewer` -> verified/rejected evidence display fields.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> frontend `VITE_API_BASE_URL` and private-key boundary.
- `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure` -> expected frontend API, page, and component locations.
- `docs/plans/Master_Plan.md` > `# 18. Quality Rules` > `## 18.1 Grounding Rule` -> answers must be grounded in verified chunks.
- `docs/plans/Master_Plan.md` > `# 18. Quality Rules` > `## 18.3 Citation Rule` -> citations use file name plus quoted text.
- `docs/plans/Master_Plan.md` > `# 21. Non-Goals for MVP` -> no multi-user auth/JWT and other non-MVP features.
- `README.md` > `## Overview` -> Plan 12 backend chat/evidence APIs are implemented; frontend chat/evidence screens remain planned.
- `README.md` > `## Main Workflows` > `### Frontend Document API Client` -> existing Axios document API boundary through `apiClient`.
- `README.md` > `## Main Workflows` > `### Frontend Reusable Document Components` -> existing upload/documents frontend shell, routes, styles, and 320px support.
- `README.md` > `## Running the Project` > `### Backend API` -> mounted chat and agent-run inspection endpoints.
- `README.md` > `## Running the Project` > `### Production Frontend Build` -> current build command.
- `README.md` > `## Testing and Validation` -> no frontend test script currently exists; `npm run build` and `npm run preview` are configured.
- `README.md` > `## Development Notes for AI Agents` > `Important coordination rules` -> preserve frontend API/client boundary and do not move backend-only secrets to frontend.
- `README.md` > `## Known Gaps or Unclear Areas` -> frontend chat and evidence UI remain planned while public chat/evidence/log APIs are mounted.

## Approved Architecture Summary

Plan 14 approves a React 19, TypeScript, Vite, React Router, and Axios frontend extension built on the existing `frontend/src/api/client.ts` base client and `VITE_API_BASE_URL`. The frontend must call existing FastAPI endpoints only: `POST /api/chat/ask` for questions, `GET /api/agent-runs/{agent_run_id}/evidence` for evidence, and the existing document list API for ready-document selection.

The chat request contract contains an optional `session_id`, a non-empty `question`, and one or more selected `document_ids`. The chat response contains `answer`, `confidence`, `citations` shaped as file name plus quote, and `agent_run_id`. Evidence responses contain `verified_chunks` and `rejected_chunks`; the UI must keep those groups visually and semantically separate.

The frontend already has routed upload and document list pages, typed document API helpers, document status types, React Router navigation, responsive plain CSS, and no configured frontend test script. Plan 14 must preserve those existing routes while adding `/chat` and a direct evidence route such as `/evidence/:agentRunId`. Tests are conditional because `frontend/package.json` currently has no `test` script or testing libraries. The mandatory automated validation is `npm run build`, plus manual browser checks when backend/frontend services and at least one ready document are available.

Plan 14 does not approve backend work. It must not add database migrations, backend schemas, FastAPI routes, auth/JWT, provider calls from the browser, frontend secrets, streaming chat, editable evidence, multi-session chat history beyond passing an optional `session_id` when already available, or agent logs/debug UI.

## Global Implementation Rules

- Keep `docs/plans/Plan_14.md` as the source of truth for scope, file contracts, API calls, UI states, tests, acceptance, failure handling, and reviewer checks.
- Use `docs/plans/Master_Plan.md` only to clarify the approved target architecture, grounding/citation rules, chat/evidence endpoint shapes, and secret boundary.
- Use `README.md` and inspected frontend files only to understand current implementation state: React 19, Vite, TypeScript, React Router, Axios, document API/types, upload/documents routes, plain CSS, and no frontend test script.
- Make frontend-only runtime changes unless a frontend type import needs to consume existing frontend document types. Do not change backend API contracts, services, schemas, migrations, storage, retrieval, agent workflow, authentication, or provider configuration.
- Use the existing `apiClient` for chat and evidence HTTP calls. Preserve `VITE_API_BASE_URL` as the only required frontend runtime setting.
- Never add, read, log, bundle, or expose `SUPABASE_SERVICE_ROLE_KEY`, `QDRANT_API_KEY`, `SHOPAIKEY_API_KEY`, prompts, provider base secrets, or other backend-only settings in frontend code.
- Do not call Supabase, Qdrant, ShopAIKey, or any provider service directly from the browser.
- Do not call `GET /api/agent-runs/{agent_run_id}/logs` or build any agent logs/debug UI in Plan 14.
- Do not call `POST /api/documents/{document_id}/index`, invent document processing controls, or require document processing changes from the frontend.
- Let users select only documents whose frontend status is exactly `ready`. Documents with `uploaded`, `processing`, or `failed` status may be shown as unavailable context but must not be selectable for chat.
- Validate that the question is non-empty after trimming before submit.
- Validate that at least one ready document is selected before submit.
- Support selecting one or more ready documents because the backend request accepts `document_ids: string[]`.
- Disable duplicate chat submission while a chat request is active, and restore controls after success or failure.
- Store the latest returned `agent_run_id` after successful chat response so evidence can be opened for that answer.
- Load evidence only after a successful answer or when the user opens the evidence viewer/panel. Evidence load failure must not erase the displayed answer.
- Show answer, confidence, and citations. Citation display must use file name and quoted text.
- Do not show internal chunk IDs in the normal chat answer UI. The evidence UI should focus on file name, quote, page number where present, verification/rejection reason, and simple reasoning flag where present; chunk IDs are not required for Plan 14 display.
- Missing citations must render an explicit "no citations returned" state and should be reported as a backend issue during validation rather than hidden.
- Show safe error messages for backend chat failures, evidence failures, and backend connection failures. Never render stack traces, raw error objects, provider details, or secrets.
- Keep verified and rejected evidence visually separate and read-only.
- Keep long answers, file names, quotes, citations, reasons, buttons, and status text wrapping within their containers at desktop and 320-375px mobile widths.
- Use visible focus states and do not communicate status by color alone.
- Preserve the existing compact, work-focused application shell. Do not add a marketing landing page or decorative-only UI.
- Preserve the existing plain CSS approach in `frontend/src/styles.css`; do not add Tailwind, TanStack Query, a state-management library, a component framework, or a testing stack unless explicitly justified by existing project conventions or the user.
- Treat frontend tests as conditional on real test infrastructure. Do not fabricate `npm test` results or add broad test infrastructure just to satisfy the optional test references.
- Update the progress tracker only after each task's acceptance and validation conditions pass or an allowed blocked condition is recorded.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable React and TypeScript code.
- Use descriptive names for API functions, types, components, props, state, handlers, validation helpers, routes, styles, and tests.
- Keep functions, components, and modules focused on one clear responsibility.
- Prefer simple, explicit state and control flow over clever abstractions.
- Follow the existing React 19, Vite, Axios, React Router, and strict TypeScript conventions.
- Use clear TypeScript types for API requests, API responses, component props, chat state, evidence state, and validation states.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded backend URLs.
- Add comments only for non-obvious error mapping, evidence-loading timing, or browser-specific decisions.
- Keep frontend code free of backend-only secrets and backend-only configuration names except where a scope-safety check explicitly verifies they are absent.
- Avoid adding formatters, linters, state-management libraries, query libraries, CSS frameworks, test frameworks, or architecture changes outside Plan 14 unless already present or explicitly required.

## Batch Map

- Batch01 - Chat and Evidence Contracts and API Clients
- Batch02 - Ready Document Selector and Question Input Components
- Batch03 - Answer and Evidence Display Components
- Batch04 - Chat Page Flow and Evidence Loading
- Batch05 - Routing, Navigation, Styling, and Scope Hardening
- Batch06 - Validation, Reporting, and Reviewer Handoff

## Mandatory Batch01 - Chat and Evidence Contracts and API Clients

### Goal

Create the typed frontend contracts and API boundaries needed by the chat and evidence UI.

### Why this batch exists

The UI depends on a stable, typed boundary for chat requests, chat responses, citations, evidence chunks, and safe API error handling before components and pages are assembled.

### Inputs / Dependencies

- `docs/plans/Plan_14.md`
- `docs/plans/Master_Plan.md`
- `README.md`
- Existing `frontend/src/api/client.ts`
- Existing `frontend/src/api/documents.ts`
- Existing `frontend/src/types/documents.ts`
- Completed Plan 12 backend endpoints
- Completed Plan 13 frontend document list/types

### Tasks

- [x] (01A): Define frontend chat and evidence types
  - Source of Truth: `docs/plans/Plan_14.md` > `## 7. Data Model / Schema Changes`
  - Source Requirements:
    - Add frontend-only chat request/response, citation, and evidence response types.
    - Do not add backend database schema changes.
  - Details: Create the shared type definitions required by chat API clients, answer display, and evidence display.
  - Dependencies: Completed Plan 13 document type baseline.
  - User Action: None.
  - Agent Work: Add `frontend/src/types/chat.ts` with `AskQuestionRequest`, `AskQuestionResponse`, citation types, `AgentRunEvidence`, verified evidence chunk type, and rejected evidence chunk type matching Plan 14.
  - Output: Typed frontend chat and evidence contracts.
  - Acceptance: Types represent optional `session_id`, non-empty question ownership at validation layer, `document_ids: string[]`, nullable confidence, citations with `file_name` and `quote`, `agent_run_id`, and verified/rejected evidence arrays.
  - Validation: Run TypeScript build in Batch06; inspect imports compile without `any` or backend-only model leakage.
  - Blocked Condition: None.
  - Files: `frontend/src/types/chat.ts`

- [x] (01B): Add the chat ask API client
  - Source of Truth: `docs/plans/Plan_14.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_14.md` > `## 8. API Design`; `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.4 Ask Question`
  - Source Requirements:
    - `frontend/src/api/chat.ts` must contain `askQuestion`.
    - Frontend must call `POST /api/chat/ask` through the existing backend API.
    - Response includes answer, confidence, citations, and `agent_run_id`.
  - Details: Add a typed wrapper for chat submission using the existing Axios client.
  - Dependencies: (01A), existing `frontend/src/api/client.ts`.
  - User Action: None.
  - Agent Work: Implement `askQuestion(request)` in `frontend/src/api/chat.ts`, encode no secrets, return `response.data`, and add safe chat API error mapping consistent with current document API behavior.
  - Output: Typed chat API helper and safe frontend error helper.
  - Acceptance: The client posts to `/api/chat/ask` only, uses `apiClient`, returns typed data, and maps backend `detail`, connection failures, and generic failures to safe display messages.
  - Validation: Run `npm run build`; optionally add API client tests only if a real frontend test runner exists.
  - Blocked Condition: None.
  - Files: `frontend/src/api/chat.ts`

- [x] (01C): Add the agent-run evidence API client
  - Source of Truth: `docs/plans/Plan_14.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_14.md` > `## 8. API Design`; `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.5 Get Evidence`
  - Source Requirements:
    - `frontend/src/api/agentRuns.ts` must contain `getAgentRunEvidence`.
    - Frontend must call `GET /api/agent-runs/{agent_run_id}/evidence`.
    - Evidence response contains verified and rejected chunks.
  - Details: Add a typed wrapper for loading evidence by returned agent run ID.
  - Dependencies: (01A), existing `frontend/src/api/client.ts`.
  - User Action: None.
  - Agent Work: Implement `getAgentRunEvidence(agentRunId)` in `frontend/src/api/agentRuns.ts`, encode the route parameter, return typed evidence data, and include safe evidence API error mapping.
  - Output: Typed evidence API helper.
  - Acceptance: The client calls only `/api/agent-runs/{agent_run_id}/evidence`, not `/logs`, provider APIs, Supabase, or Qdrant.
  - Validation: Run `npm run build`; inspect route encoding and safe error mapping.
  - Blocked Condition: None.
  - Files: `frontend/src/api/agentRuns.ts`

- [x] (01D): Confirm frontend runtime configuration and API scope boundaries
  - Source of Truth: `docs/plans/Plan_14.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_14.md` > `## 4. Out of Scope`; `README.md` > `## Development Notes for AI Agents` > `Important coordination rules`
  - Source Requirements:
    - `VITE_API_BASE_URL` is the only required frontend runtime setting.
    - Private provider keys, internal prompts, and backend-only secrets must not be exposed.
    - Agent logs/debug UI is out of scope.
  - Details: Keep new clients aligned with existing frontend configuration and avoid creating unapproved frontend runtime settings.
  - Dependencies: (01B), (01C).
  - User Action: None.
  - Agent Work: Review new API code for direct provider calls, hardcoded backend origins, backend-only env names, prompt exposure, `/logs` calls, and development indexing calls.
  - Output: Scope-safe frontend API boundary.
  - Acceptance: No frontend runtime setting beyond `VITE_API_BASE_URL` is required and no out-of-scope endpoint is introduced.
  - Validation: Search frontend code for prohibited provider/config/log/index references during Batch06.
  - Blocked Condition: None.
  - Files: `frontend/src/api/chat.ts`, `frontend/src/api/agentRuns.ts`, `frontend/src/api/client.ts`

### Files or Modules Likely Created or Updated

- `frontend/src/types/chat.ts`
- `frontend/src/api/chat.ts`
- `frontend/src/api/agentRuns.ts`

### Required Outputs / Artifacts

- Typed chat request/response and evidence response contracts.
- `askQuestion` API client.
- `getAgentRunEvidence` API client.
- Safe frontend error mapping for chat and evidence calls.

### Acceptance Criteria

- Chat and evidence types match Plan 14.
- Chat client posts to `/api/chat/ask` through `apiClient`.
- Evidence client gets `/api/agent-runs/{agent_run_id}/evidence` through `apiClient`.
- No backend-only secret, provider, log, indexing, auth, or schema scope is introduced.

### Required Tests or Validations

- `cd frontend && npm run build` in Batch06.
- Frontend API tests only if a real frontend test runner exists.
- Scope search for frontend secrets, provider direct calls, logs endpoint calls, and development indexing calls in Batch06.

### Explicit Non-Goals

- Backend route/schema/service changes.
- Agent logs API client or logs UI.
- Streaming chat client.
- External provider browser calls.

## Mandatory Batch02 - Ready Document Selector and Question Input Components

### Goal

Create reusable UI controls for selecting ready documents and entering a validated question.

### Why this batch exists

The chat page must prevent invalid submissions before it calls the backend. Ready-document filtering and question validation should be reusable, typed, and easy to verify.

### Inputs / Dependencies

- Batch01 types and API boundaries.
- Existing `frontend/src/api/documents.ts`
- Existing `frontend/src/types/documents.ts`
- Existing routed frontend shell and styling.

### Tasks

- [ ] (02A): Build a ready-document selector component
  - Source of Truth: `docs/plans/Plan_14.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_14.md` > `## 8. API Design`; `README.md` > `## Main Workflows` > `### Frontend Document API Client`
  - Source Requirements:
    - `DocumentSelector.tsx` selects one or more ready documents.
    - Only documents with status `ready` can be selected for chat.
    - At least one selected ready document is required before submit.
  - Details: Add a reusable selector that receives or loads document list data and exposes selected ready document IDs to the chat page.
  - Dependencies: Existing `listDocuments()` and `DocumentListItem` type.
  - User Action: None.
  - Agent Work: Create `frontend/src/components/DocumentSelector.tsx` with ready-only selection, unavailable treatment for non-ready documents, loading/empty/error support as needed, and multi-select behavior.
  - Output: Ready-document selector component.
  - Acceptance: `ready` documents are selectable; `uploaded`, `processing`, and `failed` documents are not selectable; no-ready-documents state is clear.
  - Validation: Manual browser check in Batch06; component compiles under `npm run build`.
  - Blocked Condition: None.
  - Files: `frontend/src/components/DocumentSelector.tsx`

- [ ] (02B): Add document selection state and validation helpers
  - Source of Truth: `docs/plans/Plan_14.md` > `## 8. API Design`; `docs/plans/Plan_14.md` > `## 13. Failure Handling`
  - Source Requirements:
    - At least one ready document must be selected.
    - Chat with no selected document must show a validation error.
    - No ready documents must show a clear empty state.
  - Details: Keep selection state predictable and guard chat submission before network requests.
  - Dependencies: (02A).
  - User Action: None.
  - Agent Work: Add typed selection state and validation output that the chat page can use to display messages and disable/guard submission.
  - Output: Selection validation behavior.
  - Acceptance: Submit attempts with no selected ready document are blocked before `askQuestion` is called and display a clear safe message.
  - Validation: Manual negative test in Batch06; optional component tests only if a real frontend test runner exists.
  - Blocked Condition: None.
  - Files: `frontend/src/components/DocumentSelector.tsx`, `frontend/src/pages/ChatPage.tsx`

- [ ] (02C): Build the reusable chat input component
  - Source of Truth: `docs/plans/Plan_14.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_14.md` > `## 8. API Design`; `docs/plans/Plan_14.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - `ChatBox.tsx` must provide textarea/input, submit button, disabled loading state, and validation message.
    - Question must be non-empty.
    - Empty question must block submission.
  - Details: Add a reusable controlled question form for the chat page.
  - Dependencies: Batch01.
  - User Action: None.
  - Agent Work: Create `frontend/src/components/ChatBox.tsx` with trimmed question validation, disabled/busy submit state, accessible label, validation feedback, and submit callback.
  - Output: Reusable chat input component.
  - Acceptance: Empty or whitespace-only questions are blocked before `askQuestion` is called; duplicate submit is disabled while loading.
  - Validation: Manual negative test in Batch06; build compiles.
  - Blocked Condition: None.
  - Files: `frontend/src/components/ChatBox.tsx`

### Files or Modules Likely Created or Updated

- `frontend/src/components/DocumentSelector.tsx`
- `frontend/src/components/ChatBox.tsx`
- `frontend/src/pages/ChatPage.tsx` during integration

### Required Outputs / Artifacts

- Ready-only multi-select document selector.
- Question input form with empty-question validation and loading/disabled state.
- Selection validation behavior for no selected documents and no ready documents.

### Acceptance Criteria

- Only ready documents can be selected for chat.
- One or more ready document IDs can be selected.
- Empty questions are blocked before network requests.
- Duplicate submissions are disabled during active chat submission.

### Required Tests or Validations

- `cd frontend && npm run build` in Batch06.
- Manual browser checks for no ready documents if that state is available, no selected document, empty question, and loading/disabled submit.
- Conditional frontend tests only if a real test command exists.

### Explicit Non-Goals

- Document processing or indexing controls.
- Document deletion.
- Chat session history UI.
- Backend status mutation.

## Mandatory Batch03 - Answer and Evidence Display Components

### Goal

Create reusable components for displaying grounded answers, confidence, citations, and read-only evidence groups.

### Why this batch exists

Answer and evidence rendering need clear formatting and separation before page-level orchestration. These components carry the verified-evidence rule into the UI.

### Inputs / Dependencies

- Batch01 chat and evidence types.
- Existing frontend styling conventions.

### Tasks

- [ ] (03A): Build the answer display component
  - Source of Truth: `docs/plans/Plan_14.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_14.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `# 18. Quality Rules` > `## 18.3 Citation Rule`
  - Source Requirements:
    - `AnswerPanel.tsx` displays final answer, confidence, and citations.
    - Citation format shows file name and quoted text.
    - Missing citations displays an explicit no-citations state.
  - Details: Add a reusable answer panel for successful chat responses.
  - Dependencies: (01A).
  - User Action: None.
  - Agent Work: Create `frontend/src/components/AnswerPanel.tsx` with answer text, confidence rendering for numeric or null confidence, citation list, no-citations state, and no internal chunk ID display.
  - Output: Answer display component.
  - Acceptance: Answer, confidence, and citations are readable; citations show only `file_name` and `quote`; long text wraps; missing citations are visible.
  - Validation: Manual happy-path and missing-citation inspection in Batch06 when data is available; build compiles.
  - Blocked Condition: None.
  - Files: `frontend/src/components/AnswerPanel.tsx`

- [ ] (03B): Build the evidence display component
  - Source of Truth: `docs/plans/Plan_14.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_14.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 14. Frontend Page Plan` > `## 14.4 Evidence Viewer`
  - Source Requirements:
    - `EvidencePanel.tsx` displays verified and rejected chunks.
    - Verified evidence shows file name, quote, page number if present, verification reason, and simple reasoning flag.
    - Rejected evidence shows file name, quote, and rejection reason.
  - Details: Add a reusable evidence panel that can be embedded in chat and reused by the direct evidence viewer page.
  - Dependencies: (01A), (01C).
  - User Action: None.
  - Agent Work: Create `frontend/src/components/EvidencePanel.tsx` with separate verified and rejected sections, empty states for either group, read-only rendering, and safe wrapping for long quotes/reasons.
  - Output: Evidence display component.
  - Acceptance: Verified and rejected evidence are visually separate, labeled by status text, read-only, and readable at mobile and desktop widths.
  - Validation: Manual evidence viewer check in Batch06; build compiles.
  - Blocked Condition: None.
  - Files: `frontend/src/components/EvidencePanel.tsx`

- [ ] (03C): Add component-level accessibility and wrapping styles
  - Source of Truth: `docs/plans/Plan_14.md` > `## 13. Failure Handling`; `docs/plans/Plan_14.md` > `## 15. Reviewer Checklist`; `README.md` > `## Main Workflows` > `### Frontend Reusable Document Components`
  - Source Requirements:
    - Long answers and quotes must wrap without overflowing containers.
    - UI stays usable at mobile and desktop widths.
    - Citations and evidence are visible and readable.
  - Details: Extend existing plain CSS for answer, citation, selector, chat box, and evidence UI without introducing a new styling system.
  - Dependencies: (02A), (02C), (03A), (03B).
  - User Action: None.
  - Agent Work: Add or update CSS classes in `frontend/src/styles.css` for wrapping, layout, focus, disabled states, status text, evidence grouping, and narrow viewport behavior.
  - Output: Responsive and accessible component styling.
  - Acceptance: No horizontal overflow from long file names, questions, answers, quotes, reasons, or buttons at 320px minimum width; interactive controls have visible focus.
  - Validation: Manual responsive/focus checks in Batch06.
  - Blocked Condition: None.
  - Files: `frontend/src/styles.css`

### Files or Modules Likely Created or Updated

- `frontend/src/components/AnswerPanel.tsx`
- `frontend/src/components/EvidencePanel.tsx`
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- Reusable answer panel.
- Reusable verified/rejected evidence panel.
- Styles for readable, wrapped, accessible chat/evidence content.

### Acceptance Criteria

- Answer, confidence, and citations are displayed.
- Citation format is file name plus quote.
- Evidence viewer separates verified and rejected chunks.
- Evidence remains read-only.
- Long text wraps without layout overflow.

### Required Tests or Validations

- `cd frontend && npm run build` in Batch06.
- Manual happy-path citation/evidence checks in Batch06.
- Manual responsive checks at desktop and 320-375px mobile widths in Batch06.

### Explicit Non-Goals

- Editing verified or rejected evidence.
- Showing internal prompts.
- Agent logs/debug display.
- Decorative or marketing UI.

## Mandatory Batch04 - Chat Page Flow and Evidence Loading

### Goal

Assemble the chat experience and evidence loading flow so the user can ask a grounded question and inspect evidence for the returned run.

### Why this batch exists

Plan 14 is testable only when the full page flow connects document selection, question submission, returned answer rendering, `agent_run_id` storage, and evidence retrieval.

### Inputs / Dependencies

- Batch01 API clients and types.
- Batch02 selector and chat box.
- Batch03 answer and evidence panels.
- Existing Plan 13 routed app shell.
- Completed Plan 12 chat/evidence backend endpoints.

### Tasks

- [ ] (04A): Create the main chat page
  - Source of Truth: `docs/plans/Plan_14.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_14.md` > `## 9. Implementation Steps`; `docs/plans/Plan_14.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - `ChatPage.tsx` combines document selector, chat box, answer panel, and evidence trigger.
    - User can select one or more ready documents.
    - User can submit a non-empty question.
  - Details: Build the page-level state machine for loading documents, selecting ready documents, asking a question, and rendering the answer.
  - Dependencies: Batch01, Batch02, Batch03.
  - User Action: None.
  - Agent Work: Create `frontend/src/pages/ChatPage.tsx`, load documents via existing `listDocuments()`, pass ready documents to the selector, call `askQuestion()` with selected IDs and trimmed question, and render loading, empty, validation, error, success, and no-citations states.
  - Output: Reachable chat page component ready for route integration.
  - Acceptance: Chat request is sent only after valid question and selected ready document IDs; answer/confidence/citations render from actual backend response.
  - Validation: Manual happy-path and negative checks in Batch06; build compiles.
  - Blocked Condition: None.
  - Files: `frontend/src/pages/ChatPage.tsx`

- [ ] (04B): Add chat-page evidence trigger and lazy evidence loading
  - Source of Truth: `docs/plans/Plan_14.md` > `## 1. Goal`; `docs/plans/Plan_14.md` > `## 9. Implementation Steps`; `docs/plans/Plan_14.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Store the last `agent_run_id` after an answer is returned.
    - Load evidence only after a successful answer or when the user opens the evidence panel.
    - Evidence load failure must not erase the answer.
  - Details: Connect the returned `agent_run_id` to evidence viewing from the chat page.
  - Dependencies: (04A), (01C), (03B).
  - User Action: None.
  - Agent Work: Add state for latest response, evidence open/loading/error/data states, an evidence trigger button/link, and use `getAgentRunEvidence()` only after a successful chat response.
  - Output: Chat page can open evidence for the latest returned run.
  - Acceptance: Evidence loads for the returned run ID, verified/rejected chunks render separately, evidence errors are safe, and existing answer remains visible on evidence failure.
  - Validation: Manual evidence load/failure checks in Batch06.
  - Blocked Condition: None.
  - Files: `frontend/src/pages/ChatPage.tsx`, `frontend/src/components/EvidencePanel.tsx`

- [ ] (04C): Create the direct evidence viewer page
  - Source of Truth: `docs/plans/Plan_14.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_14.md` > `## 9. Implementation Steps`; `docs/plans/Plan_14.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - `EvidenceViewerPage.tsx` provides direct URL access if routing supports `agent_run_id`.
    - Evidence viewer displays verified and rejected chunks.
  - Details: Add a routeable evidence page that reads an agent run ID from the URL and loads evidence directly.
  - Dependencies: (01C), (03B).
  - User Action: None.
  - Agent Work: Create `frontend/src/pages/EvidenceViewerPage.tsx`, read the route parameter with React Router, validate presence of the ID, fetch evidence, and render loading, error, empty, verified, and rejected states using `EvidencePanel`.
  - Output: Direct evidence viewer page component.
  - Acceptance: `/evidence/:agentRunId` or the chosen equivalent direct route can load and display evidence for a valid run ID; missing/invalid route parameter shows a safe message.
  - Validation: Manual direct route check in Batch06 when an `agent_run_id` is available.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only if no successful chat run or valid `agent_run_id` is available for manual direct-route validation.
  - Files: `frontend/src/pages/EvidenceViewerPage.tsx`

### Files or Modules Likely Created or Updated

- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/pages/EvidenceViewerPage.tsx`
- `frontend/src/components/EvidencePanel.tsx`
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- Main chat page with ready-document selection and question submission.
- Latest answer display with confidence and citations.
- Evidence trigger and lazy evidence loading.
- Direct evidence viewer page.

### Acceptance Criteria

- User can select one or more ready documents.
- User can submit a non-empty question.
- Chat page displays answer, confidence, and citations.
- Chat page stores returned `agent_run_id`.
- Evidence viewer displays verified and rejected chunks.
- Evidence failure does not erase the answer.

### Required Tests or Validations

- `cd frontend && npm run build` in Batch06.
- Manual happy-path chat and evidence checks in Batch06.
- Manual negative checks for empty question, no selected document, backend failure, and evidence failure in Batch06.

### Explicit Non-Goals

- Streaming answer UI.
- Full multi-session chat history.
- Agent logs/debug UI.
- Backend workflow changes.

## Mandatory Batch05 - Routing, Navigation, Styling, and Scope Hardening

### Goal

Wire the new chat and evidence pages into the existing frontend shell, polish responsive behavior, and verify scope boundaries before final validation.

### Why this batch exists

The feature is not complete until it is reachable through navigation/routes and the frontend remains compact, accessible, responsive, and within the approved Plan 14 scope.

### Inputs / Dependencies

- Batch04 page components.
- Existing `frontend/src/App.tsx`.
- Existing `frontend/src/styles.css`.
- Existing React Router setup from Plan 13.

### Tasks

- [ ] (05A): Add chat and evidence routes to the application shell
  - Source of Truth: `docs/plans/Plan_14.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_14.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 14. Frontend Page Plan` > `## 14.3 Chat With Document Page`
  - Source Requirements:
    - `frontend/src/App.tsx` must add route/navigation for Chat and Evidence.
    - Chat page must be reachable from navigation.
    - Direct evidence viewer should support `agent_run_id` routing.
  - Details: Extend the existing compact navigation and route table.
  - Dependencies: (04A), (04C).
  - User Action: None.
  - Agent Work: Import `ChatPage` and `EvidenceViewerPage`, add a `/chat` route, add a direct evidence route such as `/evidence/:agentRunId`, add a Chat navigation link, and keep root/default route behavior clear.
  - Output: Routed chat and evidence pages.
  - Acceptance: `/chat` is reachable from navigation without full-page reload; a direct evidence route renders the evidence page; existing `/upload` and `/documents` still work.
  - Validation: Manual route/navigation smoke check in Batch06; build compiles.
  - Blocked Condition: None.
  - Files: `frontend/src/App.tsx`

- [ ] (05B): Complete responsive and accessible chat/evidence styling
  - Source of Truth: `docs/plans/Plan_14.md` > `## 13. Failure Handling`; `docs/plans/Plan_14.md` > `## 15. Reviewer Checklist`; `README.md` > `## Main Workflows` > `### Frontend Reusable Document Components`
  - Source Requirements:
    - Long answers and quotes wrap without overflowing containers.
    - UI stays usable at mobile and desktop widths.
    - Status should not be communicated by color alone.
  - Details: Add final CSS for page layout, selector rows, form states, answer/citation/evidence groups, loading/error/empty states, and focus/disabled treatment.
  - Dependencies: Batch02, Batch03, Batch04, (05A).
  - User Action: None.
  - Agent Work: Update `frontend/src/styles.css` using existing naming/style conventions and responsive constraints.
  - Output: Production-ready chat/evidence UI styling.
  - Acceptance: Chat/evidence UI remains readable and controllable at 320px, 375px, and desktop widths; focus is visible; error/empty/loading states are distinguishable by text and structure.
  - Validation: Manual responsive/focus checks in Batch06.
  - Blocked Condition: None.
  - Files: `frontend/src/styles.css`

- [ ] (05C): Perform frontend scope hardening before validation
  - Source of Truth: `docs/plans/Plan_14.md` > `## 4. Out of Scope`; `docs/plans/Plan_14.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_14.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Do not implement agent logs/debug UI.
    - Do not expose internal prompts or API keys.
    - Do not add authentication.
    - No hardcoded secrets.
  - Details: Audit the frontend changes for forbidden scope and remove any accidental out-of-scope additions.
  - Dependencies: Batch01 through (05B).
  - User Action: None.
  - Agent Work: Search/inspect frontend code for logs/debug UI, `/logs` calls, provider names/direct calls, backend-only secret names, prompt text exposure, auth/JWT UI, evidence editing controls, streaming behavior, hardcoded backend origins, and backend/schema changes.
  - Output: Scope-hardened frontend implementation.
  - Acceptance: The diff is limited to approved frontend files plus optional frontend tests; no backend/schema/config secrets or out-of-scope features are added.
  - Validation: Record the exact scope-search commands and results in the execution report.
  - Blocked Condition: None.
  - Files: `frontend/src/**`, optional frontend tests if real test runner exists

### Files or Modules Likely Created or Updated

- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/pages/EvidenceViewerPage.tsx`

### Required Outputs / Artifacts

- `/chat` route and navigation link.
- Direct evidence route.
- Responsive chat/evidence styles.
- Scope-hardening evidence for reviewer.

### Acceptance Criteria

- Chat page exists and is reachable from navigation.
- Evidence route works for a returned `agent_run_id`.
- Existing upload/documents routes remain intact.
- UI works at desktop and 320-375px mobile widths.
- No logs/debug UI, auth, streaming, evidence editing, hardcoded secrets, or backend changes are introduced.

### Required Tests or Validations

- `cd frontend && npm run build` in Batch06.
- Manual route/navigation/browser checks in Batch06.
- Scope-search commands in Batch06.

### Explicit Non-Goals

- Changing root to a marketing landing page.
- Adding backend APIs.
- Adding agent logs/debug page.
- Adding new runtime configuration.

## Mandatory Batch06 - Validation, Reporting, and Reviewer Handoff

### Goal

Prove the Plan 14 frontend work builds, stays in scope, works in the browser where required setup exists, and is ready for reviewer verification.

### Why this batch exists

Plan 14 explicitly requires build checks, conditional frontend tests, manual chat/evidence testing, negative tests, and reporting. This batch prevents fake success and documents any user-action blockers.

### Inputs / Dependencies

- Completed Batch01 through Batch05.
- Backend running with Plan 12 chat/evidence APIs for manual checks.
- Frontend dev server for manual checks.
- At least one processed/indexed document with status `ready` for meaningful happy-path chat testing.

### Tasks

- [ ] (06A): Run required frontend automated validation
  - Source of Truth: `docs/plans/Plan_14.md` > `## 11. Required Tests`; `README.md` > `## Running the Project` > `### Production Frontend Build`; `README.md` > `## Testing and Validation`
  - Source Requirements:
    - Run `cd frontend && npm run build`.
    - Run frontend tests only if configured.
    - Do not fabricate test results.
  - Details: Execute the required build and conditional frontend tests.
  - Dependencies: Batch01 through Batch05.
  - User Action: None.
  - Agent Work: Run `npm run build` from `frontend/`; inspect `frontend/package.json` for a real `test` script before deciding whether `npm test` exists; run it only if real.
  - Output: Recorded automated validation results.
  - Acceptance: `npm run build` passes; frontend test status is accurately reported as run or not configured.
  - Validation: Command output recorded in execution report.
  - Blocked Condition: None for build unless dependency installation is missing and cannot be repaired without user action; frontend tests are not blocked when no real test command exists.
  - Files: `docs/reports/report_14_execute_agent.md` during execution reporting

- [ ] (06B): Perform happy-path manual chat and evidence browser validation
  - Source of Truth: `docs/plans/Plan_14.md` > `## 11. Required Tests`; `docs/plans/Plan_14.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_14.md` > `## 5. Dependencies`
  - Source Requirements:
    - Start backend and frontend.
    - Open Chat page.
    - Select a ready document.
    - Ask the Plan 14 manual question or an equivalent question grounded by the ready document.
    - Confirm answer, confidence, citations, and evidence viewer.
  - Details: Validate the full user path with real browser interaction and real backend endpoints when setup exists.
  - Dependencies: (06A), available backend/frontend runtime, at least one ready document.
  - User Action: User must provide or confirm a processed/indexed ready document if none exists in the configured backend data.
  - Agent Work: Start or reuse backend/frontend dev servers, open the app in a browser, navigate to `/chat`, select a ready document, submit a grounded question, inspect answer/confidence/citations, open evidence, and confirm verified/rejected chunks are visible.
  - Output: Manual happy-path validation result.
  - Acceptance: Chat request returns a visible answer, confidence, citations, and `agent_run_id`; evidence viewer loads verified and rejected evidence for that run.
  - Validation: Browser/manual test notes, endpoint/network observations where available, and screenshots only if useful.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if no ready document, missing provider/backend credentials, missing Supabase/Qdrant data, or unavailable live backend setup prevents meaningful chat/evidence validation.
  - Files: `docs/reports/report_14_execute_agent.md` during execution reporting

- [ ] (06C): Perform negative, responsive, and accessibility browser checks
  - Source of Truth: `docs/plans/Plan_14.md` > `## 11. Required Tests`; `docs/plans/Plan_14.md` > `## 13. Failure Handling`; `docs/plans/Plan_14.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Empty question shows validation error.
    - No selected document shows validation error.
    - Backend failure shows safe error display.
    - Evidence viewer separates verified and rejected chunks.
    - UI stays usable at mobile and desktop widths.
  - Details: Validate failure handling and responsive behavior without requiring backend code changes.
  - Dependencies: Batch01 through Batch05, frontend dev server, browser access.
  - User Action: None unless backend outage simulation requires user-controlled infrastructure.
  - Agent Work: Test empty-question submit, no-selection submit, no-ready-documents state if reachable, backend chat failure or connection failure, evidence load failure if feasible, long text wrapping, keyboard focus, and 320px/375px/desktop layouts.
  - Output: Manual negative/responsive validation result.
  - Acceptance: Validation errors and backend/evidence errors are clear and safe; answer remains visible after evidence failure; no horizontal overflow; keyboard focus is visible.
  - Validation: Browser/manual test notes and exact blocked conditions if any scenario cannot be simulated safely.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for checks that require unavailable backend state or user-controlled external setup; local validation checks must still run where possible.
  - Files: `docs/reports/report_14_execute_agent.md` during execution reporting

- [ ] (06D): Write execution report and reviewer handoff
  - Source of Truth: `docs/plans/Plan_14.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_14.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Report files created, files modified, commands run, test results, known issues, and intentional out-of-scope exclusions.
    - Include whether manual chat and evidence viewer tests were performed.
    - Reviewer must verify scope, tests, acceptance, secrets, no fake success, architecture, ready-only selection, citations, evidence separation, and responsive UI.
  - Details: Produce a complete execution report for A2 review.
  - Dependencies: (06A), (06B), (06C), scope-hardening checks.
  - User Action: None.
  - Agent Work: Append or create `docs/reports/report_14_execute_agent.md` with task IDs, implementation summary, changed files, commands/results, manual browser status, blockers, known issues, out-of-scope work not implemented, and notes for reviewer.
  - Output: Execution report ready for reviewer.
  - Acceptance: The report contains enough evidence for review and does not mark blocked manual checks as passed.
  - Validation: Reviewer can trace each accepted task ID to commands, manual checks, or explicit blocked-by-user status.
  - Blocked Condition: None.
  - Files: `docs/reports/report_14_execute_agent.md`

### Files or Modules Likely Created or Updated

- `docs/reports/report_14_execute_agent.md`
- Optional frontend test files only if a real frontend test runner exists and tests are implemented during execution
- No runtime source files should be changed in Batch06 except minor fixes required by failed validation

### Required Outputs / Artifacts

- Passing `npm run build` result.
- Accurate frontend test status.
- Manual happy-path chat/evidence validation status.
- Manual negative/responsive/accessibility validation status.
- Scope-hardening search results.
- Execution report for reviewer.

### Acceptance Criteria

- Frontend build passes.
- Tests are run only if a real frontend test command exists.
- Manual chat/evidence browser testing is performed or safely marked `BLOCKED_BY_USER_ACTION`.
- Negative validation is performed for empty question and no selected document.
- Backend/evidence failure behavior is checked where feasible.
- Responsive and focus checks are performed.
- Execution report includes files, commands, results, known issues, out-of-scope work, and browser-test status.

### Required Tests or Validations

- `cd frontend && npm run build`
- `cd frontend && npm test` only if `frontend/package.json` contains a real `test` script
- Browser/manual chat and evidence checks
- Browser/manual negative checks
- Browser/manual responsive/focus checks
- Scope-search commands for frontend secret/provider/log/debug/auth/indexing boundaries

### Explicit Non-Goals

- Backend tests unless execution unexpectedly changes backend files, which should normally not happen.
- Creating fake ready documents in production data.
- Claiming live chat success without a real ready document and successful backend response.
- Committing work before review unless the orchestrator explicitly reaches the batch commit gate.

## Optional Future Tracks

These tracks are not part of the mandatory MVP batch chain for Plan 14.

- Agent logs/debug UI. This is explicitly out of scope for Plan 14 even though the backend logs endpoint is mounted.
- Streaming chat responses.
- Multi-session chat history UI beyond optional `session_id` pass-through if later approved.
- Evidence editing, moderation, or manual verification changes.
- Authentication/JWT or multi-user document selection.
- Source page preview, document comparison, export, or graph visualization.
- Adding a frontend testing framework if the project owner wants a separate testing-infrastructure milestone.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05
- Batch05 -> Batch06

Optional future tracks are outside the mandatory dependency chain.

## Global Verification Checklist

- [ ] `docs/plans/Plan_14.md` remained the scope authority.
- [ ] `docs/plans/Master_Plan.md` was used only for architecture, endpoint, grounding, citation, and secret-boundary clarification.
- [ ] `README.md` was used only for current project state, commands, and known gaps.
- [ ] `frontend/src/types/chat.ts` defines the approved chat request, chat response, citation, verified evidence, rejected evidence, and agent-run evidence types.
- [ ] `askQuestion` is implemented through the existing Axios `apiClient`.
- [ ] `getAgentRunEvidence` is implemented through the existing Axios `apiClient`.
- [ ] `VITE_API_BASE_URL` remains the only required frontend runtime setting.
- [ ] No Supabase, Qdrant, ShopAIKey, prompt, provider key, or other private backend value is exposed in frontend code.
- [ ] No frontend call goes directly to Supabase, Qdrant, ShopAIKey, or any provider service.
- [ ] Frontend does not call `GET /api/agent-runs/{agent_run_id}/logs`.
- [ ] Frontend does not call `POST /api/documents/{document_id}/index`.
- [ ] No backend API, schema, migration, storage, retrieval, agent workflow, processing, or authentication change was added.
- [ ] No agent logs/debug UI was added.
- [ ] No streaming chat UI was added.
- [ ] No full multi-session chat history UI was added.
- [ ] No evidence editing controls were added.
- [ ] No authentication/JWT UI or logic was added.
- [ ] Document selector loads or receives document list data from the existing document API boundary.
- [ ] Only documents with status `ready` are selectable for chat.
- [ ] `uploaded`, `processing`, and `failed` documents cannot be submitted as selected chat documents.
- [ ] Multi-select supports one or more selected ready document IDs.
- [ ] Empty or whitespace-only question submission is blocked before the chat API call.
- [ ] Submitting with no selected ready document is blocked before the chat API call.
- [ ] Duplicate chat submission is disabled while a chat request is active.
- [ ] Chat page has truthful loading, success, error, validation, no-ready-documents, and empty/no-answer states.
- [ ] Backend chat errors show safe frontend text.
- [ ] Backend connection failures show a clear connection message.
- [ ] Chat success reflects the actual returned backend answer, confidence, citations, and `agent_run_id`.
- [ ] Answer display shows final answer, confidence, and citations.
- [ ] Citation format shows file name and quoted text.
- [ ] Missing citations display an explicit no-citations state and are reported as a backend issue during validation.
- [ ] Normal chat answer UI does not expose internal chunk IDs.
- [ ] Evidence loading occurs only after a successful answer or direct evidence page open.
- [ ] Evidence load failure does not erase the displayed answer.
- [ ] Evidence viewer displays verified and rejected chunks in separate sections.
- [ ] Verified evidence displays file name, quote, optional page number, verification reason, and simple reasoning flag where present.
- [ ] Rejected evidence displays file name, quote, and rejection reason.
- [ ] Evidence display is read-only.
- [ ] `/chat` route works.
- [ ] Direct evidence route works with an `agent_run_id` when available.
- [ ] Existing `/upload` and `/documents` routes still work.
- [ ] Navigation works without full-page reload.
- [ ] Placeholder and marketing landing content are absent.
- [ ] Chat and evidence UI are usable at desktop and 320-375px mobile widths.
- [ ] Button labels, file names, questions, answers, citations, quotes, reasons, and status text do not create horizontal overflow.
- [ ] Keyboard focus is visible for interactive controls.
- [ ] Status and evidence grouping are not communicated by color alone.
- [ ] `npm run build` was run and passed.
- [ ] Frontend tests were run only if a real test command exists.
- [ ] Absence of frontend test infrastructure was reported accurately when applicable.
- [ ] Manual browser testing status was reported.
- [ ] Happy-path chat/evidence testing passed or was safely marked `BLOCKED_BY_USER_ACTION`.
- [ ] Empty-question, no-selected-document, backend failure, evidence failure, list/ready-document availability, and responsive checks passed or were safely marked `BLOCKED_BY_USER_ACTION`.
- [ ] Execution report includes files created, files modified, commands, results, known issues, intentionally out-of-scope work, and browser-test status.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [ ] Batch01 - Chat and Evidence Contracts and API Clients
- [ ] Batch02 - Ready Document Selector and Question Input Components
- [ ] Batch03 - Answer and Evidence Display Components
- [ ] Batch04 - Chat Page Flow and Evidence Loading
- [ ] Batch05 - Routing, Navigation, Styling, and Scope Hardening
- [ ] Batch06 - Validation, Reporting, and Reviewer Handoff

### Task IDs

#### Batch01
- [x] (01A): Define frontend chat and evidence types
- [x] (01B): Add the chat ask API client
- [x] (01C): Add the agent-run evidence API client
- [x] (01D): Confirm frontend runtime configuration and API scope boundaries

#### Batch02
- [ ] (02A): Build a ready-document selector component
- [ ] (02B): Add document selection state and validation helpers
- [ ] (02C): Build the reusable chat input component

#### Batch03
- [ ] (03A): Build the answer display component
- [ ] (03B): Build the evidence display component
- [ ] (03C): Add component-level accessibility and wrapping styles

#### Batch04
- [ ] (04A): Create the main chat page
- [ ] (04B): Add chat-page evidence trigger and lazy evidence loading
- [ ] (04C): Create the direct evidence viewer page

#### Batch05
- [ ] (05A): Add chat and evidence routes to the application shell
- [ ] (05B): Complete responsive and accessible chat/evidence styling
- [ ] (05C): Perform frontend scope hardening before validation

#### Batch06
- [ ] (06A): Run required frontend automated validation
- [ ] (06B): Perform happy-path manual chat and evidence browser validation
- [ ] (06C): Perform negative, responsive, and accessibility browser checks
- [ ] (06D): Write execution report and reviewer handoff

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
- reason: missing ready document, missing backend/provider setup, missing manual setup, or other safe summary

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
