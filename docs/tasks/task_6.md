# Plan 6 - Basic Semantic Retrieval Execution Tasks

## Purpose

Create a detailed execution task file for the approved basic semantic retrieval milestone. This task file guides a future Execution Agent to embed user questions with ShopAIKey, search indexed chunks in Qdrant with cosine similarity, always filter by `SINGLE_USER_ID`, optionally filter by selected document IDs, and expose the result contract through `POST /api/retrieval/search` as required by `docs/plans/Plan_6.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_6.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Conflict note: `docs/plans/Master_Plan.md` describes the broader Agent 1 retrieval phase with GraphRAG, keyword scoring, metadata scoring, final scoring, optional rerank, and LangGraph integration. `docs/plans/Plan_6.md` is narrower and explicitly excludes GraphRAG expansion, hybrid scoring, rerank, agents, chat, LangGraph, and frontend search UI. `docs/plans/Plan_6.md` is the scope authority for this task file.

## Source Section Index

- `docs/plans/Plan_6.md` > `## 1. Goal` -> semantic retrieval endpoint using ShopAIKey question embedding, Qdrant search, Top-K chunk results, `SINGLE_USER_ID`, and optional document filters.
- `docs/plans/Plan_6.md` > `## 2. Why This Plan Exists` -> basic vector search primitive and result schema before GraphRAG and hybrid scoring.
- `docs/plans/Plan_6.md` > `## 3. Scope` -> semantic retrieval service, ShopAIKey question embedding, Qdrant user/document filtering, configurable Top-K, API route, payload return, and mocked tests.
- `docs/plans/Plan_6.md` > `## 4. Out of Scope` -> prohibited GraphRAG, hybrid scoring, Agent 1, rerank, chat, LangGraph, and frontend search UI.
- `docs/plans/Plan_6.md` > `## 5. Dependencies` -> completed Plans 1, 2, 4, and 5, with chunks already indexed into Qdrant.
- `docs/plans/Plan_6.md` > `## 6. Required Files and Folders` -> expected retrieval API, service, Qdrant, ShopAIKey, schema, main, and test files.
- `docs/plans/Plan_6.md` > `## 7. Data Model / Schema Changes` -> no database schema changes, request schema, response schema, and Qdrant filter requirements.
- `docs/plans/Plan_6.md` > `## 8. API Design` -> `POST /api/retrieval/search`, request/response bodies, error responses, and validation rules.
- `docs/plans/Plan_6.md` > `## 9. Implementation Steps` -> ordered settings, schemas, service, embedding, Qdrant helper, filters, score mapping, payload/content mapping, route, router registration, and tests.
- `docs/plans/Plan_6.md` > `## 10. Configuration and Environment Variables` -> backend-only retrieval, single-user, ShopAIKey, and Qdrant settings.
- `docs/plans/Plan_6.md` > `## 11. Required Tests` -> unit tests, API checks, selected document check, and negative checks.
- `docs/plans/Plan_6.md` > `## 12. Acceptance Criteria` -> endpoint, embedding, filters, metadata, configurable Top-K, empty-question rejection, and out-of-scope boundaries.
- `docs/plans/Plan_6.md` > `## 13. Failure Handling` -> 400/500 behavior, empty results, malformed payload tolerance, and safe logging.
- `docs/plans/Plan_6.md` > `## 14. Agent Report Requirement` -> required execution report fields and example semantic search response or mocked-test note.
- `docs/plans/Plan_6.md` > `## 15. Reviewer Checklist` -> scope, tests, acceptance, secrets, architecture, user filter, document filter, score semantics, and no final answer generation.
- `docs/plans/Master_Plan.md` > `## 2. Tech Stack` -> Python, FastAPI, Pydantic, Qdrant Cloud, and ShopAIKey OpenAI-compatible API are approved.
- `docs/plans/Master_Plan.md` > `## 3. Authentication Policy` -> single-user MVP and backend-only Supabase, Qdrant, and ShopAIKey secrets.
- `docs/plans/Master_Plan.md` > `## 7. Qdrant Cloud Design` -> `document_chunks` collection, payload fields, `SINGLE_USER_ID` filtering, selected document filters, and no direct frontend Qdrant access.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.3 Top-K Settings` -> `semantic_top_k` default alignment with broader retrieval configuration.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> approved backend environment variable names and frontend secret boundary.
- `docs/plans/Master_Plan.md` > `## Phase 6: Agent 1 Retrieval` -> broader phase alignment while keeping this task limited to Plan 6 semantic search.

## Approved Architecture Summary

The approved architecture for Plan 6 is a backend-only semantic retrieval primitive for the single-user Document QA Agent MVP. Plans 1, 2, 4, and 5 must already provide the FastAPI backend foundation, Supabase metadata and chunk rows, parsed chunks, ShopAIKey embedding client, Qdrant client, indexed vectors, and Qdrant payload metadata.

The backend must expose `POST /api/retrieval/search` under `/api/retrieval`. The request accepts a non-empty `question`, optional `document_ids`, and optional `top_k`. When `top_k` is omitted, the backend uses `RETRIEVAL_SEMANTIC_TOP_K`. The value must be validated between 1 and 50.

The retrieval service must trim and validate the question, embed it through the existing ShopAIKey embedding function, search Qdrant with the query vector, and always include a `user_id = SINGLE_USER_ID` payload filter. When `document_ids` are provided, the Qdrant filter must additionally constrain payload `document_id` to the selected IDs. Results must map Qdrant payloads and scores into the required response fields, including chunk ID, document ID, file name, file type, content or preview, page number, section title, chunk index, and `semantic_similarity`.

If Qdrant payloads do not contain full chunk content, the backend should fetch chunk content from Supabase by `chunk_id` while preserving `SINGLE_USER_ID` ownership. Missing indexed chunks should return HTTP 200 with an empty result list. Malformed or partial payloads should not crash response mapping when nullable schema fields can represent the missing data; malformed points should be logged safely.

