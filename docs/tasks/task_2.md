# Plan 2 - Database Schema and Supabase Setup Execution Tasks

## Purpose

Create a detailed execution task file for the approved Supabase PostgreSQL schema and backend Supabase service milestone. This task file guides a future Execution Agent to add the schema migration, backend-only Supabase configuration, service client, connectivity helper, focused tests, and manual Supabase setup verification required by `docs/plans/Plan_2.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_2.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Conflict note: No blocking conflict was found. `docs/plans/Master_Plan.md` confirms the same storage/database direction, single-user MVP policy, backend-only private secrets, and required Supabase PostgreSQL table families. `docs/plans/Plan_2.md` remains the scope authority for this task file.

## Source Section Index

- `docs/plans/Plan_2.md` > `## 1. Goal` -> Supabase schema, storage assumption, backend service client, and connectivity success condition.
- `docs/plans/Plan_2.md` > `## 2. Why This Plan Exists` -> durable schema dependency for upload, chunks, GraphRAG, chat, and agent logs.
- `docs/plans/Plan_2.md` > `## 3. Scope` -> required schema, indexes, backend client, connection helper, commands, storage bucket assumption, and `SINGLE_USER_ID` policy.
- `docs/plans/Plan_2.md` > `## 4. Out of Scope` -> prohibited upload, parsing, chunking, embeddings, Qdrant, frontend, auth, JWT, and multi-user work.
- `docs/plans/Plan_2.md` > `## 5. Dependencies` -> Plan 1 completion and Supabase project requirement.
- `docs/plans/Plan_2.md` > `## 6. Required Files and Folders` -> expected backend service, database, migration, health, test, dependency, and env files.
- `docs/plans/Plan_2.md` > `## 7. Data Model / Schema Changes` -> required tables, fields, relationships, allowed document statuses, and indexes.
- `docs/plans/Plan_2.md` > `## 8. API Design` -> no public endpoint requirement and optional internal connection helper/health flag.
- `docs/plans/Plan_2.md` > `## 9. Implementation Steps` -> ordered implementation details.
- `docs/plans/Plan_2.md` > `## 10. Configuration and Environment Variables` -> backend-only Supabase and single-user variables.
- `docs/plans/Plan_2.md` > `## 11. Required Tests` -> unit, manual database, manual storage, and optional backend connection checks.
- `docs/plans/Plan_2.md` > `## 12. Acceptance Criteria` -> completion conditions and forbidden frontend/Auth behavior.
- `docs/plans/Plan_2.md` > `## 13. Failure Handling` -> clear missing config, storage, query, and migration failure behavior.
- `docs/plans/Plan_2.md` > `## 14. Agent Report Requirement` -> required execution report fields and migration application status.
- `docs/plans/Plan_2.md` > `## 15. Reviewer Checklist` -> review expectations and extra schema/secret safety checks.
- `docs/plans/Master_Plan.md` > `## 2. Tech Stack` -> Supabase PostgreSQL and Supabase Storage are approved storage services.
- `docs/plans/Master_Plan.md` > `## 3. Authentication Policy` -> single-user MVP, no Auth/JWT, backend-only private secrets.
- `docs/plans/Master_Plan.md` > `## 6. Data Storage Design` -> Supabase storage bucket and table purpose clarification.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> broader backend env naming consistency.

## Approved Architecture Summary

The approved architecture for this plan is a backend-only Supabase integration for a single-user Document QA Agent MVP. Supabase PostgreSQL stores document metadata, parsed chunks, GraphRAG entities and relationships, chat sessions/messages, agent runs, and agent step logs. Supabase Storage stores original uploaded files in a bucket named by `SUPABASE_STORAGE_BUCKET`, expected to be `documents` for local setup. The backend initializes Supabase with `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`; the frontend must never receive or reference the service-role key. No public API endpoints are required, and the basic health endpoint must continue working without Supabase unless dependency checks are explicitly requested through a query flag.

## Global Implementation Rules

- Keep `docs/plans/Plan_2.md` as the source of truth for scope and validation.
- Do not implement document upload endpoints, storage uploads, parsing, chunking, embeddings, Qdrant integration, frontend pages, Auth/JWT, login, multi-user account tables, or user auth policies.
- Do not add real Supabase URLs, service-role keys, bucket credentials, or other secrets to repository files.
- Add placeholders only to `backend/.env.example`; use `.env` only for local uncommitted secret values.
- Keep `SUPABASE_SERVICE_ROLE_KEY` backend-only and absent from frontend source, frontend env examples, and generated client bundles.
- Preserve the no-auth MVP decision by using `SINGLE_USER_ID` as the owner identifier for rows created by later plans.
- Keep the existing basic health endpoint working without Supabase credentials.
- Report manual Supabase setup and migration status honestly; do not claim that SQL was applied or a bucket exists unless verified.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, settings, and tests.
- Keep functions and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, Supabase Python client, and PostgreSQL migration conventions for the files being created.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless the plan explicitly requires them.
- Add comments only where they clarify a non-obvious decision or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Do not add formatter, linter, framework, or architecture changes outside Plan 2 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Backend Supabase Configuration
- Batch02 - Database Schema Migration and Storage Assumptions
- Batch03 - Backend Supabase Service and Optional Dependency Health
- Batch04 - Validation, Manual Setup Checks, and Handoff

