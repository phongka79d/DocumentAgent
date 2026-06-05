# Plan 5 - ShopAIKey Embeddings and Qdrant Indexing Execution Tasks

## Purpose

Create a detailed execution task file for the approved embeddings and Qdrant indexing milestone. This task file guides a future Execution Agent to generate embeddings for ready document chunks through ShopAIKey, create or verify the Qdrant Cloud `document_chunks` collection, upsert chunk vectors with required metadata, persist each stable Qdrant point ID back to `document_chunks.qdrant_point_id`, and validate the behavior required by `docs/plans/Plan_5.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_5.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Conflict note: `docs/plans/Master_Plan.md` describes the broader retrieval pipeline and Phase 4 mentions vector search returning relevant chunks. `docs/plans/Plan_5.md` explicitly excludes semantic search APIs, GraphRAG, retrieval scoring, chat completion, rerank, agents, and frontend exposure. `docs/plans/Plan_5.md` is the scope authority for this task file.

## Source Section Index

- `docs/plans/Plan_5.md` > `## 1. Goal` -> generate embeddings, index ready chunks in Qdrant, and persist non-null `qdrant_point_id`.
- `docs/plans/Plan_5.md` > `## 2. Why This Plan Exists` -> vectors connect parsed chunks to future semantic retrieval while keeping private keys backend-only.
- `docs/plans/Plan_5.md` > `## 3. Scope` -> ShopAIKey client, Qdrant client, collection setup, indexing service, tests, and smoke path.
- `docs/plans/Plan_5.md` > `## 4. Out of Scope` -> prohibited semantic search, GraphRAG, retrieval scoring, chat completion, rerank, agents, and frontend exposure.
- `docs/plans/Plan_5.md` > `## 5. Dependencies` -> completed Plans 1 through 4, `document_chunks` rows, Qdrant Cloud project/key, and ShopAIKey key.
- `docs/plans/Plan_5.md` > `## 6. Required Files and Folders` -> expected service, schema, test, dependency, and env example files.
- `docs/plans/Plan_5.md` > `## 7. Data Model / Schema Changes` -> no table changes, `qdrant_point_id` update rule, collection properties, payload format, and indexing result schema.
- `docs/plans/Plan_5.md` > `## 8. API Design` -> no required public API, optional development-only indexing endpoint contract.
- `docs/plans/Plan_5.md` > `## 9. Implementation Steps` -> ordered configuration, ShopAIKey, Qdrant, payload, orchestration, skipping, partial error, and test requirements.
- `docs/plans/Plan_5.md` > `## 10. Configuration and Environment Variables` -> required backend-only ShopAIKey and Qdrant variables.
- `docs/plans/Plan_5.md` > `## 11. Required Tests` -> mocked unit tests, manual indexing smoke test, Qdrant dashboard check, and database check.
- `docs/plans/Plan_5.md` > `## 12. Acceptance Criteria` -> endpoint, configurable model, collection, point, payload, persistence, skip behavior, secret boundary, and out-of-scope criteria.
- `docs/plans/Plan_5.md` > `## 13. Failure Handling` -> missing config, timeout, malformed response, Qdrant failure, vector-size mismatch, and no-chunk behavior.
- `docs/plans/Plan_5.md` > `## 14. Agent Report Requirement` -> required execution report fields and live-vs-mocked validation status.
- `docs/plans/Plan_5.md` > `## 15. Reviewer Checklist` -> scope, tests, acceptance, secrets, architecture, frontend boundary, point IDs, payload fields, and failed upsert behavior.
- `docs/plans/Master_Plan.md` > `## 2. Tech Stack` -> Python, FastAPI, Pydantic, Qdrant Cloud, and ShopAIKey OpenAI-compatible API are approved.
- `docs/plans/Master_Plan.md` > `## 3. Authentication Policy` -> single-user MVP and backend-only Supabase, Qdrant, and ShopAIKey secrets.
- `docs/plans/Master_Plan.md` > `## 7. Qdrant Cloud Design` -> `document_chunks` collection, payload fields, `SINGLE_USER_ID` filtering, and no direct frontend Qdrant access.
- `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.4 Embedding Flow` -> ShopAIKey embeddings endpoint, Qdrant vector storage, chunk metadata storage, and configurable embedding model.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> approved backend environment variable names and frontend secret boundary.
- `docs/plans/Master_Plan.md` > `## Phase 4: Embeddings and Qdrant Indexing` -> phase alignment and high-level acceptance criteria.

## Approved Architecture Summary

The approved architecture for this plan is a backend-only embedding and vector indexing pipeline for the single-user Document QA Agent MVP. Plans 1 through 4 must already provide the FastAPI backend foundation, Supabase metadata/storage layer, upload flow, parsing, chunking, and persisted `document_chunks` rows. Plan 5 begins with ready documents and chunk rows whose `qdrant_point_id` is null.

The backend must load ShopAIKey and Qdrant settings from backend configuration only, call the ShopAIKey OpenAI-compatible `POST {SHOPAIKEY_BASE_URL}/embeddings` endpoint with the configured embedding model, create or verify the Qdrant Cloud `document_chunks` collection using cosine distance, upsert one vector per unindexed chunk, and update the chunk row with a stable point ID only after Qdrant upsert succeeds. Stable point IDs should use the chunk UUID string unless existing project constraints require an equivalent deterministic value.

The Qdrant point payload must include `user_id`, `document_id`, `chunk_id`, `file_name`, `file_type`, `page_number`, `section_title`, `chunk_index`, and a safe `content_preview` limited to the first 500 characters of chunk content. Indexing must filter document and chunk access by `SINGLE_USER_ID`, reject documents that are not `ready`, skip already indexed chunks by default, and record per-chunk errors without hiding partial failures.

