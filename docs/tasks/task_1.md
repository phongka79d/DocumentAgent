# RagDocument Phase 1 MVP Execution Tasks

## Purpose

Create an execution-ready task document for RagDocument Phase 1: a personal single-user document RAG MVP with upload, indexing, retrieval, reranking, grounded answers, and source citations.

This file is for future execution agents. It does not implement code, tests, migrations, frontend UI, backend logic, or external resources by itself.

## Authoritative Source

- Primary source: `docs/plans/Plan_1.md`
- Supporting source: `docs/plans/Master_Plan.md`
- Scope: Phase 1 only, "Minimal Useful RAG with LangGraph"

## Source Section Index

- `docs/plans/Plan_1.md` > top-level plan metadata -> Phase 1 scope, goal, approved architecture, technology stack, and excluded features.
- `docs/plans/Plan_1.md` > `## Master Plan Contract` -> Master Plan sections included and excluded from Phase 1.
- `docs/plans/Plan_1.md` > `## Target File Structure` -> expected backend, frontend, and docs layout.
- `docs/plans/Plan_1.md` > `## Batch 1: Backend Foundation` -> backend package, health route, settings, and admin token gate.
- `docs/plans/Plan_1.md` > `## Batch 2: Database and Storage Contract` -> Supabase schema and service clients.
- `docs/plans/Plan_1.md` > `## Batch 3: Upload and Document APIs` -> upload validation, document service, and document endpoints.
- `docs/plans/Plan_1.md` > `## Batch 4: Parsing and Chunking` -> parser registry and fixed token chunker.
- `docs/plans/Plan_1.md` > `## Batch 5: LangGraph Ingestion` -> ingestion state, nodes, graph, indexing, and reindexing.
- `docs/plans/Plan_1.md` > `## Batch 6: Retrieval and Chat Graph` -> retrieval, reranking, neighbor context, query graph, and chat route.
- `docs/plans/Plan_1.md` > `## Batch 7: Frontend MVP` -> React Vite app, API client, upload/list UI, chat UI, and citations.
- `docs/plans/Plan_1.md` > `## Batch 8: End-to-End Verification` -> run docs, automated verification, and manual smoke test.
- `docs/plans/Plan_1.md` > `## Phase 1 Acceptance Criteria` -> full MVP acceptance requirements.
- `docs/plans/Plan_1.md` > `## Execution Order` -> mandatory batch order and batch commit messages.
- `docs/plans/Master_Plan.md` > `## 1. Project Scope` -> MVP capabilities and single-user boundary.
- `docs/plans/Master_Plan.md` > `## 2. MVP Design Principles` -> optional admin token gate and deterministic LangGraph usage.
- `docs/plans/Master_Plan.md` > `## 6. Upload Flow` -> upload-only responsibilities and duplicate behavior.
- `docs/plans/Master_Plan.md` > `## 7. Indexing Flow` -> indexing from existing stored document rows.
- `docs/plans/Master_Plan.md` > `## 8. LangGraph Ingestion Graph` -> ingestion flow, state, node responsibilities, and failures.
- `docs/plans/Master_Plan.md` > `## 9. MVP Query Flow` -> query flow from question to sourced answer.
- `docs/plans/Master_Plan.md` > `## 10. LangGraph Query Graph` -> query state and node responsibilities.
- `docs/plans/Master_Plan.md` > `## 11. Retrieval Configuration` -> retrieval and context defaults.
- `docs/plans/Master_Plan.md` > `## 12. Optional Document Filtering in Chat` -> optional document filters and Qdrant payload filtering.
- `docs/plans/Master_Plan.md` > `## 13. Neighbor Context Expansion` -> neighbor expansion rules.
- `docs/plans/Master_Plan.md` > `## 14. Supabase Storage Design` -> bucket and storage path.
- `docs/plans/Master_Plan.md` > `## 15. Supabase Postgres Schema` -> MVP tables and indexes.
- `docs/plans/Master_Plan.md` > `## 16. Qdrant Collection and Payload` -> collection name and required payload.
- `docs/plans/Master_Plan.md` > `## 17. Chunking` -> fixed token chunking and chunker interface.
- `docs/plans/Master_Plan.md` > `## 19. Re-indexing Flow` -> reindex cleanup and rebuild order.
- `docs/plans/Master_Plan.md` > `## 20. Document Deletion Flow` -> deletion order.
- `docs/plans/Master_Plan.md` > `## 21. API Endpoints` -> required and optional MVP endpoints.
- `docs/plans/Master_Plan.md` > `## 22. Updated .env` -> required environment values and defaults.
- `docs/plans/Master_Plan.md` > `## 23. Error Handling` -> upload, ingestion, and query error behavior.
- `docs/plans/Master_Plan.md` > `## 25. Answer Prompt` -> answer grounding prompt.
- `docs/plans/Master_Plan.md` > `## 26. Source Citation Format` -> API and frontend citation format.
- `docs/plans/Master_Plan.md` > `## 28. Features Explicitly Not in MVP` -> explicit non-goals.
- `docs/plans/Master_Plan.md` > `## 29. Final MVP Checklist` -> final completion checklist.

## Approved Architecture Summary

RagDocument Phase 1 is a personal single-user RAG application. A React Vite TypeScript frontend talks to a FastAPI backend. The backend owns all secrets and external service access for Supabase Storage/Postgres, Qdrant Cloud, ShopAIKey OpenAI-compatible embedding/chat APIs, Jina Reranker, and deterministic LangGraph workflows.

Upload and indexing are separate. Upload stores the original file, computes a file hash, prevents duplicates, creates a document row, and returns the document ID. Indexing starts from the existing document row and original file in Supabase Storage, runs a LangGraph ingestion graph, parses, chunks, embeds, saves chunks, upserts vectors, and marks the document ready or failed.

Chat uses a LangGraph query graph. The graph validates the question, embeds it, retrieves Top 40 Qdrant candidates, optionally filters by document IDs, reranks Top 5 with Jina, adds neighbor chunks up to a capped context of 8 chunks, generates an answer using only retrieved context, and returns source citations.

## Global Implementation Rules

- Execute batches in order: Batch01 -> Batch02 -> Batch03 -> Batch04 -> Batch05 -> Batch06 -> Batch07 -> Batch08.
- Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` when implementing this task file task-by-task.
- Keep Phase 1 limited to the approved MVP scope.
- Keep backend-only secrets in backend configuration and environment variables.
- Do not expose Supabase service role keys, ShopAIKey keys, Qdrant keys, or Jina keys to the frontend.
- Do not introduce authentication, login, signup, OAuth, user profiles, organizations, roles, tenant isolation, relation graphs, OCR, PPTX parsing, hybrid search, autonomous agents, or multi-agent workflows.
- Keep upload separate from indexing.
- Keep LangGraph state free of large binaries, original file bytes, and temporary upload paths.
- Use `.env.example` for placeholder names only if an example env file is created. Never commit real `.env` values.
- Report tasks that require external accounts, API keys, buckets, collections, or manual setup as `BLOCKED_BY_USER_ACTION` until the user completes the setup.
- Create a small commit after each completed batch using the batch commit message from `docs/plans/Plan_1.md` > `## Execution Order`.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code.
- Use descriptive names for modules, functions, variables, components, settings, and tests.
- Keep functions, components, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow the standard conventions of React, Vite, TypeScript, FastAPI, Pydantic, LangGraph, pytest, and the existing repository layout.
- Use clear typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless explicitly required by the plan.
- Add comments only for non-obvious decisions or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Avoid adding formatters, linters, frameworks, or architecture changes outside the source plan unless already present or explicitly requested.

## Batch Map

- Batch01 - Backend Foundation: initialize FastAPI, health route, settings, and optional admin token gate.
- Batch02 - Database and Storage Contract: define Supabase SQL schema and lazy service clients.
- Batch03 - Upload and Document APIs: implement schemas, validation, hashing, document service, and document routes.
- Batch04 - Parsing and Chunking: implement parser interface, registry, and fixed token chunker.
- Batch05 - LangGraph Ingestion: implement ingestion state, nodes, graph, index, and reindex behavior.
- Batch06 - Retrieval and Chat Graph: implement retrieval, reranking, neighbor expansion, query graph, and chat route.
- Batch07 - Frontend MVP: implement React Vite app, API client, document UI, chat UI, and source display.
- Batch08 - End-to-End Verification: document local run steps, run full automated checks, and complete manual MVP smoke test.