## Mandatory Batch01 - Backend Supabase Configuration

### Goal

Prepare backend dependencies, settings, package markers, and environment examples needed for backend-only Supabase access.

### Why this batch exists

The migration and service client need a stable backend package layout and typed configuration before any Supabase connection helper can be implemented safely.

### Inputs / Dependencies

- `docs/plans/Plan_2.md`
- Completed Plan 1 foundation
- Existing backend package, settings module, and health endpoint from Plan 1
- Supabase project details supplied by the user only through local environment values

### Tasks

- [x] (01A): Add Supabase backend dependency
  - Source of Truth: `docs/plans/Plan_2.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_2.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Add Supabase client dependencies to `backend/requirements.txt`.
    - Keep dependencies scoped to backend service-client setup.
  - Details: Extend the backend dependency list so the Supabase Python client can be imported by service code and tests.
  - Dependencies: Completed Plan 1 backend foundation.
  - User Action: None.
  - Agent Work: Add the appropriate Supabase Python client package to `backend/requirements.txt`, preserving existing dependencies and avoiding unrelated package changes.
  - Output: Updated backend dependency file.
  - Acceptance: Dependency file contains the Supabase client package needed by `backend/app/services/supabase_service.py`.
  - Validation: `cd backend` then install/update dependencies as needed before running tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/requirements.txt`

