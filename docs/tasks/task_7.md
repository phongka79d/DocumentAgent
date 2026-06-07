# Plan 7 - Medium GraphRAG Data Model and Graph Builder Execution Tasks

## Purpose

Create a detailed execution task file for the approved medium GraphRAG data model and graph builder milestone. This task file guides a future Execution Agent to extract validated entities from document chunks, persist `document_entities`, persist `document_relationships`, and build the medium graph path `Document -> Section -> Chunk -> Entity -> Relationship` required by `docs/plans/Plan_7.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_7.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Conflict note: `docs/plans/Master_Plan.md` describes the broader medium GraphRAG and retrieval roadmap, including graph-based retrieval expansion in the larger MVP. `docs/plans/Plan_7.md` is narrower and explicitly excludes community detection, graph visualization, hybrid retrieval scoring, Agent 1, and frontend graph APIs. `docs/plans/Plan_7.md` is the scope authority for this task file.

## Source Section Index

- `docs/plans/Plan_7.md` > `## 1. Goal` -> build medium GraphRAG metadata and create persisted entity and relationship rows.
- `docs/plans/Plan_7.md` > `## 2. Why This Plan Exists` -> create the graph layer needed for later hybrid retrieval and Agent 1 scoring.
- `docs/plans/Plan_7.md` > `## 3. Scope` -> entity extraction, validation, persistence, relationship types, graph builder service, and graph tests.
- `docs/plans/Plan_7.md` > `## 4. Out of Scope` -> prohibited community detection, graph visualization, hybrid retrieval scoring, Agent 1, perfect extraction, unvalidated JSON inserts, and frontend graph APIs.
- `docs/plans/Plan_7.md` > `## 5. Dependencies` -> completed Plans 1, 2, and 4; Plan 5 optional; ShopAIKey chat config required when LLM extraction is used.
- `docs/plans/Plan_7.md` > `## 6. Required Files and Folders` -> expected graph builder, extraction service, ShopAIKey, Supabase helpers, graph schemas, tests, and env example.
- `docs/plans/Plan_7.md` > `## 7. Data Model / Schema Changes` -> no database schema changes, existing graph tables, draft schemas, allowed entity types, and allowed relationship types.
- `docs/plans/Plan_7.md` > `## 8. API Design` -> no required public API endpoints and optional development-only graph build endpoint.
- `docs/plans/Plan_7.md` > `## 9. Implementation Steps` -> ordered configuration, chat helper, schemas, extraction, validation, fallback, graph build, de-duplication, relationships, counts, and tests.
- `docs/plans/Plan_7.md` > `## 10. Configuration and Environment Variables` -> backend-only ShopAIKey, graph extraction, and single-user settings.
- `docs/plans/Plan_7.md` > `## 11. Required Tests` -> entity extraction tests, graph builder tests, manual graph checks, SQL checks, and negative checks.
- `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria` -> validated extraction, persisted rows, relationship links, normalized weights, safe rebuilds, invalid JSON handling, and scope boundaries.
- `docs/plans/Plan_7.md` > `## 13. Failure Handling` -> missing document, no chunks, ShopAIKey failure, invalid JSON, database insert failure, and rebuild partial-state reporting.
- `docs/plans/Plan_7.md` > `## 14. Agent Report Requirement` -> required execution report fields and graph count reporting.
- `docs/plans/Plan_7.md` > `## 15. Reviewer Checklist` -> scope, tests, acceptance, secrets, architecture, graph level, validation, scoping, and prompt boundaries.
- `docs/plans/Master_Plan.md` > `## 2. Tech Stack` -> Python, FastAPI, LangChain, LangGraph, Pydantic, Supabase, Qdrant, and ShopAIKey are approved.
- `docs/plans/Master_Plan.md` > `## 3. Authentication Policy` -> single-user MVP and backend-only Supabase, Qdrant, and ShopAIKey secrets.
- `docs/plans/Master_Plan.md` > `## 6. Data Storage Design` > `### 6.2 Supabase PostgreSQL Tables` -> `documents`, `document_chunks`, `document_entities`, and `document_relationships` table fields.
- `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.5 Medium-Level GraphRAG Construction` -> medium graph level, document-section-chunk-entity path, required graph features, entity examples, relationship examples, and no community detection.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> approved backend environment variable names and frontend secret boundary.
- `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure` -> expected backend service locations for `graph_builder.py`, `shopaikey_service.py`, and `supabase_service.py`.

## Approved Architecture Summary

The approved architecture for Plan 7 is a backend-only medium GraphRAG builder for the single-user Document QA Agent MVP. Plans 1, 2, and 4 must already provide the backend foundation, Supabase schema foundation, and persisted `document_chunks` rows. Plan 5 vectors may exist but are not required for graph construction.

The graph builder must load chunks for one document filtered by `SINGLE_USER_ID`, extract entities and candidate entity relationships from chunk text, validate extraction output with Pydantic, and persist only validated graph data. LLM extraction may use ShopAIKey chat completion through the backend-only `SHOPAIKEY_API_KEY`, `SHOPAIKEY_BASE_URL`, and `SHOPAIKEY_CHAT_MODEL` settings. Tests and local development may disable LLM extraction with `GRAPH_EXTRACTION_ENABLED` and use a deterministic fallback that extracts obvious dates and repeated capitalized terms.

The backend must use the existing `document_entities` and `document_relationships` tables. No database table changes are approved. Entity rows must be de-duplicated by normalized entity name, entity type, and document, and must include `user_id = SINGLE_USER_ID`. Relationship rows must represent document-section, section-chunk, chunk-entity, entity-entity, and chunk-chunk links where supported by available metadata. Relationship weights must be numeric and normalized between 0 and 1 where practical.

The graph build must be safely rerunnable. Existing graph rows for the document must be cleared before rebuild to prevent duplicates, and failures after clearing must report the partial state safely. No public frontend graph API is required. An optional development-only backend endpoint may be added only if needed for local triggering and must not be exposed through the frontend.

No community detection, graph visualization, hybrid retrieval scoring, Agent 1 retrieval logic, answer generation, LangGraph workflow, or frontend graph UI is approved in this plan.

## Global Implementation Rules