No database table changes are approved in this plan. No semantic search endpoint, GraphRAG construction, retrieval scoring, chat completion, rerank, agent workflow, or frontend exposure is approved. A development-only backend indexing endpoint may be added only if it is clearly marked internal/development and is not wired into frontend behavior.

## Global Implementation Rules

- Keep `docs/plans/Plan_5.md` as the source of truth for scope, validation, and out-of-scope boundaries.
- Depend on completed Plan 1, Plan 2, Plan 3, and Plan 4 work; do not reimplement backend foundation, Supabase schema foundation, upload, parsing, or chunking unless a narrow integration change is required.
- Do not create or alter database tables; use the existing `documents` and `document_chunks` tables.
- Do not implement semantic search APIs, GraphRAG, retrieval scoring, chat completion, rerank, LangGraph agents, frontend indexing controls, or frontend references to ShopAIKey/Qdrant secrets.
- Keep `SHOPAIKEY_API_KEY`, `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_EMBEDDING_MODEL`, `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`, and `SINGLE_USER_ID` backend-only.
- Use `.env.example` for placeholder names only and never commit real secrets.
- Do not hardcode embedding model names, Qdrant collection names, API keys, or provider URLs inside business logic.
- Always filter document and chunk lookup by `SINGLE_USER_ID`.
- Reject indexing if the document status is not `ready`.
- Skip chunks that already have `qdrant_point_id` unless a later plan explicitly adds a reindex flag.
- Update `document_chunks.qdrant_point_id` only after the corresponding Qdrant upsert succeeds.
- Record per-chunk indexing errors in the returned indexing result; do not mark failed chunks as indexed.
- Fail loudly on Qdrant vector-size mismatch and include a safe instruction to verify collection setup.
- Do not claim live ShopAIKey, Qdrant, Supabase, or manual smoke validation passed unless required user setup exists and the validation was actually run.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, settings, routes, schemas, service helpers, payload builders, and tests.
- Keep functions, services, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, HTTP client, Qdrant client, and Supabase Python client conventions for the approved stack.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless the plan explicitly requires them.
- Add comments only where they clarify a non-obvious decision or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Do not add formatter, linter, framework, or architecture changes outside Plan 5 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Backend Configuration, Dependencies, Schemas, and Supabase Helpers
- Batch02 - ShopAIKey Embedding Client
- Batch03 - Qdrant Collection and Vector Upsert Service
- Batch04 - Indexing Orchestration and Optional Development Trigger
- Batch05 - Tests, Smoke Checks, and Handoff

## Mandatory Batch01 - Backend Configuration, Dependencies, Schemas, and Supabase Helpers

### Goal

Prepare backend configuration, dependency declarations, internal schemas, and Supabase helper contracts required by the embedding and indexing pipeline.

### Why this batch exists

ShopAIKey, Qdrant, and indexing orchestration all depend on typed backend settings, internal result models, and safe Supabase access to ready documents and chunks needing indexing.

### Inputs / Dependencies

- `docs/plans/Plan_5.md`
- Completed Plan 1 backend foundation
- Completed Plan 2 Supabase schema foundation
- Completed Plan 3 upload metadata behavior
- Completed Plan 4 parsed `document_chunks` rows
- Existing backend configuration, schema, dependency, and Supabase service patterns

### Tasks

- [x] (01A): Add backend-only ShopAIKey and Qdrant configuration
  - Source of Truth: `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Plan_5.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Master_Plan.md` > `## 3. Authentication Policy`; `docs/plans/Master_Plan.md` > `# 15. Environment Variables`
  - Source Requirements:
    - Add `SHOPAIKEY_API_KEY`, `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_EMBEDDING_MODEL`, `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION` to backend settings and `.env.example`.
    - All ShopAIKey and Qdrant variables are backend-only.
    - Real secret values must not be committed.
  - Details: Extend the existing backend configuration system and `.env.example` with the required variable names and safe placeholders. Ensure missing required values produce clear backend configuration errors without printing secret values.
  - Dependencies: Completed Plan 1 configuration pattern.
  - User Action: User must provide real ShopAIKey and Qdrant values in local `.env` before live indexing or smoke checks can pass.
  - Agent Work: Update backend config and `.env.example` using existing project style; do not touch frontend env files except to confirm private keys are absent if needed.
  - Output: Backend settings expose required ShopAIKey and Qdrant configuration safely.
  - Acceptance: Backend code can read all required settings; `.env.example` contains only placeholders; missing config is reported clearly and safely.
  - Validation: Run backend config/unit tests affected by settings; inspect `.env.example` and changed frontend files for secret exposure.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live indexing if real provider credentials are missing.
  - Files: `backend/app/core/config.py`, `backend/.env.example`

- [x] (01B): Add indexing dependencies without unrelated provider packages
  - Source of Truth: `docs/plans/Plan_5.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## 2. Tech Stack`
  - Source Requirements:
    - Add `qdrant-client`.
    - Add an HTTP client dependency if not already present.
    - Use ShopAIKey through its OpenAI-compatible HTTP endpoint.
  - Details: Update backend dependencies with the Qdrant client and a suitable existing or minimal HTTP client. Prefer an HTTP client already used by the project; add a new dependency only if needed for reliable request, timeout, and mock testing behavior.
  - Dependencies: Completed Plan 1 backend dependency workflow.
  - User Action: None.
  - Agent Work: Update `backend/requirements.txt` only for required indexing dependencies.
  - Output: Backend dependency file supports Qdrant client usage and mocked HTTP embedding tests.
  - Acceptance: ShopAIKey and Qdrant services can import required dependencies in the backend test environment.
  - Validation: `cd backend` then run relevant import or pytest commands in Batch05.
  - Blocked Condition: None for mocked/local tests.
  - Files: `backend/requirements.txt`

