# Plan 13 - Frontend Upload and Document List Execution Tasks

## Purpose

Create a detailed execution task file for the approved frontend upload and document list milestone. This task file guides a future Execution Agent to replace the placeholder React shell with typed document API clients, reusable upload and document-status components, upload and document list pages, routing/navigation, compact responsive styling, required build validation, conditional frontend tests, manual browser checks, and an execution report for `docs/plans/Plan_13.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_13.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Current project context reviewed: `README.md`
- Current frontend files inspected for planning context: `frontend/package.json`, `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/api/client.ts`, `frontend/src/styles.css`, `frontend/vite.config.ts`, and `frontend/tsconfig.json`
- Conflict note: No blocking architecture conflict was found. Plan 13 narrows the broader master-plan frontend phase to upload and document listing only. Therefore document selection for chat, document deletion, chat UI, evidence UI, and agent logs UI are not part of this task even where the master plan mentions them. The master plan names Tailwind CSS as a target technology, but the current frontend uses plain `styles.css`, and Plan 13 explicitly allows adjusting that existing file. This task does not require adding Tailwind. `docs/plans/Plan_13.md` remains the scope authority.

## Source Section Index

- `docs/plans/Plan_13.md` > `## 1. Goal` -> upload supported files through the backend and display the resulting document list.
- `docs/plans/Plan_13.md` > `## 2. Why This Plan Exists` -> provide the document-management frontend before chat and evidence UI.
- `docs/plans/Plan_13.md` > `## 3. Scope` -> API clients, pages, progress, validation, statuses, errors, routing, build, and conditional tests.
- `docs/plans/Plan_13.md` > `## 4. Out of Scope` -> no chat, evidence viewer, logs UI, frontend secrets, auth/JWT, or unapproved deletion.
- `docs/plans/Plan_13.md` > `## 5. Dependencies` -> completed Plans 1 and 3; status UI must work even when documents remain `uploaded`.
- `docs/plans/Plan_13.md` > `## 6. Required Files and Folders` -> expected frontend API, type, page, component, route, style, package, and optional test files.
- `docs/plans/Plan_13.md` > `## 7. Data Model / Schema Changes` -> frontend document status, list item, and upload response types.
- `docs/plans/Plan_13.md` > `## 8. API Design` -> existing upload/list/detail endpoints and frontend file validation rules.
- `docs/plans/Plan_13.md` > `## 9. Implementation Steps` -> ordered routing, API, component, page, refresh, testing, and build work.
- `docs/plans/Plan_13.md` > `## 10. Configuration and Environment Variables` -> `VITE_API_BASE_URL` and prohibited frontend secret variables.
- `docs/plans/Plan_13.md` > `## 11. Required Tests` -> frontend build, conditional tests, manual UI checks, and backend compatibility checks.
- `docs/plans/Plan_13.md` > `## 12. Acceptance Criteria` -> required pages, formats, progress, metadata, refresh, build, secret safety, and scope.
- `docs/plans/Plan_13.md` > `## 13. Failure Handling` -> connection, unsupported type, upload, failed processing, empty-list, and slow-upload behavior.
- `docs/plans/Plan_13.md` > `## 14. Agent Report Requirement` -> files, commands, results, issues, exclusions, and browser-test status.
- `docs/plans/Plan_13.md` > `## 15. Reviewer Checklist` -> scope, tests, secrets, architecture, responsive usability, and backend-only API access.
- `docs/plans/Master_Plan.md` > `## 2. Tech Stack` > `### Frontend` -> React, TypeScript, frontend styling, and Axios-compatible target stack.
- `docs/plans/Master_Plan.md` > `## 4. Supported Document Types` -> PDF, DOCX, TXT, and CSV support.
- `docs/plans/Master_Plan.md` > `## 5. Core Features` > `### 5.1 Upload Document` -> frontend upload entry point backed by document upload behavior.
- `docs/plans/Master_Plan.md` > `## 5. Core Features` > `### 5.2 Document List Page` -> document name, type, time, status, chunk count, and processing error display.
- `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.1 Upload Document` -> upload endpoint request and response shape.
- `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.2 List Documents` -> list endpoint and document item shape.
- `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.3 Get Document Detail` -> detail endpoint and response shape.
- `docs/plans/Master_Plan.md` > `# 14. Frontend Page Plan` > `## 14.1 Upload Document Page` -> drag/drop, validation, progress, status, and errors.
- `docs/plans/Master_Plan.md` > `# 14. Frontend Page Plan` > `## 14.2 Document List Page` -> list and refresh-status expectations, limited by Plan 13 scope.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> frontend base URL and private-key boundary.
- `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure` -> expected frontend API, page, and component locations.
- `docs/plans/Master_Plan.md` > `# 17. Implementation Phases` > `## Phase 10: Frontend UI` -> upload and document list belong to the approved frontend phase.
- `docs/plans/Master_Plan.md` > `# 19. MVP Success Criteria` -> supported uploads and backend-only private keys.
- `README.md` > `## Overview` -> current backend capabilities and placeholder frontend status.
- `README.md` > `## Repository Structure` -> current frontend shell, Axios client, and style file.
- `README.md` > `## Main Workflows` > `### Document Upload` -> current upload behavior and supported formats.
- `README.md` > `## Main Workflows` > `### Document Listing and Detail` -> mounted list/detail routes and response behavior.
- `README.md` > `## Configuration` -> current `VITE_API_BASE_URL` requirement and backend-only credentials.
- `README.md` > `## Setup` > `### Frontend` -> current frontend setup command and environment configuration.
- `README.md` > `## Running the Project` > `### Frontend Dev Server` -> Vite development server command and expected URL.
- `README.md` > `## Running the Project` > `### Production Frontend Build` -> current build command behavior.
- `README.md` > `## Testing and Validation` -> no frontend test script currently exists; build and preview are configured.
- `README.md` > `## Development Notes for AI Agents` > `Important coordination rules` -> expand the placeholder frontend and keep API/secret boundaries intact.
- `README.md` > `## Known Gaps or Unclear Areas` -> frontend is a placeholder and upload does not trigger processing automatically.

## Approved Architecture Summary

Plan 13 approves a React 19, TypeScript, and Vite frontend document-management experience built on the existing Axios client in `frontend/src/api/client.ts`. The frontend must use `VITE_API_BASE_URL` to call the existing FastAPI document endpoints. It must not connect directly to Supabase, Qdrant, ShopAIKey, or the backend's internal development indexing route.

The frontend contract consists of typed `uploadDocument`, `listDocuments`, and `getDocument` functions; document status types for `uploaded`, `processing`, `ready`, and `failed`; reusable `UploadBox`, `StatusBadge`, and `DocumentCard` components; an upload page with file validation, progress, disabled duplicate submission, success/error feedback, and refreshed recent-document feedback; and a document list page with loading, empty, error, refresh, metadata, status, chunk count, and processing error states.