No database schema changes are approved in this plan. No GraphRAG expansion, hybrid scoring formula, Agent 1 implementation, rerank, chat endpoint, LangGraph workflow, final answer generation, or frontend search UI is approved.

## Global Implementation Rules

- Keep `docs/plans/Plan_6.md` as the source of truth for scope, validation, and out-of-scope boundaries.
- Depend on completed Plan 1, Plan 2, Plan 4, and Plan 5 work; do not reimplement backend foundation, Supabase schema foundation, parsing, chunking, embedding, or indexing unless a narrow retrieval integration change is required.
- Do not create or alter database tables.
- Do not implement GraphRAG expansion, hybrid scoring, Agent 1, rerank, chat, LangGraph, answer generation, or frontend search UI.
- Keep `SINGLE_USER_ID`, `SHOPAIKEY_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION` backend-only.
- Use `.env.example` for placeholder names only and never commit real secrets.
- Do not hardcode Top-K defaults, ShopAIKey model names, Qdrant collection names, API keys, provider URLs, or user IDs inside business logic.
- Always filter Qdrant search by `user_id = SINGLE_USER_ID`.
- Apply document filtering through Qdrant payload `document_id` only when `document_ids` are provided.
- Validate `question` after trimming whitespace.
- Validate `top_k` so values below 1 or above 50 return HTTP 400.
- Preserve FastAPI/Pydantic invalid UUID behavior so invalid document IDs return HTTP 422.
- Convert Qdrant scores to `semantic_similarity` consistently; document the conversion if the client returns distance instead of similarity.
- Return empty results for no matching chunks instead of treating no results as a failure.
- Use safe public error messages for ShopAIKey and Qdrant failures, with detailed backend logs that do not expose secrets.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, settings, routes, schemas, service helpers, filters, response mappers, and tests.
- Keep functions, services, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, Qdrant client, Supabase Python client, and HTTP client conventions for the approved stack.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless the plan explicitly requires them.
- Add comments only where they clarify a non-obvious decision or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Do not add formatter, linter, framework, or architecture changes outside Plan 6 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Retrieval Configuration, Schemas, and Router Foundation
- Batch02 - Qdrant Filtered Search Helper
- Batch03 - Semantic Retrieval Service and Result Mapping
- Batch04 - Retrieval API Route and Error Handling
- Batch05 - Tests, Smoke Checks, and Handoff

## Mandatory Batch01 - Retrieval Configuration, Schemas, and Router Foundation

### Goal

Prepare backend configuration, retrieval request/response schemas, and route module foundation needed by the semantic retrieval API.

### Why this batch exists

The semantic retrieval endpoint depends on a typed default Top-K setting, validated request/response models, and a backend route module that can be wired without exposing provider configuration to frontend code.

### Inputs / Dependencies

- `docs/plans/Plan_6.md`
- Completed Plan 1 backend foundation and configuration system
- Completed Plan 5 ShopAIKey and Qdrant configuration
- Existing backend schema and API router patterns

### Tasks

- [ ] (01A): Add semantic retrieval Top-K backend configuration
  - Source of Truth: `docs/plans/Plan_6.md` > `## 9. Implementation Steps`; `docs/plans/Plan_6.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.3 Top-K Settings`; `docs/plans/Master_Plan.md` > `# 15. Environment Variables`
  - Source Requirements:
    - Add `RETRIEVAL_SEMANTIC_TOP_K` to backend settings and `.env.example`.
    - `top_k` defaults to `RETRIEVAL_SEMANTIC_TOP_K`.
    - The setting is backend-only and defaults should align with semantic Top-K.
  - Details: Extend the existing backend settings with a typed semantic Top-K default and add a safe placeholder/example to `backend/.env.example`.
  - Dependencies: Completed Plan 1 configuration pattern; completed Plan 5 backend env pattern.
  - User Action: None for local mocked tests; user may tune the value in `.env` for live retrieval behavior.
  - Agent Work: Update backend config and `.env.example` using existing project style.
  - Output: Backend settings expose `RETRIEVAL_SEMANTIC_TOP_K` safely.
  - Acceptance: Retrieval code can read the setting; `.env.example` contains only a non-secret example value; frontend env files do not reference backend-only retrieval/provider secrets.
  - Validation: Run backend config/import tests or retrieval tests after implementation; inspect changed env files for secret exposure.
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/core/config.py`, `backend/.env.example`

- [ ] (01B): Create retrieval request and response schemas
  - Source of Truth: `docs/plans/Plan_6.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_6.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_6.md` > `## 8. API Design`; `docs/plans/Plan_6.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Create `SearchRequest`, `RetrievalResult`, and `SearchResponse` models.
    - Request includes `question`, optional `document_ids`, and optional `top_k`.
    - Response includes `question` and `results`.
    - Results include chunk ID, document ID, file metadata, content/preview, page/section metadata, chunk index, and `semantic_similarity`.
  - Details: Define Pydantic models in `backend/app/schemas/retrieval.py`. Use UUID typing for document and chunk identifiers where appropriate so invalid document IDs produce FastAPI/Pydantic validation errors. Allow nullable metadata fields where Qdrant payloads may omit optional values.
  - Dependencies: Existing schema package style.
  - User Action: None.
  - Agent Work: Create the retrieval schema module and export it through the existing schemas package style when needed.
  - Output: Typed retrieval API request and response models.
  - Acceptance: API and service tests can import the models; schema fields match Plan 6 request and response contracts.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_api.py -v` after API implementation.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/retrieval.py`, `backend/app/schemas/__init__.py`