- [x] (01B): Add backend-only Supabase environment placeholders
  - Source of Truth: `docs/plans/Plan_2.md` > `## 3. Scope`; `docs/plans/Plan_2.md` > `## 9. Implementation Steps`; `docs/plans/Plan_2.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Master_Plan.md` > `# 15. Environment Variables`
  - Source Requirements:
    - Add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET` to `backend/.env.example`.
    - Keep `SINGLE_USER_ID` backend-only.
    - Never expose `SUPABASE_SERVICE_ROLE_KEY` to frontend files.
  - Details: Document the backend-only variables required for Supabase connection tests and storage bucket lookup.
  - Dependencies: Completed Plan 1 env example.
  - User Action: User must put real Supabase values only in local `.env`, never in `.env.example`.
  - Agent Work: Add safe placeholder/example values to `backend/.env.example`; do not edit frontend env examples with private Supabase values.
  - Output: Updated backend env example with Supabase placeholders.
  - Acceptance: `backend/.env.example` includes Supabase variable names and no real secrets; frontend env files remain private-key-free.
  - Validation: Inspect `backend/.env.example` and run a frontend secret-name search in Batch04.
  - Blocked Condition: None for placeholder work; `BLOCKED_BY_USER_ACTION` for real local values needed by live connectivity validation.
  - Files: `backend/.env.example`, frontend env files for inspection only

- [x] (01C): Extend backend settings for Supabase variables
  - Source of Truth: `docs/plans/Plan_2.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_2.md` > `## 9. Implementation Steps`; `docs/plans/Plan_2.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_2.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Extend `Settings` in `backend/app/core/config.py` with Supabase variables.
    - Missing `SUPABASE_URL` must produce a clear backend configuration error when Supabase service code is used.
    - Missing `SUPABASE_SERVICE_ROLE_KEY` must produce a clear backend configuration error when Supabase service code is used.
    - Basic health must keep working without Supabase.
  - Details: Add typed settings fields while avoiding app startup failure for routes that do not need Supabase.
  - Dependencies: (01B)
  - User Action: None.
  - Agent Work: Add Supabase settings to the existing config pattern, with safe defaults or optional typing where needed so basic app import and health remain independent of Supabase credentials.
  - Output: Updated backend settings module.
  - Acceptance: Existing basic health tests still pass without real Supabase credentials; Supabase service calls can detect missing required values clearly.
  - Validation: Run existing backend tests and new service tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/core/config.py`

- [x] (01D): Add services and database package markers
  - Source of Truth: `docs/plans/Plan_2.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_2.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Create `backend/app/services/__init__.py`.
    - Create `backend/app/db/__init__.py`.
    - Prepare `backend/app/db/migrations/` for migration SQL.
  - Details: Establish importable backend packages for service and database code.
  - Dependencies: Completed Plan 1 backend package layout.
  - User Action: None.
  - Agent Work: Create missing package marker files and migration folder without adding runtime behavior.
  - Output: Importable services and database packages.
  - Acceptance: `backend/app/services` and `backend/app/db` are valid Python packages, and the migrations folder exists.
  - Validation: Inspect file tree and run backend import/tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/services/__init__.py`, `backend/app/db/__init__.py`, `backend/app/db/migrations/`

### Files or Modules Likely Created or Updated

- `backend/requirements.txt`
- `backend/.env.example`
- `backend/app/core/config.py`
- `backend/app/services/__init__.py`
- `backend/app/db/__init__.py`
- `backend/app/db/migrations/`

### Required Outputs / Artifacts

- Supabase dependency in backend requirements.
- Backend-only Supabase env placeholders.
- Supabase settings fields.
- Service and database package markers.

### Acceptance Criteria

- Backend dependency file supports importing the Supabase client.
- Backend settings expose Supabase values without exposing them to frontend.
- Basic health remains independent from Supabase credentials.
- No real secrets are committed.

### Required Tests or Validations

- Inspect `backend/requirements.txt`.
- Inspect `backend/.env.example`.
- Run existing backend tests during Batch04.
- Search frontend files for backend-only Supabase secret names during Batch04.

### Explicit Non-Goals

- Do not create a Supabase project.
- Do not enter real Supabase credentials into tracked files.
- Do not implement upload, parsing, chunking, embeddings, Qdrant, frontend, Auth/JWT, or multi-user logic.

## Mandatory Batch02 - Database Schema Migration and Storage Assumptions

### Goal

Create the initial Supabase PostgreSQL migration with all required MVP tables and indexes, and document the storage bucket/manual schema application assumptions.

### Why this batch exists

Document upload, chunk persistence, GraphRAG metadata, chat history, and agent logs all need durable tables before later feature plans write data.

### Inputs / Dependencies

- `docs/plans/Plan_2.md`
- `docs/plans/Master_Plan.md` for table purpose clarification
- Batch01 package/folder preparation
- Supabase PostgreSQL enabled by user

### Tasks

- [x] (02A): Create document metadata and chunk tables
  - Source of Truth: `docs/plans/Plan_2.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Master_Plan.md` > `## 6. Data Storage Design`
  - Source Requirements:
    - Create `documents`.
    - Create `document_chunks`.
    - `document_chunks.document_id` references `documents(id)` with `on delete cascade`.
    - Document statuses are `uploaded`, `processing`, `ready`, and `failed`.
  - Details: Add the document-level and chunk-level tables exactly needed for later upload, parsing, and chunk persistence.
  - Dependencies: (01D)
  - User Action: None for writing SQL; user action is required later to apply SQL in Supabase.
  - Agent Work: Create `backend/app/db/migrations/001_initial_schema.sql` with `documents` and `document_chunks` table definitions, required defaults, nullable fields, and cascade relationship.
  - Output: Migration SQL containing document and chunk tables.
  - Acceptance: SQL includes all fields from the plan for both tables and preserves the required cascade behavior.
  - Validation: Manual SQL execution in Supabase during Batch04; inspect migration contents before execution.
  - Blocked Condition: None for repository SQL; `BLOCKED_BY_USER_ACTION` if Supabase project access is unavailable for manual execution.
  - Files: `backend/app/db/migrations/001_initial_schema.sql`

- [x] (02B): Create GraphRAG entity and relationship tables
  - Source of Truth: `docs/plans/Plan_2.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Master_Plan.md` > `## 6. Data Storage Design`
  - Source Requirements:
    - Create `document_entities`.
    - Create `document_relationships`.
    - `document_entities.document_id` references `documents(id)` with `on delete cascade`.
    - `document_entities.chunk_id` references `document_chunks(id)` with `on delete cascade`.
  - Details: Add the medium-level GraphRAG persistence tables without implementing extraction or retrieval logic.
  - Dependencies: (02A)
  - User Action: None for writing SQL.
  - Agent Work: Add `document_entities` and `document_relationships` table SQL with all fields and foreign-key behavior specified by the plan.
  - Output: Migration SQL containing GraphRAG metadata tables.
  - Acceptance: SQL includes all fields from the plan and keeps GraphRAG logic itself out of scope.
  - Validation: Manual SQL execution in Supabase during Batch04; inspect migration contents before execution.
  - Blocked Condition: None for repository SQL; `BLOCKED_BY_USER_ACTION` if Supabase project access is unavailable for manual execution.
  - Files: `backend/app/db/migrations/001_initial_schema.sql`