- Keep `docs/plans/Plan_7.md` as the source of truth for scope, validation, and out-of-scope boundaries.
- Use `docs/plans/Master_Plan.md` only to clarify the approved stack, table fields, single-user policy, environment variable names, and broader architecture boundaries.
- Depend on completed Plan 1, Plan 2, and Plan 4 work; do not reimplement backend foundation, Supabase schema foundation, upload, parsing, or chunking unless a narrow graph integration change is required.
- Do not create or alter database tables.
- Use existing `document_entities` and `document_relationships` tables.
- Keep `SHOPAIKEY_API_KEY`, `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_CHAT_MODEL`, `GRAPH_EXTRACTION_ENABLED`, and `SINGLE_USER_ID` backend-only.
- Use `.env.example` for placeholder names only and never commit real secrets.
- Do not hardcode ShopAIKey model names, API keys, provider URLs, user IDs, entity type lists, or relationship type lists inside business logic when they belong in settings or schema constants.
- Always load documents, chunks, entities, and graph rebuild targets through `SINGLE_USER_ID` where the schema supports user ownership.
- Do not insert unvalidated LLM JSON into Supabase.
- Reject invalid entity types, invalid relationship types, invalid IDs, invalid weights, and malformed extraction structures before persistence.
- Normalize relationship weights to the range `0.0` to `1.0` where practical.
- Clear existing graph rows for the document before rebuild to prevent duplicate rows.
- Report partial rebuild state safely if graph rows were cleared and a later persistence step fails.
- Keep extraction prompts focused on entity and relationship extraction only; do not ask the model to answer user questions.
- Do not expose graph APIs to the frontend in this plan.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, settings, routes, schemas, service helpers, extraction models, relationship builders, and tests.
- Keep functions, services, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, Supabase Python client, and HTTP client conventions for the approved stack.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless the plan explicitly requires them.
- Add comments only where they clarify a non-obvious decision or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Do not add formatter, linter, framework, or architecture changes outside Plan 7 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Graph Configuration, Schemas, and Supabase Contracts
- Batch02 - ShopAIKey Chat and Entity Extraction Service
- Batch03 - Graph Builder Rebuild and Structural Relationships
- Batch04 - Entity Persistence and Relationship Expansion
- Batch05 - Processing Integration, Tests, Smoke Checks, and Handoff

## Mandatory Batch01 - Graph Configuration, Schemas, and Supabase Contracts

### Goal

Prepare backend graph configuration, validated graph schemas, and Supabase helper contracts required by the medium GraphRAG builder.

### Why this batch exists

Graph extraction and graph building must be typed, backend-only, single-user scoped, and ready to persist to the existing graph tables before any LLM output or relationship rows are inserted.

### Inputs / Dependencies

- `docs/plans/Plan_7.md`
- `docs/plans/Master_Plan.md`
- Completed Plan 1 backend foundation and configuration system
- Completed Plan 2 Supabase schema foundation
- Completed Plan 4 persisted `document_chunks` rows
- Existing backend schema and Supabase service patterns

### Tasks

- [x] (01A): Add backend-only graph extraction configuration
  - Source of Truth: `docs/plans/Plan_7.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Master_Plan.md` > `# 15. Environment Variables`
  - Source Requirements:
    - Add `SHOPAIKEY_CHAT_MODEL` to settings and `.env.example` if not already present.
    - Add `GRAPH_EXTRACTION_ENABLED` so tests or local development can use deterministic fallback.
    - Keep ShopAIKey and graph extraction settings backend-only.
  - Details: Extend the existing backend settings and `backend/.env.example` with missing graph extraction variables. Use safe placeholder values only and preserve existing config style.
  - Dependencies: Completed Plan 1 configuration pattern.
  - User Action: User must provide real ShopAIKey values in local `.env` before live LLM extraction can pass.
  - Agent Work: Update backend config and `.env.example`; do not touch frontend env files except to confirm private keys are absent if needed.
  - Output: Backend settings expose graph extraction and ShopAIKey chat model configuration safely.
  - Acceptance: Backend code can read `SHOPAIKEY_CHAT_MODEL` and `GRAPH_EXTRACTION_ENABLED`; `.env.example` contains only non-secret placeholders; frontend files do not reference backend-only graph extraction settings.
  - Validation: Run backend config/import tests or graph tests after implementation; inspect env changes for secret exposure.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live LLM extraction if required ShopAIKey values are missing.
  - Files: `backend/app/core/config.py`, `backend/.env.example`

- [x] (01B): Create validated graph schemas and allowed type constants
  - Source of Truth: `docs/plans/Plan_7.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_7.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Create `backend/app/schemas/graph.py`.
    - Include `EntityDraft`, `RelationshipDraft`, `GraphBuildResult`, and validated LLM output models.
    - Allowed entity types include person, date, organization, policy, contract term, job position, probation period, salary, deadline, condition, and other.
    - Allowed relationship types include document-section, section-chunk, chunk-entity, entity-entity, chunk-chunk, and semantic relationship terms from Plan 7.
  - Details: Define Pydantic models for extraction output, persistence drafts, graph build counts, and graph build errors. Validate required IDs, non-empty names, allowed types, and numeric weights. Keep LLM-facing models separate from persistence models when that makes validation clearer.
  - Dependencies: Existing schema package style.
  - User Action: None.
  - Agent Work: Create graph schema module and export it through the existing schema package style when needed.
  - Output: Typed graph schemas and constants used by extraction, graph building, and tests.
  - Acceptance: Services and tests can import graph models; invalid entity types, relationship types, malformed weights, and malformed extraction structures fail validation before persistence.
  - Validation: `cd backend` then run `pytest tests/test_entity_extraction_service.py -v` after extraction tests exist.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/graph.py`, `backend/app/schemas/__init__.py`