- [ ] (01C): Prepare retrieval API module without adding behavior outside scope
  - Source of Truth: `docs/plans/Plan_6.md` > `## 3. Scope`; `docs/plans/Plan_6.md` > `## 4. Out of Scope`; `docs/plans/Plan_6.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_6.md` > `## 8. API Design`
  - Source Requirements:
    - Add `backend/app/api/retrieval.py`.
    - The route path is `/api/retrieval/search` once registered.
    - Do not implement frontend search UI, chat, LangGraph, rerank, GraphRAG, or agents.
  - Details: Create or prepare the retrieval router module following existing backend API patterns. Keep route implementation for Batch04 if service dependencies are not ready yet.
  - Dependencies: (01B), existing API package style.
  - User Action: None.
  - Agent Work: Add the router module and imports needed for later route registration.
  - Output: Retrieval API module ready for the search route.
  - Acceptance: Module imports without side effects and does not expose backend-only secrets or unsupported functionality.
  - Validation: Backend import tests after route wiring.
  - Blocked Condition: None.
  - Files: `backend/app/api/retrieval.py`

### Files or Modules Likely Created or Updated

- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/app/schemas/retrieval.py`
- `backend/app/schemas/__init__.py`
- `backend/app/api/retrieval.py`

### Required Outputs / Artifacts

- Backend-only `RETRIEVAL_SEMANTIC_TOP_K` setting.
- Safe `.env.example` placeholder/example for semantic Top-K.
- Retrieval request and response Pydantic schemas.
- Retrieval API router module.

### Acceptance Criteria

- Default semantic Top-K is configurable through backend settings.
- Request and response schemas match Plan 6.
- Invalid document UUIDs can be rejected by schema validation.
- No frontend environment or UI changes expose or consume backend-only provider settings.
- No GraphRAG, hybrid scoring, rerank, chat, LangGraph, agents, or answer generation is added.

### Required Tests or Validations

- Backend import/config validation.
- `cd backend`
- Retrieval API tests after Batch04.
- Changed-file inspection for frontend secret exposure and out-of-scope additions.

### Explicit Non-Goals

- Do not implement semantic retrieval service logic in this batch unless needed for schema import validation.
- Do not create database migrations.
- Do not add frontend search UI.
- Do not add graph, scoring, rerank, chat, or agent behavior.

## Mandatory Batch02 - Qdrant Filtered Search Helper

### Goal

Add a Qdrant vector search helper that applies mandatory single-user filtering, optional selected-document filtering, and consistent score handling.

### Why this batch exists

Semantic retrieval must never query Qdrant without the `SINGLE_USER_ID` filter, and the retrieval service needs one focused helper that hides Qdrant client details while returning mappable chunk points.

### Inputs / Dependencies

- Batch01 configuration foundation
- Completed Plan 5 Qdrant client/service and indexed `document_chunks` collection
- Qdrant payload format from Plan 5 and Master Plan

### Tasks

- [ ] (02A): Implement Qdrant semantic vector search with mandatory user filter
  - Source of Truth: `docs/plans/Plan_6.md` > `## 3. Scope`; `docs/plans/Plan_6.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_6.md` > `## 9. Implementation Steps`; `docs/plans/Plan_6.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 7. Qdrant Cloud Design`
  - Source Requirements:
    - Add `search_vectors(query_vector, top_k, document_ids)` in `backend/app/services/qdrant_service.py`.
    - Always filter by `user_id = SINGLE_USER_ID`.
    - Search the configured Qdrant collection.
    - Use cosine similarity search against indexed chunk vectors.
  - Details: Extend the existing Qdrant service with a typed helper for query-vector search. Build the Qdrant filter using existing client conventions and ensure the `user_id` condition is always present.
  - Dependencies: (01A), completed Plan 5 Qdrant service.
  - User Action: User must have indexed chunks in Qdrant before live retrieval can return non-empty results.
  - Agent Work: Add the search helper using backend-only Qdrant settings and existing Qdrant client initialization.
  - Output: Qdrant search helper returning scored points or equivalent typed search results.
  - Acceptance: Mocked tests prove the user filter is present on every search request and the configured collection is used.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_service.py -v` after service tests are added.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live non-empty retrieval if Qdrant collection or indexed chunks are unavailable.
  - Files: `backend/app/services/qdrant_service.py`

- [ ] (02B): Add optional document ID filtering through Qdrant payload
  - Source of Truth: `docs/plans/Plan_6.md` > `## 1. Goal`; `docs/plans/Plan_6.md` > `## 3. Scope`; `docs/plans/Plan_6.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_6.md` > `## 8. API Design`; `docs/plans/Plan_6.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 7. Qdrant Cloud Design`
  - Source Requirements:
    - If `document_ids` is provided, filter `document_id` in the provided list.
    - `document_ids` can be omitted or empty for all documents owned by `SINGLE_USER_ID`.
    - Reviewer must confirm document filters use payload `document_id`.
  - Details: Implement document filtering only when the caller provides a non-empty list. Convert UUID values to the string format used in Qdrant payloads if the existing payload stores IDs as strings.
  - Dependencies: (02A), retrieval request schema.
  - User Action: None.
  - Agent Work: Add filter construction and tests for omitted, empty, and populated document ID lists.
  - Output: Qdrant helper supports selected-document semantic search.
  - Acceptance: Mocked tests prove selected documents are represented in the Qdrant payload filter and that omitted/empty filters still include the user filter.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/qdrant_service.py`, `backend/tests/test_retrieval_service.py`

- [ ] (02C): Normalize Qdrant score semantics and failure behavior
  - Source of Truth: `docs/plans/Plan_6.md` > `## 8. API Design`; `docs/plans/Plan_6.md` > `## 9. Implementation Steps`; `docs/plans/Plan_6.md` > `## 13. Failure Handling`; `docs/plans/Plan_6.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Convert Qdrant scores to `semantic_similarity`.
    - If Qdrant returns distance instead of similarity, normalize consistently and document the conversion.
    - Qdrant search failure returns HTTP 500 with a safe public message and detailed backend log.
  - Details: Make the helper or retrieval mapper explicit about score interpretation. Keep provider/client exceptions wrapped in a project-specific or existing safe retrieval error so the API can return public-safe 500 responses.
  - Dependencies: (02A)
  - User Action: None.
  - Agent Work: Add score conversion, documentation comment if needed, and safe exception wrapping.
  - Output: Consistent `semantic_similarity` source and safe Qdrant error behavior.
  - Acceptance: Tests verify score mapping and Qdrant failure propagation without leaking secrets.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/qdrant_service.py`, `backend/app/services/retrieval_service.py`, `backend/tests/test_retrieval_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/qdrant_service.py`
- `backend/app/services/retrieval_service.py` if shared exceptions or score mappers are placed there
- `backend/tests/test_retrieval_service.py`

### Required Outputs / Artifacts

- `search_vectors(query_vector, top_k, document_ids)` or equivalent Qdrant helper.
- Mandatory `SINGLE_USER_ID` Qdrant filter.
- Optional payload `document_id` filter.
- Explicit score semantics for `semantic_similarity`.
- Safe Qdrant failure propagation.

### Acceptance Criteria

- Qdrant search never runs without the user filter.
- Document filters use Qdrant payload `document_id`.
- Omitted or empty `document_ids` search all indexed chunks for `SINGLE_USER_ID`.
- Qdrant scores are mapped consistently to `semantic_similarity`.
- Qdrant failures can be returned as safe HTTP 500 errors by the API layer.

### Required Tests or Validations

- Mocked Qdrant search tests.
- `cd backend`
- `pytest tests/test_retrieval_service.py -v`
- Changed-file inspection confirming Qdrant credentials remain backend-only.

### Explicit Non-Goals

- Do not add GraphRAG graph queries.
- Do not add keyword overlap, metadata match, final scoring formula, or hybrid retrieval.
- Do not add rerank.
- Do not expose Qdrant directly to frontend.

## Mandatory Batch03 - Semantic Retrieval Service and Result Mapping

### Goal

Implement the backend semantic retrieval orchestration that validates the question, embeds it with ShopAIKey, searches Qdrant, enriches or maps result content, and returns the Plan 6 response model.

### Why this batch exists

The API route should stay thin. The retrieval service owns the semantic search workflow, dependency calls, payload-to-response mapping, and safe handling of empty or malformed search results.

### Inputs / Dependencies

- Batch01 schemas and setting
- Batch02 Qdrant search helper
- Completed Plan 5 ShopAIKey embedding service
- Existing Supabase service patterns for chunk lookup
- Indexed chunks in Qdrant for live validation

### Tasks

- [ ] (03A): Implement `semantic_search(question, document_ids=None, top_k=None)` orchestration
  - Source of Truth: `docs/plans/Plan_6.md` > `## 1. Goal`; `docs/plans/Plan_6.md` > `## 3. Scope`; `docs/plans/Plan_6.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_6.md` > `## 8. API Design`; `docs/plans/Plan_6.md` > `## 9. Implementation Steps`; `docs/plans/Plan_6.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Create `backend/app/services/retrieval_service.py`.
    - Add `semantic_search(question, document_ids=None, top_k=None)`.
    - Trim and validate the question before embedding.
    - Call `create_embedding(question)` from `shopaikey_service.py`.
    - Use `RETRIEVAL_SEMANTIC_TOP_K` when `top_k` is omitted.
    - `top_k` must be between 1 and 50.
  - Details: Implement a typed service entry point that trims whitespace, rejects empty questions, resolves default Top-K, validates bounds, calls ShopAIKey, and delegates vector search to Qdrant.
  - Dependencies: (01A), (01B), Batch02, completed Plan 5 ShopAIKey service.
  - User Action: User must provide a real ShopAIKey API key before live embedding calls can pass.
  - Agent Work: Add the service module, validation errors, dependency calls, and tests with mocked ShopAIKey/Qdrant.
  - Output: Semantic retrieval service entry point.
  - Acceptance: Mocked tests prove empty question rejection, default Top-K, Top-K bounds, embedding call input, and Qdrant delegation.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_service.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live retrieval if `SHOPAIKEY_API_KEY` or provider setup is missing.
  - Files: `backend/app/services/retrieval_service.py`, `backend/tests/test_retrieval_service.py`