- [x] (02C): Create chat and agent log tables
  - Source of Truth: `docs/plans/Plan_2.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Master_Plan.md` > `## 6. Data Storage Design`
  - Source Requirements:
    - Create `chat_sessions`.
    - Create `chat_messages`.
    - Create `agent_runs`.
    - Create `agent_steps`.
    - `chat_messages.session_id` references `chat_sessions(id)` with `on delete cascade`.
    - `agent_steps.agent_run_id` references `agent_runs(id)` with `on delete cascade`.
  - Details: Add the persistence tables required for future chat sessions, messages, full agent runs, and detailed agent step logs.
  - Dependencies: (02A)
  - User Action: None for writing SQL.
  - Agent Work: Add chat and agent table SQL with all fields, defaults, JSONB defaults, nullable fields, and foreign-key behavior specified by the plan.
  - Output: Migration SQL containing chat and agent log tables.
  - Acceptance: SQL includes all fields from the plan and preserves cascade/nulling behavior for dependent rows.
  - Validation: Manual SQL execution in Supabase during Batch04; inspect migration contents before execution.
  - Blocked Condition: None for repository SQL; `BLOCKED_BY_USER_ACTION` if Supabase project access is unavailable for manual execution.
  - Files: `backend/app/db/migrations/001_initial_schema.sql`

- [x] (02D): Add required indexes
  - Source of Truth: `docs/plans/Plan_2.md` > `## 3. Scope`; `docs/plans/Plan_2.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_2.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Create indexes needed by document ownership, document lookup, chunk lookup, graph lookup, chat sessions, and agent logs.
    - Include every required index listed in the plan.
    - Include the unique index on `(document_id, chunk_index)`.
  - Details: Add all required index SQL after table creation in dependency-safe order.
  - Dependencies: (02A), (02B), (02C)
  - User Action: None for writing SQL.
  - Agent Work: Add all required `create index if not exists` and `create unique index if not exists` statements exactly matching the plan's lookup needs.
  - Output: Migration SQL containing required indexes.
  - Acceptance: Migration contains every required index from `docs/plans/Plan_2.md`.
  - Validation: Inspect migration contents and confirm indexes exist after manual SQL application in Batch04.
  - Blocked Condition: None for repository SQL; `BLOCKED_BY_USER_ACTION` if Supabase project access is unavailable for manual execution.
  - Files: `backend/app/db/migrations/001_initial_schema.sql`

- [x] (02E): Record storage bucket and migration application instructions
  - Source of Truth: `docs/plans/Plan_2.md` > `## 1. Goal`; `docs/plans/Plan_2.md` > `## 3. Scope`; `docs/plans/Plan_2.md` > `## 9. Implementation Steps`; `docs/plans/Plan_2.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_2.md` > `## 11. Required Tests`; `docs/plans/Master_Plan.md` > `## 6. Data Storage Design`
  - Source Requirements:
    - Document the `documents` storage bucket assumption.
    - Add development commands for applying the schema manually in Supabase SQL editor or CLI.
    - Verify the bucket named by `SUPABASE_STORAGE_BUCKET` exists; create it manually in Supabase if missing.
  - Details: Make the manual Supabase setup requirements explicit without fabricating credentials or creating external resources automatically.
  - Dependencies: (01B), (02D)
  - User Action: User must provide Supabase project access and create or confirm the configured storage bucket if missing.
  - Agent Work: Record the manual SQL-editor/CLI application command path and bucket assumption in an existing appropriate project documentation location if one exists; otherwise include it in the execution report and handoff notes. Keep tracked docs free of real secrets.
  - Output: Manual setup instructions and bucket assumption recorded for reviewer handoff.
  - Acceptance: Future reviewer can tell whether the migration was applied manually, by CLI, or only added to the repository, and whether the configured bucket exists.
  - Validation: Manual database/storage checks in Batch04.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if Supabase access or bucket creation is not available.
  - Files: `backend/app/db/migrations/001_initial_schema.sql`, `backend/.env.example`, existing project docs if appropriate, execution report

### Files or Modules Likely Created or Updated

- `backend/app/db/migrations/001_initial_schema.sql`
- `backend/.env.example`
- Existing project docs if appropriate
- Execution report chosen by the future Execution Agent

### Required Outputs / Artifacts

- Initial schema migration with 8 required tables.
- Required indexes and unique chunk index.
- Storage bucket assumption and migration application instructions.

### Acceptance Criteria

- Migration creates `documents`, `document_chunks`, `document_entities`, `document_relationships`, `chat_sessions`, `chat_messages`, `agent_runs`, and `agent_steps`.
- Required indexes exist in the SQL.
- Required cascade/nulling foreign-key behavior is preserved.
- Storage bucket assumption is documented safely.
- No upload, parsing, embedding, Qdrant, frontend, Auth/JWT, or multi-user work is added.

### Required Tests or Validations

- Inspect migration SQL for all required tables and indexes.
- Open Supabase SQL editor and run `backend/app/db/migrations/001_initial_schema.sql`.
- Confirm all 8 tables exist after applying the migration.
- Confirm a Supabase Storage bucket named by `SUPABASE_STORAGE_BUCKET` exists.

### Explicit Non-Goals

- Do not upload files to storage.
- Do not parse or chunk documents.
- Do not generate embeddings.
- Do not connect to Qdrant.
- Do not create user auth policies or account tables.