## Mandatory Batch01 - Backend Foundation

### Goal

Create a runnable FastAPI backend foundation with package dependencies, health route, settings, and an optional admin token gate.

### Why this batch exists

All backend API, service, graph, and test work depends on a consistent package layout, application entrypoint, settings layer, and basic request security policy.

### Inputs / Dependencies

- `docs/plans/Plan_1.md` > `## Batch 1: Backend Foundation`
- `docs/plans/Plan_1.md` > `## Target File Structure`
- `docs/plans/Master_Plan.md` > `## 2. MVP Design Principles`
- `docs/plans/Master_Plan.md` > `## 22. Updated .env`

### Tasks

- [x] (01A): Initialize FastAPI backend package
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 1: Backend Foundation` > `### Task 1.1: Initialize FastAPI backend package`
  - Source Requirements:
    - Create the backend package and test scaffold.
    - Add required runtime and test dependencies.
    - Add `/api/health` returning `{"status": "ok"}`.
    - Set application title to `RagDocument API`.
    - Configure CORS from `FRONTEND_ORIGIN`.
    - Include documents and chat routers under `/api`.
  - Details: Establish the backend project, package metadata, basic app factory or app instance, health route, and first backend verification.
  - Dependencies: None
  - User Action: None
  - Agent Work: Create package files, app entrypoint, API route package files, health route, and initial config test scaffold.
  - Specific Steps:
    1. Create `backend/pyproject.toml` with the runtime dependencies listed in the source plan.
    2. Add pytest development dependencies listed in the source plan.
    3. Create the `backend/app` package and route package structure.
    4. Implement the FastAPI application in `backend/app/main.py`.
    5. Add `GET /api/health` returning `{"status": "ok"}`.
    6. Configure application title as `RagDocument API`.
    7. Add CORS configuration using `FRONTEND_ORIGIN` from settings once settings exist, or with a compatible interim structure that is completed by `(01B)`.
    8. Ensure documents and chat routers are included under `/api` when those routers are created in later batches.
    9. Add initial tests in `backend/tests/test_config.py` or adjust after settings are implemented.
    10. Run `cd backend; python -m pytest tests/test_config.py -v`.
  - Output: Backend package scaffold, FastAPI application, health route, and initial backend tests.
  - Acceptance: `/api/health` exists and returns `{"status": "ok"}`; one or more backend tests pass.
  - Validation: `cd backend; python -m pytest tests/test_config.py -v`
  - Blocked Condition: None
  - Files: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/api/__init__.py`, `backend/app/api/routes/__init__.py`, `backend/app/api/routes/health.py`, `backend/tests/conftest.py`, `backend/tests/test_config.py`

- [x] (01B): Add settings and optional admin token gate
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 1: Backend Foundation` > `### Task 1.2: Add settings and optional admin token gate`; `docs/plans/Master_Plan.md` > `## 2. MVP Design Principles` > `### 2.1. Single-User by Default`; `docs/plans/Master_Plan.md` > `## 22. Updated .env`
  - Source Requirements:
    - Implement all required settings fields from the phase plan.
    - Use defaults from Master Plan section 22 when optional for local development.
    - Empty `ADMIN_API_TOKEN` disables the gate.
    - Non-empty `ADMIN_API_TOKEN` requires matching `X-Admin-API-Token`.
  - Details: Add a typed settings layer, backend-safe error/security helpers, and tests for config loading and optional admin token behavior.
  - Dependencies: `(01A)`
  - User Action: User must provide real `.env` values before external integrations are validated.
  - Agent Work: Implement settings, security dependency, error helpers, app integration, and tests using safe placeholder values only.
  - Specific Steps:
    1. Create `backend/app/core/config.py` with a Pydantic settings class.
    2. Add fields for app env, frontend origin, admin token, Supabase, ShopAIKey, Qdrant, Jina, retrieval, chunking, upload, and generation settings.
    3. Apply local-development defaults for optional values where supported by Master Plan section 22.
    4. Create `backend/app/core/security.py` with `require_admin_token`.
    5. Ensure an empty admin token bypasses the dependency for local-only use.
    6. Ensure a non-empty admin token rejects missing or wrong `X-Admin-API-Token`.
    7. Create `backend/app/core/errors.py` for reusable safe error shapes if needed by later API work.
    8. Wire CORS in `backend/app/main.py` to `FRONTEND_ORIGIN`.
    9. Extend `backend/tests/test_config.py` for settings load and token gate behavior.
    10. Run `cd backend; python -m pytest tests/test_config.py -v`.
  - Output: Settings module, security dependency, error helper module, app config integration, and tests.
  - Acceptance: Settings load; empty admin token is accepted; wrong token is rejected when configured.
  - Validation: `cd backend; python -m pytest tests/test_config.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only if real external values are required for a validation beyond local settings tests.
  - Files: `backend/app/core/config.py`, `backend/app/core/security.py`, `backend/app/core/errors.py`, `backend/app/main.py`, `backend/tests/test_config.py`

### Files or Modules Likely Created or Updated

- `backend/pyproject.toml`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/security.py`
- `backend/app/core/errors.py`
- `backend/app/api/routes/health.py`
- `backend/tests/conftest.py`
- `backend/tests/test_config.py`

### Required Outputs / Artifacts

- Runnable backend app scaffold.
- Passing initial backend configuration tests.
- Optional admin token gate.

### Acceptance Criteria

- Health endpoint returns `{"status": "ok"}`.
- Settings include all fields listed by the source plan.
- Empty admin token allows local development.
- Non-empty admin token requires `X-Admin-API-Token`.
- No frontend code or external resource setup is introduced in this batch.

### Required Tests or Validations

- `cd backend; python -m pytest tests/test_config.py -v`

### Explicit Non-Goals

- Do not implement upload, indexing, retrieval, chat, frontend, Supabase schema, or external clients in this batch.
- Do not add full authentication.
- Do not create or commit real secrets.

## Mandatory Batch02 - Database and Storage Contract

### Goal

Define the Supabase MVP schema contract and backend client factories for Supabase, Qdrant, ShopAIKey, and Jina without making network calls in tests.

### Why this batch exists

The document, chunk, storage, embedding, vector, and reranking layers need a shared schema and safe service-client construction before API and graph implementation begins.

### Inputs / Dependencies

- Batch01 completed.
- `docs/plans/Plan_1.md` > `## Batch 2: Database and Storage Contract`
- `docs/plans/Master_Plan.md` > `## 14. Supabase Storage Design`
- `docs/plans/Master_Plan.md` > `## 15. Supabase Postgres Schema`
- `docs/plans/Master_Plan.md` > `## 16. Qdrant Collection and Payload`
- `docs/plans/Master_Plan.md` > `## 22. Updated .env`

### Tasks

- [x] (02A): Create Supabase schema document
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 2: Database and Storage Contract` > `### Task 2.1: Create Supabase schema document`; `docs/plans/Master_Plan.md` > `## 15. Supabase Postgres Schema`
  - Source Requirements:
    - Add SQL for `documents`, `document_chunks`, and optional `messages`.
    - Include all required indexes from the phase plan.
    - Exclude users, profiles, organizations, roles, conversations, and document relations.
  - Details: Create the SQL artifact the user will run manually in Supabase.
  - Dependencies: `(01A)`, `(01B)`
  - User Action: User must run `docs/database/supabase_schema.sql` in Supabase before live database validation.
  - Agent Work: Write SQL for only the MVP tables and indexes.
  - Specific Steps:
    1. Create `docs/database/supabase_schema.sql`.
    2. Add the `documents` table exactly aligned with Master Plan section 15.1.
    3. Add the `document_chunks` table exactly aligned with Master Plan section 15.2.
    4. Add the optional `messages` table exactly aligned with Master Plan section 15.3.
    5. Add the indexes required by the phase plan.
    6. Verify no user, profile, organization, role, conversation, or relation tables are present.
    7. Run `Get-Content docs/database/supabase_schema.sql`.
  - Output: Supabase schema SQL file.
  - Acceptance: SQL contains only the three MVP tables and required indexes.
  - Validation: `Get-Content docs/database/supabase_schema.sql`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for actually applying the SQL to Supabase.
  - Files: `docs/database/supabase_schema.sql`

