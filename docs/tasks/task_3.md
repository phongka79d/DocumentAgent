# Plan 3 - Document Upload and Metadata Execution Tasks

## Purpose

Create a detailed execution task file for the approved document upload and metadata milestone. This task file guides a future Execution Agent to add backend-only document upload validation, Supabase Storage upload, document metadata persistence, list/detail APIs, and focused verification required by `docs/plans/Plan_3.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_3.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Conflict note: `docs/plans/Master_Plan.md` describes the broader upload pipeline as starting processing after upload, while `docs/plans/Plan_3.md` explicitly excludes parsing, chunking, processing-status updates, embeddings, Qdrant, and frontend upload UI. `docs/plans/Plan_3.md` is the scope authority for this task file, so this milestone stops at stored original files and `uploaded` document metadata.

## Source Section Index

- `docs/plans/Plan_3.md` > `## 1. Goal` -> upload success condition, storage object, `documents` row, `SINGLE_USER_ID`, and document APIs.
- `docs/plans/Plan_3.md` > `## 2. Why This Plan Exists` -> document records and original files are prerequisites for later processing.
- `docs/plans/Plan_3.md` > `## 3. Scope` -> required schemas, validation, endpoints, storage path, metadata insert, user filtering, and tests.
- `docs/plans/Plan_3.md` > `## 4. Out of Scope` -> prohibited parsing, chunks, processing status, embeddings, Qdrant, frontend, and deletion work.
- `docs/plans/Plan_3.md` > `## 5. Dependencies` -> Plan 1/2 completion and Supabase table/bucket prerequisites.
- `docs/plans/Plan_3.md` > `## 6. Required Files and Folders` -> expected backend API, schemas, service, utility, tests, and router registration files.
- `docs/plans/Plan_3.md` > `## 7. Data Model / Schema Changes` -> no table changes, insert shape, and response models.
- `docs/plans/Plan_3.md` > `## 8. API Design` -> upload, list, and detail API contracts, errors, and validation rules.
- `docs/plans/Plan_3.md` > `## 9. Implementation Steps` -> ordered implementation details.
- `docs/plans/Plan_3.md` > `## 10. Configuration and Environment Variables` -> backend-only variables and upload size setting.
- `docs/plans/Plan_3.md` > `## 11. Required Tests` -> backend tests, curl checks, manual Supabase checks, and negative checks.
- `docs/plans/Plan_3.md` > `## 12. Acceptance Criteria` -> completion conditions and forbidden out-of-scope work.
- `docs/plans/Plan_3.md` > `## 13. Failure Handling` -> invalid file, empty file, upload failure, metadata failure, missing config, and safe path behavior.
- `docs/plans/Plan_3.md` > `## 14. Agent Report Requirement` -> required execution report fields and minimum successful/negative upload test evidence.
- `docs/plans/Plan_3.md` > `## 15. Reviewer Checklist` -> review expectations and extra single-user, path, frontend, and secret checks.
- `docs/plans/Master_Plan.md` > `## 2. Tech Stack` -> FastAPI, Pydantic, Supabase Storage, and Supabase PostgreSQL are approved.
- `docs/plans/Master_Plan.md` > `## 3. Authentication Policy` -> single-user MVP and backend-only private secrets.
- `docs/plans/Master_Plan.md` > `## 4. Supported Document Types` -> PDF, DOCX, TXT, and CSV support.
- `docs/plans/Master_Plan.md` > `## 6. Data Storage Design` > `### 6.1 Supabase Storage` -> suggested storage bucket and object path.
- `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.1 Upload Document` -> upload endpoint shape.
- `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.2 List Documents` -> list endpoint shape.
- `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.3 Get Document Detail` -> detail endpoint shape.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> backend-only Supabase and `SINGLE_USER_ID` variable names.
- `docs/plans/Master_Plan.md` > `## Phase 2: Document Upload and Storage` -> upload/storage phase acceptance alignment.

## Approved Architecture Summary

The approved architecture for this plan is a backend-only FastAPI document upload and metadata layer for a single-user Document QA Agent MVP. The backend validates PDF, DOCX, TXT, and CSV uploads, reads file bytes safely, stores the original file in Supabase Storage under `documents/{SINGLE_USER_ID}/{document_id}/{safe_filename}`, and inserts a row in the existing Supabase PostgreSQL `documents` table with status `uploaded`, `chunk_count` set to `0`, and `error_message` set to `null`. Document list and detail APIs must always filter by `SINGLE_USER_ID`. The detail response returns an empty `chunks` list because parsing and chunking are outside this plan. No frontend UI, document processing, embeddings, Qdrant calls, deletion API, authentication, JWT, or multi-user behavior is part of this milestone.

