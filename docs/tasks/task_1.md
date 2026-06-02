# Plan 1 - Project Foundation Execution Tasks

## Purpose

Create a detailed execution task file for the approved project foundation milestone. This task file guides a future Execution Agent to build only the runnable FastAPI backend foundation, React TypeScript frontend foundation, environment configuration, logging, CORS, health check, and minimal verification required by `docs/plans/Plan_1.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_1.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- User revision request: future Execution Agents must keep implementation code clean, standard, and easy to understand.
- Conflict note: `docs/plans/Master_Plan.md` includes broader Phase 1 connectivity tasks for Supabase, Qdrant, and ShopAIKey. `docs/plans/Plan_1.md` explicitly makes those out of scope, so they are not part of this task file.

## Source Section Index

- `## 1. Goal` -> runnable foundation, health endpoint, and excluded external services.
- `## 2. Why This Plan Exists` -> stable layout and conventions for later plans.
- `## 3. Scope` -> required backend, frontend, config, logging, CORS, env examples, tests, and secret convention work.
- `## 4. Out of Scope` -> prohibited Supabase, Qdrant, ShopAIKey, document, retrieval, agent, auth, and production deployment work.
- `## 5. Dependencies` -> no prior plan dependency; Python and Node.js are local prerequisites.
- `## 6. Required Files and Folders` -> expected files and packages.
- `## 7. Data Model / Schema Changes` -> no database changes and required health response schema.
- `## 8. API Design` -> `GET /api/health` contract.
- `## 9. Implementation Steps` -> ordered implementation details.
- `## 10. Configuration and Environment Variables` -> backend and frontend env variables.
- `## 11. Required Tests` -> backend pytest, manual health check, and frontend build commands.
- `## 12. Acceptance Criteria` -> completion conditions and forbidden logic checks.
- `## 13. Failure Handling` -> default settings and startup/build failure behavior.
- `## 14. Agent Report Requirement` -> required execution report fields.
- `## 15. Reviewer Checklist` -> review expectations and extra safety checks.

## Approved Architecture Summary

The approved architecture for this plan is a local project foundation with a FastAPI backend and a Vite React TypeScript frontend. The backend owns all private configuration and exposes a mounted health API at `/api/health`. The frontend uses `VITE_API_BASE_URL` for API calls and must not contain backend-only secrets. Supabase, Qdrant, ShopAIKey, document processing, retrieval, agents, authentication, and production deployment are intentionally deferred.

## Global Implementation Rules

- Keep `docs/plans/Plan_1.md` as the source of truth for scope.
- Do not implement Supabase, Qdrant, ShopAIKey, document parsing, retrieval, agents, authentication, JWT, login, multi-user support, or deployment configuration.
- Do not add real secrets to any file.
- Keep backend-only variables out of frontend source and frontend `.env.example`.
- Use placeholders only in `.env.example` files.
- Preserve a layout that later plans can extend without guessing file locations.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

### Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, components, settings, and tests.
- Keep functions, components, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, React, TypeScript, Vite, and Axios conventions for the files being created.
- Keep TypeScript and Python typing clear where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless the plan explicitly requires them.
- Add comments only where they clarify a non-obvious decision or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Do not add formatter, linter, framework, or architecture changes outside Plan 1 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Backend Foundation and Health API
- Batch02 - Frontend Foundation and API Client
- Batch03 - Verification, Safety Checks, and Handoff

## Mandatory Batch01 - Backend Foundation and Health API

### Goal

Create a runnable FastAPI backend with environment-driven settings, logging, CORS, and a working `GET /api/health` endpoint.

### Why this batch exists

Later backend services depend on a stable application entrypoint, configuration pattern, package layout, and first API contract.

### Inputs / Dependencies

- `docs/plans/Plan_1.md`
- Local Python installation
- No previous plan dependency

### Tasks