- [x] (02B): Add external service client factories
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 2: Database and Storage Contract` > `### Task 2.2: Add service clients`; `docs/plans/Master_Plan.md` > `## 3. Technology Stack`; `docs/plans/Master_Plan.md` > `## 22. Updated .env`
  - Source Requirements:
    - Implement lazy client factories that read from `Settings`.
    - Keep service role keys and API keys backend-only.
    - Add tests that construct factories without network calls.
  - Details: Add backend service modules that centralize client construction and avoid immediate external calls during import or tests.
  - Dependencies: `(01B)`, `(02A)`
  - User Action: User must provide real Supabase, Qdrant, ShopAIKey, and Jina values before live integration validation.
  - Agent Work: Implement lazy factories and tests with monkeypatched settings.
  - Specific Steps:
    1. Create `backend/app/services/supabase_client.py`.
    2. Create `backend/app/services/qdrant_client.py`.
    3. Create `backend/app/services/shopaikey_client.py`.
    4. Create `backend/app/services/jina_client.py`.
    5. Ensure all factories read from the settings layer at construction time.
    6. Avoid client creation at module import time if it would perform network work.
    7. Add tests that monkeypatch settings with safe placeholder values.
    8. Assert factories construct clients or wrappers without contacting external services.
    9. Run `cd backend; python -m pytest tests/test_config.py -v`.
  - Output: Service client factory modules and tests.
  - Acceptance: Client factory tests pass without contacting Supabase, Qdrant, ShopAIKey, or Jina.
  - Validation: `cd backend; python -m pytest tests/test_config.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live service connection checks requiring real credentials.
  - Files: `backend/app/services/supabase_client.py`, `backend/app/services/qdrant_client.py`, `backend/app/services/shopaikey_client.py`, `backend/app/services/jina_client.py`, `backend/tests/test_config.py`

### Files or Modules Likely Created or Updated

- `docs/database/supabase_schema.sql`
- `backend/app/services/supabase_client.py`
- `backend/app/services/qdrant_client.py`
- `backend/app/services/shopaikey_client.py`
- `backend/app/services/jina_client.py`
- `backend/tests/test_config.py`

### Required Outputs / Artifacts

- Supabase schema SQL file.
- Lazy backend-only external service client factories.
- Tests proving factories do not require network calls.

### Acceptance Criteria

- SQL includes only `documents`, `document_chunks`, optional `messages`, and their indexes.
- Backend client factories use `Settings`.
- Secrets remain backend-only.
- No frontend code contains service keys.

### Required Tests or Validations

- `Get-Content docs/database/supabase_schema.sql`
- `cd backend; python -m pytest tests/test_config.py -v`

### Explicit Non-Goals

- Do not apply the SQL automatically to Supabase.
- Do not create external accounts, buckets, or Qdrant collections.
- Do not make live network calls in unit tests.

## Mandatory Batch03 - Upload and Document APIs

### Goal

Implement upload validation, hashing, document schemas, document service behavior, and all document API routes while keeping upload separate from indexing.

### Why this batch exists

The MVP needs durable document records and explicit upload/index lifecycle operations before parsing, chunking, and LangGraph ingestion can be wired in.

### Inputs / Dependencies

- Batch01 and Batch02 completed.
- `docs/plans/Plan_1.md` > `## Batch 3: Upload and Document APIs`
- `docs/plans/Master_Plan.md` > `## 6. Upload Flow`
- `docs/plans/Master_Plan.md` > `## 14. Supabase Storage Design`
- `docs/plans/Master_Plan.md` > `## 20. Document Deletion Flow`
- `docs/plans/Master_Plan.md` > `## 21. API Endpoints`
- `docs/plans/Master_Plan.md` > `## 23. Error Handling`

### Tasks

- [x] (03A): Add schemas, hashing, and upload validation
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 3: Upload and Document APIs` > `### Task 3.1: Add schemas, hashing, and validation`; `docs/plans/Master_Plan.md` > `## 6.1. Upload Validation`; `docs/plans/Master_Plan.md` > `## 21.3. Chat Request`; `docs/plans/Master_Plan.md` > `## 21.4. Chat Response`
  - Source Requirements:
    - Define document, upload, chat, and citation request/response schemas.
    - Calculate SHA-256 file hash over upload bytes.
    - Reject empty, oversized, unsupported, and obviously mismatched uploads.
    - Support PDF, DOCX, TXT, and Markdown.
  - Details: Add typed API models plus deterministic validation and hashing utilities.
  - Dependencies: `(01B)`
  - User Action: None
  - Agent Work: Implement Pydantic schemas, SHA-256 helper, upload validation, and focused tests.
  - Specific Steps:
    1. Create `backend/app/models/schemas.py`.
    2. Add `DocumentResponse`, `DocumentListResponse`, `UploadDocumentResponse`, `ChatRequest`, `ChatResponse`, and `SourceCitation`.
    3. Create `backend/app/services/hashing.py`.
    4. Implement SHA-256 hashing over file bytes.
    5. Create `backend/app/services/validation.py`.
    6. Validate file size, emptiness, supported extension, accepted MIME type when provided, and obvious extension/MIME conflicts.
    7. Add tests for deterministic hashing.
    8. Add tests for accepted and rejected upload cases.
    9. Run `cd backend; python -m pytest tests/test_hashing.py tests/test_validation.py -v`.
  - Output: API schemas, hashing service, validation service, and tests.
  - Acceptance: Hashing is deterministic; invalid uploads are rejected; supported file names are accepted.
  - Validation: `cd backend; python -m pytest tests/test_hashing.py tests/test_validation.py -v`
  - Blocked Condition: None
  - Files: `backend/app/models/schemas.py`, `backend/app/services/hashing.py`, `backend/app/services/validation.py`, `backend/tests/test_hashing.py`, `backend/tests/test_validation.py`

- [x] (03B): Implement document service
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 3: Upload and Document APIs` > `### Task 3.2: Implement document service`; `docs/plans/Master_Plan.md` > `## 6.2. Duplicate Upload Behavior`; `docs/plans/Master_Plan.md` > `## 14. Supabase Storage Design`; `docs/plans/Master_Plan.md` > `## 20. Document Deletion Flow`
  - Source Requirements:
    - Implement document listing, lookup, duplicate lookup, creation, storage upload, and deletion service functions.
    - Use storage path `documents/{document_id}/original/{file_name}`.
    - Duplicate file hashes return the existing document and do not create a second file, row, chunk set, or vector set.
  - Details: Centralize document database and storage operations behind service functions that API routes and graphs can use.
  - Dependencies: `(02B)`, `(03A)`
  - User Action: User must apply Supabase schema and configure storage bucket before live service validation.
  - Agent Work: Implement service functions with test doubles or mocks where real Supabase access is not available.
  - Specific Steps:
    1. Create `backend/app/services/documents.py`.
    2. Implement `list_documents()`.
    3. Implement `get_document(document_id)`.
    4. Implement `find_document_by_hash(file_hash)`.
    5. Implement `create_uploaded_document(file_name, mime_type, file_size, file_hash, storage_path, title)`.
    6. Implement `upload_original_file(storage_path, bytes, content_type)`.
    7. Implement `delete_document_and_file(document_id)` with Qdrant cleanup before row deletion when deletion behavior is fully wired.
    8. Enforce duplicate behavior in the service or make route orchestration call duplicate lookup before upload/create.
    9. Add or prepare API document tests using mocks.
  - Output: Document service module and document API tests updated for service behavior.
  - Acceptance: Duplicate behavior returns existing document metadata and prevents duplicate storage/database/vector work.
  - Validation: Covered by `(03C)` route tests and service-level tests if added.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live Supabase storage/database validation without configured project and bucket.
  - Files: `backend/app/services/documents.py`, `backend/tests/test_api_documents.py`