## Global Implementation Rules

- Keep `docs/plans/Plan_3.md` as the source of truth for scope and validation.
- Depend on the Plan 1 FastAPI foundation and Plan 2 Supabase schema/service foundation.
- Do not create or alter database tables in this plan; use the existing `documents` table from Plan 2.
- Do not parse document content, create `document_chunks`, change status to `processing` or `ready`, generate embeddings, call Qdrant, call ShopAIKey, or implement agents.
- Do not build frontend upload UI or change frontend files unless a shared contract file already exists and is explicitly required by the implementation.
- Keep `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`, `SUPABASE_STORAGE_BUCKET`, and `SINGLE_USER_ID` backend-only.
- Use `.env.example` for placeholders only and never commit real secrets.
- Sanitize filenames before constructing Supabase Storage paths.
- Filter every document read by `user_id = SINGLE_USER_ID`.
- Return safe public error messages and keep sensitive provider details out of API responses.
- Do not claim live Supabase upload validation passed unless real local credentials and bucket setup were present and the validation command was actually run.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, settings, routes, schemas, and tests.
- Keep functions and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, Supabase Python client, and Python file-handling conventions for the files being created.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless the plan explicitly requires them.
- Add comments only where they clarify a non-obvious decision or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Do not add formatter, linter, framework, or architecture changes outside Plan 3 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Document Schemas, Upload Validation, and Configuration
- Batch02 - Supabase Storage and Document Metadata Service
- Batch03 - Document API Routes and Router Registration
- Batch04 - Tests, Manual Validation, and Handoff

## Mandatory Batch01 - Document Schemas, Upload Validation, and Configuration

### Goal

Create the backend schema, validation, and upload-size configuration foundation required before storage or API routes are implemented.

### Why this batch exists

The upload service and API routes need stable response models, supported-type validation, safe filename handling, and upload-size settings before accepting document bytes.

### Inputs / Dependencies

- `docs/plans/Plan_3.md`
- Completed Plan 1 backend foundation
- Completed Plan 2 Supabase settings and table setup
- Existing backend configuration pattern

### Tasks