- [x] (01C): Add Supabase graph lookup and persistence helper contracts
  - Source of Truth: `docs/plans/Plan_7.md` > `## 3. Scope`; `docs/plans/Plan_7.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 6. Data Storage Design` > `### 6.2 Supabase PostgreSQL Tables`
  - Source Requirements:
    - Add helpers for chunk lookup, entity inserts, relationship inserts, and clearing graph rows for rebuild.
    - Fetch document and chunks filtered by `SINGLE_USER_ID`.
    - Insert rows into `document_entities`.
    - Insert rows into `document_relationships`.
    - Use existing graph tables without schema changes.
  - Details: Extend `supabase_service.py` with focused helper methods for loading a document, listing chunks, clearing graph rows for a document, inserting entities, finding existing entities for de-duplication, and inserting relationships. Preserve single-user filtering where the table supports it.
  - Dependencies: (01B), completed Plan 2 Supabase schema, completed Plan 4 chunk persistence.
  - User Action: None for mocked tests; real Supabase setup is required for live graph checks.
  - Agent Work: Add helper methods using existing Supabase client conventions and safe error handling.
  - Output: Supabase service supports graph build orchestration without schema changes.
  - Acceptance: Helpers filter document/chunk/entity access by `SINGLE_USER_ID`, clear graph rows by document, and insert only validated entity and relationship payloads.
  - Validation: Mocked graph builder tests; optional SQL checks after live graph build.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live validation if Supabase credentials, tables, or processed chunks are unavailable.
  - Files: `backend/app/services/supabase_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/app/schemas/graph.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/supabase_service.py`

### Required Outputs / Artifacts

- Backend-only graph extraction settings.
- Safe `.env.example` graph extraction placeholders.
- Validated graph schema models and allowed type constants.
- Supabase helper contracts for graph lookup, clearing, entity persistence, and relationship persistence.

### Acceptance Criteria

- `SHOPAIKEY_CHAT_MODEL` is configurable when LLM extraction is enabled.
- `GRAPH_EXTRACTION_ENABLED` can disable LLM extraction for fallback tests or local development.
- Graph schemas reject malformed or unsupported extraction output before persistence.
- Supabase helpers preserve `SINGLE_USER_ID` scoping where the schema supports it.
- No database table changes are added.
- No frontend file references backend-only graph or ShopAIKey settings.

### Required Tests or Validations

- Backend config/import validation.
- `cd backend`
- Entity extraction and graph builder tests after later batches are implemented.
- Changed-file inspection for hardcoded secrets, table migrations, and frontend secret exposure.

### Explicit Non-Goals

- Do not implement entity extraction logic in this batch unless needed for schema validation.
- Do not create database migrations.
- Do not add graph APIs or frontend graph UI.
- Do not implement graph retrieval, hybrid scoring, agents, or answer generation.

## Mandatory Batch02 - ShopAIKey Chat and Entity Extraction Service

### Goal

Implement a backend-only entity extraction service that can use ShopAIKey chat completion for strict JSON extraction or a deterministic fallback for tests and local development.

### Why this batch exists

The graph builder cannot persist reliable entities or relationships until extraction output is structured, validated, safely failed, and available without live LLM calls in tests.

### Inputs / Dependencies

- Batch01 settings and graph schemas
- Existing ShopAIKey service from prior plans, if present
- `docs/plans/Plan_7.md`

### Tasks

- [x] (02A): Add ShopAIKey chat completion helper for structured extraction
  - Source of Truth: `docs/plans/Plan_7.md` > `## 5. Dependencies`; `docs/plans/Plan_7.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 10. Configuration and Environment Variables`
  - Source Requirements:
    - Add `chat_completion(messages, response_format=None)` to `shopaikey_service.py`.
    - Use ShopAIKey chat completion config when LLM extraction is used.
    - Use `SHOPAIKEY_API_KEY`, `SHOPAIKEY_BASE_URL`, and `SHOPAIKEY_CHAT_MODEL`.
    - Keep credentials backend-only.
  - Details: Extend the existing ShopAIKey service with a typed chat completion helper that sends OpenAI-compatible `/chat/completions` requests, uses configured model values, supports optional response format, applies safe timeout behavior, and maps provider failures to safe backend exceptions.
  - Dependencies: (01A), existing ShopAIKey service patterns from prior plans.
  - User Action: User must provide real ShopAIKey chat configuration before live LLM extraction can pass.
  - Agent Work: Implement or extend `shopaikey_service.py` without exposing secrets or changing embedding behavior.
  - Output: Reusable backend chat completion helper for graph extraction.
  - Acceptance: Mocked tests can verify configured model usage, endpoint path, safe auth handling, response parsing, and failure mapping without real credentials.
  - Validation: `cd backend` then run `pytest tests/test_entity_extraction_service.py -v` after extraction tests are added; run existing ShopAIKey service tests if present.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live LLM extraction if ShopAIKey credentials or chat model are missing.
  - Files: `backend/app/services/shopaikey_service.py`, `backend/tests/test_entity_extraction_service.py`

- [x] (02B): Implement strict JSON entity extraction with Pydantic validation
  - Source of Truth: `docs/plans/Plan_7.md` > `## 3. Scope`; `docs/plans/Plan_7.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_7.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_7.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Create `backend/app/services/entity_extraction_service.py`.
    - Implement `extract_entities_for_chunk(chunk)`.
    - Prompt the model to return strict JSON containing entities and relationships only.
    - Validate LLM output with Pydantic before inserting anything.
    - Extraction prompts must not ask the model to answer user questions.
  - Details: Implement extraction orchestration that builds a chunk-focused prompt, calls the chat helper when enabled, parses JSON, validates against graph schemas, attaches the source chunk ID where required, and returns validated entity and relationship drafts without performing database writes.
  - Dependencies: (01B), (02A)
  - User Action: None for mocked tests; real ShopAIKey setup is needed for live LLM extraction.
  - Agent Work: Create the extraction service, prompt builder, parser, and validation flow.
  - Output: Validated extraction results for one chunk.
  - Acceptance: Valid LLM JSON produces typed entity and relationship drafts; unsupported types, missing fields, invalid weights, and malformed JSON are rejected before persistence.
  - Validation: `cd backend` then run `pytest tests/test_entity_extraction_service.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live extraction when ShopAIKey setup is missing and fallback is not enabled.
  - Files: `backend/app/services/entity_extraction_service.py`, `backend/app/schemas/graph.py`, `backend/tests/test_entity_extraction_service.py`