- [x] (03C): Implement document routes
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 3: Upload and Document APIs` > `### Task 3.3: Implement document routes`; `docs/plans/Master_Plan.md` > `## 21.1. Required MVP Endpoints`; `docs/plans/Master_Plan.md` > `## 21.2. Optional Endpoints`; `docs/plans/Master_Plan.md` > `## 7. Indexing Flow`; `docs/plans/Master_Plan.md` > `## 20. Document Deletion Flow`
  - Source Requirements:
    - Add upload, list, detail, index, reindex, delete, and chunk-inspection endpoints.
    - Keep upload separate from indexing.
    - Duplicate upload response must include existing `document_id`, status, and `duplicate=true`.
    - Delete route deletes Qdrant vectors before document row deletion.
  - Details: Expose document lifecycle endpoints under `/api` and keep graph calls stubbed or injected until ingestion exists in Batch05.
  - Dependencies: `(03A)`, `(03B)`
  - User Action: None for mocked route tests; external setup needed for live endpoint testing.
  - Agent Work: Implement router, wire it into `main.py`, and add tests.
  - Specific Steps:
    1. Create `backend/app/api/routes/documents.py`.
    2. Implement `POST /api/documents/upload`.
    3. Implement `GET /api/documents`.
    4. Implement `GET /api/documents/{document_id}`.
    5. Implement `POST /api/documents/{document_id}/index`.
    6. Implement `POST /api/documents/{document_id}/reindex`.
    7. Implement `DELETE /api/documents/{document_id}`.
    8. Implement `GET /api/documents/{document_id}/chunks`.
    9. Wire router into `backend/app/main.py`.
    10. Add tests for upload validation, duplicate response, index invocation shape, and deletion ordering.
    11. Run `cd backend; python -m pytest tests/test_api_documents.py -v`.
  - Output: Document route module, app integration, and document API tests.
  - Acceptance: Route tests validate upload, duplicate handling, index graph input shape, and delete cleanup ordering.
  - Validation: `cd backend; python -m pytest tests/test_api_documents.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live endpoint validation that requires Supabase, Qdrant, and credentials.
  - Files: `backend/app/api/routes/documents.py`, `backend/app/main.py`, `backend/tests/test_api_documents.py`

### Files or Modules Likely Created or Updated

- `backend/app/models/schemas.py`
- `backend/app/services/hashing.py`
- `backend/app/services/validation.py`
- `backend/app/services/documents.py`
- `backend/app/api/routes/documents.py`
- `backend/app/main.py`
- `backend/tests/test_hashing.py`
- `backend/tests/test_validation.py`
- `backend/tests/test_api_documents.py`

### Required Outputs / Artifacts

- Upload and document schemas.
- Hashing and validation services.
- Document service module.
- Document API routes and tests.

### Acceptance Criteria

- Upload and indexing are separate.
- Upload validates file size, type, emptiness, MIME compatibility, and file hash.
- Duplicate upload returns existing document metadata without duplicate persistence.
- Document routes match the required MVP endpoint set plus chunk inspection.
- Delete endpoint performs vector cleanup before document row deletion.

### Required Tests or Validations

- `cd backend; python -m pytest tests/test_hashing.py tests/test_validation.py -v`
- `cd backend; python -m pytest tests/test_api_documents.py -v`

### Explicit Non-Goals

- Do not implement parsers, chunkers, ingestion graph internals, retrieval, chat graph internals, or frontend UI in this batch.
- Do not add authentication beyond the optional admin token gate.

## Mandatory Batch04 - Parsing and Chunking

### Goal

Add document parsers and a fixed token chunker that produce normalized outputs for ingestion.

### Why this batch exists

The ingestion graph needs deterministic parser and chunker services before it can process stored documents and create vector-ready chunks.

### Inputs / Dependencies

- Batch03 completed.
- `docs/plans/Plan_1.md` > `## Batch 4: Parsing and Chunking`
- `docs/plans/Master_Plan.md` > `## 8.3. Ingestion Node Responsibilities`
- `docs/plans/Master_Plan.md` > `## 17. Chunking`

### Tasks

- [ ] (04A): Add parser interface and registry
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 4: Parsing and Chunking` > `### Task 4.1: Add parser interface and registry`; `docs/plans/Master_Plan.md` > `## 8.3. Ingestion Node Responsibilities` > `#### parse_document_node`
  - Source Requirements:
    - Normalize parser output to text, pages, and metadata.
    - Implement PDF with PyMuPDF, DOCX with python-docx, TXT with UTF-8 fallback, and Markdown as text.
    - Reject empty extracted text.
    - Registry maps supported extensions and MIME types.
  - Details: Create parser modules that hide file-type-specific extraction behind a common interface.
  - Dependencies: `(03A)`
  - User Action: None
  - Agent Work: Implement parser base, file-type parsers, registry, parse errors, and tests with in-memory content where possible.
  - Specific Steps:
    1. Create `backend/app/parsing/base.py`.
    2. Create `backend/app/parsing/pdf.py`.
    3. Create `backend/app/parsing/docx.py`.
    4. Create `backend/app/parsing/text.py`.
    5. Create `backend/app/parsing/markdown.py`.
    6. Create `backend/app/parsing/registry.py`.
    7. Normalize outputs to `text`, `pages`, and `metadata`.
    8. Reject empty extracted text with a clear parse error.
    9. Add tests for TXT, Markdown, registry mappings, and empty extraction failures.
    10. Run `cd backend; python -m pytest tests/test_parsers.py -v`.
  - Output: Parser modules, registry, and parser tests.
  - Acceptance: TXT and Markdown parser tests pass; registry maps supported file types; empty extraction raises a parse error.
  - Validation: `cd backend; python -m pytest tests/test_parsers.py -v`
  - Blocked Condition: None
  - Files: `backend/app/parsing/base.py`, `backend/app/parsing/pdf.py`, `backend/app/parsing/docx.py`, `backend/app/parsing/text.py`, `backend/app/parsing/markdown.py`, `backend/app/parsing/registry.py`, `backend/tests/test_parsers.py`

- [ ] (04B): Add fixed token chunker
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 4: Parsing and Chunking` > `### Task 4.2: Add fixed token chunker`; `docs/plans/Master_Plan.md` > `## 17. Chunking`
  - Source Requirements:
    - Implement `BaseChunker` and `FixedTokenChunker`.
    - Use default chunk size 500 tokens, overlap 150 tokens, and step 350 tokens.
    - Return chunk metadata fields required by the phase plan.
    - Empty text produces a clear chunking error.
  - Details: Create a token chunker that is deterministic and leaves room for future smart section chunking.
  - Dependencies: `(04A)`
  - User Action: None
  - Agent Work: Implement chunker and tests for sequence, overlap, metadata, and failure cases.
  - Specific Steps:
    1. Create `backend/app/chunking/token_chunker.py`.
    2. Implement `BaseChunker`.
    3. Implement `FixedTokenChunker`.
    4. Read chunk size and overlap defaults from settings or constructor defaults compatible with settings.
    5. Produce chunk index, content, content hash, token count, type, heading, section path, page start/end, and token start/end fields.
    6. Reject empty text with a clear error.
    7. Add tests for sequential indexes.
    8. Add tests verifying 150-token overlap when multiple chunks are produced.
    9. Run `cd backend; python -m pytest tests/test_chunker.py -v`.
  - Output: Fixed token chunker module and tests.
  - Acceptance: Chunk indexes are sequential; overlap is 150 tokens for multi-chunk output; empty text errors clearly.
  - Validation: `cd backend; python -m pytest tests/test_chunker.py -v`
  - Blocked Condition: None
  - Files: `backend/app/chunking/token_chunker.py`, `backend/tests/test_chunker.py`

### Files or Modules Likely Created or Updated

- `backend/app/parsing/*`
- `backend/app/chunking/token_chunker.py`
- `backend/tests/test_parsers.py`
- `backend/tests/test_chunker.py`

### Required Outputs / Artifacts

- Normalized parsers for PDF, DOCX, TXT, and Markdown.
- Parser registry.
- Fixed token chunker.
- Parser and chunker tests.

### Acceptance Criteria

- Supported file types parse into normalized output.
- Empty parse output is rejected.
- Fixed token chunking uses 500 tokens and 150 overlap by default.
- Chunk metadata includes all fields required by ingestion and citation flows.

### Required Tests or Validations

- `cd backend; python -m pytest tests/test_parsers.py -v`
- `cd backend; python -m pytest tests/test_chunker.py -v`

### Explicit Non-Goals