The current frontend has Axios but no router or frontend test runner. React Router is therefore a required dependency for the approved page navigation. Automated frontend tests remain conditional because Plan 13 requires them only where a test stack exists, and the current `frontend/package.json` has no `test` script or testing libraries. The mandatory validation path is `npm run build` plus the Plan 13 manual browser checks. A future Execution Agent must not report `npm test` as run unless a real test script exists.

The backend currently accepts uploads and stores document metadata with status `uploaded`, but upload does not automatically invoke document processing. The UI must display the status returned by the backend and remain useful when documents stay `uploaded`. It must not call `POST /api/documents/{document_id}/index`, invent a processing endpoint, or claim that a document will become `ready` without backend processing.

Plan 13 does not approve a document detail page even though it requires a typed detail API client. `getDocument(documentId)` must be implemented for the frontend API boundary, but this task must not invent an unapproved detail route/page. Chat selection, document deletion, chat, evidence, logs, authentication, and marketing-page work remain outside this milestone.

## Global Implementation Rules

- Keep `docs/plans/Plan_13.md` as the source of truth for scope, file contracts, API calls, status behavior, failure handling, tests, and acceptance.
- Use `docs/plans/Master_Plan.md` only to clarify the existing frontend phase, document fields, supported formats, API shapes, and secret boundary.
- Use `README.md` and the inspected frontend files only to understand the current implementation state: React 19/Vite/TypeScript and Axios exist; routing, pages, components, and frontend tests do not.
- Make frontend-only runtime changes unless a backend incompatibility prevents Plan 13 from working. Do not change backend API contracts, storage, processing, indexing, authentication, or database schemas as part of this task.
- Use the existing `apiClient` for all document HTTP calls and preserve `VITE_API_BASE_URL` as the only required frontend environment variable.
- Never add, read, log, bundle, or expose `SUPABASE_SERVICE_ROLE_KEY`, `QDRANT_API_KEY`, `SHOPAIKEY_API_KEY`, or other backend-only settings in frontend code.
- Do not call Supabase, Qdrant, ShopAIKey, or any provider service directly from the browser.
- Do not call the internal development endpoint `POST /api/documents/{document_id}/index` from frontend code.
- Keep the document status union limited to `uploaded`, `processing`, `ready`, and `failed` unless the backend contract is deliberately changed by another approved plan.
- Accept `.pdf`, `.docx`, `.txt`, and `.csv` case-insensitively. Reject unsupported extensions before sending a request.
- Reject a selected file with `size === 0` before upload. Do not fabricate browser file size when it is unavailable.
- Send uploads with `FormData` and allow Axios/browser multipart handling to set the correct request boundary.
- Report upload progress from Axios progress events. If a total byte count is unavailable, show an in-progress state without displaying a fabricated percentage.
- Keep upload submission disabled while a request is active, and restore it after success or failure.
- Show safe backend error details when available and a clear connection error when no backend response is available. Never show stack traces, secrets, or raw internal objects.
- Display each list item's file name, file type, created time, status, chunk count, and `error_message` when present.
- Use explicit loading, empty, error, uploading, success, and refresh states. Do not represent a failed fetch or upload as an empty list or successful action.
- Refresh recent document feedback after a successful upload and provide a manual refresh action on the document list page.
- Do not require automatic polling. Manual refresh is sufficient unless a simple existing pattern supports polling without expanding scope.
- Use React Router for `/upload` and `/documents`, with a clear root/default route and navigation between both pages.
- Keep the UI compact and work-focused. Do not build a marketing landing page.
- Preserve the existing plain CSS approach in `frontend/src/styles.css`; do not add Tailwind, a component framework, or a design system only for this milestone.
- Ensure the upload form, navigation, cards/rows, labels, statuses, and actions remain usable at desktop and mobile widths with a minimum viewport width of 320px.
- Treat frontend tests as conditional on real test infrastructure. Do not fabricate a test command or add a broad testing stack unless explicitly justified during execution.
- Update the progress tracker only after each task's acceptance and validation conditions pass or an allowed blocked condition is recorded.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable React and TypeScript code.
- Use descriptive names for API functions, types, components, props, state, handlers, validation helpers, routes, styles, and tests.
- Keep functions, components, and modules focused on one clear responsibility.
- Prefer simple, explicit state and control flow over clever abstractions.
- Follow the existing React 19, Vite, Axios, and strict TypeScript conventions.
- Use clear TypeScript types for API responses, component props, upload state, and status values.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded backend URLs.
- Add comments only for non-obvious error mapping, progress behavior, or browser-specific decisions.
- Keep frontend code free of backend-only secrets and backend-only configuration names except where a scope-safety test or documentation check explicitly verifies they are absent.
- Avoid adding formatters, linters, state-management libraries, query libraries, CSS frameworks, test frameworks, or architecture changes outside Plan 13 unless already present or explicitly required.

## Batch Map

- Batch01 - Frontend Contracts, Routing Dependency, and Document API Client
- Batch02 - Reusable Upload and Document Display Components
- Batch03 - Upload Page and Recent Document Feedback
- Batch04 - Document List Page and Status Refresh
- Batch05 - Application Routing, Navigation, Styling, and Scope Hardening
- Batch06 - Automated/Manual Validation, Reporting, and Reviewer Handoff

## Mandatory Batch01 - Frontend Contracts, Routing Dependency, and Document API Client

### Goal

Prepare the typed frontend contracts and dependencies required by both pages before UI behavior is implemented.

### Why this batch exists

The upload and document list pages depend on one consistent API boundary, exact backend response types, and real routing support. Establishing those contracts first reduces duplicated request and status logic in later components.

### Inputs / Dependencies

- `docs/plans/Plan_13.md`
- `docs/plans/Master_Plan.md`
- `README.md`
- Existing `frontend/src/api/client.ts`
- Existing `frontend/package.json` and `frontend/package-lock.json`
- Mounted backend document upload, list, and detail endpoints from completed Plan 3

### Tasks

- [ ] (01A): Add the required React Router dependency
  - Source of Truth: `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `README.md` > `## Repository Structure`
  - Source Requirements:
    - Add React Router if the app does not already have routing.
    - Update `frontend/package.json` when routing dependencies are needed.
    - Preserve the existing React/Vite frontend.
  - Details: Confirm routing is still absent, then add the React Router package compatible with the installed React version. Update the lockfile through the package manager. Do not add unrelated dependencies.
  - Dependencies: None.
  - User Action: None.
  - Agent Work: Install the routing dependency and verify it resolves in the frontend build.
  - Output: Updated frontend dependency manifest and lockfile with React Router available.
  - Acceptance: Frontend code can import the selected React Router APIs, and no unrelated package/framework is added.
  - Validation: Inspect `frontend/package.json`; run `npm run build` after routing is wired in Batch05.
  - Blocked Condition: None unless package installation cannot access the configured registry; report the dependency-resolution failure safely.
  - Files: `frontend/package.json`, `frontend/package-lock.json`