- [x] (02C): Implement deterministic fallback and controlled invalid-output behavior
  - Source of Truth: `docs/plans/Plan_7.md` > `## 4. Out of Scope`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_7.md` > `## 11. Required Tests`; `docs/plans/Plan_7.md` > `## 13. Failure Handling`
  - Source Requirements:
    - If LLM JSON is invalid, return a controlled extraction error or fallback result.
    - Do not insert malformed rows.
    - Add deterministic fallback that extracts obvious dates and repeated capitalized terms if LLM extraction is disabled in tests.
    - Missing or failed ShopAIKey extraction must be reported safely.
  - Details: Add fallback extraction for disabled LLM mode and tests. For enabled LLM mode, handle provider failures and invalid JSON with safe error objects or fallback behavior that is explicit and testable. Never hide malformed data by silently inserting it.
  - Dependencies: (02B)
  - User Action: None for fallback tests.
  - Agent Work: Implement fallback rules, controlled errors, and safe logging.
  - Output: Extraction can run deterministically in tests and fails safely for invalid provider output.
  - Acceptance: Invalid JSON cannot produce persisted graph rows; fallback returns predictable date and repeated-capitalized-term entities; provider errors identify the affected chunk safely.
  - Validation: `cd backend` then run `pytest tests/test_entity_extraction_service.py -v`
  - Blocked Condition: None for mocked/fallback tests.
  - Files: `backend/app/services/entity_extraction_service.py`, `backend/tests/test_entity_extraction_service.py`

- [x] (02D): Add focused entity extraction tests
  - Source of Truth: `docs/plans/Plan_7.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_7.md` > `## 11. Required Tests`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_7.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Add `backend/tests/test_entity_extraction_service.py`.
    - Test valid JSON parsing.
    - Test invalid JSON handling.
    - Test fallback behavior.
    - Negative checks must confirm malformed rows are not inserted.
  - Details: Mock ShopAIKey chat calls and settings. Cover valid extraction, invalid JSON, unsupported entity type, unsupported relationship type, missing required fields, invalid weights, disabled LLM fallback, provider failure, and prompt boundaries.
  - Dependencies: (02A), (02B), (02C)
  - User Action: None.
  - Agent Work: Create extraction tests and run them.
  - Output: Entity extraction test coverage and command result.
  - Acceptance: Tests pass or failures are reported honestly with safe error context.
  - Validation: `cd backend` then `pytest tests/test_entity_extraction_service.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/tests/test_entity_extraction_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/shopaikey_service.py`
- `backend/app/services/entity_extraction_service.py`
- `backend/app/schemas/graph.py`
- `backend/tests/test_entity_extraction_service.py`

### Required Outputs / Artifacts

- ShopAIKey chat completion helper for structured JSON extraction.
- Entity extraction service for one chunk.
- Strict extraction prompt and parser.
- Controlled invalid-output behavior.
- Deterministic fallback behavior for disabled LLM mode.
- Focused entity extraction tests.

### Acceptance Criteria

- Entity extraction can run for chunk content.
- Valid extraction output is represented by graph schemas.
- Invalid LLM JSON is rejected or handled through explicit fallback.
- Unsupported entity and relationship types are rejected.
- Relationship weights are validated and normalized where practical.
- Tests do not require real ShopAIKey credentials.
- Extraction prompts do not ask the model to answer user questions.
- No malformed extraction rows are inserted into Supabase.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_entity_extraction_service.py -v`
- Existing ShopAIKey service tests if the shared service is changed.
- Changed-file inspection for hardcoded secrets and prompt scope.

### Explicit Non-Goals

- Do not write database rows from the extraction service.
- Do not require perfect entity extraction.
- Do not implement graph builder persistence in this batch.
- Do not implement retrieval scoring, Agent 1, chat QA, or frontend graph APIs.

## Mandatory Batch03 - Graph Builder Rebuild and Structural Relationships

### Goal

Implement graph builder orchestration for document and chunk loading, safe rebuild clearing, section node concepts, and structural document-section-chunk relationships.

### Why this batch exists

The graph must represent the required `Document -> Section -> Chunk` structure before chunk entities and entity relationships can be linked consistently.

### Inputs / Dependencies

- Batch01 Supabase graph helpers and graph schemas
- Batch02 extraction service
- Completed Plan 4 chunk metadata, including `section_title` where available

### Tasks

- [x] (03A): Implement `build_document_graph(document_id)` document and chunk loading
  - Source of Truth: `docs/plans/Plan_7.md` > `## 1. Goal`; `docs/plans/Plan_7.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## 3. Authentication Policy`
  - Source Requirements:
    - Create `backend/app/services/graph_builder.py`.
    - Implement `build_document_graph(document_id)`.
    - Fetch document and chunks filtered by `SINGLE_USER_ID`.
    - Missing document returns a clear not-found error.
    - Document with no chunks returns a clear no-chunks error.
  - Details: Add the graph builder entry point that validates the requested document belongs to `SINGLE_USER_ID`, loads chunks in stable chunk order, handles missing/no-chunk cases before clearing existing graph rows, and prepares a result object for counts and errors.
  - Dependencies: (01B), (01C), (02B)
  - User Action: None for mocked tests; processed chunks are required for live graph builds.
  - Agent Work: Create graph builder service and graph build exception/result handling.
  - Output: Graph builder entry point can load a document and chunks safely.
  - Acceptance: Missing documents and no-chunk documents fail with clear safe errors; valid documents proceed to graph build stages.
  - Validation: `cd backend` then run `pytest tests/test_graph_builder.py -v` after graph builder tests are added.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live graph build if no processed document/chunks exist.
  - Files: `backend/app/services/graph_builder.py`, `backend/tests/test_graph_builder.py`