- [x] (01A): Add document API response schemas
  - Source of Truth: `docs/plans/Plan_3.md` > `## 3. Scope`; `docs/plans/Plan_3.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_3.md` > `## 7. Data Model / Schema Changes`
  - Source Requirements:
    - Add document Pydantic schemas.
    - Create `DocumentUploadResponse`, `DocumentListItem`, `DocumentListResponse`, and `DocumentDetailResponse`.
    - Response models must represent upload, list, and detail contracts.
  - Details: Define typed Pydantic response models for upload success, document list items, list wrapper, and document detail with an empty `chunks` field.
  - Dependencies: Completed Plan 1 backend package layout.
  - User Action: None.
  - Agent Work: Create or update the schemas package and document schema module using the existing project style.
  - Output: Document response schemas importable by API routes and tests.
  - Acceptance: Schema classes match the API response shapes required by Plan 3.
  - Validation: Run backend schema/import tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/__init__.py`, `backend/app/schemas/documents.py`

- [x] (01B): Add supported document type and upload validation utilities
  - Source of Truth: `docs/plans/Plan_3.md` > `## 3. Scope`; `docs/plans/Plan_3.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_3.md` > `## 8. API Design`; `docs/plans/Plan_3.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## 4. Supported Document Types`
  - Source Requirements:
    - Support PDF, DOCX, TXT, and CSV only.
    - File extension must be `.pdf`, `.docx`, `.txt`, or `.csv`.
    - Content type must match the extension when provided.
    - Empty files must be rejected.
    - Filename must be sanitized before use in storage paths.
  - Details: Implement file type detection, upload byte validation, optional content-type checks, and safe filename normalization in a utility module.
  - Dependencies: Completed Plan 1 backend package layout.
  - User Action: None.
  - Agent Work: Create `SUPPORTED_DOCUMENT_TYPES`, `get_file_type(filename)`, `validate_upload_file(upload_file, max_bytes)`, and any small helper needed for safe filenames without adding parsing logic.
  - Output: Reusable upload validation utilities.
  - Acceptance: Unsupported extensions and empty files fail with clear validation errors; supported extensions can produce a file type and safe filename.
  - Validation: Run upload validation tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/utils/__init__.py`, `backend/app/utils/file_validation.py`

- [x] (01C): Add upload size configuration
  - Source of Truth: `docs/plans/Plan_3.md` > `## 8. API Design`; `docs/plans/Plan_3.md` > `## 9. Implementation Steps`; `docs/plans/Plan_3.md` > `## 10. Configuration and Environment Variables`
  - Source Requirements:
    - Add `MAX_UPLOAD_BYTES` to backend settings.
    - Use a conservative default such as `25_000_000`.
    - Return HTTP 413 for files too large if a max size is configured.
  - Details: Extend backend settings and env examples with a backend-only upload size limit that validation code can consume.
  - Dependencies: Completed Plan 2 settings pattern.
  - User Action: None.
  - Agent Work: Add typed `MAX_UPLOAD_BYTES` configuration with a safe default and placeholder/example value in backend env docs.
  - Output: Backend settings and env example support upload-size validation.
  - Acceptance: App imports without requiring a real value, and upload validation can enforce the configured maximum.
  - Validation: Run backend config tests and upload validation tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/core/config.py`, `backend/.env.example`, backend config tests if present

- [x] (01D): Confirm Plan 3 package boundaries and imports
  - Source of Truth: `docs/plans/Plan_3.md` > `## 4. Out of Scope`; `docs/plans/Plan_3.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_3.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Keep upload, validation, schemas, and service modules in backend packages.
    - Do not change frontend except shared config if truly necessary.
    - Service-role key remains backend-only.
  - Details: Ensure new modules are placed under the intended backend package structure and import cleanly without creating frontend or processing dependencies.
  - Dependencies: (01A), (01B), (01C)
  - User Action: None.
  - Agent Work: Add package markers where missing, use existing import style, and avoid frontend or processing imports.
  - Output: Backend package structure ready for document service and API routes.
  - Acceptance: New schema and utility modules can be imported in tests without side effects.
  - Validation: Run backend import/tests in Batch04 and inspect changed file list for scope.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/__init__.py`, `backend/app/utils/__init__.py`, backend package files as needed

### Files or Modules Likely Created or Updated

- `backend/app/schemas/__init__.py`
- `backend/app/schemas/documents.py`
- `backend/app/utils/__init__.py`
- `backend/app/utils/file_validation.py`
- `backend/app/core/config.py`
- `backend/.env.example`
- Existing backend config tests if the setting is covered there

### Required Outputs / Artifacts

- Document response schema module.
- Upload validation utility module.
- Backend upload-size setting and env placeholder.
- Importable backend package markers.

### Acceptance Criteria

- PDF, DOCX, TXT, and CSV are the only supported document types.
- Unsupported file types and empty files are rejected before storage upload.
- Upload size limit is configurable through backend settings.
- Filename sanitization is available before constructing storage paths.
- No frontend files or processing modules are introduced.

### Required Tests or Validations

- Backend schema import test or API test coverage in Batch04.
- Upload validation unit coverage in Batch04.
- Backend config test or direct settings validation in Batch04.
- Scope inspection confirming frontend was not changed.

### Explicit Non-Goals

- Do not parse document content.
- Do not create `document_chunks`.
- Do not generate embeddings or call Qdrant/ShopAIKey.
- Do not implement frontend upload UI.
- Do not add authentication or multi-user behavior.

## Mandatory Batch02 - Supabase Storage and Document Metadata Service

### Goal

Implement backend service behavior that stores uploaded original files in Supabase Storage and persists document metadata in the existing `documents` table.

### Why this batch exists

Document APIs need a single service layer that coordinates validation output, storage upload, metadata insert, list queries, detail lookup, and safe failure handling.

### Inputs / Dependencies

- Batch01 validation, schemas, and settings
- Completed Plan 2 Supabase service foundation
- Supabase Storage bucket named by `SUPABASE_STORAGE_BUCKET`
- Existing `documents` table from Plan 2
- User-provided local Supabase credentials for live checks only

### Tasks

- [x] (02A): Add Supabase helpers for document storage and metadata
  - Source of Truth: `docs/plans/Plan_3.md` > `## 3. Scope`; `docs/plans/Plan_3.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_3.md` > `## 9. Implementation Steps`; `docs/plans/Plan_3.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## 6. Data Storage Design` > `### 6.1 Supabase Storage`
  - Source Requirements:
    - Upload bytes to Supabase Storage using bucket `SUPABASE_STORAGE_BUCKET`.
    - Insert document rows into Supabase PostgreSQL.
    - Missing Supabase configuration must produce safe backend errors.
  - Details: Extend the existing Supabase service module with focused helpers for uploading original files and reading/writing document metadata.
  - Dependencies: Batch01, completed Plan 2 Supabase service foundation.
  - User Action: User must provide real Supabase credentials and bucket setup in local `.env` for live validation; no user action is needed for mocked tests.
  - Agent Work: Add helper functions for storage upload, document insert, list query, and detail query using the existing Supabase client/config pattern.
  - Output: Supabase service helpers used by document service.
  - Acceptance: Helpers are mockable, keep credentials backend-only, and can surface storage/query failures without leaking secrets.
  - Validation: Run mocked Supabase helper/service tests in Batch04.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live Supabase validation if real credentials, table, or bucket are missing.
  - Files: `backend/app/services/supabase_service.py`