- [ ] (01B): Add typed document API response models
  - Source of Truth: `docs/plans/Plan_13.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_13.md` > `## 8. API Design`; `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.1 Upload Document`; `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.2 List Documents`; `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.3 Get Document Detail`
  - Source Requirements:
    - Define `DocumentStatus` as `uploaded | processing | ready | failed`.
    - Define `DocumentListItem` with document metadata and optional processing error.
    - Define `DocumentUploadResponse`.
    - Support the existing detail response used by `getDocument`.
  - Details: Create strict frontend TypeScript types matching the mounted backend schemas. Include a list response wrapper and detail type without weakening required fields to `any`.
  - Dependencies: None.
  - User Action: None.
  - Agent Work: Create `frontend/src/types/documents.ts` with status, upload, list, list wrapper, and detail response types.
  - Output: Shared typed document contracts for API and UI modules.
  - Acceptance: API functions and components can use the types without duplicate inline response shapes.
  - Validation: TypeScript compilation through `npm run build`.
  - Blocked Condition: None.
  - Files: `frontend/src/types/documents.ts`

- [ ] (01C): Implement typed upload, list, and detail API functions
  - Source of Truth: `docs/plans/Plan_13.md` > `## 3. Scope`; `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 8. API Design`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Implement `uploadDocument(file, onUploadProgress)`.
    - Implement `listDocuments()`.
    - Implement `getDocument(documentId)`.
    - Use existing backend document endpoints through the configured Axios client.
  - Details: Create a document API module using `apiClient`. Build upload requests with `FormData`, pass Axios upload progress to the caller, unwrap typed response data, and URL-encode or otherwise safely place the document ID in the detail path.
  - Dependencies: (01B).
  - User Action: User must set `VITE_API_BASE_URL` in the local frontend environment when running against the backend.
  - Agent Work: Implement the three typed API functions without direct provider/storage calls.
  - Output: `frontend/src/api/documents.ts`.
  - Acceptance: Functions target `POST /api/documents/upload`, `GET /api/documents`, and `GET /api/documents/{document_id}` through `apiClient`.
  - Validation: TypeScript build; conditional API client tests in Batch06; browser network inspection during manual validation.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live requests if `VITE_API_BASE_URL` is missing; static implementation and build must still proceed.
  - Files: `frontend/src/api/documents.ts`, `frontend/src/api/client.ts` only if a small existing-client adjustment is required

- [ ] (01D): Define safe document API error and progress handling contracts
  - Source of Truth: `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 13. Failure Handling`; `docs/plans/Plan_13.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Show backend error messages when upload fails.
    - Show a clear connection error when the backend is unavailable.
    - Show progress without fake success.
    - Frontend must use backend APIs only.
  - Details: Add a small typed helper or clearly documented API error contract that can distinguish safe backend `detail` text from no-response connection failures and generic request failures. Keep progress representation valid when Axios does not provide a total.
  - Dependencies: (01C).
  - User Action: None.
  - Agent Work: Implement reusable error extraction and progress data mapping in the document API module or a focused co-located helper.
  - Output: Shared safe error/progress behavior for both pages.
  - Acceptance: UI callers receive clear display text and never need to render raw Axios error objects or fabricate upload percentages.
  - Validation: Conditional tests in Batch06 and manual unavailable-backend/upload checks.
  - Blocked Condition: None.
  - Files: `frontend/src/api/documents.ts` and/or a small focused helper under `frontend/src/api/`

### Files or Modules Likely Created or Updated

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/src/types/documents.ts`
- `frontend/src/api/documents.ts`
- `frontend/src/api/client.ts` only if required

### Required Outputs / Artifacts

- React Router dependency.
- Shared document TypeScript types.
- Typed upload/list/detail API functions.
- Safe API error and upload-progress mapping.

### Acceptance Criteria

- API functions use `apiClient` and `VITE_API_BASE_URL`.
- Document types match backend response fields.
- No direct Supabase, Qdrant, ShopAIKey, or indexing calls exist.
- No test framework or unrelated dependency is added in this batch.

### Required Tests or Validations

- TypeScript validation through the Batch06 build.
- Dependency manifest review.
- Conditional API client tests only when a frontend test runner exists.

### Explicit Non-Goals

- Do not change backend endpoints or schemas.
- Do not add a document detail page.
- Do not add chat, deletion, processing, indexing, authentication, or provider integrations.

## Mandatory Batch02 - Reusable Upload and Document Display Components

### Goal

Build focused reusable components for file selection, status display, and document metadata before composing the pages.

### Why this batch exists

Both pages need consistent status and document presentation, while upload behavior needs a reusable browser file-selection boundary with validation-friendly events and accessible controls.

### Inputs / Dependencies

- Batch01 document types and API contracts
- Existing React and plain CSS setup
- Supported format and metadata requirements from Plan 13

### Tasks

- [ ] (02A): Create the reusable status badge
  - Source of Truth: `docs/plans/Plan_13.md` > `## 3. Scope`; `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## 5. Core Features` > `### 5.2 Document List Page`
  - Source Requirements:
    - Display distinct states for `uploaded`, `processing`, `ready`, and `failed`.
    - Status text must remain readable and must not overflow.
  - Details: Implement a typed `StatusBadge` that maps each approved status to clear visible text and a distinct semantic CSS class. Do not use color as the only indicator.
  - Dependencies: (01B).
  - User Action: None.
  - Agent Work: Create the component and its focused styles.
  - Output: Reusable status badge.
  - Acceptance: All four status values render predictable labels and visually distinct states.
  - Validation: TypeScript build; conditional component test; manual responsive inspection.
  - Blocked Condition: None.
  - Files: `frontend/src/components/StatusBadge.tsx`, `frontend/src/styles.css`

- [ ] (02B): Create the reusable document card or row
  - Source of Truth: `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 5. Core Features` > `### 5.2 Document List Page`
  - Source Requirements:
    - Show file name, file type, upload time, status, chunk count, and processing error.
    - Reuse the status component.
  - Details: Implement a typed `DocumentCard` or compact row that accepts one `DocumentListItem`, formats the creation time safely, preserves long file names, and renders `error_message` only when present.
  - Dependencies: (01B), (02A).
  - User Action: None.
  - Agent Work: Create the component and responsive metadata layout.
  - Output: Reusable document item presentation for recent uploads and the full list.
  - Acceptance: Every required field is visible; failed-document error text is distinguishable from general page errors; long labels do not break the layout.
  - Validation: TypeScript build; conditional component test; manual desktop/mobile inspection.
  - Blocked Condition: None.
  - Files: `frontend/src/components/DocumentCard.tsx`, `frontend/src/styles.css`