- [x] (03B): Clear existing graph rows safely before rebuild
  - Source of Truth: `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_7.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Clear existing graph rows for the document before rebuild to prevent duplicates.
    - Graph build can be rerun without duplicating old rows.
    - Rebuild failure must not leave duplicate graph rows if rows were cleared first.
    - Report partial state if rebuild fails after clearing.
  - Details: Call Supabase clear helpers only after document and chunk preconditions pass. Clear relationship rows and entity rows for the document using safe document-scoped filters. Track that clear occurred so failures can report partial-state risk.
  - Dependencies: (01C), (03A)
  - User Action: None.
  - Agent Work: Implement rebuild clearing in graph builder and mocked tests for rerun behavior.
  - Output: Rebuilds start from a clean graph state for the document.
  - Acceptance: Rebuilding the same document does not duplicate prior entities or relationships; failures after clearing are reported honestly.
  - Validation: `cd backend` then run `pytest tests/test_graph_builder.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/graph_builder.py`, `backend/app/services/supabase_service.py`, `backend/tests/test_graph_builder.py`

- [x] (03C): Create section node concepts and structural relationships
  - Source of Truth: `docs/plans/Plan_7.md` > `## 1. Goal`; `docs/plans/Plan_7.md` > `## 3. Scope`; `docs/plans/Plan_7.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.5 Medium-Level GraphRAG Construction`
  - Source Requirements:
    - Represent graph path `Document -> Section -> Chunk -> Entity -> Relationship`.
    - Create document-section and section-chunk relationship records where supported by available metadata.
    - For each chunk, create a section node concept from `section_title` or a default section key.
    - Insert `document_contains_section` relationships using source type `document` and target type `section`.
    - Insert `section_contains_chunk` relationships using section key and chunk ID.
  - Details: Derive stable section keys from chunk `section_title`, page metadata, or chunk group defaults. Insert one document-section relationship per section and one section-chunk relationship per chunk. Do not create a new sections table.
  - Dependencies: (03A), (03B)
  - User Action: None.
  - Agent Work: Implement section key derivation, structural relationship payloads, and mocked persistence tests.
  - Output: Persisted document-section and section-chunk relationships for the document.
  - Acceptance: Relationship rows use allowed relationship types, valid source/target types, stable IDs, normalized weights, and safe descriptions.
  - Validation: `cd backend` then run `pytest tests/test_graph_builder.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/graph_builder.py`, `backend/tests/test_graph_builder.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/graph_builder.py`
- `backend/app/services/supabase_service.py`
- `backend/app/schemas/graph.py`
- `backend/tests/test_graph_builder.py`

### Required Outputs / Artifacts

- Graph builder entry point.
- Missing-document and no-chunks failure behavior.
- Document-scoped graph clearing before rebuild.
- Stable section key derivation.
- `document_contains_section` relationships.
- `section_contains_chunk` relationships.

### Acceptance Criteria

- `build_document_graph(document_id)` exists.
- Document and chunks are fetched through `SINGLE_USER_ID`.
- Missing documents and no-chunk documents return clear safe errors.
- Graph rebuilds clear existing graph rows before inserting new rows.
- Rebuilds do not duplicate old graph rows.
- Document-section and section-chunk relationships are persisted with allowed relationship types.
- No database schema changes or section table are added.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_graph_builder.py -v`
- Mocked tests for missing document, no chunks, clear-before-rebuild, section defaults, and structural relationship creation.

### Explicit Non-Goals

- Do not persist entities or entity relationships in this batch unless needed for integrated graph builder tests in Batch04.
- Do not add graph retrieval expansion.
- Do not add graph visualization or frontend APIs.
- Do not implement Agent 1 or hybrid scoring.

## Mandatory Batch04 - Entity Persistence and Relationship Expansion

### Goal

Persist extracted entities, de-duplicate entity rows, create chunk-entity and entity-entity links, add chunk-chunk overlap relationships, and return graph build counts.

### Why this batch exists

The medium GraphRAG layer is useful only when extracted entities are persisted once per document and linked back to chunks and related graph nodes with validated relationship rows.

### Inputs / Dependencies

- Batch02 entity extraction service
- Batch03 graph builder structural relationship flow
- Existing `document_entities` and `document_relationships` tables

### Tasks

- [x] (04A): Extract and persist de-duplicated document entities
  - Source of Truth: `docs/plans/Plan_7.md` > `## 1. Goal`; `docs/plans/Plan_7.md` > `## 3. Scope`; `docs/plans/Plan_7.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Add entity extraction from chunk text.
    - Insert rows into `document_entities`.
    - Insert extracted entities into `document_entities`, de-duplicating by normalized `entity_name`, `entity_type`, and document.
    - `document_entities` rows are created with `user_id = SINGLE_USER_ID`.
  - Details: For each chunk, call the extraction service, normalize entity names for de-duplication, insert new entity rows with document ID, chunk ID where appropriate, user ID, entity type, and description, and reuse existing inserted entity IDs for repeated entities.
  - Dependencies: (02B), (02C), (03A), (03B)
  - User Action: None for mocked/fallback tests; real ShopAIKey setup is required for live LLM extraction unless fallback is enabled.
  - Agent Work: Implement entity extraction loop, de-duplication map, Supabase entity insert calls, and tests for duplicate entities.
  - Output: Persisted, de-duplicated `document_entities` rows for a graph build.
  - Acceptance: Duplicate entity names/types for the same document do not create duplicate rows; rows include `user_id = SINGLE_USER_ID`; invalid extraction results are not inserted.
  - Validation: `cd backend` then run `pytest tests/test_graph_builder.py -v`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live LLM extraction if ShopAIKey setup is missing and fallback is not enabled.
  - Files: `backend/app/services/graph_builder.py`, `backend/app/services/supabase_service.py`, `backend/tests/test_graph_builder.py`