- Do not implement smart section chunking.
- Do not implement OCR, PPTX parsing, image extraction, or table preservation.
- Do not wire full ingestion graph behavior in this batch.

## Mandatory Batch05 - LangGraph Ingestion

### Goal

Implement the ingestion graph state, nodes, compiled graph, indexing route behavior, and reindex cleanup flow.

### Why this batch exists

Indexing is the core backend workflow that turns uploaded stored documents into chunks, embeddings, Qdrant vectors, and ready document records.

### Inputs / Dependencies

- Batch04 completed.
- `docs/plans/Plan_1.md` > `## Batch 5: LangGraph Ingestion`
- `docs/plans/Master_Plan.md` > `## 7. Indexing Flow`
- `docs/plans/Master_Plan.md` > `## 8. LangGraph Ingestion Graph`
- `docs/plans/Master_Plan.md` > `## 16. Qdrant Collection and Payload`
- `docs/plans/Master_Plan.md` > `## 19. Re-indexing Flow`
- `docs/plans/Master_Plan.md` > `## 23. Error Handling`

### Tasks

- [ ] (05A): Add ingestion state and nodes
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 5: LangGraph Ingestion` > `### Task 5.1: Add ingestion state and nodes`; `docs/plans/Master_Plan.md` > `## 8.2. IngestionState`; `docs/plans/Master_Plan.md` > `## 8.3. Ingestion Node Responsibilities`
  - Source Requirements:
    - Define `IngestionState` with fields from Master Plan section 8.2.
    - Exclude original file bytes, upload file paths, and large binary data.
    - Implement required ingestion nodes.
    - Ensure `save_chunks_node` runs before `upsert_qdrant_node`.
    - Fatal errors set `status=failed` and a clear `error_message`.
  - Details: Implement deterministic ingestion node functions that pass small identifiers and metadata through LangGraph state.
  - Dependencies: `(02B)`, `(03B)`, `(04A)`, `(04B)`
  - User Action: User must configure Supabase, ShopAIKey, and Qdrant for live end-to-end indexing.
  - Agent Work: Implement state type, nodes, service interactions, error handling, and tests with stubs/mocks.
  - Specific Steps:
    1. Create `backend/app/graphs/ingestion_state.py`.
    2. Define `IngestionState` from Master Plan section 8.2.
    3. Create `backend/app/graphs/ingestion_nodes.py`.
    4. Implement `load_document_record_node`.
    5. Implement `mark_processing_node`.
    6. Implement `parse_document_node`.
    7. Implement `chunk_document_node`.
    8. Implement `save_chunks_node`.
    9. Implement `embed_chunks_node`.
    10. Implement `upsert_qdrant_node`.
    11. Implement `mark_ready_node`.
    12. Implement `mark_failed_node`.
    13. Add tests ensuring large binary fields are not in state and fatal errors mark failed.
  - Output: Ingestion state, ingestion node module, and tests.
  - Acceptance: Nodes use small graph state, save chunks before vector upsert, and mark fatal failures clearly.
  - Validation: Covered by `cd backend; python -m pytest tests/test_ingestion_graph.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live indexing without external credentials and prepared resources.
  - Files: `backend/app/graphs/ingestion_state.py`, `backend/app/graphs/ingestion_nodes.py`, `backend/tests/test_ingestion_graph.py`

- [ ] (05B): Build ingestion graph and route integration
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 5: LangGraph Ingestion` > `### Task 5.2: Build ingestion graph`; `docs/plans/Master_Plan.md` > `## 8.1. Ingestion Graph Flow`; `docs/plans/Master_Plan.md` > `## 19. Re-indexing Flow`; `docs/plans/Master_Plan.md` > `## 23.2. Ingestion Errors`
  - Source Requirements:
    - Compile the graph in the exact required order.
    - Route fatal failures to `mark_failed`.
    - Index route invokes graph with only `{"document_id": "document-uuid"}`.
    - Reindex route deletes old Qdrant vectors and old chunks before graph invocation.
    - Ready path stores document processing metadata.
  - Details: Compile the LangGraph ingestion workflow and connect document index/reindex endpoints to it.
  - Dependencies: `(05A)`, `(03C)`
  - User Action: User must provide real external setup before live route validation.
  - Agent Work: Build graph module, wire routes, implement reindex cleanup orchestration, and add tests.
  - Specific Steps:
    1. Create `backend/app/graphs/ingestion_graph.py`.
    2. Add nodes in the required order from START to END.
    3. Add fatal failure routing to `mark_failed`.
    4. Wire `POST /api/documents/{document_id}/index` to invoke graph with only `document_id`.
    5. Wire `POST /api/documents/{document_id}/reindex` to delete old Qdrant vectors and chunks before graph invocation.
    6. Ensure successful indexing updates total chunks, parser metadata, chunking metadata, embedding metadata, Qdrant collection, and indexed timestamp.
    7. Add graph-order tests.
    8. Add route integration tests for index and reindex behavior.
    9. Run `cd backend; python -m pytest tests/test_ingestion_graph.py tests/test_api_documents.py -v`.
  - Output: Compiled ingestion graph and document route integration.
  - Acceptance: Graph invokes nodes in order; index route passes only document ID; failed parse marks failed; ready path stores required metadata.
  - Validation: `cd backend; python -m pytest tests/test_ingestion_graph.py tests/test_api_documents.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live indexing without Supabase, Qdrant, ShopAIKey, and stored documents.
  - Files: `backend/app/graphs/ingestion_graph.py`, `backend/app/api/routes/documents.py`, `backend/tests/test_ingestion_graph.py`, `backend/tests/test_api_documents.py`

### Files or Modules Likely Created or Updated

- `backend/app/graphs/ingestion_state.py`
- `backend/app/graphs/ingestion_nodes.py`
- `backend/app/graphs/ingestion_graph.py`
- `backend/app/api/routes/documents.py`
- `backend/tests/test_ingestion_graph.py`
- `backend/tests/test_api_documents.py`

### Required Outputs / Artifacts

- Deterministic ingestion LangGraph workflow.
- Index and reindex route integration.
- Tests for graph order, failure handling, and API invocation shape.

### Acceptance Criteria

- Graph state excludes large binary data.
- Indexing starts from an existing document row.
- `save_chunks` occurs before `upsert_qdrant`.
- Fatal failures mark documents failed with clear error messages.
- Reindex deletes old vectors and chunks before rebuilding.

### Required Tests or Validations

- `cd backend; python -m pytest tests/test_ingestion_graph.py tests/test_api_documents.py -v`

### Explicit Non-Goals

- Do not add query decomposition, relation graph expansion, agents, or complex planning loops.
- Do not implement frontend in this batch.
- Do not fabricate external credentials or resources.

## Mandatory Batch06 - Retrieval and Chat Graph

### Goal

Implement retrieval, optional document filtering, Jina reranking fallback, neighbor context expansion, the query graph, and the chat API route.

### Why this batch exists

The MVP is useful only when indexed chunks can be retrieved, grounded into an answer, and returned with source citations.

### Inputs / Dependencies

- Batch05 completed.
- `docs/plans/Plan_1.md` > `## Batch 6: Retrieval and Chat Graph`
- `docs/plans/Master_Plan.md` > `## 9. MVP Query Flow`
- `docs/plans/Master_Plan.md` > `## 10. LangGraph Query Graph`
- `docs/plans/Master_Plan.md` > `## 11. Retrieval Configuration`
- `docs/plans/Master_Plan.md` > `## 12. Optional Document Filtering in Chat`
- `docs/plans/Master_Plan.md` > `## 13. Neighbor Context Expansion`
- `docs/plans/Master_Plan.md` > `## 21.3. Chat Request`
- `docs/plans/Master_Plan.md` > `## 21.4. Chat Response`
- `docs/plans/Master_Plan.md` > `## 25. Answer Prompt`
- `docs/plans/Master_Plan.md` > `## 26. Source Citation Format`

### Tasks