- [ ] (02C): Create the reusable file input and optional dropzone
  - Source of Truth: `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 8. API Design`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 14. Frontend Page Plan` > `## 14.1 Upload Document Page`
  - Source Requirements:
    - Provide a file input.
    - Optional drag-and-drop behavior is allowed.
    - Accepted formats are PDF, DOCX, TXT, and CSV.
    - Upload controls must be usable.
  - Details: Implement `UploadBox` with a native file input as the reliable baseline. Add drag-and-drop only if it remains accessible and simple. Use the `accept` attribute for the approved extensions while retaining explicit validation because browser filtering is not sufficient.
  - Dependencies: (01B).
  - User Action: None.
  - Agent Work: Create the component with typed selected-file callbacks, disabled state support, selected-file feedback, and keyboard-accessible controls.
  - Output: Reusable upload selection component.
  - Acceptance: User can select an approved file with the native control; disabled state prevents changes during upload; optional drop behavior does not replace keyboard access.
  - Validation: TypeScript build; manual keyboard/file-selection check.
  - Blocked Condition: None.
  - Files: `frontend/src/components/UploadBox.tsx`, `frontend/src/styles.css`

- [ ] (02D): Implement supported-file and empty-file validation
  - Source of Truth: `docs/plans/Plan_13.md` > `## 8. API Design`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Accept `.pdf`, `.docx`, `.txt`, and `.csv`.
    - Reject unsupported files before upload.
    - Reject an empty file when browser file size is available.
    - Show a clear supported-types message.
  - Details: Add a pure validation function, either co-located with `UploadBox` or in a small frontend utility module, so page code can validate before calling the API and conditional tests can exercise the rules. Handle extension casing consistently.
  - Dependencies: (02C).
  - User Action: None.
  - Agent Work: Implement deterministic file validation and clear user-facing messages.
  - Output: Reusable validation result used by the upload page.
  - Acceptance: Supported non-empty files pass; unsupported extensions and zero-byte files fail before any API request.
  - Validation: Conditional unit tests in Batch06; manual unsupported-file check.
  - Blocked Condition: None.
  - Files: `frontend/src/components/UploadBox.tsx` and/or `frontend/src/utils/fileValidation.ts`

### Files or Modules Likely Created or Updated

- `frontend/src/components/StatusBadge.tsx`
- `frontend/src/components/DocumentCard.tsx`
- `frontend/src/components/UploadBox.tsx`
- `frontend/src/utils/fileValidation.ts` if a separate helper is justified
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- Typed status badge.
- Typed document card/row.
- Accessible file selection component.
- Deterministic extension and empty-file validation.

### Acceptance Criteria

- Components remain small and reusable.
- All four statuses and all required document fields are represented.
- Native file input remains available even if drag/drop is added.
- Unsupported and zero-byte files are rejected before API upload.

### Required Tests or Validations

- TypeScript build.
- Conditional component/unit tests if a runner exists.
- Manual keyboard, long-label, desktop, and mobile-width checks.

### Explicit Non-Goals

- Do not add a component framework or CSS framework.
- Do not add document selection for chat.
- Do not add deletion controls or a detail page.

## Mandatory Batch03 - Upload Page and Recent Document Feedback

### Goal

Deliver a complete upload workflow with validation, visible progress, safe errors, duplicate-submit prevention, and refreshed recent-document feedback.

### Why this batch exists

The user needs one reliable page that turns a browser-selected file into a backend upload while making every request state visible and immediately reflecting the resulting document metadata.

### Inputs / Dependencies

- Batch01 API functions and error/progress behavior
- Batch02 upload, status, and document display components
- Running backend and valid frontend base URL for live validation

### Tasks

- [ ] (03A): Build upload page selection and validation state
  - Source of Truth: `docs/plans/Plan_13.md` > `## 3. Scope`; `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Create `UploadDocumentPage.tsx`.
    - Validate the selected file before upload.
    - Show clear unsupported-file and empty-file errors.
  - Details: Compose `UploadBox` into the page with explicit selected-file, validation-error, upload-error, success, and upload-state handling. Clear stale messages when a new file is chosen without hiding current request state.
  - Dependencies: (02C), (02D).
  - User Action: None.
  - Agent Work: Create the upload page's selection and validation behavior.
  - Output: Upload page that prevents invalid files from reaching the API.
  - Acceptance: Invalid files produce clear messages and no upload request; valid files enable the upload action when not already uploading.
  - Validation: Conditional component test; manual unsupported and zero-byte file checks.
  - Blocked Condition: None.
  - Files: `frontend/src/pages/UploadDocumentPage.tsx`

- [ ] (03B): Implement upload request, progress, and duplicate-submit prevention
  - Source of Truth: `docs/plans/Plan_13.md` > `## 3. Scope`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_13.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Upload through the backend.
    - Show progress while upload is in flight.
    - Disable duplicate submit during slow uploads.
    - Restore interaction after completion or failure.
  - Details: Call `uploadDocument` only after validation. Render determinate percentage when total bytes are known and a clear indeterminate uploading state otherwise. Disable file replacement and submit during the active request.
  - Dependencies: (01C), (01D), (03A).
  - User Action: User must provide a reachable backend through `VITE_API_BASE_URL` for live validation.
  - Agent Work: Implement request lifecycle and progress UI.
  - Output: Functional upload submission with visible request state.
  - Acceptance: One active request can exist at a time; progress is visible; success/failure always clears the busy state.
  - Validation: Conditional component/API tests; browser network and slow-request behavior check.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live upload only when frontend/backend environment setup is unavailable.
  - Files: `frontend/src/pages/UploadDocumentPage.tsx`, `frontend/src/styles.css`

- [ ] (03C): Show upload success, backend failures, and connection failures safely
  - Source of Truth: `docs/plans/Plan_13.md` > `## 8. API Design`; `docs/plans/Plan_13.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_13.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Show backend error text when safe.
    - Show a clear connection error when the backend is unavailable.
    - Show successful document response/status without fake processing claims.
  - Details: Render success using the returned file name and status. Map backend `detail` messages through the shared error helper. Do not claim processing or readiness when the backend returns `uploaded`.
  - Dependencies: (01D), (03B).
  - User Action: None for implementation; backend availability is required for live checks.
  - Agent Work: Add accurate success and error feedback with retry-ready state.
  - Output: Safe user-visible upload result states.
  - Acceptance: Backend rejection, no-response connection failure, and success are visibly distinct; raw error objects and secrets are not rendered.
  - Validation: Conditional tests; manual unavailable-backend and rejected-upload checks.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live backend-dependent validation.
  - Files: `frontend/src/pages/UploadDocumentPage.tsx`

- [ ] (03D): Add recent document feedback and refresh after upload
  - Source of Truth: `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_13.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Upload page combines upload and recent document feedback.
    - Refresh the document list after upload success.
    - Empty document results must have an empty state.
  - Details: Load a compact recent-document section through `listDocuments`, reuse `DocumentCard`, and refresh it after a successful upload. Keep list-fetch errors separate from upload errors so one does not overwrite the other.
  - Dependencies: (01C), (02B), (03C).
  - User Action: User must provide a reachable backend for live list refresh validation.
  - Agent Work: Add initial recent-list loading, empty/error states, and post-upload refresh behavior.
  - Output: Upload page immediately reflects the uploaded document when the backend list returns it.
  - Acceptance: Successful upload triggers a real list fetch; the recent area renders loading, empty, error, or document content accurately.
  - Validation: Conditional component/API tests; manual TXT upload and post-success list check.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live refresh validation if backend/storage configuration is unavailable.
  - Files: `frontend/src/pages/UploadDocumentPage.tsx`, `frontend/src/components/DocumentCard.tsx`