- [x] (04B): Insert chunk-entity and valid entity-entity relationships
  - Source of Truth: `docs/plans/Plan_7.md` > `## 3. Scope`; `docs/plans/Plan_7.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_7.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Insert rows into `document_relationships`.
    - Create chunk-entity and entity-entity relationship records where supported by available metadata.
    - Insert `chunk_mentions_entity` relationships for each extracted entity.
    - Insert `entity_related_to_entity` relationships when extraction returns a valid relation.
    - Database insert failure stops graph build and reports the operation that failed.
  - Details: After entity persistence resolves entity IDs, insert chunk-to-entity relationships for every chunk mention. Resolve extracted entity-to-entity relation endpoints from names to inserted IDs, discard or report invalid unresolved endpoints safely, and persist only allowed relationship types.
  - Dependencies: (04A)
  - User Action: None.
  - Agent Work: Implement relationship resolution, payload validation, Supabase relationship insert calls, and insert-failure handling.
  - Output: Persisted `chunk_mentions_entity` and valid `entity_related_to_entity` relationship rows.
  - Acceptance: Relationship rows point to valid chunk/entity identifiers, use allowed relationship types, have weights in range, and fail safely on insert errors.
  - Validation: `cd backend` then run `pytest tests/test_graph_builder.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/graph_builder.py`, `backend/tests/test_graph_builder.py`

- [x] (04C): Add chunk-chunk relationships from strong entity overlap
  - Source of Truth: `docs/plans/Plan_7.md` > `## 3. Scope`; `docs/plans/Plan_7.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Create chunk-chunk relationship records where supported by available metadata.
    - Add `chunk_related_to_chunk` relationships when chunks share strong entity overlap.
    - Relationship weights are numeric and normalized between 0 and 1 where practical.
  - Details: Compare chunk entity sets after de-duplication. Add chunk-chunk relationships only when overlap is strong enough to be meaningful. Use deterministic weighting, avoid self-links, and avoid duplicate symmetric links.
  - Dependencies: (04A), (04B)
  - User Action: None.
  - Agent Work: Implement overlap scoring and relationship payload creation with tests for threshold, no self-links, and duplicate prevention.
  - Output: Valid `chunk_related_to_chunk` relationships for strongly related chunks.
  - Acceptance: Strong entity overlap produces normalized relationship weights; weak overlap does not create noisy relationships; duplicate chunk-chunk rows are avoided.
  - Validation: `cd backend` then run `pytest tests/test_graph_builder.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/services/graph_builder.py`, `backend/tests/test_graph_builder.py`

- [x] (04D): Return graph build counts and safe failure summaries
  - Source of Truth: `docs/plans/Plan_7.md` > `## 8. API Design`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_7.md` > `## 13. Failure Handling`; `docs/plans/Plan_7.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Return counts for inserted entities and relationships.
    - Optional development-only endpoint response includes `document_id`, `entity_count`, and `relationship_count`.
    - Execution report must include counts for entities and relationships produced in a sample or mocked graph build.
    - ShopAIKey failure marks extraction failure for the affected chunk and reports it.
  - Details: Populate `GraphBuildResult` with document ID, entity count, relationship count, skipped or failed extraction details, and partial-state flags when relevant. Keep error messages safe and free of secrets.
  - Dependencies: (04A), (04B), (04C)
  - User Action: None.
  - Agent Work: Finalize result aggregation and safe error reporting in graph builder.
  - Output: Graph build result counts and safe failure summaries.
  - Acceptance: Successful builds report accurate entity and relationship counts; extraction failures identify affected chunks safely; database failures stop the build with the failed operation name.
  - Validation: `cd backend` then run `pytest tests/test_graph_builder.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/graph_builder.py`, `backend/app/schemas/graph.py`, `backend/tests/test_graph_builder.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/graph_builder.py`
- `backend/app/services/entity_extraction_service.py`
- `backend/app/services/supabase_service.py`
- `backend/app/schemas/graph.py`
- `backend/tests/test_graph_builder.py`

### Required Outputs / Artifacts

- De-duplicated `document_entities` persistence.
- `chunk_mentions_entity` relationships.
- Valid `entity_related_to_entity` relationships.
- Strong-overlap `chunk_related_to_chunk` relationships.
- Accurate `GraphBuildResult` entity and relationship counts.
- Safe extraction and database failure summaries.

### Acceptance Criteria

- Entity extraction runs for document chunks.
- Extracted entities are validated before persistence.
- `document_entities` rows are created with `user_id = SINGLE_USER_ID`.
- Duplicate entities are not inserted repeatedly for the same document.
- `document_relationships` rows represent document-section-chunk-entity links.
- Entity-to-entity relationships are inserted only when endpoints resolve to valid inserted entities.
- Chunk-to-chunk relationships are added only for strong entity overlap.
- Relationship weights are numeric and normalized between 0 and 1 where practical.
- Graph build result reports inserted entity and relationship counts.
- Invalid LLM JSON, ShopAIKey failures, and database failures are handled safely.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_graph_builder.py -v`
- Mocked tests for de-duplication, relationship types, chunk overlap, rebuild behavior, insert failure handling, and result counts.

### Explicit Non-Goals

- Do not implement community detection.
- Do not implement graph visualization.
- Do not implement graph retrieval expansion or hybrid scoring.
- Do not implement Agent 1.
- Do not add frontend graph APIs.

## Mandatory Batch05 - Processing Integration, Tests, Smoke Checks, and Handoff

### Goal

Connect the graph builder to the backend graph build path supported by the current application, prove the graph behavior with tests and smoke checks, and produce an honest handoff report.

### Why this batch exists

Plan 7 completion depends on evidence that processed documents can produce graph rows, graph builds can be rerun safely, and manual/live checks are only claimed when required user setup exists.

### Inputs / Dependencies

- Batch01 through Batch04 implementation
- Existing document processing flow from prior plans
- Local backend test environment
- Optional real ShopAIKey API key, Supabase setup, processed document, and chunks for live checks

### Tasks

- [ ] (05A): Wire graph builder into the supported backend graph build path
  - Source of Truth: `docs/plans/Plan_7.md` > `## 1. Goal`; `docs/plans/Plan_7.md` > `## 8. API Design`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## 5. Core Features` > `### 5.1 Upload Document`; `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.5 Medium-Level GraphRAG Construction`
  - Source Requirements:
    - Processed documents should produce `document_entities` and `document_relationships` rows.
    - Run graph builder for the document after chunks exist.
    - No required public API endpoints exist in this plan.
    - Optional development-only endpoint may be added only if needed.
  - Details: Integrate `build_document_graph(document_id)` at the existing backend processing point after chunks are persisted, if the current project already has a processing orchestration path. If automatic integration is not safe with the current architecture, provide an internal service call or development-only backend trigger and document why. Do not wire any frontend graph API.
  - Dependencies: Batch03, Batch04, existing document processing service or route structure.
  - User Action: User must provide a processed document for live validation.
  - Agent Work: Wire graph build into the narrow supported backend path, add mocked integration coverage, and keep graph failures reported safely.
  - Output: Processed-document graph build path or clearly documented internal/development trigger.
  - Acceptance: A document with chunks can trigger graph building and produce entity and relationship counts without adding frontend graph APIs.
  - Validation: Run graph builder tests and any existing processing tests affected by the integration.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live validation if no processed document/chunks or required provider setup exists.
  - Files: `backend/app/services/graph_builder.py`, existing backend processing service/module, optional development-only API file if needed