- [x] (01A): Create backend folder structure and dependency file
  - Source of Truth: `docs/plans/Plan_1.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_1.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Create `backend/app`, `backend/app/api`, `backend/app/core`, `backend/app/models`, and `backend/tests`.
    - Create `backend/requirements.txt` with FastAPI foundation dependencies.
  - Details: Establish backend package layout and dependency list for the foundation.
  - Dependencies: None
  - User Action: Ensure Python is installed locally.
  - Agent Work: Create required backend directories, package markers, and `requirements.txt` containing `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `python-dotenv`, `httpx`, and `pytest`.
  - Output: Backend directory skeleton and dependency file.
  - Acceptance: Required backend files and folders exist and dependency names match the plan.
  - Validation: Inspect file tree and dependency file contents.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if Python is unavailable and dependencies/tests cannot be run.
  - Files: `backend/app/main.py`, `backend/app/api/__init__.py`, `backend/app/core/`, `backend/app/models/__init__.py`, `backend/tests/`, `backend/requirements.txt`

- [x] (01B): Implement backend settings loading
  - Source of Truth: `docs/plans/Plan_1.md` > `## 3. Scope`; `docs/plans/Plan_1.md` > `## 9. Implementation Steps`; `docs/plans/Plan_1.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_1.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Settings must load from environment variables.
    - `APP_ENV` defaults to `development`.
    - `SINGLE_USER_ID` defaults to `single_user` and remains backend-side.
    - `FRONTEND_ORIGIN` defaults to `http://localhost:5173`.
  - Details: Add a typed settings layer that reads environment values and `.env` safely.
  - Dependencies: (01A)
  - User Action: None.
  - Agent Work: Implement `Settings` in `backend/app/core/config.py` using `pydantic-settings` and `python-dotenv` support.
  - Output: Backend configuration module.
  - Acceptance: Settings can be imported and default values are available without a populated `.env`.
  - Validation: Run backend tests or a focused import check during Batch03.
  - Blocked Condition: None.
  - Files: `backend/app/core/config.py`

- [x] (01C): Implement backend logging and FastAPI app wiring
  - Source of Truth: `docs/plans/Plan_1.md` > `## 3. Scope`; `docs/plans/Plan_1.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_1.md` > `## 9. Implementation Steps`; `docs/plans/Plan_1.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Add backend logging setup.
    - Configure CORS for local frontend.
    - Use `FastAPI(title="Document QA Agent")`.
    - Backend startup failures must appear in logs.
  - Details: Wire app creation, startup logging, and CORS middleware around configured settings.
  - Dependencies: (01B)
  - User Action: None.
  - Agent Work: Implement `setup_logging()` with Python logging at level `INFO`, call it from the app entrypoint, configure CORS with `FRONTEND_ORIGIN`, and expose the FastAPI application object.
  - Output: Runnable backend app entrypoint and logging module.
  - Acceptance: `app.main:app` imports successfully and CORS allows the configured frontend origin.
  - Validation: Run backend tests and manual `uvicorn app.main:app --reload` check during Batch03.
  - Blocked Condition: None.
  - Files: `backend/app/core/logging.py`, `backend/app/main.py`

- [x] (01D): Implement health router and response contract
  - Source of Truth: `docs/plans/Plan_1.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_1.md` > `## 8. API Design`; `docs/plans/Plan_1.md` > `## 9. Implementation Steps`; `docs/plans/Plan_1.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Add `GET /api/health`.
    - Return `status`, `service`, and `app_env`.
    - Response status is HTTP 200 when healthy.
    - Do not require request validation.
  - Details: Add a health API router mounted under `/api`.
  - Dependencies: (01B), (01C)
  - User Action: None.
  - Agent Work: Implement `backend/app/api/health.py` with `APIRouter`, optional `HealthResponse` Pydantic schema, and route `/health`; include router in `backend/app/main.py` under `/api`.
  - Output: Health endpoint returning the required JSON structure.
  - Acceptance: `GET /api/health` returns HTTP 200 and `{"status":"ok","service":"document-qa-agent","app_env":"development"}` by default.
  - Validation: `cd backend` then `pytest tests/test_health.py -v`; manual curl check during Batch03.
  - Blocked Condition: None.
  - Files: `backend/app/api/health.py`, `backend/app/main.py`