### Files or Modules Likely Created or Updated

- `frontend/src/pages/UploadDocumentPage.tsx`
- `frontend/src/components/UploadBox.tsx`
- `frontend/src/components/DocumentCard.tsx`
- `frontend/src/api/documents.ts`
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- Complete upload page.
- Pre-request file validation.
- Determinate or indeterminate upload progress.
- Duplicate-submit prevention.
- Safe success, backend-error, and connection-error states.
- Recent document list refreshed after success.

### Acceptance Criteria

- PDF, DOCX, TXT, and CSV files can enter the upload workflow.
- Unsupported and empty files do not reach the backend.
- Upload progress and busy state are visible.
- Upload result matches the backend response status.
- Recent document feedback refreshes after success.

### Required Tests or Validations

- Conditional upload-page tests if a runner exists.
- `npm run build`.
- Manual TXT upload, progress, duplicate-submit, unsupported-file, unavailable-backend, and recent-list refresh checks.

### Explicit Non-Goals

- Do not trigger processing or indexing.
- Do not promise automatic status progression.
- Do not add multiple-file upload, resumable upload, deletion, chat, or document detail UI.

## Mandatory Batch04 - Document List Page and Status Refresh

### Goal

Deliver the full document list page with initial loading, manual refresh, required metadata, status/error visibility, and accurate empty/failure states.

### Why this batch exists

The upload page provides immediate feedback, but users also need a dedicated location to inspect all uploaded documents and refresh statuses independently of a new upload.

### Inputs / Dependencies

- Batch01 list API and types
- Batch02 document/status display components
- Backend document list route

### Tasks

- [ ] (04A): Build document list loading and rendering
  - Source of Truth: `docs/plans/Plan_13.md` > `## 3. Scope`; `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Create `DocumentListPage.tsx`.
    - Fetch documents on load.
    - Show file name, type, time, status, chunk count, and errors.
  - Details: Call `listDocuments` on initial page load and render every returned item through `DocumentCard`. Keep request state explicit and avoid stale state updates after unmount where the chosen React pattern requires cleanup.
  - Dependencies: (01C), (02B).
  - User Action: User must provide a reachable backend for live data.
  - Agent Work: Create the dedicated page and initial fetch lifecycle.
  - Output: Document list page backed by the existing API.
  - Acceptance: All returned documents render with required metadata and status information.
  - Validation: Conditional component/API tests; manual page-load check.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live data validation if backend setup is unavailable.
  - Files: `frontend/src/pages/DocumentListPage.tsx`

- [ ] (04B): Add loading, empty, connection-error, and list-error states
  - Source of Truth: `docs/plans/Plan_13.md` > `## 13. Failure Handling`; `docs/plans/Plan_13.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Empty document list shows an empty state.
    - Backend unavailable shows a clear connection error.
    - UI remains usable at desktop and mobile widths.
  - Details: Distinguish the first loading state, an actual empty response, and a failed request. Keep an existing successfully loaded list visible during a later refresh failure when practical, while clearly reporting that refresh failed.
  - Dependencies: (01D), (04A).
  - User Action: None for implementation.
  - Agent Work: Implement truthful list-state presentation and safe retry behavior.
  - Output: Complete list failure and empty-state handling.
  - Acceptance: A request error is never displayed as an empty document collection; retry remains available.
  - Validation: Conditional tests; manual empty-list and unavailable-backend checks where setup permits.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live backend-dependent checks.
  - Files: `frontend/src/pages/DocumentListPage.tsx`, `frontend/src/styles.css`

- [ ] (04C): Add manual document status refresh
  - Source of Truth: `docs/plans/Plan_13.md` > `## 3. Scope`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `# 14. Frontend Page Plan` > `## 14.2 Document List Page`
  - Source Requirements:
    - Provide a refresh action.
    - Display current backend statuses.
    - UI must work when documents remain `uploaded`.
  - Details: Add a visible refresh button that re-fetches the list, prevents overlapping refreshes, and communicates refreshing state. Do not add a processing/index call or require polling.
  - Dependencies: (04A), (04B).
  - User Action: None for implementation; changing live status requires backend-side processing outside this plan.
  - Agent Work: Implement manual refresh behavior and preserve accurate backend status display.
  - Output: User-controlled list/status refresh.
  - Acceptance: Refresh issues exactly one list request at a time and updates the rendered data; `uploaded` remains a valid stable state.
  - Validation: Conditional component test; manual network/status refresh check.
  - Blocked Condition: None for implementation. Live observation of status transitions may remain unavailable because upload processing is not triggered by the current upload route; document this limitation rather than blocking the page.
  - Files: `frontend/src/pages/DocumentListPage.tsx`

### Files or Modules Likely Created or Updated

- `frontend/src/pages/DocumentListPage.tsx`
- `frontend/src/components/DocumentCard.tsx`
- `frontend/src/components/StatusBadge.tsx`
- `frontend/src/api/documents.ts`
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- Dedicated all-documents page.
- Initial loading and accurate list rendering.
- Empty and failure states.
- Manual refresh with overlap prevention.

### Acceptance Criteria

- Page fetches documents on load.
- Every required field and failed-processing message is rendered.
- Empty and request-failure states are distinct.
- User can refresh without triggering processing or indexing.

### Required Tests or Validations

- Conditional document-list component tests.
- `npm run build`.
- Manual initial load, empty/error state where feasible, and refresh checks.

### Explicit Non-Goals

- Do not add automatic processing or indexing.
- Do not add deletion, document selection for chat, detail-page navigation, or polling as a requirement.

## Mandatory Batch05 - Application Routing, Navigation, Styling, and Scope Hardening

### Goal

Integrate both pages into the application shell with clear navigation, responsive work-focused styling, accessible interaction states, and verified frontend/backend boundaries.

### Why this batch exists

Individually functional pages are not a usable application until users can reach them predictably, understand their current location, and use them across supported viewport sizes without exposing forbidden backend concerns.

### Inputs / Dependencies

- Batch01 React Router dependency
- Batch03 upload page
- Batch04 document list page
- Existing `App.tsx`, `main.tsx`, and `styles.css`

### Tasks