- [x] (01C): Add internal embedding and indexing schemas
  - Source of Truth: `docs/plans/Plan_5.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_5.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Create `backend/app/schemas/embeddings.py`.
    - Include internal models for embedding requests, indexed chunk payloads, and indexing results.
    - Indexing result shape includes `document_id`, `indexed_count`, `failed_count`, and `errors`.
  - Details: Define Pydantic models for embedding input/result, Qdrant payloads, per-chunk errors, and document indexing results. Keep these models internal to backend service/API responses and avoid leaking provider secrets or low-level client objects.
  - Dependencies: Existing Pydantic and schema package style.
  - User Action: None.
  - Agent Work: Create the embeddings schema module and export it through the existing schemas package style when needed.
  - Output: Typed internal schema models for embedding, payload, and indexing result handling.
  - Acceptance: Services and tests can import and use schemas; result models match the required Plan 5 response shape.
  - Validation: `cd backend` then run `pytest tests/test_embedding_service.py -v` after service implementation.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/embeddings.py`, `backend/app/schemas/__init__.py`

- [ ] (01D): Add Supabase helpers for indexing reads and point ID updates
  - Source of Truth: `docs/plans/Plan_5.md` > `## 3. Scope`; `docs/plans/Plan_5.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_5.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## 3. Authentication Policy`
  - Source Requirements:
    - Add helpers for listing chunks that need indexing.
    - Add helpers for updating `qdrant_point_id`.
    - Fetch document and chunks filtered by `SINGLE_USER_ID`.
    - Use existing `document_chunks.qdrant_point_id`; no table changes.
  - Details: Extend `supabase_service.py` with focused helpers for loading a document by ID and single-user owner, listing chunks where `qdrant_point_id` is null, and updating one chunk row with a stable point ID after Qdrant upsert succeeds.
  - Dependencies: Completed Plan 2 Supabase schema and Plan 4 chunk persistence behavior.
  - User Action: None for mocked tests; real Supabase setup is required for live validation.
  - Agent Work: Add helper methods using existing Supabase client conventions and safe error handling.
  - Output: Supabase service supports document indexing orchestration without schema changes.
  - Acceptance: Helpers filter by `SINGLE_USER_ID`, return enough metadata for Qdrant payloads, and update only the intended chunk row.
  - Validation: Mocked embedding service tests; optional database check after live indexing.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live validation if Supabase credentials/tables/chunks are unavailable.
  - Files: `backend/app/services/supabase_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/requirements.txt`
- `backend/app/schemas/embeddings.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/supabase_service.py`

### Required Outputs / Artifacts

- Backend-only ShopAIKey and Qdrant settings.
- Safe `.env.example` placeholders.
- Required backend dependencies.
- Internal embedding/indexing schemas.
- Supabase helper methods for chunks needing indexing and `qdrant_point_id` updates.

### Acceptance Criteria

- Required settings are loaded through backend config and not hardcoded.
- `.env.example` has placeholder values only.
- Dependencies support Qdrant and HTTP embedding calls.
- Internal schemas represent embedding requests, Qdrant payloads, and indexing results.
- Supabase helpers always filter by `SINGLE_USER_ID`.
- No database schema changes are added.
- No frontend file exposes backend-only variables.

### Required Tests or Validations

- Backend config/import validation.
- `cd backend`
- Relevant pytest commands from Batch05 after services are implemented.
- Changed-file inspection for hardcoded secrets and frontend secret exposure.

### Explicit Non-Goals

- Do not create real ShopAIKey or Qdrant accounts from code.
- Do not commit `.env` or real secrets.
- Do not modify database schema.
- Do not implement vector search or retrieval APIs.

## Mandatory Batch02 - ShopAIKey Embedding Client

### Goal

Implement a backend-only ShopAIKey embedding client that sends OpenAI-compatible embedding requests and handles provider failures safely.

### Why this batch exists

Indexing cannot proceed until chunk text can be converted into embedding vectors through the configured ShopAIKey embeddings endpoint with predictable errors and testable request construction.

### Inputs / Dependencies

- Batch01 configuration and dependencies
- Existing backend service style
- ShopAIKey OpenAI-compatible API configuration

### Tasks

- [ ] (02A): Implement ShopAIKey embedding request construction
  - Source of Truth: `docs/plans/Plan_5.md` > `## 3. Scope`; `docs/plans/Plan_5.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.4 Embedding Flow`
  - Source Requirements:
    - Create `backend/app/services/shopaikey_service.py`.
    - Add `create_embedding(text: str) -> list[float]`.
    - Use `POST {SHOPAIKEY_BASE_URL}/embeddings`.
    - Send model from `SHOPAIKEY_EMBEDDING_MODEL`.
    - Do not hardcode the embedding model inside business logic.
  - Details: Build the embedding request using backend config, bearer authentication, a safe timeout, and a request body compatible with OpenAI-style embeddings. Keep the public function small and typed.
  - Dependencies: (01A), (01B), (01C)
  - User Action: User must provide a real ShopAIKey API key in `.env` before live calls can pass.
  - Agent Work: Implement the service module and any provider-specific exception type needed by the indexing service.
  - Output: `create_embedding(text: str) -> list[float]` function that returns a vector for valid provider responses.
  - Acceptance: Mocked tests verify endpoint path, authorization header behavior without exposing the key, configured model usage, input text inclusion, and vector return.
  - Validation: `cd backend` then `pytest tests/test_shopaikey_service.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live embedding calls if `SHOPAIKEY_API_KEY` or related config is missing.
  - Files: `backend/app/services/shopaikey_service.py`, `backend/tests/test_shopaikey_service.py`

- [ ] (02B): Handle ShopAIKey errors and malformed responses
  - Source of Truth: `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Plan_5.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Handle HTTP timeout.
    - Handle non-2xx response.
    - Handle malformed JSON.
    - Handle missing embedding vector.
    - Missing ShopAIKey config produces a clear backend error.
    - ShopAIKey malformed response raises a clear embedding error.
  - Details: Convert provider, network, timeout, invalid JSON, and invalid response-shape failures into safe backend exceptions. Error messages must not include full API keys, raw secrets, or excessive provider response bodies.
  - Dependencies: (02A)
  - User Action: None for mocked tests.
  - Agent Work: Add failure handling and focused tests for each failure mode.
  - Output: Safe embedding service failure behavior.
  - Acceptance: Mocked tests prove timeout, non-2xx, malformed JSON, missing vector, and missing config are handled with clear safe errors.
  - Validation: `cd backend` then `pytest tests/test_shopaikey_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/shopaikey_service.py`, `backend/tests/test_shopaikey_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/shopaikey_service.py`