- [ ] (03B): Map Qdrant payload fields into retrieval results
  - Source of Truth: `docs/plans/Plan_6.md` > `## 3. Scope`; `docs/plans/Plan_6.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_6.md` > `## 9. Implementation Steps`; `docs/plans/Plan_6.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_6.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## 7. Qdrant Cloud Design`
  - Source Requirements:
    - Return chunk content and metadata from Supabase/Qdrant payload.
    - Results include chunk ID, document ID, file name, file type, content, content preview, page number, section title, chunk index, and `semantic_similarity`.
    - Missing payload fields should not crash response mapping; use nulls where schema allows them and log malformed points.
  - Details: Convert Qdrant points into `RetrievalResult` objects. Use Qdrant payload fields directly when present. Treat required identity fields carefully; skip or log points that cannot be safely identified.
  - Dependencies: (01B), Batch02, (03A)
  - User Action: None for mocked tests.
  - Agent Work: Implement response mapping and tests for complete payloads, optional missing fields, malformed points, and score mapping.
  - Output: Retrieval response results match Plan 6 schema.
  - Acceptance: Tests verify payload field mapping, nullable metadata behavior, and no crash on malformed optional payload fields.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/retrieval_service.py`, `backend/app/schemas/retrieval.py`, `backend/tests/test_retrieval_service.py`

- [ ] (03C): Fetch full chunk content from Supabase when Qdrant payload has only preview
  - Source of Truth: `docs/plans/Plan_6.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_6.md` > `## 9. Implementation Steps`; `docs/plans/Plan_6.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## 3. Authentication Policy`; `docs/plans/Master_Plan.md` > `## 6.2 Supabase PostgreSQL Tables` > `## Table: document_chunks`
  - Source Requirements:
    - If full chunk content is not stored in Qdrant payload, fetch it from Supabase by `chunk_id`.
    - Missing indexed chunks returns HTTP 200 with an empty results list.
    - Backend access must preserve single-user ownership.
  - Details: Add or reuse Supabase helper methods to fetch chunk content by chunk IDs for `SINGLE_USER_ID`. Merge Supabase `content` into result objects while retaining Qdrant `content_preview`. If chunk rows are absent, return safe nullable content/preview behavior or omit points according to the schema and tests.
  - Dependencies: (03B), existing Supabase service patterns.
  - User Action: User must have Supabase setup and indexed chunks before live content enrichment can be fully validated.
  - Agent Work: Add focused Supabase retrieval helper only if existing helpers do not already support this lookup.
  - Output: Retrieval results include full chunk content when available.
  - Acceptance: Mocked tests prove chunk content lookup is filtered by `SINGLE_USER_ID` and merged correctly; missing rows do not crash retrieval.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_service.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live content enrichment if Supabase setup or chunk rows are missing.
  - Files: `backend/app/services/retrieval_service.py`, `backend/app/services/supabase_service.py`, `backend/tests/test_retrieval_service.py`