- [x] (02B): Implement document upload orchestration service
  - Source of Truth: `docs/plans/Plan_3.md` > `## 1. Goal`; `docs/plans/Plan_3.md` > `## 3. Scope`; `docs/plans/Plan_3.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_3.md` > `## 9. Implementation Steps`; `docs/plans/Plan_3.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Generate a UUID before storage upload.
    - Store original uploads at `documents/{SINGLE_USER_ID}/{document_id}/{original_filename}`.
    - Insert a `documents` row with status `uploaded`.
    - Set `chunk_count` to `0` and `error_message` to `null`.
    - Do not pretend upload completed if metadata insert fails after storage upload succeeds.
  - Details: Create the service function that reads validated upload bytes, builds a safe storage path, uploads to storage, inserts metadata, and returns upload response data.
  - Dependencies: (01B), (01C), (02A)
  - User Action: None for implementation and mocked tests; real upload validation needs local Supabase setup.
  - Agent Work: Create `document_service.py` with upload orchestration and explicit error paths for validation, storage, and metadata failures.
  - Output: Backend document upload service.
  - Acceptance: A supported upload can produce a `document_id`, storage path, and `uploaded` metadata insert shape for `SINGLE_USER_ID`.
  - Validation: Run upload service tests with mocked Supabase helpers in Batch04.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live upload validation if Supabase credentials, storage bucket, or documents table are missing.
  - Files: `backend/app/services/document_service.py`

- [x] (02C): Implement document list and detail service operations
  - Source of Truth: `docs/plans/Plan_3.md` > `## 1. Goal`; `docs/plans/Plan_3.md` > `## 3. Scope`; `docs/plans/Plan_3.md` > `## 8. API Design`; `docs/plans/Plan_3.md` > `## 9. Implementation Steps`; `docs/plans/Plan_3.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - `GET /api/documents` must return only documents for `SINGLE_USER_ID`.
    - List documents ordered by `created_at desc`.
    - Detail lookup must include `user_id = SINGLE_USER_ID`.
    - Detail response must include empty `chunks` because chunking is out of scope.
  - Details: Add service functions for listing documents and fetching one document by ID while applying the single-user filter in every query.
  - Dependencies: (02A)
  - User Action: None for mocked tests; live validation requires existing Supabase data.
  - Agent Work: Implement list and detail service functions that map Supabase rows into the schema-ready response shapes.
  - Output: Document metadata list/detail service functions.
  - Acceptance: List and detail queries are always scoped to `SINGLE_USER_ID`; missing documents return a not-found outcome.
  - Validation: Run list/detail service and API tests in Batch04.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live validation if Supabase credentials or documents table are missing.
  - Files: `backend/app/services/document_service.py`, `backend/app/services/supabase_service.py`