- [ ] (06A): Add retrieval service
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 6: Retrieval and Chat Graph` > `### Task 6.1: Add retrieval service`; `docs/plans/Master_Plan.md` > `## 11. Retrieval Configuration`; `docs/plans/Master_Plan.md` > `## 12. Optional Document Filtering in Chat`; `docs/plans/Master_Plan.md` > `## 13. Neighbor Context Expansion`
  - Source Requirements:
    - Qdrant retrieval uses `RETRIEVAL_SEMANTIC_TOP_K` with default 40.
    - Missing or empty `document_ids` searches all ready documents.
    - Provided `document_ids` apply a Qdrant payload filter.
    - Jina failure falls back to Qdrant score sorting.
    - Neighbor expansion keeps reranked chunks, adds previous/next chunks, deduplicates, caps context, and prefers reranked chunks.
  - Details: Implement chunk lookup and retrieval orchestration functions used by query graph nodes.
  - Dependencies: `(02B)`, `(05B)`
  - User Action: User must configure Qdrant, ShopAIKey, Jina, and indexed documents for live retrieval.
  - Agent Work: Implement retrieval and chunk service functions with tests using mocks.
  - Specific Steps:
    1. Create `backend/app/services/chunks.py`.
    2. Create `backend/app/services/retrieval.py`.
    3. Implement Qdrant semantic retrieval with default top K of 40.
    4. Implement optional document ID filtering.
    5. Implement Jina reranking to final top K of 5.
    6. Implement fallback to Qdrant score sorting when Jina fails and reranking is enabled.
    7. Implement previous/next neighbor fetching by document ID and chunk index.
    8. Deduplicate context chunks by chunk ID.
    9. Cap context at default max candidates of 8.
    10. Add tests for filters, fallback, caps, and deduplication.
    11. Run `cd backend; python -m pytest tests/test_query_graph.py -v`.
  - Output: Chunk and retrieval service modules with query graph tests.
  - Acceptance: Filters pass to Qdrant; Jina failure falls back; neighbor expansion caps and deduplicates context.
  - Validation: `cd backend; python -m pytest tests/test_query_graph.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live retrieval without configured external services and indexed data.
  - Files: `backend/app/services/chunks.py`, `backend/app/services/retrieval.py`, `backend/tests/test_query_graph.py`

- [ ] (06B): Add query state, nodes, and graph
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 6: Retrieval and Chat Graph` > `### Task 6.2: Add query state, nodes, and graph`; `docs/plans/Master_Plan.md` > `## 10.2. QueryState`; `docs/plans/Master_Plan.md` > `## 10.3. Query Node Responsibilities`; `docs/plans/Master_Plan.md` > `## 25. Answer Prompt`; `docs/plans/Master_Plan.md` > `## 26. Source Citation Format`
  - Source Requirements:
    - Define `QueryState` with fields from Master Plan section 10.2.
    - Implement prepare, retrieve, rerank, neighbor expansion, answer generation, and optional message save nodes.
    - Use the exact answer grounding system prompt from the plan.
    - Return source citations with required fields.
    - Message saving failure does not fail chat response.
  - Details: Build the deterministic query graph used by the chat endpoint.
  - Dependencies: `(06A)`, `(03A)`
  - User Action: User must configure ShopAIKey for live answer generation.
  - Agent Work: Implement query state, nodes, compiled graph, and tests.
  - Specific Steps:
    1. Create `backend/app/graphs/query_state.py`.
    2. Create `backend/app/graphs/query_nodes.py`.
    3. Create `backend/app/graphs/query_graph.py`.
    4. Implement `prepare_query_node`.
    5. Implement `retrieve_qdrant_node`.
    6. Implement `jina_rerank_node`.
    7. Implement `expand_neighbor_context_node`.
    8. Implement `generate_answer_node` using only retrieved context and the exact system prompt.
    9. Implement `save_message_optional_node`.
    10. Ensure empty questions return validation errors.
    11. Ensure no retrieved chunks returns `No relevant information found in indexed documents.`
    12. Ensure sources use the required citation fields.
    13. Run `cd backend; python -m pytest tests/test_query_graph.py -v`.
  - Output: Query state, nodes, compiled graph, and tests.
  - Acceptance: Query graph validates input, uses only retrieved context, returns grounded answers and sources, and ignores message-save failures.
  - Validation: `cd backend; python -m pytest tests/test_query_graph.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live answer generation without credentials or indexed data.
  - Files: `backend/app/graphs/query_state.py`, `backend/app/graphs/query_nodes.py`, `backend/app/graphs/query_graph.py`, `backend/tests/test_query_graph.py`

- [ ] (06C): Add chat route
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 6: Retrieval and Chat Graph` > `### Task 6.3: Add chat route`; `docs/plans/Master_Plan.md` > `## 21.1. Required MVP Endpoints`; `docs/plans/Master_Plan.md` > `## 21.3. Chat Request`; `docs/plans/Master_Plan.md` > `## 21.4. Chat Response`
  - Source Requirements:
    - Add `POST /api/chat`.
    - Accept `question`, optional `document_ids`, and `save_message`.
    - Default `save_message` to false.
    - Return answer and sources.
  - Details: Expose the query graph through a FastAPI route and schema-backed response.
  - Dependencies: `(06B)`
  - User Action: None for mocked route tests; external setup needed for live chat.
  - Agent Work: Create chat router, wire into app, and add API tests.
  - Specific Steps:
    1. Create `backend/app/api/routes/chat.py`.
    2. Implement `POST /api/chat`.
    3. Validate request using `ChatRequest`.
    4. Invoke query graph.
    5. Return `ChatResponse`.
    6. Wire router into `backend/app/main.py`.
    7. Add tests for graph invocation, optional document IDs, default `save_message=false`, and response shape.
    8. Run `cd backend; python -m pytest tests/test_api_chat.py tests/test_query_graph.py -v`.
  - Output: Chat API route, app integration, and chat API tests.
  - Acceptance: Chat route invokes query graph and returns answer plus sources.
  - Validation: `cd backend; python -m pytest tests/test_api_chat.py tests/test_query_graph.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live chat without configured external services and indexed data.
  - Files: `backend/app/api/routes/chat.py`, `backend/app/main.py`, `backend/tests/test_api_chat.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/chunks.py`
- `backend/app/services/retrieval.py`
- `backend/app/graphs/query_state.py`
- `backend/app/graphs/query_nodes.py`
- `backend/app/graphs/query_graph.py`
- `backend/app/api/routes/chat.py`
- `backend/app/main.py`
- `backend/tests/test_query_graph.py`
- `backend/tests/test_api_chat.py`

### Required Outputs / Artifacts

- Retrieval and neighbor context services.
- Query LangGraph workflow.
- Chat API route.
- Tests for retrieval, graph behavior, and chat route response shape.

### Acceptance Criteria

- Chat endpoint supports optional document filters.
- Qdrant retrieves Top 40 candidates by default.
- Jina reranks Top 5 by default.
- Jina failure falls back to Qdrant scores.
- Neighbor expansion caps context at 8 by default.
- Generated answers use only retrieved context.
- Source citations include all required fields.

### Required Tests or Validations

- `cd backend; python -m pytest tests/test_query_graph.py -v`
- `cd backend; python -m pytest tests/test_api_chat.py tests/test_query_graph.py -v`

### Explicit Non-Goals

- Do not add query classification, query decomposition, relation graph expansion, grounding verification, or autonomous agent behavior.
- Do not make message history mandatory.

## Mandatory Batch07 - Frontend MVP

### Goal

Create the React Vite TypeScript frontend with API client, upload and document management UI, chat UI, and source citation display.

### Why this batch exists

The MVP needs a usable browser interface for the full upload, index, chat, cite, and delete workflow.

### Inputs / Dependencies

- Batch06 completed.
- `docs/plans/Plan_1.md` > `## Batch 7: Frontend MVP`
- `docs/plans/Master_Plan.md` > `## 4. High-Level Architecture`
- `docs/plans/Master_Plan.md` > `## 21. API Endpoints`
- `docs/plans/Master_Plan.md` > `## 26. Source Citation Format`

### Tasks