- `backend/tests/test_shopaikey_service.py`
- `backend/app/core/config.py` if configuration access adjustments are needed

### Required Outputs / Artifacts

- ShopAIKey embedding service function.
- Provider-specific safe exception handling.
- Mocked ShopAIKey request construction and failure tests.

### Acceptance Criteria

- ShopAIKey embeddings client sends requests to `/embeddings`.
- Embedding model comes from configuration.
- Backend uses the API key only on the server side.
- Timeouts, non-2xx responses, malformed JSON, missing vectors, and missing config fail safely.
- No chat completion, rerank, retrieval, agent, or frontend behavior is added.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_shopaikey_service.py -v`
- Scope inspection confirming no chat completion or rerank call was added for this milestone.

### Explicit Non-Goals

- Do not call `/chat/completions`.
- Do not call `/rerank`.
- Do not expose ShopAIKey to frontend code.
- Do not fabricate a successful live embedding response.

## Mandatory Batch03 - Qdrant Collection and Vector Upsert Service

### Goal

Implement a backend-only Qdrant service that creates or verifies the vector collection and upserts chunk vectors with required payload metadata.

### Why this batch exists

Chunk embeddings need durable vector storage in Qdrant before future retrieval plans can perform semantic search and scoring.

### Inputs / Dependencies

- Batch01 configuration, dependencies, and schemas
- Batch02 vector output shape
- Qdrant Cloud project and API key for live validation

### Tasks

- [ ] (03A): Implement Qdrant client initialization and collection setup
  - Source of Truth: `docs/plans/Plan_5.md` > `## 3. Scope`; `docs/plans/Plan_5.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_5.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## 7. Qdrant Cloud Design`
  - Source Requirements:
    - Create `backend/app/services/qdrant_service.py`.
    - Add `get_qdrant_client()`.
    - Add `ensure_collection(vector_size)`.
    - Use cosine distance for the Qdrant collection.
    - Collection name defaults to or is configured as `document_chunks`.
    - Vector size is derived from the first ShopAIKey embedding response and then enforced by config/setup.
  - Details: Initialize the Qdrant client from backend-only settings. Implement collection creation or verification using cosine distance and the configured collection name. If an existing collection has an incompatible vector size or distance, raise a clear setup error.
  - Dependencies: (01A), (01B), (01C)
  - User Action: User must provide `QDRANT_URL`, `QDRANT_API_KEY`, and a reachable Qdrant Cloud project for live validation.
  - Agent Work: Implement Qdrant client setup and collection verification using `qdrant-client`.
  - Output: Qdrant service can create or verify `document_chunks` with the expected vector size and cosine distance.
  - Acceptance: Mocked tests verify client construction, collection creation, existing collection verification, and mismatch failure behavior.
  - Validation: `cd backend` then `pytest tests/test_qdrant_service.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live Qdrant validation if real Qdrant setup is missing.
  - Files: `backend/app/services/qdrant_service.py`, `backend/tests/test_qdrant_service.py`

- [ ] (03B): Implement Qdrant payload builder and vector upsert helper
  - Source of Truth: `docs/plans/Plan_5.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Plan_5.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 7. Qdrant Cloud Design`
  - Source Requirements:
    - Add `upsert_chunk_vector(point_id, vector, payload)`.
    - Create deterministic point IDs such as the chunk UUID string.
    - Build Qdrant payload with all required metadata.
    - Include a safe `content_preview`.
    - Each indexed chunk creates one Qdrant point.
  - Details: Build a typed payload from chunk/document metadata with `content_preview` limited to the first 500 characters. Upsert one vector using the stable chunk UUID point ID. Keep point creation separate from Supabase row updates so the indexing service can update `qdrant_point_id` only after upsert success.
  - Dependencies: (03A)
  - User Action: None for mocked tests.
  - Agent Work: Implement payload construction and vector upsert helper with safe error handling.
  - Output: Qdrant service can upsert one chunk vector with required metadata.
  - Acceptance: Mocked tests verify stable point ID usage, all payload fields, preview truncation, vector passthrough, and no `qdrant_point_id` update behavior inside the Qdrant service.
  - Validation: `cd backend` then `pytest tests/test_qdrant_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/qdrant_service.py`, `backend/tests/test_qdrant_service.py`

- [ ] (03C): Handle Qdrant failures without marking chunks indexed
  - Source of Truth: `docs/plans/Plan_5.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_5.md` > `## 13. Failure Handling`; `docs/plans/Plan_5.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Qdrant connection failure records an indexing error and does not update `qdrant_point_id`.
    - Qdrant vector-size mismatch must fail loudly and instruct the agent to verify collection setup.
    - Confirm errors do not mark a chunk indexed when Qdrant upsert failed.
  - Details: Convert Qdrant connection, collection, upsert, and vector-size failures into safe service exceptions that the indexing orchestrator can record per chunk or as setup failure. Do not mutate Supabase from this service.
  - Dependencies: (03A), (03B)
  - User Action: None for mocked tests.
  - Agent Work: Add failure handling and tests for Qdrant failure cases.
  - Output: Safe Qdrant failure behavior.
  - Acceptance: Mocked tests prove upsert failure surfaces to the indexing service and no point ID persistence occurs from Qdrant service code.
  - Validation: `cd backend` then `pytest tests/test_qdrant_service.py -v`; final orchestration tests in Batch05.
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/qdrant_service.py`, `backend/tests/test_qdrant_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/qdrant_service.py`
- `backend/tests/test_qdrant_service.py`
- `backend/app/schemas/embeddings.py` if payload schema adjustments are needed

### Required Outputs / Artifacts

- Qdrant client initialization helper.
- Collection creation/verification with cosine distance.
- Vector upsert helper.
- Required payload construction with safe content preview.
- Mocked Qdrant service tests.

### Acceptance Criteria

- Qdrant collection is created or verified with cosine distance.
- Vector size is derived from actual embeddings and enforced during setup.
- Each indexed chunk can map to one stable Qdrant point.
- Payload includes `user_id`, `document_id`, `chunk_id`, `file_name`, `file_type`, `page_number`, `section_title`, `chunk_index`, and `content_preview`.
- Qdrant failures do not update `document_chunks.qdrant_point_id`.
- Qdrant and API key configuration remains backend-only.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_qdrant_service.py -v`
- Manual Qdrant dashboard check in Batch05 when real Qdrant setup is available.