- [x] (02D): Preserve Plan 3 failure and scope boundaries in service code
  - Source of Truth: `docs/plans/Plan_3.md` > `## 4. Out of Scope`; `docs/plans/Plan_3.md` > `## 13. Failure Handling`; `docs/plans/Plan_3.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Supabase Storage upload failure returns failure and does not insert a success row.
    - Metadata insert failure returns failure with a clear log entry.
    - Storage path must not include unsafe path separators from the original filename.
    - No parsing, chunking, embeddings, Qdrant, agents, or frontend changes.
  - Details: Make service failures explicit and safe, and keep upload metadata work separated from future processing responsibilities.
  - Dependencies: (02B), (02C)
  - User Action: None.
  - Agent Work: Add precise exception/error handling, logging, and tests hooks without swallowing failures or exposing secrets.
  - Output: Service behavior that fails honestly and stays in scope.
  - Acceptance: Failure tests can prove unsupported/empty/upload/insert failures do not report fake success.
  - Validation: Run negative service tests and scope checks in Batch04.
  - Blocked Condition: None for mocked validation.
  - Files: `backend/app/services/document_service.py`, `backend/app/services/supabase_service.py`, backend logging usage if needed

### Files or Modules Likely Created or Updated

- `backend/app/services/document_service.py`
- `backend/app/services/supabase_service.py`
- `backend/app/utils/file_validation.py`
- Backend logging/config modules if existing patterns require it

### Required Outputs / Artifacts

- Supabase helper functions for document storage and metadata.
- Document upload orchestration service.
- Document list and detail service functions.
- Safe failure handling for validation, storage, metadata, config, and not-found cases.

### Acceptance Criteria

- Upload service uses `SINGLE_USER_ID` for document ownership.
- Storage path follows `documents/{SINGLE_USER_ID}/{document_id}/{safe_filename}`.
- Document metadata insert uses status `uploaded`, `chunk_count` `0`, and `error_message` `null`.
- List/detail service queries include `SINGLE_USER_ID`.
- Upload and metadata failures do not produce fake success.
- Backend-only secrets remain backend-only.

### Required Tests or Validations

- Mocked upload success service test.
- Mocked unsupported type and empty file tests.
- Mocked Supabase upload failure test.
- Mocked metadata insert failure test.
- List/detail service tests verifying `SINGLE_USER_ID` filters.

### Explicit Non-Goals

- Do not apply database migrations.
- Do not create a Supabase bucket from code unless the existing project pattern already includes a safe manual check helper.
- Do not process uploaded documents after metadata insert.
- Do not create chunks, embeddings, Qdrant points, chat records, agent runs, or frontend UI.

## Mandatory Batch03 - Document API Routes and Router Registration

### Goal

Expose backend document upload, list, and detail endpoints under `/api/documents` using the service layer from Batch02.

### Why this batch exists

Plan 3 is testable through HTTP API contracts, so the backend must provide route handlers that map multipart uploads and metadata reads to the approved response and error shapes.

### Inputs / Dependencies

- Batch01 schemas and validation
- Batch02 document service functions
- Existing FastAPI app and router patterns from Plan 1/2

### Tasks

- [x] (03A): Add document upload API route
  - Source of Truth: `docs/plans/Plan_3.md` > `## 1. Goal`; `docs/plans/Plan_3.md` > `## 3. Scope`; `docs/plans/Plan_3.md` > `## 8. API Design`; `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.1 Upload Document`
  - Source Requirements:
    - Add `POST /api/documents/upload`.
    - Request body is multipart/form-data with field `file`.
    - Response contains `document_id`, `file_name`, and `status`.
    - Error responses include 400 unsupported file type, 400 empty file, 413 too large when configured, and 500 storage/metadata failures.
  - Details: Implement the upload route using FastAPI `UploadFile`, the document upload service, and the approved response schema.
  - Dependencies: Batch01, (02B), (02D)
  - User Action: None for implementation and mocked tests.
  - Agent Work: Create `backend/app/api/documents.py` with upload route and safe error mapping.
  - Output: Upload endpoint available under `/api/documents/upload`.
  - Acceptance: API test can upload supported files through `TestClient` with mocked service and receive the approved response.
  - Validation: Run upload API tests in Batch04.
  - Blocked Condition: None for mocked API tests; live curl upload may be `BLOCKED_BY_USER_ACTION` if local Supabase setup is missing.
  - Files: `backend/app/api/documents.py`