- [x] (01E): Add backend environment example and secret convention
  - Source of Truth: `docs/plans/Plan_1.md` > `## 3. Scope`; `docs/plans/Plan_1.md` > `## 9. Implementation Steps`; `docs/plans/Plan_1.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_1.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_1.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Create `backend/.env.example` with placeholders and no real keys.
    - Keep secrets backend-only by convention.
    - `SINGLE_USER_ID` must be present only in backend configuration.
  - Details: Document backend-safe environment names required by this plan only.
  - Dependencies: (01B)
  - User Action: None.
  - Agent Work: Create `backend/.env.example` containing `APP_ENV`, `SINGLE_USER_ID`, and `FRONTEND_ORIGIN` example placeholder values.
  - Output: Backend env example with no real secrets.
  - Acceptance: Backend env example contains only Plan 1 backend variables and no Supabase, Qdrant, ShopAIKey, or private key values.
  - Validation: Inspect `backend/.env.example` and search frontend files for backend-only variable names during Batch03.
  - Blocked Condition: None.
  - Files: `backend/.env.example`

- [x] (01F): Add backend health test
  - Source of Truth: `docs/plans/Plan_1.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_1.md` > `## 9. Implementation Steps`; `docs/plans/Plan_1.md` > `## 11. Required Tests`; `docs/plans/Plan_1.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Add `backend/tests/test_health.py` using `fastapi.testclient.TestClient`.
    - Verify `GET /api/health` returns HTTP 200 and status `ok`.
  - Details: Add a focused backend test that locks the health endpoint response contract.
  - Dependencies: (01D)
  - User Action: None.
  - Agent Work: Implement the test using `TestClient` and assert status code plus required response fields.
  - Output: Backend health endpoint test.
  - Acceptance: Test fails if the route is missing, returns non-200, or omits required fields.
  - Validation: `cd backend` then `pytest tests/test_health.py -v` during Batch03.
  - Blocked Condition: None.
  - Files: `backend/tests/test_health.py`

### Files or Modules Likely Created or Updated

- `backend/app/main.py`
- `backend/app/api/__init__.py`
- `backend/app/api/health.py`
- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/models/__init__.py`
- `backend/tests/test_health.py`
- `backend/requirements.txt`
- `backend/.env.example`

### Required Outputs / Artifacts

- Runnable FastAPI app object.
- Health endpoint mounted at `/api/health`.
- Backend settings and logging foundation.
- Backend env example.
- Backend health test.

### Acceptance Criteria

- Backend starts with `uvicorn app.main:app --reload`.
- `GET /api/health` returns HTTP 200.
- Health response includes `status`, `service`, and `app_env`.
- Backend settings load from `.env` and environment variables.
- Backend starts without Supabase, Qdrant, or ShopAIKey variables.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_health.py -v`
- `uvicorn app.main:app --reload`
- `curl http://localhost:8000/api/health`

### Explicit Non-Goals

- No Supabase client or database access.
- No Qdrant client or vector search.
- No ShopAIKey requests.
- No document parsing, chunking, embedding, retrieval, or agent logic.
- No authentication, JWT, login, or multi-user support.

## Mandatory Batch02 - Frontend Foundation and API Client

### Goal

Create a Vite React TypeScript frontend foundation with a minimal app shell, API client configuration, frontend env example, and build script support.

### Why this batch exists

Later UI pages depend on a stable frontend entrypoint, TypeScript setup, API client convention, and safe environment variable boundary.

### Inputs / Dependencies

- `docs/plans/Plan_1.md`
- Local Node.js installation
- Batch01 backend API base URL convention

### Tasks

- [x] (02A): Create frontend Vite React TypeScript skeleton
  - Source of Truth: `docs/plans/Plan_1.md` > `## 3. Scope`; `docs/plans/Plan_1.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_1.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Create frontend Vite React TypeScript files under `frontend/`.
    - Add `frontend/package.json`, `frontend/tsconfig.json`, and `frontend/vite.config.ts`.
  - Details: Establish the frontend project with scripts and dependencies needed to build.
  - Dependencies: None.
  - User Action: Ensure Node.js is installed locally.
  - Agent Work: Create the Vite React TypeScript skeleton and package scripts for at least `build`.
  - Output: Frontend project skeleton.
  - Acceptance: Frontend package files and TypeScript/Vite config files exist.
  - Validation: `cd frontend` then `npm install` and `npm run build` during Batch03.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if Node.js is unavailable and install/build cannot run.
  - Files: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/src/main.tsx`