- [ ] (05A): Mount the router provider and page routes
  - Source of Truth: `docs/plans/Plan_13.md` > `## 3. Scope`; `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Add basic routing for upload and document list.
    - Ensure the router provider is mounted.
  - Details: Mount the selected React Router provider in the appropriate entry layer. Define stable `/upload` and `/documents` routes, plus a clear root/default behavior that lands users on the tool rather than a placeholder or marketing page.
  - Dependencies: (01A), Batch03, Batch04.
  - User Action: None.
  - Agent Work: Replace the placeholder shell with route rendering and a safe fallback route.
  - Output: Navigable application routes.
  - Acceptance: Direct navigation and browser refresh work for both routes under the Vite development server; the placeholder text is removed.
  - Validation: `npm run build`; manual direct-route and navigation checks.
  - Blocked Condition: None.
  - Files: `frontend/src/App.tsx`, `frontend/src/main.tsx`

- [ ] (05B): Add compact navigation between Upload and Documents
  - Source of Truth: `docs/plans/Plan_13.md` > `## 3. Scope`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Add navigation between upload and document list.
    - Keep the UI work-focused and compact.
    - Do not create a marketing landing page.
  - Details: Add a simple application header/nav with clear labels, visible active state, and keyboard-focus treatment. Keep navigation focused on the two approved pages.
  - Dependencies: (05A).
  - User Action: None.
  - Agent Work: Implement route links and active-page feedback.
  - Output: Compact two-page navigation.
  - Acceptance: Users can move between pages without a full reload; labels and active state remain readable at narrow widths.
  - Validation: Manual mouse and keyboard navigation checks.
  - Blocked Condition: None.
  - Files: `frontend/src/App.tsx`, `frontend/src/styles.css`

- [ ] (05C): Complete responsive, accessible, work-focused styling
  - Source of Truth: `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Adjust styles consistently with the existing frontend.
    - Upload form must be usable on desktop and mobile widths.
    - Button labels and status text must not overflow.
    - Do not replace the tool with a landing page.
  - Details: Refactor the centered placeholder styles into a compact application layout. Add visible focus states, disabled/busy states, readable error/success treatment, wrapping/ellipsis rules for long file names, and mobile layout behavior down to 320px. Preserve plain CSS.
  - Dependencies: (02A), (02B), (02C), (05B).
  - User Action: None.
  - Agent Work: Complete the page/component styling and accessibility-oriented visual states.
  - Output: Responsive desktop/mobile document-management UI.
  - Acceptance: Controls remain reachable and readable; long labels do not cause horizontal overflow; status is not communicated by color alone.
  - Validation: Manual checks at representative desktop width and 320-375px mobile width; keyboard focus inspection.
  - Blocked Condition: None.
  - Files: `frontend/src/styles.css`, page/component files only where semantic markup changes are required

- [ ] (05D): Enforce frontend secret, endpoint, and scope boundaries
  - Source of Truth: `docs/plans/Plan_13.md` > `## 4. Out of Scope`; `docs/plans/Plan_13.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_13.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_13.md` > `## 15. Reviewer Checklist`; `README.md` > `## Development Notes for AI Agents` > `Important coordination rules`
  - Source Requirements:
    - No Supabase, Qdrant, or ShopAIKey keys in frontend code.
    - No chat, evidence, logs, auth/JWT, or unapproved deletion.
    - Frontend calls backend APIs only.
  - Details: Review all changed frontend files and dependency changes. Confirm only `VITE_API_BASE_URL` is used for configuration, no private key names/values are introduced, and no internal indexing or out-of-scope routes/components are added.
  - Dependencies: (05A), (05B), (05C).
  - User Action: None.
  - Agent Work: Run focused searches and inspect the final frontend diff.
  - Output: Scope and secret-boundary confirmation for the execution report.
  - Acceptance: Changed frontend code contains no private credentials, direct provider calls, internal index calls, chat/evidence/log/auth/deletion UI, or marketing landing page.
  - Validation: Git diff review and targeted `rg` searches documented in Batch06 report.
  - Blocked Condition: None.
  - Files: All changed frontend files; `docs/reports/report_13_execute_agent.md`

### Files or Modules Likely Created or Updated

- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/styles.css`
- Frontend page/component files for semantic markup corrections

### Required Outputs / Artifacts

- Router provider and two stable routes.
- Compact navigation.
- Responsive and accessible styling.
- Scope, endpoint, and secret-boundary review.

### Acceptance Criteria

- `/upload` and `/documents` are reachable and navigable.
- No placeholder or marketing landing page remains.
- UI works at desktop and mobile widths.
- Private keys and backend-only behavior remain outside frontend code.

### Required Tests or Validations

- `npm run build`.
- Manual direct-route, navigation, keyboard, desktop, and mobile-width checks.
- Diff and forbidden-string/endpoint review.

### Explicit Non-Goals

- Do not add Tailwind, a UI framework, auth, chat, evidence, logs, deletion, detail routing, processing controls, or indexing controls.

## Mandatory Batch06 - Automated/Manual Validation, Reporting, and Reviewer Handoff

### Goal

Run all available automated and mandatory manual validations, document environment-dependent blocks honestly, create the execution report, and prepare the task for review.

### Why this batch exists

Plan 13 requires a passing frontend build, manual browser workflow checks, conditional tests, backend compatibility confirmation, and an explicit report of what was and was not validated.

### Inputs / Dependencies

- Batch01 through Batch05 completed
- Frontend dependencies installed
- Running frontend for browser checks
- Running backend at the configured `VITE_API_BASE_URL` for live upload/list checks
- Valid backend Supabase configuration for live document persistence
- A supported TXT fixture and an unsupported file for manual validation

### Tasks

- [ ] (06A): Add file-validation tests only when a frontend test runner exists
  - Source of Truth: `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 11. Required Tests`; `README.md` > `## Testing and Validation`
  - Source Requirements:
    - Add tests for file validation where frontend testing infrastructure exists.
    - Current repository has no frontend `test` script.
  - Details: Re-check `frontend/package.json` at execution time. If a real runner has been added by approved concurrent work, add focused tests for all four supported extensions, case handling, unsupported files, and zero-byte files. Otherwise record that tests are not configured and do not fabricate or invoke `npm test`.
  - Dependencies: (02D).
  - User Action: None.
  - Agent Work: Add conditional tests or document the verified absence of test infrastructure.
  - Output: Real validation tests or an accurate not-configured result.
  - Acceptance: Test coverage exists when infrastructure exists; otherwise the report clearly states why no test command/file was added.
  - Validation: Run the configured test command only if present.
  - Blocked Condition: None. Absence of optional test infrastructure is not `BLOCKED_BY_USER_ACTION`.
  - Files: `frontend/src/components/UploadBox.test.tsx`, `frontend/src/utils/fileValidation.test.ts`, or existing test-convention equivalents only if a runner exists