- [ ] (03B): Add document list API route
  - Source of Truth: `docs/plans/Plan_3.md` > `## 1. Goal`; `docs/plans/Plan_3.md` > `## 3. Scope`; `docs/plans/Plan_3.md` > `## 8. API Design`; `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.2 List Documents`
  - Source Requirements:
    - Add `GET /api/documents`.
    - Response body contains `documents`.
    - Metadata reads must always filter by `user_id = SINGLE_USER_ID`.
    - Metadata query failures return HTTP 500.
  - Details: Implement the list route using the document service and response schema.
  - Dependencies: (02C)
  - User Action: None for mocked API tests.
  - Agent Work: Add list route and map query failures to safe public errors.
  - Output: Document list endpoint.
  - Acceptance: API test receives a `documents` array and service tests prove single-user filtering happens below the route.
  - Validation: Run list API tests in Batch04.
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/api/documents.py`

- [ ] (03C): Add document detail API route
  - Source of Truth: `docs/plans/Plan_3.md` > `## 1. Goal`; `docs/plans/Plan_3.md` > `## 3. Scope`; `docs/plans/Plan_3.md` > `## 8. API Design`; `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.3 Get Document Detail`
  - Source Requirements:
    - Add `GET /api/documents/{document_id}`.
    - Invalid UUID returns HTTP 422.
    - Unknown document for `SINGLE_USER_ID` returns HTTP 404.
    - Response includes empty `chunks`.
  - Details: Implement a detail route with typed UUID path handling and not-found mapping.
  - Dependencies: (02C)
  - User Action: None for mocked API tests.
  - Agent Work: Add detail route, use FastAPI/Pydantic UUID validation, and return the approved detail schema.
  - Output: Document detail endpoint.
  - Acceptance: API tests cover valid detail response, random unknown UUID 404, and invalid UUID 422.
  - Validation: Run detail API tests in Batch04.
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/api/documents.py`

- [ ] (03D): Register documents router without disrupting existing APIs
  - Source of Truth: `docs/plans/Plan_3.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_3.md` > `## 9. Implementation Steps`; `docs/plans/Plan_3.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Register the documents router in `backend/app/main.py`.
    - Include the documents router under `/api/documents`.
    - Existing backend health behavior should remain intact.
  - Details: Wire the document router into the FastAPI app using the existing route organization and without changing unrelated endpoints.
  - Dependencies: (03A), (03B), (03C)
  - User Action: None.
  - Agent Work: Update app routing and imports so `/api/documents/upload`, `/api/documents`, and `/api/documents/{document_id}` are reachable.
  - Output: Main FastAPI app includes the document router.
  - Acceptance: Existing health tests still pass and document route tests can resolve the endpoints.
  - Validation: Run backend tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/main.py`, `backend/app/api/documents.py`, `backend/app/api/__init__.py` if needed

### Files or Modules Likely Created or Updated

- `backend/app/api/documents.py`
- `backend/app/main.py`
- `backend/app/api/__init__.py` if existing router exports require it
- `backend/app/schemas/documents.py`
- `backend/app/services/document_service.py`

### Required Outputs / Artifacts

- Upload route under `/api/documents/upload`.
- List route under `/api/documents`.
- Detail route under `/api/documents/{document_id}`.
- Router registration in the FastAPI app.

### Acceptance Criteria

- Supported upload requests can return `document_id`, `file_name`, and `status`.
- Unsupported and empty uploads map to HTTP 400.
- Oversized uploads map to HTTP 413 when max size is configured.
- List and detail endpoints use the approved response bodies.
- Unknown document IDs return HTTP 404.
- Invalid UUID path values return HTTP 422.
- Existing health endpoint behavior remains intact.

### Required Tests or Validations

- FastAPI `TestClient` upload API tests with mocked service.
- FastAPI `TestClient` list and detail API tests with mocked service.
- Existing health tests.
- Route import/startup test through backend pytest.

### Explicit Non-Goals

- Do not add frontend pages or upload components.
- Do not add deletion endpoints.
- Do not start document processing from the upload route.
- Do not create authentication, JWT, sessions, or multi-user route behavior.

## Mandatory Batch04 - Tests, Manual Validation, and Handoff

### Goal

Prove the upload and metadata API contract with focused tests, safe scope checks, and honest live Supabase validation status.

### Why this batch exists

Plan 3 completion depends on test evidence, negative checks, single-user filtering verification, and clear reporting of any manual Supabase setup that blocks live validation.

### Inputs / Dependencies

- Batch01 schemas, validation, and config
- Batch02 services
- Batch03 API routes
- Local backend test environment
- Optional real Supabase credentials, bucket, and documents table for live manual checks

### Tasks

- [ ] (04A): Add upload API tests with mocked document service
  - Source of Truth: `docs/plans/Plan_3.md` > `## 3. Scope`; `docs/plans/Plan_3.md` > `## 8. API Design`; `docs/plans/Plan_3.md` > `## 11. Required Tests`; `docs/plans/Plan_3.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Add upload tests with FastAPI `TestClient` and mocked document service.
    - Include at least one successful upload test.
    - Include unsupported-file negative test evidence.
    - Cover empty file validation failure.
  - Details: Create API tests that prove the upload route contract without requiring live Supabase.
  - Dependencies: Batch03 upload route.
  - User Action: None.
  - Agent Work: Add tests for supported upload success, unsupported file type, empty file, and optionally oversized upload if implemented by route-level validation.
  - Output: Upload API test coverage.
  - Acceptance: Tests fail before behavior exists and pass after route/service behavior satisfies Plan 3.
  - Validation: `cd backend` then `pytest tests/test_document_upload.py -v`
  - Blocked Condition: None.
  - Files: `backend/tests/test_document_upload.py`