- [x] (02B): Implement frontend API client configuration
  - Source of Truth: `docs/plans/Plan_1.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_1.md` > `## 9. Implementation Steps`; `docs/plans/Plan_1.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_1.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Create `frontend/src/api/client.ts`.
    - Use `axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL })`.
    - Frontend API base URL may fail later if missing at runtime, but build should pass with `.env.example` documenting the variable.
  - Details: Add a single shared Axios client that future frontend API modules can reuse.
  - Dependencies: (02A)
  - User Action: None.
  - Agent Work: Add Axios dependency and create the API client using `VITE_API_BASE_URL`.
  - Output: Frontend API client module.
  - Acceptance: Client module compiles and references only frontend-safe `VITE_API_BASE_URL`.
  - Validation: `npm run build` and secret-name search during Batch03.
  - Blocked Condition: None.
  - Files: `frontend/src/api/client.ts`, `frontend/package.json`

- [x] (02C): Implement minimal app shell and styles
  - Source of Truth: `docs/plans/Plan_1.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_1.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Create `frontend/src/App.tsx`.
    - Create `frontend/src/styles.css`.
    - Render the app name and a placeholder for future routes.
  - Details: Provide a minimal visible UI confirming frontend startup without implementing later pages.
  - Dependencies: (02A)
  - User Action: None.
  - Agent Work: Implement `App.tsx`, import global CSS from `main.tsx`, and keep UI limited to foundation confirmation.
  - Output: Minimal frontend app shell.
  - Acceptance: Frontend renders the app name and a future-routes placeholder.
  - Validation: `npm run build` during Batch03.
  - Blocked Condition: None.
  - Files: `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/styles.css`

- [x] (02D): Add frontend environment example and enforce frontend-safe boundary
  - Source of Truth: `docs/plans/Plan_1.md` > `## 3. Scope`; `docs/plans/Plan_1.md` > `## 9. Implementation Steps`; `docs/plans/Plan_1.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_1.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_1.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Create `frontend/.env.example` with `VITE_API_BASE_URL=http://localhost:8000`.
    - Frontend `.env.example` contains only `VITE_API_BASE_URL`.
    - No private backend keys are exposed in frontend code.
  - Details: Document the only frontend-safe environment variable for this plan.
  - Dependencies: (02B)
  - User Action: None.
  - Agent Work: Create `frontend/.env.example` and inspect frontend files to ensure backend-only variables are absent.
  - Output: Frontend env example.
  - Acceptance: Frontend env example contains only `VITE_API_BASE_URL`; frontend files do not reference `SINGLE_USER_ID`, Supabase, Qdrant, or ShopAIKey secret variable names.
  - Validation: `rg "SINGLE_USER_ID|SUPABASE|QDRANT|SHOPAIKEY" frontend` should return no secret references unless explicitly justified as absent from built code; `npm run build` passes.
  - Blocked Condition: None.
  - Files: `frontend/.env.example`, `frontend/src/api/client.ts`

### Files or Modules Likely Created or Updated

- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/styles.css`
- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/vite.config.ts`
- `frontend/.env.example`

### Required Outputs / Artifacts

- Vite React TypeScript frontend skeleton.
- Shared Axios API client.
- Minimal app shell and CSS.
- Frontend env example.

### Acceptance Criteria

- Frontend builds successfully.
- `frontend/.env.example` contains only `VITE_API_BASE_URL`.
- Frontend code does not expose or reference backend-only private keys.
- No later feature pages are implemented in this foundation batch.

### Required Tests or Validations

- `cd frontend`
- `npm install`
- `npm run build`
- Search frontend files for backend-only secret variable names.

### Explicit Non-Goals

- No upload page.
- No document list page.
- No chat page.
- No evidence viewer.
- No agent logs page.
- No production deployment configuration.

## Mandatory Batch03 - Verification, Safety Checks, and Handoff