- [ ] (06B): Add API client and page tests only when a frontend test runner exists
  - Source of Truth: `docs/plans/Plan_13.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_13.md` > `## 9. Implementation Steps`; `docs/plans/Plan_13.md` > `## 11. Required Tests`
  - Source Requirements:
    - Add API client tests if a frontend test runner exists.
    - Add upload page UI tests if testing infrastructure exists.
    - Validate progress, supported/unsupported files, list refresh, and errors where practical.
  - Details: If a real configured runner and DOM/API mocking pattern exist, add focused tests for endpoint/method/FormData behavior, progress callback mapping, invalid-file request prevention, duplicate-submit prevention, and post-success list refresh. Do not install a broad test stack solely to create these optional files.
  - Dependencies: (01C), (01D), Batch03, Batch04.
  - User Action: None.
  - Agent Work: Add conditional API/component tests or record that the current test stack is absent.
  - Output: Focused tests or an accurate not-configured result.
  - Acceptance: Any created tests run and pass; no placeholder tests or fabricated output exist.
  - Validation: Configured frontend test command, if present.
  - Blocked Condition: None.
  - Files: `frontend/src/api/documents.test.ts`, `frontend/src/pages/UploadDocumentPage.test.tsx`, `frontend/src/pages/DocumentListPage.test.tsx` only if supported by configured infrastructure

- [ ] (06C): Run the mandatory frontend build and available automated tests
  - Source of Truth: `docs/plans/Plan_13.md` > `## 11. Required Tests`; `docs/plans/Plan_13.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_13.md` > `## 15. Reviewer Checklist`; `README.md` > `## Running the Project` > `### Production Frontend Build`; `README.md` > `## Testing and Validation`
  - Source Requirements:
    - Run `npm run build`.
    - Run frontend tests only if configured.
    - Fix TypeScript errors.
    - Do not claim tests were run when they were not.
  - Details: Execute the build from `frontend/`. If a test script exists, run it and capture real results. Fix all in-scope TypeScript/build/test failures before marking this task complete.
  - Dependencies: (06A), (06B), Batch05.
  - User Action: None unless package installation is externally unavailable.
  - Agent Work: Run and report mandatory automated validation.
  - Output: Passing frontend build and real test results when applicable.
  - Acceptance: `npm run build` exits successfully; configured tests pass; absent tests are reported as not configured.
  - Validation: `cd frontend` then `npm run build`; `npm test` or the actual configured test command only if present.
  - Blocked Condition: None unless dependency installation is impossible because of external registry/network state; do not claim completion while the build is unverified.
  - Files: Runtime/test files only as required to resolve in-scope failures; `docs/reports/report_13_execute_agent.md`

- [ ] (06D): Run manual browser upload, list, error, and responsive checks
  - Source of Truth: `docs/plans/Plan_13.md` > `## 11. Required Tests`; `docs/plans/Plan_13.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_13.md` > `## 13. Failure Handling`; `docs/plans/Plan_13.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Start backend and frontend.
    - Upload a TXT file and confirm progress.
    - Confirm the uploaded document appears in the list.
    - Reject an unsupported file clearly.
    - Refresh existing documents.
    - Check desktop/mobile usability and non-overflowing labels.
  - Details: Use a real browser against the local frontend. Inspect the network destination to confirm calls use the configured backend base URL. Check `/upload` and `/documents`, supported/unsupported selection, progress/busy state, success/error display, list refresh, failed-status error rendering if data exists, keyboard navigation, and representative desktop/mobile widths.
  - Dependencies: (06C).
  - User Action: User must provide or retain valid backend `.env`/Supabase setup and `frontend/.env` base URL if live upload/list validation cannot run with existing local configuration.
  - Agent Work: Run browser checks when setup is available; otherwise mark only the affected live checks `BLOCKED_BY_USER_ACTION` with a safe reason while still completing static/build validation.
  - Output: Manual browser validation evidence or precise blocked status.
  - Acceptance: Required checks pass, or each environment-dependent check is explicitly marked blocked without fake success.
  - Validation: Browser session against the local frontend and backend; record whether manual testing was performed.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if backend credentials, Supabase project/storage, frontend base URL, supported fixture, or running services are unavailable.
  - Files: `docs/reports/report_13_execute_agent.md`

- [ ] (06E): Create the execution report and complete final scope review
  - Source of Truth: `docs/plans/Plan_13.md` > `## 4. Out of Scope`; `docs/plans/Plan_13.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_13.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Report files created and modified.
    - Report commands and test results.
    - Report known issues and manual browser-test status.
    - Report intentionally excluded out-of-scope work.
    - Confirm scope, tests, secrets, architecture, responsive UI, and backend-only API access.
  - Details: Create the standard Plan 13 execution report. Include exact build/test/manual outcomes, blocked user actions, upload-processing limitation, scope exclusions, changed dependency rationale, and focused diff/secret/endpoint review results. Update this task progress tracker only for tasks whose acceptance and validation conditions are satisfied or whose allowed blocked condition is recorded.
  - Dependencies: (06C), (06D), (05D).
  - User Action: None.
  - Agent Work: Write the report, review the final diff, synchronize tracker state, and prepare reviewer handoff.
  - Output: `docs/reports/report_13_execute_agent.md` and synchronized `docs/tasks/task_13.md`.
  - Acceptance: Report includes every Plan 13 required field, does not claim blocked live checks as passed, and explicitly confirms no out-of-scope UI or frontend secrets were added.
  - Validation: Read the report and task tracker; compare task IDs and final changed-file list; review git diff and targeted scope searches.
  - Blocked Condition: None.
  - Files: `docs/reports/report_13_execute_agent.md`, `docs/tasks/task_13.md`

### Files or Modules Likely Created or Updated

- Conditional frontend test files only if real test infrastructure exists
- Frontend runtime files as needed to fix validation failures
- `docs/reports/report_13_execute_agent.md`
- `docs/tasks/task_13.md` progress tracker during execution

### Required Outputs / Artifacts

- Passing `npm run build`.
- Real frontend test results when tests are configured.
- Manual browser results or safe environment-dependent blocked statuses.
- Scope, secret, endpoint, responsive, and architecture review.
- Plan 13 execution report.

### Acceptance Criteria

- Frontend build passes.
- Optional tests are handled honestly according to available infrastructure.
- Required browser checks are run or explicitly blocked by missing user/environment setup.
- Report states whether browser testing was performed.
- No fake success, secret leakage, or out-of-scope work appears.

### Required Tests or Validations

- `cd frontend`
- `npm run build`
- Configured frontend test command only if present.
- Manual `/upload` and `/documents` browser checks.
- TXT upload, progress, unsupported-file, list refresh, connection-error, desktop/mobile, and label-overflow checks where setup permits.
- Git diff, forbidden secret-name, provider-call, internal-index-route, and out-of-scope UI review.

### Explicit Non-Goals

- Do not fabricate automated or manual results.
- Do not add a test framework solely to satisfy conditional test wording.
- Do not create backend credentials, Supabase resources, or live documents on behalf of the user without explicit approval.
- Do not implement chat, evidence, logs, auth/JWT, deletion, processing/index controls, a detail page, or a marketing landing page.