- [ ] (04B): Add document API and service tests for metadata behavior
  - Source of Truth: `docs/plans/Plan_3.md` > `## 3. Scope`; `docs/plans/Plan_3.md` > `## 8. API Design`; `docs/plans/Plan_3.md` > `## 9. Implementation Steps`; `docs/plans/Plan_3.md` > `## 11. Required Tests`; `docs/plans/Plan_3.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_3.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Test list and detail API contracts.
    - Test service upload success with mocked Supabase helpers.
    - Test upload failure and insert failure.
    - Verify all document queries filter by `SINGLE_USER_ID`.
    - Unknown document UUID returns HTTP 404.
  - Details: Add metadata API tests and service-level tests that cover list/detail contracts, single-user filtering, success insert shape, storage failure, metadata failure, and not-found behavior.
  - Dependencies: Batch02, Batch03.
  - User Action: None.
  - Agent Work: Add or extend test files using mocks rather than live Supabase for deterministic CI/local runs.
  - Output: Document API and service test coverage.
  - Acceptance: Tests prove the required metadata contract and failure behavior without external credentials.
  - Validation: `cd backend` then `pytest tests/test_document_upload.py tests/test_document_api.py -v`
  - Blocked Condition: None.
  - Files: `backend/tests/test_document_upload.py`, `backend/tests/test_document_api.py`, existing Supabase/document service tests if appropriate

- [ ] (04C): Run backend regression, secret, and scope validations
  - Source of Truth: `docs/plans/Plan_3.md` > `## 4. Out of Scope`; `docs/plans/Plan_3.md` > `## 11. Required Tests`; `docs/plans/Plan_3.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_3.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 3. Authentication Policy`
  - Source Requirements:
    - Run required backend tests.
    - Confirm no hardcoded secrets.
    - Confirm frontend was not changed except shared config if truly necessary.
    - Confirm service-role key remains backend-only.
    - Confirm out-of-scope work was not added.
  - Details: Execute the required pytest command and inspect for scope/secret regressions before reporting completion.
  - Dependencies: (04A), (04B)
  - User Action: None.
  - Agent Work: Run backend tests, inspect changed files, and search for frontend exposure of backend-only secret names.
  - Output: Verification evidence for execution report.
  - Acceptance: Required tests pass or failures are reported honestly; no out-of-scope or secret exposure is found.
  - Validation: `cd backend` then `pytest tests/test_document_upload.py tests/test_document_api.py -v`; run existing backend tests as appropriate; run a repository search for backend-only secret names in frontend files.
  - Blocked Condition: None for mocked/local tests.
  - Files: Test files and changed implementation files for inspection

- [ ] (04D): Perform live API and Supabase checks when user setup is available
  - Source of Truth: `docs/plans/Plan_3.md` > `## 1. Goal`; `docs/plans/Plan_3.md` > `## 5. Dependencies`; `docs/plans/Plan_3.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_3.md` > `## 11. Required Tests`; `docs/plans/Plan_3.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_3.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Supabase Storage bucket must exist.
    - Supabase schema must include the `documents` table.
    - Curl upload/list/detail checks should be run when possible.
    - Manual checks must confirm original file exists in storage and a row exists in `documents`.
  - Details: Validate the implementation against a real local backend and Supabase only when the user has provided required local setup outside tracked files.
  - Dependencies: (04C)
  - User Action: User must provide valid local `.env` values, a Supabase Storage bucket, and the existing `documents` table before live checks can pass.
  - Agent Work: Run curl upload/list/detail checks, confirm storage object and document row through safe local tooling or manual user confirmation, and report any missing setup as blocked.
  - Output: Live validation evidence or clear blocked-by-user status.
  - Acceptance: Supported upload returns HTTP 200 with `document_id`; storage object and `documents` row exist; unsupported `.exe`, empty `.txt`, and random UUID checks behave as required.
  - Validation: Curl checks from Plan 3 and manual Supabase Storage/PostgreSQL checks.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if real Supabase credentials, bucket, documents table, sample files, or manual confirmation are missing.
  - Files: No tracked files required unless execution report artifacts are updated by the Execution Agent

### Files or Modules Likely Created or Updated

- `backend/tests/test_document_upload.py`
- `backend/tests/test_document_api.py`
- Existing backend service/config tests if extended
- Execution report artifact created by the future Execution Agent

### Required Outputs / Artifacts

- Upload API tests.
- List/detail API tests.
- Document service tests with mocked Supabase helpers.
- Backend test command results.
- Secret/scope validation notes.
- Live Supabase validation result or blocked-by-user status.
- Execution report with files, commands, tests, known issues, and out-of-scope notes.

### Acceptance Criteria

- `pytest tests/test_document_upload.py tests/test_document_api.py -v` passes or failures are reported honestly.
- At least one successful upload test and one unsupported-file negative test are included in the report.
- Single-user filtering is verified for document reads.
- No hardcoded secrets or frontend service-role exposure is found.
- Live Supabase checks are completed only when user setup exists; otherwise the blocked condition is documented.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_document_upload.py tests/test_document_api.py -v`
- Existing backend tests as appropriate for changed config/main/service code.
- `curl -X POST http://localhost:8000/api/documents/upload -F "file=@sample.pdf"` when local backend and Supabase setup are available.
- `curl http://localhost:8000/api/documents` when local backend and Supabase setup are available.
- `curl http://localhost:8000/api/documents/<document_id>` when local backend and Supabase setup are available.
- Upload `.exe` and expect HTTP 400 when live checks are available.
- Upload empty `.txt` and expect HTTP 400 when live checks are available.
- Request a random document UUID and expect HTTP 404 when live checks are available.
- Manual Supabase Storage and PostgreSQL checks when user setup is available.