### Goal

Run required validations, verify scope boundaries, and produce a concise execution report for reviewer handoff.

### Why this batch exists

The foundation is only complete when backend tests pass, frontend builds, health can be manually checked, and out-of-scope services/secrets are confirmed absent.

### Inputs / Dependencies

- Completed Batch01
- Completed Batch02
- Local Python and Node.js installations

### Tasks

- [x] (03A): Run backend automated and manual health validations
  - Source of Truth: `docs/plans/Plan_1.md` > `## 1. Goal`; `docs/plans/Plan_1.md` > `## 11. Required Tests`; `docs/plans/Plan_1.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_1.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Backend starts.
    - `GET /api/health` returns JSON without requiring Supabase, Qdrant, ShopAIKey, document parsing, retrieval, or agents.
    - Run `pytest tests/test_health.py -v`.
    - Manual check uses `uvicorn app.main:app --reload` and `curl http://localhost:8000/api/health`.
  - Details: Verify the backend actually works locally and captures failures honestly.
  - Dependencies: Batch01
  - User Action: None unless Python or required command tooling is missing.
  - Agent Work: Install dependencies if needed, run the health test, start the backend for manual health check, call the endpoint, and stop the dev server after verification.
  - Output: Backend test and manual health check results.
  - Acceptance: Pytest passes and manual health endpoint returns the required JSON.
  - Validation: Command outputs recorded in the execution report.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if local Python tooling is missing and cannot be installed by the agent.
  - Files: `backend/tests/test_health.py`, execution report or task progress notes

- [x] (03B): Run frontend install/build validation
  - Source of Truth: `docs/plans/Plan_1.md` > `## 1. Goal`; `docs/plans/Plan_1.md` > `## 11. Required Tests`; `docs/plans/Plan_1.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Run frontend install if needed.
    - Run `npm run build`.
    - TypeScript build succeeds.
  - Details: Verify the frontend foundation compiles from a clean dependency install.
  - Dependencies: Batch02
  - User Action: None unless Node.js or npm is unavailable.
  - Agent Work: Run `npm install` when dependencies are not installed, then run `npm run build`.
  - Output: Frontend dependency and build validation results.
  - Acceptance: Build completes successfully without TypeScript or Vite errors.
  - Validation: Command outputs recorded in the execution report.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if local Node.js/npm tooling is missing and cannot be installed by the agent.
  - Files: `frontend/package.json`, generated lockfile if package manager creates one, execution report or task progress notes

- [x] (03C): Verify scope, secret safety, and out-of-scope exclusions
  - Source of Truth: `docs/plans/Plan_1.md` > `## 4. Out of Scope`; `docs/plans/Plan_1.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_1.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - No Supabase, Qdrant, or ShopAIKey logic exists yet.
    - No Auth/JWT logic exists.
    - No private keys are exposed in frontend code.
    - Confirm backend can start without Supabase, Qdrant, or ShopAIKey variables.
    - Confirm `SINGLE_USER_ID` is present only in backend configuration.
  - Details: Search the codebase for prohibited implementation and secret exposure.
  - Dependencies: Batch01, Batch02
  - User Action: None.
  - Agent Work: Run targeted searches for Supabase, Qdrant, ShopAIKey, JWT/auth/login, secret key names in frontend, and `SINGLE_USER_ID` outside backend files.
  - Output: Safety verification summary.
  - Acceptance: No prohibited logic or frontend secret exposure is present; any false-positive text is documented safely.
  - Validation: Search commands and results recorded in the execution report.
  - Blocked Condition: None.
  - Files: Entire repository for inspection; no planned file changes unless fixing violations.

- [x] (03D): Produce execution report and update progress tracker
  - Source of Truth: `docs/plans/Plan_1.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_1.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Report files created, files modified, commands run, test results, known issues, and intentionally not implemented out-of-scope work.
    - Reviewer must verify scope, tests, acceptance, no hardcoded secrets, no fake success, and architecture match.
  - Details: Record the final implementation status for reviewer handoff.
  - Dependencies: (03A), (03B), (03C)
  - User Action: None.
  - Agent Work: Update this task file progress tracker if requested by the execution workflow, and write or provide the execution report with all required fields.
  - Output: Complete execution report and synchronized progress tracker.
  - Acceptance: Report includes all required fields and accurately reflects passing, failing, or blocked validations.
  - Validation: Manual review of report completeness against `## 14. Agent Report Requirement`.
  - Blocked Condition: None.
  - Files: `docs/tasks/task_1.md`, execution report location chosen by the future Execution Agent