- [ ] (05B): Add and run graph builder tests
  - Source of Truth: `docs/plans/Plan_7.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_7.md` > `## 9. Implementation Steps`; `docs/plans/Plan_7.md` > `## 11. Required Tests`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_7.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Add `backend/tests/test_graph_builder.py`.
    - Test entity and relationship persistence with mocked Supabase.
    - Add tests for valid extraction, invalid extraction, de-duplication, relationship types, and rebuild behavior.
    - Build graph for a document with no chunks and expect a clear error.
  - Details: Mock Supabase, extraction service, and settings. Cover missing document, no chunks, clear-before-rebuild, structural relationships, entity de-duplication, chunk mentions, entity related-to relationships, chunk overlap relationships, invalid extraction, ShopAIKey extraction failure, database insert failure, and count reporting.
  - Dependencies: Batch03, Batch04
  - User Action: None.
  - Agent Work: Create graph builder tests and run them.
  - Output: Graph builder test coverage and command result.
  - Acceptance: Tests pass or failures are reported honestly.
  - Validation: `cd backend` then `pytest tests/test_graph_builder.py -v`
  - Blocked Condition: None for mocked tests.
  - Files: `backend/tests/test_graph_builder.py`

- [ ] (05C): Run combined backend tests and scope/security checks
  - Source of Truth: `docs/plans/Plan_7.md` > `## 4. Out of Scope`; `docs/plans/Plan_7.md` > `## 11. Required Tests`; `docs/plans/Plan_7.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_7.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_7.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 3. Authentication Policy`
  - Source Requirements:
    - Run `pytest tests/test_entity_extraction_service.py tests/test_graph_builder.py -v`.
    - Confirm scope was followed.
    - Confirm no hardcoded secrets.
    - Confirm no fake success.
    - Confirm architecture still matches `docs/plans/Master_Plan.md`.
    - Confirm graph level remains medium and does not add community detection.
  - Details: Run required tests and affected regression tests. Inspect changed files for hardcoded keys, frontend secret exposure, community detection, graph visualization, hybrid scoring, Agent 1, frontend graph APIs, answer generation, and unvalidated LLM JSON persistence.
  - Dependencies: (02D), (05B)
  - User Action: None.
  - Agent Work: Run tests, inspect changed files, and report results honestly.
  - Output: Verification evidence for the execution report.
  - Acceptance: Required tests pass or failures are reported honestly; no secret exposure or out-of-scope work is found.
  - Validation: `cd backend` then `pytest tests/test_entity_extraction_service.py tests/test_graph_builder.py -v`; run existing backend regression tests affected by changed config, services, or processing code.
  - Blocked Condition: None for mocked/local tests.
  - Files: Test files and changed implementation files for inspection

- [ ] (05D): Perform manual graph build and SQL checks when user setup is available
  - Source of Truth: `docs/plans/Plan_7.md` > `## 1. Goal`; `docs/plans/Plan_7.md` > `## 5. Dependencies`; `docs/plans/Plan_7.md` > `## 8. API Design`; `docs/plans/Plan_7.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_7.md` > `## 11. Required Tests`; `docs/plans/Plan_7.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Upload and process a sample document.
    - Run graph builder for the document.
    - Query `document_entities` for the document ID.
    - Query `document_relationships` grouped by relationship type for the document ID.
    - Report counts for entities and relationships produced in a sample or mocked graph build.
  - Details: Validate against a real local backend and Supabase only when required `.env` values, processed chunks, and provider setup exist. Run SQL checks safely and do not print secrets. If live setup is unavailable, report mocked-only validation and `BLOCKED_BY_USER_ACTION` for live checks.
  - Dependencies: (05C)
  - User Action: User must provide valid local `.env` values, Supabase setup, and a processed document with chunks. Real ShopAIKey values are required for live LLM extraction unless fallback is explicitly enabled.
  - Agent Work: Run the graph build, query safe counts, capture entity and relationship summaries, and include them in the execution report.
  - Output: Live graph validation evidence or clear blocked-by-user status.
  - Acceptance: `document_entities` contains rows for the document; `document_relationships` contains expected relationship types; counts are reported honestly.
  - Validation: Manual graph build check and SQL checks from Plan 7.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if real credentials, Supabase setup, processed chunks, local backend, or manual confirmation are missing.
  - Files: No tracked files required unless the Execution Agent writes a report artifact.

### Files or Modules Likely Created or Updated

- `backend/app/services/graph_builder.py`
- Existing backend processing service/module if integration is supported by current architecture
- Optional development-only backend route if needed and clearly internal
- `backend/tests/test_entity_extraction_service.py`
- `backend/tests/test_graph_builder.py`
- Execution report artifact created by the future Execution Agent

### Required Outputs / Artifacts

- Supported backend graph build trigger or processing integration.
- Entity extraction test results.
- Graph builder test results.
- Combined required test command result.
- Scope and secret validation notes.
- Manual graph build counts or blocked-by-user status.
- Execution report with files created, files modified, commands run, test results, known issues, out-of-scope notes, and entity/relationship counts from sample or mocked graph build.

### Acceptance Criteria

- Required mocked tests pass or failures are reported honestly.
- Processed documents can trigger graph building through the supported backend path.
- Entity and relationship counts are reported.
- Manual live checks are completed only when user setup exists.
- No hardcoded secrets or frontend provider secret exposure exists.
- No community detection, graph visualization, hybrid retrieval scoring, Agent 1, frontend graph APIs, or answer generation is added.
- Architecture remains aligned with `docs/plans/Master_Plan.md` while keeping Plan 7 scope authority.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_entity_extraction_service.py -v`
- `pytest tests/test_graph_builder.py -v`
- `pytest tests/test_entity_extraction_service.py tests/test_graph_builder.py -v`
- Existing backend regression tests affected by config, service, or processing integration changes.
- Manual graph build check when local setup is available.
- SQL checks for `document_entities` and `document_relationships` when Supabase setup is available.
- Repository search or changed-file inspection for hardcoded secrets, frontend secret exposure, community detection, graph visualization, hybrid scoring, Agent 1, frontend graph APIs, answer generation, and unvalidated LLM JSON inserts.

### Explicit Non-Goals