### Explicit Non-Goals

- Do not fabricate Supabase project setup, credentials, bucket existence, or manual check results.
- Do not commit `.env` or real secrets.
- Do not weaken tests to avoid failures.
- Do not claim completion for live validation when blocked by missing user setup.

## Optional Future Tracks

- Parsing and chunking pipeline: This track is not part of the mandatory MVP batch chain. Later plans may parse uploaded files and create `document_chunks`.
- Embeddings, Qdrant indexing, and GraphRAG: This track is not part of the mandatory MVP batch chain. Later plans may generate embeddings and build retrieval graph data.
- Frontend upload UI: This track is not part of the mandatory MVP batch chain. Later frontend plans may add upload controls and status display.
- Document deletion: This track is not part of the mandatory MVP batch chain and must not be implemented unless explicitly added in a later plan.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04

Optional future tracks are outside the mandatory chain.

## Global Verification Checklist

- [ ] Uploading PDF, DOCX, TXT, and CSV files returns HTTP 200 and `document_id`.
- [ ] Unsupported file type returns HTTP 400.
- [ ] Empty file returns HTTP 400.
- [ ] Oversized upload returns HTTP 413 when `MAX_UPLOAD_BYTES` is configured and exceeded.
- [ ] Uploaded file exists in Supabase Storage when live validation is available.
- [ ] A row exists in `documents` when live validation is available.
- [ ] Document row uses `user_id = SINGLE_USER_ID`.
- [ ] Document row status is `uploaded`.
- [ ] Document row uses `chunk_count = 0`.
- [ ] `GET /api/documents` returns only documents for `SINGLE_USER_ID`.
- [ ] `GET /api/documents/{document_id}` returns HTTP 404 for unknown IDs.
- [ ] Invalid document UUID path values return HTTP 422.
- [ ] Storage path follows `documents/{SINGLE_USER_ID}/{document_id}/{safe_filename}`.
- [ ] Service-role key remains backend-only and is not exposed to frontend.
- [ ] No parsing, chunking, embeddings, Qdrant, ShopAIKey, agents, deletion, auth, or frontend UI were implemented.
- [ ] Required backend tests were run and results were reported honestly.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [x] Batch01 - Document Schemas, Upload Validation, and Configuration
- [x] Batch02 - Supabase Storage and Document Metadata Service
- [ ] Batch03 - Document API Routes and Router Registration
- [ ] Batch04 - Tests, Manual Validation, and Handoff

### Task IDs

#### Batch01
- [x] (01A): Add document API response schemas
- [x] (01B): Add supported document type and upload validation utilities
- [x] (01C): Add upload size configuration
- [x] (01D): Confirm Plan 3 package boundaries and imports

#### Batch02
- [x] (02A): Add Supabase helpers for document storage and metadata
- [x] (02B): Implement document upload orchestration service
- [x] (02C): Implement document list and detail service operations
- [x] (02D): Preserve Plan 3 failure and scope boundaries in service code

#### Batch03
- [x] (03A): Add document upload API route
- [ ] (03B): Add document list API route
- [ ] (03C): Add document detail API route
- [ ] (03D): Register documents router without disrupting existing APIs

#### Batch04
- [ ] (04A): Add upload API tests with mocked document service
- [ ] (04B): Add document API and service tests for metadata behavior
- [ ] (04C): Run backend regression, secret, and scope validations
- [ ] (04D): Perform live API and Supabase checks when user setup is available

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