### Files or Modules Likely Created or Updated

- `docs/tasks/task_1.md`
- Optional execution report artifact chosen by the future Execution Agent
- Dependency artifacts generated by package managers, if applicable

### Required Outputs / Artifacts

- Backend test result.
- Manual health check result.
- Frontend build result.
- Scope and secret safety verification summary.
- Execution report.

### Acceptance Criteria

- Backend and frontend validations are run.
- Failures are reported honestly and not marked complete.
- Out-of-scope features remain absent.
- Progress tracker matches completed, partial, or blocked task IDs.

### Required Tests or Validations

- `cd backend && pytest tests/test_health.py -v`
- `cd backend && uvicorn app.main:app --reload`
- `curl http://localhost:8000/api/health`
- `cd frontend && npm install`
- `cd frontend && npm run build`
- Repository searches for out-of-scope logic and frontend secret exposure.

### Explicit Non-Goals

- Do not implement fixes outside Plan 1 scope except to remove accidental out-of-scope work.
- Do not create external service projects or credentials.
- Do not claim completion when a validation was skipped, failed, or blocked.

## Optional Future Tracks

- Supabase, Qdrant, ShopAIKey connectivity, document upload, parsing, chunking, embeddings, retrieval, GraphRAG, LangGraph agents, and full frontend pages are future tracks from `docs/plans/Master_Plan.md`.
- This track is not part of the mandatory Plan 1 batch chain.

## Dependency Chain

- Batch01 -> Batch03
- Batch02 -> Batch03
- Batch01 and Batch02 may be implemented independently before Batch03.

## Global Verification Checklist

- [ ] `backend/app/main.py` exposes a FastAPI application object.
- [ ] `backend/app/core/config.py` loads `APP_ENV`, `SINGLE_USER_ID`, and `FRONTEND_ORIGIN`.
- [ ] Backend defaults work without `.env`.
- [ ] `GET /api/health` returns HTTP 200.
- [ ] Health response includes `status`, `service`, and `app_env`.
- [ ] Backend CORS uses configured frontend origin.
- [ ] Backend logging is configured at startup.
- [ ] `backend/.env.example` contains no real secrets.
- [ ] Frontend builds successfully.
- [ ] `frontend/.env.example` contains only `VITE_API_BASE_URL`.
- [ ] Frontend source has no backend-only private secret names.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.
- [ ] No Supabase, Qdrant, ShopAIKey, document parsing, retrieval, agents, auth, JWT, or login logic was added.
- [ ] Required commands and results are reported.

## Progress Tracker

### Batches

- [x] Batch01 - Backend Foundation and Health API
- [x] Batch02 - Frontend Foundation and API Client
- [x] Batch03 - Verification, Safety Checks, and Handoff

### Task IDs

#### Batch01

- [x] (01A): Create backend folder structure and dependency file
- [x] (01B): Implement backend settings loading
- [x] (01C): Implement backend logging and FastAPI app wiring
- [x] (01D): Implement health router and response contract
- [x] (01E): Add backend environment example and secret convention
- [x] (01F): Add backend health test

#### Batch02

- [x] (02A): Create frontend Vite React TypeScript skeleton
- [x] (02B): Implement frontend API client configuration
- [x] (02C): Implement minimal app shell and styles
- [x] (02D): Add frontend environment example and enforce frontend-safe boundary

#### Batch03

- [x] (03A): Run backend automated and manual health validations
- [x] (03B): Run frontend install/build validation
- [x] (03C): Verify scope, secret safety, and out-of-scope exclusions
- [x] (03D): Produce execution report and update progress tracker

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
- reason: missing API key, missing provider project, missing manual setup, missing local runtime, or other safe summary

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