- [ ] (07A): Initialize React Vite frontend
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 7: Frontend MVP` > `### Task 7.1: Initialize React Vite frontend`; `docs/plans/Master_Plan.md` > `## 3. Technology Stack`
  - Source Requirements:
    - Use React with TypeScript.
    - Set API base URL from `VITE_API_BASE_URL`.
    - Keep secrets out of frontend files.
    - Vite production build must complete.
  - Details: Create the frontend package and base app shell.
  - Dependencies: `(06C)`
  - User Action: User may provide `VITE_API_BASE_URL` for local/browser runtime configuration.
  - Agent Work: Create Vite/React/TypeScript project files and minimal app structure.
  - Specific Steps:
    1. Create `frontend/package.json`.
    2. Create `frontend/index.html`.
    3. Create `frontend/vite.config.ts`.
    4. Create `frontend/tsconfig.json`.
    5. Create `frontend/src/main.tsx`.
    6. Create `frontend/src/App.tsx`.
    7. Create `frontend/src/styles.css`.
    8. Ensure frontend API base URL is read from `VITE_API_BASE_URL`.
    9. Scan frontend code to ensure no backend-only secret names or values are embedded.
    10. Run `cd frontend; npm install`.
    11. Run `cd frontend; npm run build`.
  - Output: React Vite TypeScript frontend scaffold.
  - Acceptance: Vite build completes and frontend source contains no backend service secrets.
  - Validation: `cd frontend; npm install`; `cd frontend; npm run build`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only if package installation cannot access npm or the user must provide environment configuration for live API testing.
  - Files: `frontend/package.json`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`

- [ ] (07B): Add frontend API client and types
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 7: Frontend MVP` > `### Task 7.2: Add API client and types`; `docs/plans/Master_Plan.md` > `## 21. API Endpoints`
  - Source Requirements:
    - Implement functions for upload, list, detail, index, reindex, delete, and chat.
    - Include `X-Admin-API-Token` only when configured by the user in the browser session.
  - Details: Add typed request/response shapes and fetch helpers that target the backend API.
  - Dependencies: `(07A)`, `(03C)`, `(06C)`
  - User Action: User may configure an admin token in the browser session if backend requires it.
  - Agent Work: Implement frontend API types and client methods.
  - Specific Steps:
    1. Create `frontend/src/api/types.ts`.
    2. Mirror backend response types needed by the UI.
    3. Create `frontend/src/api/client.ts`.
    4. Implement `uploadDocument(file)`.
    5. Implement `listDocuments()`.
    6. Implement `getDocument(documentId)`.
    7. Implement `indexDocument(documentId)`.
    8. Implement `reindexDocument(documentId)`.
    9. Implement `deleteDocument(documentId)`.
    10. Implement `sendChatMessage(request)`.
    11. Add optional admin token header only when the user configured it in browser state/session.
  - Output: Typed frontend API client.
  - Acceptance: API client exposes all functions required by UI tasks and avoids hardcoded secrets.
  - Validation: Covered by `cd frontend; npm run build`
  - Blocked Condition: None
  - Files: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`

- [ ] (07C): Build upload and document list UI
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 7: Frontend MVP` > `### Task 7.3: Build upload and document list UI`; `docs/plans/Master_Plan.md` > `## 6. Upload Flow`; `docs/plans/Master_Plan.md` > `## 21.1. Required MVP Endpoints`
  - Source Requirements:
    - Show upload control for PDF, DOCX, TXT, and Markdown.
    - Show document rows with file name, status, total chunks, created time, indexed time, and error message when failed.
    - Add Index, Re-index, Delete, and Refresh actions.
    - Empty document list renders without crashing.
  - Details: Build the document management UI around the API client.
  - Dependencies: `(07B)`
  - User Action: User must run backend for live UI actions.
  - Agent Work: Implement components, app state wiring, loading/error states, and styling.
  - Specific Steps:
    1. Create `frontend/src/components/UploadPanel.tsx`.
    2. Create `frontend/src/components/DocumentList.tsx`.
    3. Wire upload and refresh behavior in `frontend/src/App.tsx`.
    4. Add actions for index, reindex, delete, and refresh.
    5. Render failed document error messages.
    6. Add a stable empty state.
    7. Update `frontend/src/styles.css`.
    8. Run `cd frontend; npm run build`.
  - Output: Upload panel, document list component, app wiring, and styles.
  - Acceptance: Build passes and document list renders empty state without crashing.
  - Validation: `cd frontend; npm run build`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live UI validation if backend and external services are not running/configured.
  - Files: `frontend/src/components/UploadPanel.tsx`, `frontend/src/components/DocumentList.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`

- [ ] (07D): Build chat and sources UI
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 7: Frontend MVP` > `### Task 7.4: Build chat and sources UI`; `docs/plans/Master_Plan.md` > `## 21.3. Chat Request`; `docs/plans/Master_Plan.md` > `## 21.4. Chat Response`; `docs/plans/Master_Plan.md` > `## 26. Source Citation Format`
  - Source Requirements:
    - Allow question entry.
    - Allow optional selected documents.
    - Show answer text.
    - Show sources as `Source 1: report.pdf, chunk 12, pages 3-4`.
    - If page numbers are unavailable, show `Source 1: report.pdf, chunk 12`.
    - Answer and citation components render from mock data.
  - Details: Build the chat experience and citation display using typed API responses.
  - Dependencies: `(07B)`, `(07C)`
  - User Action: User must run backend and have indexed documents for live chat.
  - Agent Work: Implement chat panel, source list, selected document filtering, states, and styling.
  - Specific Steps:
    1. Create `frontend/src/components/ChatPanel.tsx`.
    2. Create `frontend/src/components/SourceList.tsx`.
    3. Wire chat request state and selected documents in `frontend/src/App.tsx`.
    4. Render answer text.
    5. Render citations with page numbers when available.
    6. Render citations without page numbers when unavailable.
    7. Update `frontend/src/styles.css`.
    8. Add mock-data render coverage if the project test setup supports it, or manually verify through component state.
    9. Run `cd frontend; npm run build`.
  - Output: Chat panel, source list, app wiring, and styles.
  - Acceptance: Build passes and answer/citation components render from mock data.
  - Validation: `cd frontend; npm run build`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live chat validation without backend and indexed data.
  - Files: `frontend/src/components/ChatPanel.tsx`, `frontend/src/components/SourceList.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`

### Files or Modules Likely Created or Updated

- `frontend/package.json`
- `frontend/index.html`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api/types.ts`
- `frontend/src/api/client.ts`
- `frontend/src/components/UploadPanel.tsx`
- `frontend/src/components/DocumentList.tsx`
- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/components/SourceList.tsx`
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- React Vite TypeScript frontend.
- Typed API client.
- Upload and document list UI.
- Chat and source citation UI.
- Passing production build.

### Acceptance Criteria

- Frontend can drive upload, index, reindex, delete, refresh, and chat operations.
- UI supports optional document selection for chat.
- Source citations display in the approved format.
- No backend-only secrets are exposed in frontend code.

### Required Tests or Validations

- `cd frontend; npm install`
- `cd frontend; npm run build`

### Explicit Non-Goals

- Do not implement marketing pages.
- Do not add Supabase, Qdrant, ShopAIKey, or Jina clients directly to the frontend.
- Do not add authentication UI beyond optional user-provided admin token handling if required by the backend.

## Mandatory Batch08 - End-to-End Verification

### Goal

Document local run steps, run full automated checks, and verify the complete MVP browser flow.

### Why this batch exists

The implementation is not complete until a future execution agent proves backend tests, frontend build, and the upload/index/chat/cite/delete flow all work or reports user-blocked external setup clearly.

### Inputs / Dependencies

- Batch07 completed.
- `docs/plans/Plan_1.md` > `## Batch 8: End-to-End Verification`
- `docs/plans/Plan_1.md` > `## Phase 1 Acceptance Criteria`
- `docs/plans/Master_Plan.md` > `## 29. Final MVP Checklist`

### Tasks