- [ ] (03D): Handle ShopAIKey failures, empty result sets, and safe logging
  - Source of Truth: `docs/plans/Plan_6.md` > `## 8. API Design`; `docs/plans/Plan_6.md` > `## 11. Required Tests`; `docs/plans/Plan_6.md` > `## 13. Failure Handling`; `docs/plans/Plan_6.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - ShopAIKey embedding failure returns HTTP 500 with a safe public message and detailed backend log.
    - Missing indexed chunks returns HTTP 200 with an empty results list.
    - The execution report must include an example semantic search response or state that only mocked tests were run.
  - Details: Wrap ShopAIKey provider failures in retrieval errors that the API can translate to public-safe 500 responses. Ensure Qdrant no-match responses return an empty `results` list.
  - Dependencies: (03A), (03B)
  - User Action: User must provide real credentials and indexed chunks before live semantic response examples can be produced.
  - Agent Work: Add error handling and tests for provider failure and empty search results.
  - Output: Safe service behavior for provider failures and no-match retrieval.
  - Acceptance: Tests verify ShopAIKey failure handling, empty result list behavior, and no secret leakage in public errors.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_service.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live response example if provider credentials or indexed chunks are unavailable.
  - Files: `backend/app/services/retrieval_service.py`, `backend/tests/test_retrieval_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/retrieval_service.py`
- `backend/app/services/supabase_service.py`
- `backend/app/services/shopaikey_service.py` if narrow reuse/export adjustments are needed
- `backend/app/services/qdrant_service.py`
- `backend/app/schemas/retrieval.py`
- `backend/tests/test_retrieval_service.py`

### Required Outputs / Artifacts

- Semantic retrieval service.
- Question trimming and validation.
- Configurable/default Top-K resolution and bounds validation.
- ShopAIKey question embedding call.
- Qdrant search delegation with filters.
- Result mapper from Qdrant/Supabase to response schema.
- Safe empty-result, malformed-payload, and provider-failure handling.

### Acceptance Criteria

- Empty or whitespace-only questions are rejected.
- Omitted `top_k` uses backend default.
- `top_k` outside 1 to 50 is rejected.
- ShopAIKey embedding service is called with the trimmed question.
- Qdrant search is delegated with the embedded query vector and filters.
- Retrieval results include required chunk fields and `semantic_similarity`.
- Missing optional metadata fields do not crash response mapping.
- No matching indexed chunks return an empty `results` list.
- Provider failures are safe for public API responses and detailed only in backend logs.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_retrieval_service.py -v`
- Mocked tests for ShopAIKey, Qdrant, and Supabase dependencies.
- Changed-file inspection for no hardcoded secrets.

### Explicit Non-Goals

- Do not implement Agent 1 retrieval.
- Do not implement graph expansion, keyword overlap, metadata scoring, final scoring, rerank, verification, answer generation, chat, or LangGraph.
- Do not add database schema changes.
- Do not fabricate live semantic search examples.

## Mandatory Batch04 - Retrieval API Route and Error Handling

### Goal

Expose the semantic retrieval service through `POST /api/retrieval/search` with the required request/response contract and safe error mapping.

### Why this batch exists

The retrieval primitive must be available through a backend API route before later agent and chat plans can depend on it.

### Inputs / Dependencies

- Batch01 schemas and router foundation
- Batch03 retrieval service
- Existing FastAPI main/router registration pattern

### Tasks

- [ ] (04A): Implement `POST /api/retrieval/search`
  - Source of Truth: `docs/plans/Plan_6.md` > `## 1. Goal`; `docs/plans/Plan_6.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_6.md` > `## 8. API Design`; `docs/plans/Plan_6.md` > `## 9. Implementation Steps`; `docs/plans/Plan_6.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Implement `/api/retrieval/search` in `backend/app/api/retrieval.py`.
    - Method is `POST`.
    - Request body includes `question`, `document_ids`, and `top_k`.
    - Response body includes `question` and `results`.
  - Details: Add a thin route that accepts `SearchRequest`, delegates to `semantic_search`, and returns `SearchResponse`. Keep route code focused on HTTP concerns.
  - Dependencies: Batch03.
  - User Action: None for mocked API tests.
  - Agent Work: Implement the route using existing dependency/error patterns.
  - Output: Backend search endpoint exists.
  - Acceptance: API tests can call the route and receive the expected response contract.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_api.py -v`
  - Blocked Condition: None for mocked API tests.
  - Files: `backend/app/api/retrieval.py`, `backend/tests/test_retrieval_api.py`