### Explicit Non-Goals

- Do not implement Qdrant search.
- Do not implement retrieval filters beyond payload creation for future retrieval.
- Do not expose Qdrant URL or API key to frontend.
- Do not fabricate Qdrant collection existence or point insert results.

## Mandatory Batch04 - Indexing Orchestration and Optional Development Trigger

### Goal

Implement the indexing service that coordinates ready document chunk lookup, embedding generation, Qdrant upsert, point ID persistence, skip behavior, and optional development-only manual triggering.

### Why this batch exists

The milestone is complete only when ready document chunks without `qdrant_point_id` can move through the full backend indexing flow and persist successful point IDs while reporting partial failures honestly.

### Inputs / Dependencies

- Batch01 configuration, schemas, and Supabase helpers
- Batch02 ShopAIKey embedding client
- Batch03 Qdrant service
- Completed Plan 4 ready documents and chunk rows

### Tasks

- [ ] (04A): Implement `index_document_chunks(document_id)` orchestration
  - Source of Truth: `docs/plans/Plan_5.md` > `## 1. Goal`; `docs/plans/Plan_5.md` > `## 3. Scope`; `docs/plans/Plan_5.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Plan_5.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Create `backend/app/services/embedding_service.py`.
    - Add `index_document_chunks(document_id)`.
    - Fetch document and chunks filtered by `SINGLE_USER_ID`.
    - Reject indexing if document status is not `ready`.
    - Generate an embedding, ensure collection, upsert the point, and update the chunk row for each chunk missing `qdrant_point_id`.
    - Store each Qdrant point ID back on `document_chunks`.
  - Details: Implement orchestration in a focused backend service. Validate document ownership and status, list chunks needing indexing, create embeddings, ensure collection using the vector size from the first embedding, upsert each vector, and update `qdrant_point_id` after each successful upsert.
  - Dependencies: Batch01, Batch02, Batch03.
  - User Action: None for mocked tests; real provider and Supabase setup required for live indexing.
  - Agent Work: Create the embedding orchestration service and integrate service exceptions into the indexing result model.
  - Output: Indexing service returns `document_id`, `indexed_count`, `failed_count`, and `errors`.
  - Acceptance: Mocked tests prove successful indexing updates each unindexed chunk after Qdrant upsert and returns the required result shape.
  - Validation: `cd backend` then `pytest tests/test_embedding_service.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live indexing if real ShopAIKey, Qdrant, Supabase credentials, ready document, or chunks are missing.
  - Files: `backend/app/services/embedding_service.py`, `backend/tests/test_embedding_service.py`

- [ ] (04B): Implement skip, no-work, and partial failure behavior
  - Source of Truth: `docs/plans/Plan_5.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Plan_5.md` > `## 13. Failure Handling`; `docs/plans/Plan_5.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Skip chunks that already have `qdrant_point_id` unless an explicit reindex flag is later added.
    - Record per-chunk errors in the indexing result instead of hiding partial failures.
    - Document with no chunks returns a clear no-work result or error.
    - ShopAIKey timeout records an indexing error for the chunk.
    - Qdrant connection failure records an indexing error and does not update `qdrant_point_id`.
  - Details: Ensure already-indexed chunks are not duplicated by default. Decide, based on existing project style, whether no chunks is a no-work result or a clear error, and document the choice in the execution report. Continue indexing remaining chunks when a per-chunk failure is recoverable and record safe error summaries.
  - Dependencies: (04A)
  - User Action: None for mocked tests.
  - Agent Work: Add orchestration branches and tests for already-indexed chunks, no chunks, ShopAIKey failure, Qdrant failure, and partial success.
  - Output: Honest indexing result behavior for skip, no-work, and partial failures.
  - Acceptance: Mocked tests prove skipped chunks are not embedded/upserted, failed chunks are counted in `failed_count`, and failed Qdrant upserts do not update `qdrant_point_id`.
  - Validation: `cd backend` then `pytest tests/test_embedding_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/embedding_service.py`, `backend/tests/test_embedding_service.py`

- [ ] (04C): Add optional development-only indexing endpoint if needed
  - Source of Truth: `docs/plans/Plan_5.md` > `## 8. API Design`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Plan_5.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - No required public API endpoints in this plan.
    - Optional endpoint: `POST /api/documents/{document_id}/index`.
    - If added, the endpoint must be clearly marked development/internal and not used by the frontend yet.
    - Error responses include document not found, no chunks, ShopAIKey failure, and Qdrant failure.
  - Details: Add this route only if it is useful for local development smoke testing or consistent with existing manual processing routes. If omitted, document that indexing can be run through the service/function in the execution report. If added, keep it backend-only, clearly internal/development in code naming or route comments, and do not add frontend calls.
  - Dependencies: (04A), (04B)
  - User Action: None for mocked tests; real credentials and ready chunks required for live endpoint smoke tests.
  - Agent Work: Optionally add a FastAPI route wired to `index_document_chunks(document_id)` and route-level tests for response mapping.
  - Output: Either a development-only endpoint or a documented decision not to add one.
  - Acceptance: If added, endpoint returns required result shape and safe errors; if not added, service-level smoke path is available and report explains why.
  - Validation: If route is added, run affected API tests plus `pytest tests/test_embedding_service.py -v`; if not added, run service tests.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live endpoint validation if real setup is missing.
  - Files: `backend/app/api/documents.py`, `backend/app/main.py`, `backend/tests/test_document_indexing_api.py`, or no API files if omitted.