## Mandatory Batch03 - Backend Supabase Service and Optional Dependency Health

### Goal

Create a backend-only Supabase service client with singleton access, clear configuration/connection errors, and a lightweight database/storage connectivity helper.

### Why this batch exists

Later upload, document, and agent workflows need a safe backend Supabase access layer, but frontend and public API surfaces must not receive service-role credentials.

### Inputs / Dependencies

- Batch01 Supabase dependency and settings
- Batch02 migration table names and storage bucket name
- Existing health endpoint from Plan 1
- Supabase project credentials supplied through local backend environment values

### Tasks

- [x] (03A): Implement backend-only Supabase client singleton
  - Source of Truth: `docs/plans/Plan_2.md` > `## 1. Goal`; `docs/plans/Plan_2.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_2.md` > `## 8. API Design`; `docs/plans/Plan_2.md` > `## 9. Implementation Steps`; `docs/plans/Plan_2.md` > `## 10. Configuration and Environment Variables`
  - Source Requirements:
    - Create `backend/app/services/supabase_service.py`.
    - Initialize the Supabase client from `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
    - Add `get_supabase_client()` that returns a singleton client.
    - Keep service-role access backend-only.
  - Details: Add the service module and lazy client creation so callers reuse one backend Supabase client.
  - Dependencies: (01A), (01C), (01D)
  - User Action: User must provide real local Supabase environment values before live connection validation.
  - Agent Work: Implement typed helper functions that read backend settings, validate required Supabase values at service-call time, and initialize the Supabase Python client without exposing secrets.
  - Output: Backend Supabase service module.
  - Acceptance: `get_supabase_client()` returns the same initialized client on repeated calls when config is present, and raises a clear safe error when required config is missing.
  - Validation: Mocked tests in Batch04; optional live import/check after user provides local env values.
  - Blocked Condition: None for implementation/tests with mocks; `BLOCKED_BY_USER_ACTION` for live validation without user-provided credentials.
  - Files: `backend/app/services/supabase_service.py`

- [x] (03B): Add custom Supabase connection error handling
  - Source of Truth: `docs/plans/Plan_2.md` > `## 8. API Design`; `docs/plans/Plan_2.md` > `## 9. Implementation Steps`; `docs/plans/Plan_2.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Add a custom `SupabaseConnectionError`.
    - Missing config must produce clear backend configuration errors.
    - Supabase query failure must include the operation name in the error message.
    - Missing storage bucket must be reported as a setup failure, not silently ignored.
  - Details: Centralize safe error messages for config validation, database checks, and storage checks.
  - Dependencies: (03A)
  - User Action: None for implementation.
  - Agent Work: Implement custom exception usage in service helpers; avoid logging or returning actual secret values.
  - Output: Safe error handling in Supabase service.
  - Acceptance: Errors identify the failing operation or missing setup without leaking credentials.
  - Validation: Mocked tests for missing config, query failure, and storage failure in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/services/supabase_service.py`

- [x] (03C): Implement database and storage connectivity helper
  - Source of Truth: `docs/plans/Plan_2.md` > `## 1. Goal`; `docs/plans/Plan_2.md` > `## 8. API Design`; `docs/plans/Plan_2.md` > `## 9. Implementation Steps`; `docs/plans/Plan_2.md` > `## 11. Required Tests`; `docs/plans/Plan_2.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_2.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Add `check_supabase_connection()`.
    - Output should report `database: true` and `storage: true` when checks pass.
    - Perform a lightweight query against `documents`.
    - Check the configured storage bucket.
    - Raise `SupabaseConnectionError` with a clear message on failure.
  - Details: Add a connectivity helper that proves the schema and storage bucket are reachable without doing document upload work.
  - Dependencies: (02A), (02E), (03B)
  - User Action: User must apply the migration and confirm/create the configured storage bucket before live validation can pass.
  - Agent Work: Implement `check_supabase_connection()` using the singleton client, a safe lightweight `documents` query, and a storage bucket existence check.
  - Output: Connectivity helper returning database/storage booleans on success.
  - Acceptance: Mocked passing checks return `{"database": True, "storage": True}` or the project's equivalent Python dict; failure paths raise safe errors.
  - Validation: Mocked unit tests in Batch04; optional live command after user setup.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if live Supabase credentials, applied schema, or storage bucket are missing.
  - Files: `backend/app/services/supabase_service.py`