## Optional Future Tracks

The following work is not part of the mandatory Plan 13 batch chain:

- A dedicated frontend testing stack may be introduced by a later approved tooling or quality plan. Plan 13 tests remain conditional on infrastructure that actually exists.
- Automatic document status polling may be added by a later approved UX plan. Plan 13 requires manual refresh only.
- A document detail page may use the implemented `getDocument` client in a later approved plan.
- Document processing/background-job controls require an approved backend workflow and are outside this frontend task.
- Chat, document selection for chat, evidence viewing, agent logs, authentication, deletion, and broader frontend pages require later approved plans.

Each optional track is outside the mandatory MVP batch chain for this task file.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05
- Batch05 -> Batch06

Optional future tracks are outside the mandatory dependency chain.

## Global Verification Checklist

- [ ] `docs/plans/Plan_13.md` remained the scope authority.
- [ ] React Router is installed without unrelated dependency additions.
- [ ] `frontend/src/types/documents.ts` defines the approved document status and response types.
- [ ] `uploadDocument`, `listDocuments`, and `getDocument` are implemented through the existing Axios client.
- [ ] Upload uses `FormData`.
- [ ] Upload progress is visible and does not fabricate a percentage when total bytes are unavailable.
- [ ] Duplicate upload submission is disabled while a request is active.
- [ ] `.pdf`, `.docx`, `.txt`, and `.csv` are accepted case-insensitively.
- [ ] Unsupported extensions are rejected before upload.
- [ ] Zero-byte files are rejected before upload.
- [ ] Backend upload errors show safe backend text where available.
- [ ] Backend connection failures show a clear connection message.
- [ ] Upload success reflects the actual returned backend status.
- [ ] Recent document feedback refreshes after a successful upload.
- [ ] Upload page has truthful loading, success, error, and empty states.
- [ ] Document list page fetches on load.
- [ ] Document list page provides a manual refresh action.
- [ ] Overlapping list refresh requests are prevented.
- [ ] Document list displays file name, file type, created time, status, chunk count, and processing error.
- [ ] `uploaded`, `processing`, `ready`, and `failed` have distinct readable status treatment.
- [ ] Empty list and request failure are displayed as different states.
- [ ] `/upload` and `/documents` routes work.
- [ ] Root/default route reaches the actual tool UI.
- [ ] Navigation works without full-page reload.
- [ ] Placeholder and marketing landing content are absent.
- [ ] Upload and list UI are usable at desktop and 320-375px mobile widths.
- [ ] Button labels, file names, metadata, and status text do not create horizontal overflow.
- [ ] Keyboard focus is visible for interactive controls.
- [ ] Status is not communicated by color alone.
- [ ] `VITE_API_BASE_URL` is the only required frontend runtime setting.
- [ ] No Supabase, Qdrant, ShopAIKey, or other private key is exposed in frontend code.
- [ ] No frontend call goes directly to Supabase, Qdrant, or ShopAIKey.
- [ ] Frontend does not call `POST /api/documents/{document_id}/index`.
- [ ] No backend API, schema, migration, storage, processing, or authentication change was added.
- [ ] No chat, evidence viewer, agent logs UI, login/JWT, deletion, detail page, or document selection for chat was added.
- [ ] Current backend limitation that upload may remain `uploaded` is represented honestly.
- [ ] `npm run build` was run and passed.
- [ ] Frontend tests were run only if a real test command exists.
- [ ] Absence of frontend test infrastructure was reported accurately when applicable.
- [ ] Manual browser testing status was reported.
- [ ] TXT upload, progress, unsupported-file, list refresh, and responsive checks passed or were safely marked `BLOCKED_BY_USER_ACTION`.
- [ ] Execution report includes files created, files modified, commands, results, known issues, out-of-scope work, and browser-test status.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [ ] Batch01 - Frontend Contracts, Routing Dependency, and Document API Client
- [ ] Batch02 - Reusable Upload and Document Display Components
- [ ] Batch03 - Upload Page and Recent Document Feedback
- [ ] Batch04 - Document List Page and Status Refresh
- [ ] Batch05 - Application Routing, Navigation, Styling, and Scope Hardening
- [ ] Batch06 - Automated/Manual Validation, Reporting, and Reviewer Handoff

### Task IDs

#### Batch01

- [ ] (01A): Add the required React Router dependency
- [ ] (01B): Add typed document API response models
- [ ] (01C): Implement typed upload, list, and detail API functions
- [ ] (01D): Define safe document API error and progress handling contracts

#### Batch02

- [ ] (02A): Create the reusable status badge
- [ ] (02B): Create the reusable document card or row
- [ ] (02C): Create the reusable file input and optional dropzone
- [ ] (02D): Implement supported-file and empty-file validation

#### Batch03

- [ ] (03A): Build upload page selection and validation state
- [ ] (03B): Implement upload request, progress, and duplicate-submit prevention
- [ ] (03C): Show upload success, backend failures, and connection failures safely
- [ ] (03D): Add recent document feedback and refresh after upload

#### Batch04

- [ ] (04A): Build document list loading and rendering
- [ ] (04B): Add loading, empty, connection-error, and list-error states
- [ ] (04C): Add manual document status refresh

#### Batch05

- [ ] (05A): Mount the router provider and page routes
- [ ] (05B): Add compact navigation between Upload and Documents
- [ ] (05C): Complete responsive, accessible, work-focused styling
- [ ] (05D): Enforce frontend secret, endpoint, and scope boundaries

#### Batch06

- [ ] (06A): Add file-validation tests only when a frontend test runner exists
- [ ] (06B): Add API client and page tests only when a frontend test runner exists
- [ ] (06C): Run the mandatory frontend build and available automated tests
- [ ] (06D): Run manual browser upload, list, error, and responsive checks
- [ ] (06E): Create the execution report and complete final scope review

## Completion Reporting Rules for Future Execution Agents

### BatchXX Execution Result

#### Completed Task IDs

- (XXA): complete / partial / blocked

#### Files Created or Modified

- path

#### Tests or Validations Run

- command or browser check: result

#### User Actions Required

- action: completed / pending / not required
- details: safe summary only, never include secrets

#### Blocked-by-User Status

- status: none / BLOCKED_BY_USER_ACTION
- reason: missing `VITE_API_BASE_URL`, backend not running, missing backend `.env`, missing Supabase credentials/storage setup, missing supported fixture, missing browser-accessible local service, or other safe summary

#### Validation Responsibility

- user-provided setup confirmed: yes / no / not required
- agent validation run after setup: yes / no
- validation command or browser workflow: result

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

Future Execution Agents must not claim completion unless task validations and acceptance criteria are satisfied. Optional frontend tests must be reported as not configured when no real runner exists, not as passed. Environment-dependent browser checks may be marked `BLOCKED_BY_USER_ACTION` only with a safe, precise reason.