### Files or Modules Likely Created or Updated

- `backend/app/services/embedding_service.py`
- `backend/app/services/supabase_service.py`
- `backend/app/services/shopaikey_service.py`
- `backend/app/services/qdrant_service.py`
- `backend/app/schemas/embeddings.py`
- `backend/app/api/documents.py` if optional endpoint is added
- `backend/app/main.py` if router wiring changes are required
- `backend/tests/test_embedding_service.py`
- `backend/tests/test_document_indexing_api.py` if optional endpoint is added

### Required Outputs / Artifacts

- Indexing orchestration service.
- Required indexing result shape.
- Skip and partial failure behavior.
- Optional development-only endpoint or explicit report note that service-level smoke path was used instead.
- Mocked orchestration tests.

### Acceptance Criteria

- Only documents owned by `SINGLE_USER_ID` are indexed.
- Documents not in `ready` status are rejected.
- Chunks missing `qdrant_point_id` are embedded and upserted.
- `qdrant_point_id` is updated only after successful Qdrant upsert.
- Already-indexed chunks are skipped by default.
- Per-chunk failures are counted and reported safely.
- No-chunk documents return a clear no-work result or error.
- Optional endpoint, if added, is development/internal and not used by frontend.
- No semantic search, GraphRAG, retrieval scoring, chat completion, rerank, or agents are implemented.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_embedding_service.py -v`
- Optional API route tests if the development endpoint is added.
- Scope inspection confirming no frontend indexing call was added.

### Explicit Non-Goals

- Do not add a public user-facing indexing feature to the frontend.
- Do not implement reindex flags unless a later plan requires them.
- Do not implement vector search or answer retrieval.
- Do not mark failed chunks indexed.

## Mandatory Batch05 - Tests, Smoke Checks, and Handoff

### Goal

Prove the ShopAIKey client, Qdrant service, indexing orchestration, failure handling, scope boundaries, and optional live smoke path with focused tests and an honest execution report.

### Why this batch exists

Plan 5 completion depends on evidence that mocked unit behavior passes, external-service live checks are run only when setup exists, and backend-only secret and scope boundaries are preserved.

### Inputs / Dependencies

- Batch01 through Batch04 implementation
- Local backend test environment
- Optional real ShopAIKey API key, Qdrant Cloud project/API key, Supabase setup, ready document, and unindexed chunks for live checks

### Tasks

- [ ] (05A): Add and run ShopAIKey service tests
  - Source of Truth: `docs/plans/Plan_5.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Plan_5.md` > `## 11. Required Tests`; `docs/plans/Plan_5.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_5.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Add `backend/tests/test_shopaikey_service.py`.
    - Test embedding request payloads.
    - Test API failure behavior.
    - Test HTTP timeout, non-2xx response, malformed JSON, and missing embedding vector.
  - Details: Ensure the ShopAIKey tests mock HTTP and never require real credentials. Validate model configurability, endpoint path, safe auth handling, vector extraction, and failure mapping.
  - Dependencies: Batch02.
  - User Action: None.
  - Agent Work: Create or update tests and run them.
  - Output: ShopAIKey service test coverage and command result.
  - Acceptance: Tests pass or failures are reported honestly with safe error context.
  - Validation: `cd backend` then `pytest tests/test_shopaikey_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/tests/test_shopaikey_service.py`

- [ ] (05B): Add and run Qdrant service tests
  - Source of Truth: `docs/plans/Plan_5.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Plan_5.md` > `## 11. Required Tests`; `docs/plans/Plan_5.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_5.md` > `## 13. Failure Handling`; `docs/plans/Plan_5.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Add `backend/tests/test_qdrant_service.py`.
    - Test collection creation.
    - Test payload construction with mocked Qdrant client.
    - Confirm point IDs are stable and traceable to chunk IDs.
    - Confirm payload filtering fields are present.
  - Details: Mock the Qdrant client to verify collection creation/verification, cosine distance, vector size handling, payload fields, content preview truncation, stable chunk UUID point IDs, and failure behavior.
  - Dependencies: Batch03.
  - User Action: None.
  - Agent Work: Create or update tests and run them.
  - Output: Qdrant service test coverage and command result.
  - Acceptance: Tests pass or failures are reported honestly with safe error context.
  - Validation: `cd backend` then `pytest tests/test_qdrant_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/tests/test_qdrant_service.py`

- [ ] (05C): Add and run embedding orchestration tests
  - Source of Truth: `docs/plans/Plan_5.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_5.md` > `## 9. Implementation Steps`; `docs/plans/Plan_5.md` > `## 11. Required Tests`; `docs/plans/Plan_5.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_5.md` > `## 13. Failure Handling`; `docs/plans/Plan_5.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Add `backend/tests/test_embedding_service.py`.
    - Test indexing orchestration.
    - Test successful indexing.
    - Test already-indexed chunks.
    - Test API failure behavior.
    - Confirm errors do not mark a chunk indexed when Qdrant upsert failed.
  - Details: Mock Supabase, ShopAIKey, and Qdrant services to prove document status rejection, no chunks, successful indexing, skipped chunks, partial ShopAIKey failure, Qdrant failure, vector-size setup failure, and safe result contents.
  - Dependencies: Batch04.
  - User Action: None.
  - Agent Work: Create or update tests and run them.
  - Output: Embedding orchestration test coverage and command result.
  - Acceptance: Tests pass or failures are reported honestly; no failed chunk is marked indexed.
  - Validation: `cd backend` then `pytest tests/test_embedding_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/tests/test_embedding_service.py`