- [x] (03D): Preserve basic health and optionally add dependency health flag
  - Source of Truth: `docs/plans/Plan_2.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_2.md` > `## 8. API Design`; `docs/plans/Plan_2.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - No new public API endpoints are required in this plan.
    - If health is extended, use `GET /api/health?include_dependencies=true`.
    - Keep the existing basic health check working without Supabase.
  - Details: Make any health integration opt-in so existing readiness checks do not require external credentials.
  - Dependencies: (03C)
  - User Action: None for implementation; live dependency result still depends on user Supabase setup.
  - Agent Work: Either leave `backend/app/api/health.py` unchanged or add an optional `include_dependencies` query flag that calls `check_supabase_connection()` only when true.
  - Output: Basic health remains independent; optional dependency health is available only if implemented.
  - Acceptance: `GET /api/health` still passes without Supabase credentials. If the dependency flag is added, it reports Supabase status or safe errors only when requested.
  - Validation: Existing health tests plus new focused tests if health behavior changes.
  - Blocked Condition: None for basic health; `BLOCKED_BY_USER_ACTION` for live dependency check without user setup.
  - Files: `backend/app/api/health.py`, `backend/tests/test_health.py` if health behavior changes

### Files or Modules Likely Created or Updated

- `backend/app/services/supabase_service.py`
- `backend/app/api/health.py` only if adding optional dependency health
- `backend/tests/test_health.py` only if health behavior changes

### Required Outputs / Artifacts

- Backend-only Supabase client singleton.
- `SupabaseConnectionError`.
- `check_supabase_connection()` helper.
- Basic health endpoint preserved.
- Optional dependency health flag if implemented.

### Acceptance Criteria

- Supabase service client initializes from backend settings when credentials are present.
- Missing Supabase config fails with clear safe backend errors.
- Connection helper reports database and storage availability when setup is complete.
- Basic health works without Supabase credentials.
- Frontend has no Supabase service-role key references.

### Required Tests or Validations

- Mocked Supabase service unit tests in Batch04.
- Existing health tests.
- Optional live command after user setup:
  - `cd backend`
  - `python -c "from app.services.supabase_service import check_supabase_connection; print(check_supabase_connection())"`

### Explicit Non-Goals

- Do not add document upload or storage write logic.
- Do not add frontend Supabase clients.
- Do not expose service-role credentials through health responses or logs.
- Do not create Auth/JWT logic or policies.

## Mandatory Batch04 - Validation, Manual Setup Checks, and Handoff

### Goal

Run automated tests, perform or document manual Supabase checks, verify secret/scope boundaries, and produce the execution report required for reviewer handoff.

### Why this batch exists

Plan 2 is only complete when code-level tests pass, schema/storage setup is confirmed or explicitly blocked, and no out-of-scope or secret exposure has slipped in.

### Inputs / Dependencies

- Completed Batch01
- Completed Batch02
- Completed Batch03
- User-provided Supabase project, local `.env` values, migration application access, and storage bucket setup for live validation

### Tasks

- [x] (04A): Add mocked Supabase service tests
  - Source of Truth: `docs/plans/Plan_2.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_2.md` > `## 9. Implementation Steps`; `docs/plans/Plan_2.md` > `## 11. Required Tests`; `docs/plans/Plan_2.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Create `backend/tests/test_supabase_service.py`.
    - Write tests that mock the Supabase client.
    - Verify missing config produces a clear error.
    - Verify service helper behavior.
  - Details: Add focused unit tests that do not require real Supabase credentials.
  - Dependencies: Batch03
  - User Action: None.
  - Agent Work: Mock Supabase client creation, database query behavior, storage bucket behavior, singleton behavior, and failure paths. Keep tests free of real secrets.
  - Output: Supabase service unit tests.
  - Acceptance: Tests fail if missing config is unclear, helper output is wrong, or storage/query failure is silently ignored.
  - Validation: `cd backend` then `pytest tests/test_supabase_service.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_supabase_service.py`