- [ ] (04B): Register retrieval router under `/api/retrieval`
  - Source of Truth: `docs/plans/Plan_6.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_6.md` > `## 8. API Design`; `docs/plans/Plan_6.md` > `## 9. Implementation Steps`; `docs/plans/Plan_6.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Register retrieval router in `backend/app/main.py`.
    - Route path must be `/api/retrieval/search`.
  - Details: Wire the router using the existing FastAPI application registration style. Avoid changing unrelated routes.
  - Dependencies: (04A)
  - User Action: None.
  - Agent Work: Update application startup/router registration.
  - Output: API route is reachable at the required path.
  - Acceptance: Route appears in tests and responds under `/api/retrieval/search`.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_api.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/main.py`, `backend/app/api/retrieval.py`

- [ ] (04C): Map validation and dependency errors to required HTTP responses
  - Source of Truth: `docs/plans/Plan_6.md` > `## 8. API Design`; `docs/plans/Plan_6.md` > `## 11. Required Tests`; `docs/plans/Plan_6.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Empty question returns HTTP 400.
    - `top_k` outside allowed range returns HTTP 400.
    - Invalid document UUID returns HTTP 422.
    - ShopAIKey embedding failure returns HTTP 500.
    - Qdrant search failure returns HTTP 500.
    - Missing indexed chunks returns HTTP 200 with an empty results list.
  - Details: Convert retrieval validation and dependency failures into the required HTTP statuses. Let Pydantic/FastAPI handle invalid UUID shape where possible. Keep 500 response messages safe and generic.
  - Dependencies: (04A), Batch03 error types.
  - User Action: None for mocked tests.
  - Agent Work: Add error mapping and API tests for negative cases.
  - Output: API error behavior matches Plan 6.
  - Acceptance: API tests cover empty question, Top-K bounds, invalid UUID, ShopAIKey failure, Qdrant failure, and empty result response.
  - Validation: `cd backend` then run `pytest tests/test_retrieval_api.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/api/retrieval.py`, `backend/tests/test_retrieval_api.py`

### Files or Modules Likely Created or Updated

- `backend/app/api/retrieval.py`
- `backend/app/main.py`
- `backend/app/schemas/retrieval.py`
- `backend/app/services/retrieval_service.py`
- `backend/tests/test_retrieval_api.py`

### Required Outputs / Artifacts

- `POST /api/retrieval/search`.
- Router registered under `/api/retrieval`.
- HTTP response contract for successful search.
- HTTP error contract for validation and dependency failures.
- API route tests.

### Acceptance Criteria

- `/api/retrieval/search` exists and accepts POST requests.
- Valid requests return `question` and `results`.
- Empty question returns HTTP 400.
- Invalid `top_k` returns HTTP 400.
- Invalid document UUID returns HTTP 422.
- ShopAIKey and Qdrant failures return HTTP 500 with safe messages.
- Empty Qdrant results return HTTP 200 with an empty `results` list.
- No frontend search UI, chat, agent, or answer-generation behavior is added.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_retrieval_api.py -v`
- Manual curl checks from Batch05 when local backend and setup are available.
- Route inspection confirming the path is `/api/retrieval/search`.

### Explicit Non-Goals

- Do not add frontend API client or UI.
- Do not add `/api/chat/ask`.
- Do not add Agent 1, Agent 2, Agent 3, LangGraph, rerank, or final answer generation.
- Do not expose backend-only secrets in HTTP responses.

## Mandatory Batch05 - Tests, Smoke Checks, and Handoff

### Goal

Prove the semantic retrieval service, API contract, Qdrant filters, failure handling, scope boundaries, and optional live search path with focused tests and an honest execution report.

### Why this batch exists

Plan 6 completion depends on evidence that mocked behavior passes, external-service live checks are run only when setup exists, and backend-only secret and scope boundaries are preserved.

### Inputs / Dependencies

- Batch01 through Batch04 implementation
- Local backend test environment
- Optional real ShopAIKey API key, Qdrant Cloud project/API key, Supabase setup, and indexed chunks for live checks

### Tasks

- [ ] (05A): Add and run retrieval service tests
  - Source of Truth: `docs/plans/Plan_6.md` > `## 3. Scope`; `docs/plans/Plan_6.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_6.md` > `## 11. Required Tests`; `docs/plans/Plan_6.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_6.md` > `## 13. Failure Handling`; `docs/plans/Plan_6.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Add `backend/tests/test_retrieval_service.py`.
    - Test semantic retrieval behavior with mocked dependencies.
    - Test empty question, default Top-K, Top-K bounds, document filter, Qdrant result mapping, and dependency errors.
    - Confirm Qdrant is never queried without the user filter.
    - Confirm document filters use payload `document_id`.
    - Confirm score semantics are documented.
  - Details: Mock ShopAIKey, Qdrant, Supabase, and settings as needed. Verify validation, dependency call order, filter construction, result mapping, empty results, malformed payload tolerance, and safe error behavior.
  - Dependencies: Batch02, Batch03.
  - User Action: None.
  - Agent Work: Create or update tests and run them.
  - Output: Retrieval service test coverage and command result.
  - Acceptance: Tests pass or failures are reported honestly with safe error context.
  - Validation: `cd backend` then `pytest tests/test_retrieval_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/tests/test_retrieval_service.py`

- [ ] (05B): Add and run retrieval API tests
  - Source of Truth: `docs/plans/Plan_6.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_6.md` > `## 8. API Design`; `docs/plans/Plan_6.md` > `## 11. Required Tests`; `docs/plans/Plan_6.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_6.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Add `backend/tests/test_retrieval_api.py`.
    - Test API validation and response contract.
    - Negative checks include empty question, `top_k = 0`, and `top_k = 1000`.
    - Invalid document UUID returns 422.
  - Details: Use the existing FastAPI test client pattern. Mock the retrieval service so API tests do not require real ShopAIKey, Qdrant, or Supabase credentials.
  - Dependencies: Batch04.
  - User Action: None.
  - Agent Work: Create or update tests and run them.
  - Output: Retrieval API test coverage and command result.
  - Acceptance: Tests pass or failures are reported honestly.
  - Validation: `cd backend` then `pytest tests/test_retrieval_api.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/tests/test_retrieval_api.py`