- Do not fabricate ShopAIKey, Supabase, SQL, or manual graph build results.
- Do not commit `.env` or real secrets.
- Do not weaken tests to avoid failures.
- Do not claim completion for live validation when blocked by missing user setup.
- Do not implement optional future retrieval, scoring, agent, graph visualization, or frontend stages during validation.

## Optional Future Tracks

- Development-only graph build endpoint: This track is not part of the mandatory MVP batch chain unless the Execution Agent determines an internal trigger is needed for local validation. If added, it must remain backend-only/development-only and must not be wired into frontend behavior.
- Graph retrieval expansion: This track is not part of the mandatory Plan 7 batch chain. Later plans may use persisted graph rows to expand retrieval candidates.
- Hybrid retrieval scoring: This track is not part of the mandatory Plan 7 batch chain. Later plans may combine semantic similarity, graph relevance, keyword overlap, metadata match, and position scoring.
- Agent 1 retrieval: This track is not part of the mandatory Plan 7 batch chain. Later plans may consume graph data inside the retrieval agent.
- Community detection: This track is explicitly out of scope for Plan 7.
- Graph visualization and frontend graph APIs: This track is explicitly out of scope for Plan 7.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05

Optional future tracks are outside the mandatory chain.

## Global Verification Checklist

- [ ] `SHOPAIKEY_CHAT_MODEL` exists in backend config when LLM extraction is enabled.
- [ ] `GRAPH_EXTRACTION_ENABLED` exists in backend config or equivalent backend-only settings.
- [ ] Graph extraction settings are present in `backend/.env.example` with placeholders only.
- [ ] No real secret values are committed.
- [ ] No frontend file references ShopAIKey, Supabase service-role, graph extraction, or backend-only provider settings.
- [ ] `backend/app/schemas/graph.py` defines `EntityDraft`, `RelationshipDraft`, `GraphBuildResult`, and validated LLM output models.
- [ ] Entity types are validated against the Plan 7 allowed set.
- [ ] Relationship types are validated against the Plan 7 allowed set.
- [ ] Relationship weights are numeric and normalized between `0.0` and `1.0` where practical.
- [ ] `backend/app/services/shopaikey_service.py` provides `chat_completion(messages, response_format=None)` if not already present.
- [ ] ShopAIKey chat requests use configured backend-only base URL, API key, and chat model.
- [ ] `backend/app/services/entity_extraction_service.py` defines `extract_entities_for_chunk(chunk)` or an equivalent typed service entry point.
- [ ] Extraction prompt asks for strict JSON containing entities and relationships only.
- [ ] Extraction prompt does not ask the model to answer user questions.
- [ ] LLM JSON output is validated with Pydantic before persistence.
- [ ] Invalid LLM JSON is rejected or handled by explicit fallback without inserting malformed rows.
- [ ] Deterministic fallback extracts obvious dates and repeated capitalized terms when LLM extraction is disabled in tests.
- [ ] `backend/app/services/graph_builder.py` defines `build_document_graph(document_id)` or an equivalent typed graph build entry point.
- [ ] Documents and chunks are fetched filtered by `SINGLE_USER_ID`.
- [ ] Missing document returns a clear not-found error.
- [ ] Document with no chunks returns a clear no-chunks error.
- [ ] Existing graph rows for the document are cleared before rebuild.
- [ ] Graph rebuilds do not duplicate old entities or relationships.
- [ ] Rebuild failures after clearing report partial-state risk safely.
- [ ] Section keys are derived from `section_title` or a stable default.
- [ ] `document_contains_section` relationships are created.
- [ ] `section_contains_chunk` relationships are created.
- [ ] Extracted entities are inserted into `document_entities`.
- [ ] `document_entities` rows include `user_id = SINGLE_USER_ID`.
- [ ] Entity rows are de-duplicated by normalized `entity_name`, `entity_type`, and document.
- [ ] `chunk_mentions_entity` relationships are created for extracted entities.
- [ ] `entity_related_to_entity` relationships are created only when relation endpoints are valid.
- [ ] `chunk_related_to_chunk` relationships are created only for strong entity overlap.
- [ ] Database insert failures stop the graph build and report the failed operation safely.
- [ ] Graph build result reports inserted entity and relationship counts.
- [ ] Required mocked tests were run and results were reported honestly.
- [ ] Manual graph build and SQL checks were run only when user setup was available.
- [ ] No database table changes are added.
- [ ] No community detection, graph visualization, hybrid retrieval scoring, Agent 1, frontend graph APIs, or answer generation is implemented.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [x] Batch01 - Graph Configuration, Schemas, and Supabase Contracts
- [x] Batch02 - ShopAIKey Chat and Entity Extraction Service
- [x] Batch03 - Graph Builder Rebuild and Structural Relationships
- [x] Batch04 - Entity Persistence and Relationship Expansion
- [ ] Batch05 - Processing Integration, Tests, Smoke Checks, and Handoff

### Task IDs

#### Batch01
- [x] (01A): Add backend-only graph extraction configuration
- [x] (01B): Create validated graph schemas and allowed type constants
- [x] (01C): Add Supabase graph lookup and persistence helper contracts

#### Batch02
- [x] (02A): Add ShopAIKey chat completion helper for structured extraction
- [x] (02B): Implement strict JSON entity extraction with Pydantic validation
- [x] (02C): Implement deterministic fallback and controlled invalid-output behavior
- [x] (02D): Add focused entity extraction tests

#### Batch03
- [x] (03A): Implement `build_document_graph(document_id)` document and chunk loading
- [x] (03B): Clear existing graph rows safely before rebuild
- [x] (03C): Create section node concepts and structural relationships

#### Batch04
- [x] (04A): Extract and persist de-duplicated document entities
- [x] (04B): Insert chunk-entity and valid entity-entity relationships
- [x] (04C): Add chunk-chunk relationships from strong entity overlap
- [x] (04D): Return graph build counts and safe failure summaries

#### Batch05
- [ ] (05A): Wire graph builder into the supported backend graph build path
- [ ] (05B): Add and run graph builder tests
- [ ] (05C): Run combined backend tests and scope/security checks
- [ ] (05D): Perform manual graph build and SQL checks when user setup is available

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
- reason: missing API key, missing provider project, missing manual setup, missing processed chunks, or other safe summary

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