- [x] (04B): Run backend automated validations
  - Source of Truth: `docs/plans/Plan_2.md` > `## 11. Required Tests`; `docs/plans/Plan_2.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_2.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Run `pytest tests/test_supabase_service.py -v`.
    - Existing basic health must keep working without Supabase.
    - Missing config failures must be clear.
  - Details: Verify the new Supabase service tests and any affected existing tests.
  - Dependencies: (04A)
  - User Action: None unless local Python tooling or dependency installation is unavailable.
  - Agent Work: Install/update backend dependencies if needed, run the required Supabase service tests, and run impacted existing health tests.
  - Output: Backend test results.
  - Acceptance: Required backend tests pass or failures are reported honestly.
  - Validation: Command outputs recorded in the execution report.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if local Python tooling or dependency installation is unavailable.
  - Files: `backend/tests/test_supabase_service.py`, `backend/tests/test_health.py` if impacted, execution report

- [x] (04C): Perform manual Supabase database and storage checks
  - Source of Truth: `docs/plans/Plan_2.md` > `## 5. Dependencies`; `docs/plans/Plan_2.md` > `## 9. Implementation Steps`; `docs/plans/Plan_2.md` > `## 11. Required Tests`; `docs/plans/Plan_2.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_2.md` > `## 13. Failure Handling`; `docs/plans/Plan_2.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Requires a Supabase project with PostgreSQL and Storage enabled.
    - Apply the SQL migration in Supabase.
    - Confirm all 8 tables exist.
    - Confirm a Supabase Storage bucket named `documents` or the configured `SUPABASE_STORAGE_BUCKET` exists.
    - Report whether the SQL migration was applied manually, by CLI, or only added to the repository.
  - Details: Validate actual external setup when user-provided Supabase access is available.
  - Dependencies: (02D), (02E), (03C), (04B)
  - User Action: User must provide or confirm Supabase access, local backend env values, SQL editor/CLI migration application, and storage bucket creation if missing.
  - Agent Work: If user setup is available, run/confirm manual database and storage checks and then run the optional backend connection command. If setup is missing, report `BLOCKED_BY_USER_ACTION` with a safe reason.
  - Output: Manual database/storage verification status and optional live connection check result.
  - Acceptance: All 8 tables exist, configured storage bucket exists, and `check_supabase_connection()` reports database/storage availability, or the task is explicitly blocked by missing user setup.
  - Validation: Supabase SQL editor/CLI confirmation and optional backend connection command.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if Supabase project access, real local env values, migration application, or storage bucket setup is missing.
  - Files: `backend/app/db/migrations/001_initial_schema.sql`, local `.env` for user-managed secrets, execution report

- [ ] (04D): Verify scope, secret safety, and reviewer checklist items
  - Source of Truth: `docs/plans/Plan_2.md` > `## 4. Out of Scope`; `docs/plans/Plan_2.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_2.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_2.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 3. Authentication Policy`
  - Source Requirements:
    - `SUPABASE_SERVICE_ROLE_KEY` appears only in backend files and examples.
    - No frontend file references Supabase service-role secrets.
    - No Auth/JWT schema or logic is added.
    - Confirm every table includes `user_id` where required.
    - Confirm chunk rows cascade when a document is deleted.
    - Confirm agent steps cascade when an agent run is deleted.
  - Details: Run repository searches and schema inspections that prove Plan 2 stayed within scope and preserved security boundaries.
  - Dependencies: Batch02, Batch03
  - User Action: None.
  - Agent Work: Search frontend and repository for secret exposure/out-of-scope logic, inspect migration for required `user_id` fields and cascade rules, and record results.
  - Output: Scope and safety verification summary.
  - Acceptance: No frontend private-key exposure, no Auth/JWT/multi-user additions, and schema reviewer checks pass.
  - Validation: Targeted `rg` searches and migration inspection recorded in the execution report.
  - Blocked Condition: None.
  - Files: Entire repository for inspection; execution report

- [ ] (04E): Produce execution report and update progress tracker
  - Source of Truth: `docs/plans/Plan_2.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_2.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Report files created.
    - Report files modified.
    - Report commands run.
    - Report test results.
    - Report known issues.
    - Report what was intentionally not implemented because it is out of scope.
    - Include whether the SQL migration was applied manually, by CLI, or only added to the repository.
  - Details: Record the final implementation status for reviewer handoff without fake success.
  - Dependencies: (04A), (04B), (04C), (04D)
  - User Action: None unless manual setup remains pending.
  - Agent Work: Write or provide the execution report with all required fields, mark task IDs complete/partial/blocked accurately, and keep this progress tracker synchronized if the execution workflow requires file updates.
  - Output: Complete execution report and synchronized progress tracker.
  - Acceptance: Report includes all required fields and accurately reflects passing, failing, or blocked validations.
  - Validation: Manual review of report completeness against Plan 2 report requirements.
  - Blocked Condition: None for reporting; report may include `BLOCKED_BY_USER_ACTION` for unresolved manual Supabase setup.
  - Files: `docs/tasks/task_2.md`, execution report location chosen by the future Execution Agent

### Files or Modules Likely Created or Updated

- `backend/tests/test_supabase_service.py`
- `backend/tests/test_health.py` only if health behavior changes
- `docs/tasks/task_2.md`
- Execution report chosen by the future Execution Agent

### Required Outputs / Artifacts

- Supabase service unit test results.
- Existing health validation result if impacted.
- Manual Supabase schema application status.
- Manual storage bucket verification status.
- Optional live connection helper output.
- Scope and secret safety verification summary.
- Execution report.

### Acceptance Criteria

- `pytest tests/test_supabase_service.py -v` passes.
- Existing basic health behavior still works without Supabase credentials.
- Migration creates all 8 required tables when applied.
- Required indexes exist after migration.
- Configured storage bucket exists or setup is clearly blocked.
- No frontend file references Supabase service-role secrets.
- No Auth/JWT schema or logic is added.
- Required commands and results are reported honestly.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_supabase_service.py -v`
- Run impacted existing backend tests, especially health tests if health behavior changed.
- Open Supabase SQL editor or CLI and apply `backend/app/db/migrations/001_initial_schema.sql`.
- Confirm all 8 tables exist.
- Confirm configured Supabase Storage bucket exists.
- Optional after user setup: `python -c "from app.services.supabase_service import check_supabase_connection; print(check_supabase_connection())"`
- Search frontend files for `SUPABASE_SERVICE_ROLE_KEY` and related backend-only secret names.
- Inspect migration for required `user_id` fields, chunk cascade, and agent step cascade.