- [ ] (05C): Run combined backend tests and scope/security checks
  - Source of Truth: `docs/plans/Plan_6.md` > `## 4. Out of Scope`; `docs/plans/Plan_6.md` > `## 11. Required Tests`; `docs/plans/Plan_6.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_6.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_6.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 3. Authentication Policy`
  - Source Requirements:
    - Run required tests.
    - Confirm scope was followed.
    - Confirm no hardcoded secrets.
    - Confirm no fake success.
    - Confirm architecture still matches `docs/plans/Master_Plan.md`.
    - Confirm no final answer generation was added.
  - Details: Run the combined required pytest command and inspect changed files for hardcoded keys, frontend secret exposure, GraphRAG, hybrid scoring, rerank, Agent 1, chat, LangGraph, answer generation, and frontend UI work.
  - Dependencies: (05A), (05B)
  - User Action: None.
  - Agent Work: Run tests, inspect changed files, and report results honestly.
  - Output: Verification evidence for the execution report.
  - Acceptance: Required tests pass or failures are reported honestly; no secret exposure or out-of-scope work is found.
  - Validation: `cd backend` then `pytest tests/test_retrieval_service.py tests/test_retrieval_api.py -v`; run existing backend regression tests affected by changed config/API/service code.
  - Blocked Condition: None for mocked/local tests.
  - Files: Test files and changed implementation files for inspection

- [ ] (05D): Perform manual semantic retrieval checks when user setup is available
  - Source of Truth: `docs/plans/Plan_6.md` > `## 1. Goal`; `docs/plans/Plan_6.md` > `## 5. Dependencies`; `docs/plans/Plan_6.md` > `## 8. API Design`; `docs/plans/Plan_6.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_6.md` > `## 11. Required Tests`; `docs/plans/Plan_6.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_6.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Run the API check curl command.
    - Run the selected document check curl command.
    - Negative checks: empty question returns HTTP 400, `top_k = 0` returns HTTP 400, and `top_k = 1000` returns HTTP 400.
    - The execution report must include one example semantic search response or a note that only mocked tests were run.
  - Details: Validate against the local backend only when required `.env` values, Supabase setup, ShopAIKey credentials, Qdrant credentials, and indexed chunks exist. Use safe sample questions and never print secrets.
  - Dependencies: (05C)
  - User Action: User must provide valid local `.env` values, Qdrant Cloud project/API key, ShopAIKey API key, Supabase setup, and indexed chunks before live retrieval checks can pass.
  - Agent Work: Start or use the local backend, run the curl checks, capture safe response summaries, and include one example response or mocked-only note in the execution report.
  - Output: Live semantic retrieval validation evidence or clear blocked-by-user status.
  - Acceptance: Search returns scored chunks filtered by `SINGLE_USER_ID`; selected document filtering works; negative checks return required status codes.
  - Validation: Manual API check, selected document check, and negative curl checks from Plan 6.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if real credentials, Supabase setup, Qdrant collection, indexed chunks, local backend, or manual confirmation are missing.
  - Files: No tracked files required unless the Execution Agent writes a report artifact.

### Files or Modules Likely Created or Updated

- `backend/tests/test_retrieval_service.py`
- `backend/tests/test_retrieval_api.py`
- Changed implementation files from prior batches
- Execution report artifact created by the future Execution Agent

### Required Outputs / Artifacts

- Mocked retrieval service tests.
- Mocked retrieval API tests.
- Combined backend test command result.
- Scope and secret validation notes.
- Manual semantic retrieval result or blocked-by-user status.
- Execution report with files created, files modified, commands run, test results, known issues, out-of-scope notes, and one example semantic search response or mocked-only note.

### Acceptance Criteria

- `pytest tests/test_retrieval_service.py -v` passes or failures are reported honestly.
- `pytest tests/test_retrieval_api.py -v` passes or failures are reported honestly.
- Combined required test command passes or failures are reported honestly.
- `/api/retrieval/search` exists.
- Question embedding uses ShopAIKey embedding service.
- Qdrant search always filters by `SINGLE_USER_ID`.
- Optional document ID filtering works through payload `document_id`.
- Results include chunk ID, document ID, file name, content or preview, metadata, and `semantic_similarity`.
- Top-K is configurable and validated.
- Empty questions are rejected.
- Missing indexed chunks return HTTP 200 with an empty results list.
- ShopAIKey and Qdrant failures return safe public HTTP 500 errors.
- No hardcoded secrets or frontend provider secret exposure exists.
- No GraphRAG, hybrid scoring, rerank, Agent 1, LangGraph, chat, frontend search UI, or final answer generation is added.
- Live checks are completed only when user setup exists; otherwise the blocked condition is documented.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_retrieval_service.py -v`
- `pytest tests/test_retrieval_api.py -v`
- `pytest tests/test_retrieval_service.py tests/test_retrieval_api.py -v`
- Existing backend regression tests affected by changed config, API, or service code.
- Manual semantic retrieval curl check when local setup is available.
- Manual selected-document curl check when local setup is available.
- Manual negative curl checks for empty question and invalid Top-K values.
- Repository search or changed-file inspection for hardcoded secrets, frontend secret exposure, GraphRAG, hybrid scoring, rerank, Agent 1, LangGraph, chat, frontend search UI, and answer generation.