- [ ] (08A): Add local run documentation
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 8: End-to-End Verification` > `### Task 8.1: Add local run documentation`; `docs/plans/Master_Plan.md` > `## 22. Updated .env`
  - Source Requirements:
    - Document backend venv, install, and uvicorn commands.
    - Document frontend install and dev server commands.
    - Document required external setup for Supabase SQL, Supabase Storage bucket, Qdrant collection, and backend environment variables.
  - Details: Create operator-facing local setup instructions without including real secrets.
  - Dependencies: `(07D)`
  - User Action: User must complete external setup described in the README for live E2E validation.
  - Agent Work: Write backend README and adjust plan only if implementation discoveries change commands or paths.
  - Specific Steps:
    1. Create `backend/README.md`.
    2. Document backend virtual environment setup.
    3. Document backend install command `pip install -e ".[dev]"`.
    4. Document backend run command `uvicorn app.main:app --reload --port 8000`.
    5. Document frontend install and dev command.
    6. Document running `docs/database/supabase_schema.sql` in Supabase.
    7. Document creating the `documents` Supabase Storage bucket.
    8. Document creating Qdrant collection `document_chunks_v1` with the ShopAIKey embedding dimension.
    9. Document setting backend environment variables from Master Plan section 22 without real secret values.
    10. Modify `docs/plans/Plan_1.md` only if implementation discoveries require command/path corrections.
  - Output: Local run documentation.
  - Acceptance: README documents backend, frontend, and external setup steps safely.
  - Validation: Manual review of `backend/README.md`
  - Blocked Condition: None for documentation; live setup remains `BLOCKED_BY_USER_ACTION` until user completes it.
  - Files: `backend/README.md`, `docs/plans/Plan_1.md` only if required

- [ ] (08B): Run full automated verification
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 8: End-to-End Verification` > `### Task 8.2: Run full automated verification`
  - Source Requirements:
    - Run all backend tests.
    - Run frontend production build.
    - Backend tests and frontend build must pass.
  - Details: Execute full automated verification after implementation.
  - Dependencies: `(08A)`
  - User Action: None unless dependencies or environment setup are missing.
  - Agent Work: Run test/build commands, capture results, and fix implementation issues within approved scope.
  - Specific Steps:
    1. Run `cd backend; python -m pytest -v`.
    2. Fix failing tests that are within Phase 1 implementation scope.
    3. Run `cd frontend; npm run build`.
    4. Fix build failures that are within Phase 1 implementation scope.
    5. Record command results in the execution report.
  - Output: Verified backend tests and frontend build.
  - Acceptance: All backend tests pass and frontend production build passes.
  - Validation: `cd backend; python -m pytest -v`; `cd frontend; npm run build`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if required local environment values or dependency installation steps cannot be completed by the agent.
  - Files: No new files expected

- [ ] (08C): Run manual MVP smoke test
  - Source of Truth: `docs/plans/Plan_1.md` > `## Batch 8: End-to-End Verification` > `### Task 8.3: Run manual MVP smoke test`; `docs/plans/Plan_1.md` > `## Phase 1 Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 29. Final MVP Checklist`
  - Source Requirements:
    - Start backend on port 8000.
    - Start frontend on host `127.0.0.1` port 5173.
    - Verify upload, duplicate upload, index, ready status, chat with source citation, delete, and disappearance from list.
    - Complete the app flow for a TXT document.
  - Details: Run the final manual end-to-end browser flow against configured local services.
  - Dependencies: `(08B)`
  - User Action: User must provide completed external setup, valid `.env`, Supabase bucket/schema, Qdrant collection, and API keys before live E2E smoke test.
  - Agent Work: Start backend/frontend, use the browser to perform the smoke test, and record safe results.
  - Specific Steps:
    1. Start backend with `cd backend; uvicorn app.main:app --reload --port 8000`.
    2. Start frontend with `cd frontend; npm run dev -- --host 127.0.0.1 --port 5173`.
    3. Open `http://127.0.0.1:5173`.
    4. Upload a TXT file.
    5. Upload the same TXT file again and confirm duplicate response uses existing document.
    6. Index the uploaded document.
    7. Confirm document status becomes ready.
    8. Ask a question answerable by the TXT document.
    9. Confirm answer includes at least one source citation.
    10. Delete the document.
    11. Confirm the document no longer appears in the list.
    12. Record results without printing secrets.
  - Output: Manual MVP smoke-test result.
  - Acceptance: The app completes upload, duplicate detection, index, chat, cite, and delete flow for a TXT document.
  - Validation: Browser smoke test at `http://127.0.0.1:5173`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if external services, real credentials, Supabase schema/bucket, or Qdrant collection are missing.
  - Files: No new files expected

### Files or Modules Likely Created or Updated

- `backend/README.md`
- `docs/plans/Plan_1.md` only if implementation discoveries change commands or paths

### Required Outputs / Artifacts

- Local run documentation.
- Full backend test results.
- Frontend build result.
- Manual MVP smoke-test result or explicit blocked-by-user report.

### Acceptance Criteria

- Backend README explains local setup and required external setup.
- Backend tests pass.
- Frontend build passes.
- Manual TXT document flow passes, or missing user-controlled setup is reported as blocked.

### Required Tests or Validations

- `cd backend; python -m pytest -v`
- `cd frontend; npm run build`
- Browser smoke test at `http://127.0.0.1:5173`

### Explicit Non-Goals

- Do not commit real secrets.
- Do not fabricate API keys or external resources.
- Do not expand MVP scope during verification.

## Optional Future Tracks

These tracks are not part of the mandatory MVP batch chain.

- Phase 2 usability and retrieval quality from `docs/plans/Master_Plan.md` > `## 27. Project Phases` > `### Phase 2: Usability and Retrieval Quality`: source viewer panel, message history if useful, smart section chunking, header scoring, table preservation, neighbor tuning, and optional HTML parsing.
- Phase 3 advanced RAG from `docs/plans/Master_Plan.md` > `## 27. Project Phases` > `### Phase 3: Advanced RAG`: query decomposition, relation extraction, relation graph expansion, grounding verification, hybrid search, OCR, PPTX support, image/chart captioning, summaries, multi-vector chunks, evaluation datasets, and retrieval metrics.
- Duplicate logical document copies from `docs/plans/Master_Plan.md` > `## 6.2. Duplicate Upload Behavior`: optional future behavior only, not implemented in Phase 1.
- Safer staged reindexing from `docs/plans/Master_Plan.md` > `## 19. Re-indexing Flow`: optional later approach, not required for MVP.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05
- Batch05 -> Batch06
- Batch06 -> Batch07
- Batch07 -> Batch08

Optional future tracks are outside the mandatory chain.

## Global Verification Checklist

- [ ] Backend package installs successfully.
- [ ] Backend config tests pass.
- [ ] Supabase schema contains only MVP tables and indexes.
- [ ] Upload validation and hashing tests pass.
- [ ] Document API tests pass.
- [ ] Parser tests pass.
- [ ] Chunker tests pass.
- [ ] Ingestion graph tests pass.
- [ ] Query graph tests pass.
- [ ] Chat API tests pass.
- [ ] Full backend test suite passes.
- [ ] Frontend package installs successfully.
- [ ] Frontend production build passes.
- [ ] Frontend code contains no backend-only secrets.
- [ ] Manual TXT document MVP smoke test passes.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.
- [ ] Excluded Phase 1 features are not introduced.

## Progress Tracker

### Batches

- [ ] Batch01 - Backend Foundation
- [ ] Batch02 - Database and Storage Contract
- [ ] Batch03 - Upload and Document APIs
- [ ] Batch04 - Parsing and Chunking
- [ ] Batch05 - LangGraph Ingestion
- [ ] Batch06 - Retrieval and Chat Graph
- [ ] Batch07 - Frontend MVP
- [ ] Batch08 - End-to-End Verification

### Task IDs

#### Batch01

- [x] (01A): Initialize FastAPI backend package
- [x] (01B): Add settings and optional admin token gate

#### Batch02

- [x] (02A): Create Supabase schema document
- [x] (02B): Add external service client factories

#### Batch03

- [x] (03A): Add schemas, hashing, and upload validation
- [x] (03B): Implement document service
- [x] (03C): Implement document routes

#### Batch04

- [ ] (04A): Add parser interface and registry
- [ ] (04B): Add fixed token chunker

#### Batch05

- [ ] (05A): Add ingestion state and nodes
- [ ] (05B): Build ingestion graph and route integration

#### Batch06

- [ ] (06A): Add retrieval service
- [ ] (06B): Add query state, nodes, and graph
- [ ] (06C): Add chat route

#### Batch07

- [ ] (07A): Initialize React Vite frontend
- [ ] (07B): Add frontend API client and types
- [ ] (07C): Build upload and document list UI
- [ ] (07D): Build chat and sources UI

#### Batch08

- [ ] (08A): Add local run documentation
- [ ] (08B): Run full automated verification
- [ ] (08C): Run manual MVP smoke test

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