- [ ] (05D): Run combined backend tests and scope/security checks
  - Source of Truth: `docs/plans/Plan_5.md` > `## 4. Out of Scope`; `docs/plans/Plan_5.md` > `## 11. Required Tests`; `docs/plans/Plan_5.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_5.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_5.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 3. Authentication Policy`
  - Source Requirements:
    - Run required tests.
    - Confirm scope was followed.
    - Confirm no hardcoded secrets.
    - Confirm no fake success.
    - Confirm architecture still matches `docs/plans/Master_Plan.md`.
    - Confirm no frontend file references Qdrant or ShopAIKey secrets.
  - Details: Run the combined required pytest command and inspect changed files for hardcoded keys, frontend secret exposure, semantic search, GraphRAG, retrieval scoring, chat completion, rerank, agents, and unrelated architecture changes.
  - Dependencies: (05A), (05B), (05C)
  - User Action: None.
  - Agent Work: Run tests, inspect changed files, and report results honestly.
  - Output: Verification evidence for the execution report.
  - Acceptance: Required tests pass or failures are reported honestly; no secret exposure or out-of-scope work is found.
  - Validation: `cd backend` then `pytest tests/test_shopaikey_service.py tests/test_qdrant_service.py tests/test_embedding_service.py -v`; run existing backend regression tests affected by changed config/API/service code.
  - Blocked Condition: None for mocked/local tests.
  - Files: Test files and changed implementation files for inspection

- [ ] (05E): Perform manual indexing and Qdrant/Supabase checks when user setup is available
  - Source of Truth: `docs/plans/Plan_5.md` > `## 1. Goal`; `docs/plans/Plan_5.md` > `## 5. Dependencies`; `docs/plans/Plan_5.md` > `## 8. API Design`; `docs/plans/Plan_5.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_5.md` > `## 11. Required Tests`; `docs/plans/Plan_5.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_5.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Upload and process a TXT document.
    - Run the indexing function or endpoint for that document.
    - Confirm `indexed_count` equals document `chunk_count`.
    - Confirm Qdrant collection `document_chunks` exists.
    - Confirm points include payload `user_id`, `document_id`, `chunk_id`, `file_name`, and `content_preview`.
    - Confirm `document_chunks.qdrant_point_id` is non-null after indexing.
  - Details: Validate against real local backend, Supabase, ShopAIKey, and Qdrant only when the user has provided required local setup outside tracked files. Use the service function or optional development endpoint. Run the database check and Qdrant dashboard/client check without exposing secrets.
  - Dependencies: (05D)
  - User Action: User must provide valid local `.env` values, Qdrant Cloud project/API key, ShopAIKey API key, Supabase setup, and a ready document with chunks before live checks can pass.
  - Agent Work: Run indexing smoke check, inspect Qdrant point payloads, query `document_chunks.qdrant_point_id`, and report results safely when setup is available.
  - Output: Live validation evidence or clear blocked-by-user status.
  - Acceptance: Ready TXT document chunks are indexed, `indexed_count` equals `chunk_count`, Qdrant points have required payload fields, and chunk rows have non-null point IDs.
  - Validation: Manual indexing smoke test, Qdrant dashboard/client check, and database check from Plan 5.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if real ShopAIKey credentials, Qdrant project/API key, Supabase setup, ready document, chunks, local backend, or manual confirmation are missing.
  - Files: No tracked files required unless the Execution Agent writes a report artifact.

### Files or Modules Likely Created or Updated

- `backend/tests/test_shopaikey_service.py`
- `backend/tests/test_qdrant_service.py`
- `backend/tests/test_embedding_service.py`
- Optional `backend/tests/test_document_indexing_api.py`
- Changed implementation files from prior batches
- Execution report artifact created by the future Execution Agent

### Required Outputs / Artifacts

- Mocked tests for ShopAIKey request construction and error handling.
- Mocked tests for Qdrant collection creation, payload construction, and failure handling.
- Mocked tests for indexing orchestration, skip behavior, partial failures, and point ID persistence.
- Combined backend test command result.
- Scope and secret validation notes.
- Manual live indexing result or blocked-by-user status.
- Execution report with files created, files modified, commands run, test results, known issues, out-of-scope notes, and live-vs-mocked check status.

### Acceptance Criteria

- `pytest tests/test_shopaikey_service.py -v` passes or failures are reported honestly.
- `pytest tests/test_qdrant_service.py -v` passes or failures are reported honestly.
- `pytest tests/test_embedding_service.py -v` passes or failures are reported honestly.
- Combined required test command passes or failures are reported honestly.
- ShopAIKey embeddings client sends requests to `/embeddings`.
- Embedding model is configurable.
- Qdrant collection is created or verified with cosine distance.
- Each indexed chunk creates one Qdrant point.
- Qdrant payload includes required metadata.
- `document_chunks.qdrant_point_id` is updated after successful upsert.
- Already-indexed chunks are not duplicated by default.
- ShopAIKey and Qdrant keys are backend-only.
- No semantic search endpoint, GraphRAG, retrieval scoring, chat completion, rerank, agent logic, or frontend secret exposure is added.
- Live checks are completed only when user setup exists; otherwise the blocked condition is documented.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_shopaikey_service.py -v`
- `pytest tests/test_qdrant_service.py -v`
- `pytest tests/test_embedding_service.py -v`
- `pytest tests/test_shopaikey_service.py tests/test_qdrant_service.py tests/test_embedding_service.py -v`
- Existing backend regression tests affected by changed config, API, or service code.
- Manual TXT upload/process/index smoke check when local setup is available.
- Manual Qdrant collection and payload check when Qdrant setup is available.
- Manual database check for non-null `qdrant_point_id` when Supabase setup is available.
- Repository search or changed-file inspection for hardcoded secrets, frontend secret exposure, semantic search, GraphRAG, retrieval scoring, chat completion, rerank, and agent work.