### Explicit Non-Goals

- Do not fabricate ShopAIKey, Qdrant, Supabase, or manual check results.
- Do not commit `.env` or real secrets.
- Do not weaken tests to avoid failures.
- Do not claim completion for live validation when blocked by missing user setup.
- Do not implement optional future agent, graph, scoring, rerank, chat, answer, or frontend stages during validation.

## Optional Future Tracks

- GraphRAG expansion: This track is not part of the mandatory MVP batch chain. Later plans may use graph entities and relationships to expand retrieval candidates.
- Hybrid scoring formula: This track is not part of the mandatory MVP batch chain. Later plans may combine semantic similarity, graph relevance, keyword overlap, metadata match, and recency or position score.
- Agent 1 retrieval: This track is not part of the mandatory MVP batch chain. Later plans may wrap semantic retrieval and graph retrieval into an agent output schema.
- Rerank: This track is not part of the mandatory MVP batch chain. Later plans may call ShopAIKey rerank when explicitly enabled.
- Chat, LangGraph, verification, answer generation, and self-check: This track is not part of the mandatory MVP batch chain. Later plans may implement the full multi-agent workflow.
- Frontend search UI: This track is not part of the mandatory MVP batch chain and must not be added unless a later frontend plan requires it.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05

Optional future tracks are outside the mandatory chain.

## Global Verification Checklist

- [ ] `RETRIEVAL_SEMANTIC_TOP_K` exists in backend config.
- [ ] `RETRIEVAL_SEMANTIC_TOP_K` is present in `backend/.env.example` with a non-secret example value.
- [ ] No real secret values are committed.
- [ ] No frontend file references ShopAIKey, Qdrant, Supabase service-role, or backend-only retrieval secrets.
- [ ] `backend/app/schemas/retrieval.py` defines `SearchRequest`, `RetrievalResult`, and `SearchResponse`.
- [ ] `backend/app/services/retrieval_service.py` defines `semantic_search(question, document_ids=None, top_k=None)` or an equivalent typed service entry point.
- [ ] Question text is trimmed before validation and embedding.
- [ ] Empty or whitespace-only questions return HTTP 400.
- [ ] Omitted `top_k` uses `RETRIEVAL_SEMANTIC_TOP_K`.
- [ ] `top_k` values below 1 or above 50 return HTTP 400.
- [ ] Invalid document UUID values return HTTP 422.
- [ ] ShopAIKey question embedding uses the existing embedding service.
- [ ] Qdrant vector search uses the configured collection.
- [ ] Qdrant vector search always filters by `user_id = SINGLE_USER_ID`.
- [ ] Optional selected document filtering uses Qdrant payload `document_id`.
- [ ] Qdrant score semantics are documented or otherwise explicit.
- [ ] Results map chunk ID, document ID, file name, file type, content or preview, page number, section title, chunk index, and `semantic_similarity`.
- [ ] Full chunk content is fetched from Supabase when Qdrant payload only has preview and the lookup preserves `SINGLE_USER_ID`.
- [ ] Missing indexed chunks return HTTP 200 with an empty `results` list.
- [ ] Missing optional payload fields do not crash response mapping.
- [ ] ShopAIKey failures return safe public HTTP 500 errors and detailed backend logs without secrets.
- [ ] Qdrant failures return safe public HTTP 500 errors and detailed backend logs without secrets.
- [ ] `POST /api/retrieval/search` is registered under `/api/retrieval`.
- [ ] Required mocked tests were run and results were reported honestly.
- [ ] Manual live semantic checks were run only when user setup was available.
- [ ] No GraphRAG expansion, hybrid scoring, rerank, Agent 1, chat, LangGraph, answer generation, or frontend search UI was implemented.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [ ] Batch01 - Retrieval Configuration, Schemas, and Router Foundation
- [ ] Batch02 - Qdrant Filtered Search Helper
- [ ] Batch03 - Semantic Retrieval Service and Result Mapping
- [ ] Batch04 - Retrieval API Route and Error Handling
- [ ] Batch05 - Tests, Smoke Checks, and Handoff

### Task IDs

#### Batch01
- [ ] (01A): Add semantic retrieval Top-K backend configuration
- [ ] (01B): Create retrieval request and response schemas
- [ ] (01C): Prepare retrieval API module without adding behavior outside scope

#### Batch02
- [ ] (02A): Implement Qdrant semantic vector search with mandatory user filter
- [ ] (02B): Add optional document ID filtering through Qdrant payload
- [ ] (02C): Normalize Qdrant score semantics and failure behavior

#### Batch03
- [ ] (03A): Implement `semantic_search(question, document_ids=None, top_k=None)` orchestration
- [ ] (03B): Map Qdrant payload fields into retrieval results
- [ ] (03C): Fetch full chunk content from Supabase when Qdrant payload has only preview
- [ ] (03D): Handle ShopAIKey failures, empty result sets, and safe logging

#### Batch04
- [ ] (04A): Implement `POST /api/retrieval/search`
- [ ] (04B): Register retrieval router under `/api/retrieval`
- [ ] (04C): Map validation and dependency errors to required HTTP responses

#### Batch05
- [ ] (05A): Add and run retrieval service tests
- [ ] (05B): Add and run retrieval API tests
- [ ] (05C): Run combined backend tests and scope/security checks
- [ ] (05D): Perform manual semantic retrieval checks when user setup is available

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
- reason: missing API key, missing provider project, missing manual setup, missing indexed chunks, or other safe summary

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