### Explicit Non-Goals

- Do not claim live Supabase validation passed when credentials, migration, or bucket setup were unavailable.
- Do not create external secrets or print secret values.
- Do not implement upload, parsing, chunking, embeddings, Qdrant, frontend pages, Auth/JWT, or multi-user account logic.

## Optional Future Tracks

- Document upload endpoints, storage uploads, parsing, chunking, embeddings, Qdrant indexing, GraphRAG extraction/retrieval, chat APIs, LangGraph agents, and frontend pages are future tracks from later plans.
- This track is not part of the mandatory Plan 2 batch chain.
- If `GET /api/health?include_dependencies=true` is not implemented in Plan 2, it may remain a future optional enhancement because Plan 2 requires only the internal `check_supabase_connection()` helper.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Manual live Supabase validation in Batch04 depends on user-provided project access, local secrets, applied migration, and storage bucket setup.

## Global Verification Checklist

- [ ] `backend/requirements.txt` includes the Supabase client dependency.
- [ ] `backend/.env.example` includes `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET` placeholders only.
- [ ] `backend/app/core/config.py` exposes Supabase settings safely.
- [ ] `backend/app/services/__init__.py` exists.
- [ ] `backend/app/db/__init__.py` exists.
- [ ] `backend/app/db/migrations/001_initial_schema.sql` exists.
- [ ] Migration creates `documents`.
- [ ] Migration creates `document_chunks`.
- [ ] Migration creates `document_entities`.
- [ ] Migration creates `document_relationships`.
- [ ] Migration creates `chat_sessions`.
- [ ] Migration creates `chat_messages`.
- [ ] Migration creates `agent_runs`.
- [ ] Migration creates `agent_steps`.
- [ ] Required indexes exist, including the unique `(document_id, chunk_index)` index.
- [ ] Chunk rows cascade when a document is deleted.
- [ ] Agent steps cascade when an agent run is deleted.
- [ ] Every table includes `user_id` where required by the plan.
- [ ] `backend/app/services/supabase_service.py` provides `get_supabase_client()`.
- [x] `backend/app/services/supabase_service.py` provides `check_supabase_connection()`.
- [x] Missing Supabase config produces clear safe backend errors.
- [ ] Missing storage bucket is reported as setup failure.
- [x] Basic health works without Supabase credentials.
- [x] `pytest tests/test_supabase_service.py -v` passes or failure is reported honestly.
- [ ] Manual migration application status is reported.
- [ ] Manual storage bucket status is reported.
- [ ] `SUPABASE_SERVICE_ROLE_KEY` is not referenced in frontend files.
- [ ] No frontend Supabase service-role client is created.
- [ ] No Auth/JWT schema or logic was added.
- [ ] No document upload, parsing, chunking, embeddings, Qdrant, or frontend pages were added.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.
- [x] Required commands and results are reported.

## Progress Tracker

### Batches

- [x] Batch01 - Backend Supabase Configuration
- [x] Batch02 - Database Schema Migration and Storage Assumptions
- [x] Batch03 - Backend Supabase Service and Optional Dependency Health
- [ ] Batch04 - Validation, Manual Setup Checks, and Handoff

### Task IDs

#### Batch01

- [x] (01A): Add Supabase backend dependency
- [x] (01B): Add backend-only Supabase environment placeholders
- [x] (01C): Extend backend settings for Supabase variables
- [x] (01D): Add services and database package markers

#### Batch02

- [x] (02A): Create document metadata and chunk tables
- [x] (02B): Create GraphRAG entity and relationship tables
- [x] (02C): Create chat and agent log tables
- [x] (02D): Add required indexes
- [x] (02E): Record storage bucket and migration application instructions

#### Batch03

- [x] (03A): Implement backend-only Supabase client singleton
- [x] (03B): Add custom Supabase connection error handling
- [x] (03C): Implement database and storage connectivity helper
- [x] (03D): Preserve basic health and optionally add dependency health flag

#### Batch04

- [x] (04A): Add mocked Supabase service tests
- [x] (04B): Run backend automated validations
- [x] (04C): Perform manual Supabase database and storage checks
- [ ] (04D): Verify scope, secret safety, and reviewer checklist items
- [ ] (04E): Produce execution report and update progress tracker

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
- reason: missing API key, missing provider project, missing manual setup, missing local runtime, missing storage bucket, unapplied migration, or other safe summary

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