### Explicit Non-Goals

- Do not fabricate ShopAIKey, Qdrant, Supabase, or manual check results.
- Do not commit `.env` or real secrets.
- Do not weaken tests to avoid failures.
- Do not claim completion for live validation when blocked by missing user setup.
- Do not implement optional future retrieval or agent stages during validation.

## Optional Future Tracks

- Semantic search API: This track is not part of the mandatory MVP batch chain. Later plans may query Qdrant vectors, apply filters, and return ranked chunks.
- Medium GraphRAG construction: This track is not part of the mandatory MVP batch chain. Later plans may extract entities, create relationships, and support graph retrieval expansion.
- Retrieval scoring and Top-K selection: This track is not part of the mandatory MVP batch chain. Later plans may implement semantic similarity, graph relevance, keyword overlap, metadata match, and final score calculation.
- Rerank: This track is not part of the mandatory MVP batch chain. Later plans may call ShopAIKey rerank when explicitly enabled.
- LangGraph agents and answer generation: This track is not part of the mandatory MVP batch chain. Later plans may implement retrieval, verification, answer, self-check, and agent logging.
- Frontend indexing controls or processing status changes: This track is not part of the mandatory MVP batch chain and must not be added unless a later frontend plan requires it.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05

Optional future tracks are outside the mandatory chain.

## Global Verification Checklist

- [ ] Required ShopAIKey and Qdrant settings exist in backend config.
- [ ] Required ShopAIKey and Qdrant settings are present in `backend/.env.example` with placeholders only.
- [ ] No real secret values are committed.
- [ ] No frontend file references ShopAIKey or Qdrant private keys.
- [ ] `qdrant-client` and any required HTTP client dependency are declared.
- [ ] `backend/app/schemas/embeddings.py` defines internal models for embedding/indexing work.
- [ ] Supabase helpers filter documents and chunks by `SINGLE_USER_ID`.
- [ ] No database table changes are added.
- [ ] ShopAIKey embeddings client sends requests to `/embeddings`.
- [ ] Embedding model is configurable and not hardcoded in business logic.
- [ ] ShopAIKey timeout, non-2xx, malformed JSON, missing vector, and missing config are handled safely.
- [ ] Qdrant client uses backend-only URL/API key configuration.
- [ ] Qdrant collection `document_chunks` is created or verified with cosine distance.
- [ ] Vector size is derived from actual embedding output and enforced during collection setup.
- [ ] Stable Qdrant point IDs are traceable to chunk UUIDs.
- [ ] Qdrant payload includes `user_id`, `document_id`, `chunk_id`, `file_name`, `file_type`, `page_number`, `section_title`, `chunk_index`, and `content_preview`.
- [ ] `content_preview` is safe and limited to the first 500 characters.
- [ ] Indexing loads documents and chunks filtered by `SINGLE_USER_ID`.
- [ ] Indexing rejects documents whose status is not `ready`.
- [ ] Chunks with existing `qdrant_point_id` are skipped by default.
- [ ] Each successfully indexed chunk creates one Qdrant point.
- [ ] `document_chunks.qdrant_point_id` is updated only after Qdrant upsert succeeds.
- [ ] ShopAIKey failures are recorded as indexing errors.
- [ ] Qdrant failures are recorded as indexing errors and do not mark chunks indexed.
- [ ] No-chunk documents return a clear no-work result or error.
- [ ] Required mocked tests were run and results were reported honestly.
- [ ] Live ShopAIKey/Qdrant/Supabase checks were run only when user setup was available.
- [ ] No semantic search endpoint, GraphRAG, retrieval scoring, chat completion, rerank, agents, or frontend indexing feature was implemented.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [ ] Batch01 - Backend Configuration, Dependencies, Schemas, and Supabase Helpers
- [ ] Batch02 - ShopAIKey Embedding Client
- [ ] Batch03 - Qdrant Collection and Vector Upsert Service
- [ ] Batch04 - Indexing Orchestration and Optional Development Trigger
- [ ] Batch05 - Tests, Smoke Checks, and Handoff

### Task IDs

#### Batch01
- [x] (01A): Add backend-only ShopAIKey and Qdrant configuration
- [x] (01B): Add indexing dependencies without unrelated provider packages
- [x] (01C): Add internal embedding and indexing schemas
- [ ] (01D): Add Supabase helpers for indexing reads and point ID updates

#### Batch02
- [ ] (02A): Implement ShopAIKey embedding request construction
- [ ] (02B): Handle ShopAIKey errors and malformed responses

#### Batch03
- [ ] (03A): Implement Qdrant client initialization and collection setup
- [ ] (03B): Implement Qdrant payload builder and vector upsert helper
- [ ] (03C): Handle Qdrant failures without marking chunks indexed

#### Batch04
- [ ] (04A): Implement `index_document_chunks(document_id)` orchestration
- [ ] (04B): Implement skip, no-work, and partial failure behavior
- [ ] (04C): Add optional development-only indexing endpoint if needed

#### Batch05
- [ ] (05A): Add and run ShopAIKey service tests
- [ ] (05B): Add and run Qdrant service tests
- [ ] (05C): Add and run embedding orchestration tests
- [ ] (05D): Run combined backend tests and scope/security checks
- [ ] (05E): Perform manual indexing and Qdrant/Supabase checks when user setup is available

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
