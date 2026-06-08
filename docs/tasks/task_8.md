# Plan 8 - Hybrid Retrieval and Scoring Execution Tasks

## Purpose

Create a detailed execution task file for the approved hybrid retrieval and scoring milestone. This task file guides a future Execution Agent to combine semantic candidates and graph candidates, normalize score components, apply the required final scoring formula, and return final Top-K ranked chunks required by `docs/plans/Plan_8.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_8.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Current project context reviewed: `README.md`
- Conflict note: `docs/plans/Master_Plan.md` aligns with Plan 8 on Agent 1 retrieval steps, Top-K settings, scoring formula, optional rerank, and output schema. `README.md` describes the current semantic retrieval service and Plan 7 graph foundation. `docs/plans/Plan_8.md` remains the scope authority for this task file.

## Source Section Index

- `docs/plans/Plan_8.md` > `## 1. Goal` -> hybrid retrieval goal and required score component output.
- `docs/plans/Plan_8.md` > `## 2. Why This Plan Exists` -> transparent scoring layer before Agent 1.
- `docs/plans/Plan_8.md` > `## 3. Scope` -> graph lookup, candidate merge, normalization, keyword, metadata, position, formula, rerank placeholder, Top-K, and tests.
- `docs/plans/Plan_8.md` > `## 4. Out of Scope` -> prohibited Agent 1 wrapper, evidence verification, answer generation, unguarded rerank, chat API, and frontend UI.
- `docs/plans/Plan_8.md` > `## 5. Dependencies` -> completed Plan 5, Plan 6, and Plan 7 requirements.
- `docs/plans/Plan_8.md` > `## 6. Required Files and Folders` -> expected hybrid retrieval service, graph retrieval service, scoring utility, retrieval schemas, ShopAIKey rerank helper, and tests.
- `docs/plans/Plan_8.md` > `## 7. Data Model / Schema Changes` -> no database schema changes, hybrid candidate schema, exact final score formula, and normalization bounds.
- `docs/plans/Plan_8.md` > `## 8. API Design` -> no required public API endpoint and optional `mode` field for `/api/retrieval/search`.
- `docs/plans/Plan_8.md` > `## 9. Implementation Steps` -> ordered configuration, scoring, graph retrieval, hybrid retrieval, merge, scoring, sort, rerank, and tests.
- `docs/plans/Plan_8.md` > `## 10. Configuration and Environment Variables` -> backend-only retrieval and rerank settings.
- `docs/plans/Plan_8.md` > `## 11. Required Tests` -> scoring, graph retrieval, hybrid retrieval, manual check, and formula check.
- `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria` -> merge behavior, score components, exact formula, sort order, configurable Top-K, graph-only and semantic-only candidates, guarded rerank, and scope boundaries.
- `docs/plans/Plan_8.md` > `## 13. Failure Handling` -> semantic failure, graph failure, missing graph rows, clamping, empty candidate sets, and invalid Top-K behavior.
- `docs/plans/Plan_8.md` > `## 14. Agent Report Requirement` -> required execution report fields and scored candidate example.
- `docs/plans/Plan_8.md` > `## 15. Reviewer Checklist` -> scope, tests, acceptance, secrets, architecture, formula weights, normalization, rerank boundary, and selected document filters.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.1 Goal` -> approved retrieval signals.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.2 Retrieval Steps` -> normalize question, extract terms, semantic search, graph expansion, merge, score, sort, and return candidates.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.3 Top-K Settings` -> suggested configurable Top-K values.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.4 Scoring Formula` -> required formula, score component meanings, and normalization bounds.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.5 Optional Rerank` -> rerank may improve ordering but must not replace verification.
- `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.6 Agent 1 Output Schema` -> expected candidate score component fields.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> approved backend retrieval and rerank variable names.
- `docs/plans/Master_Plan.md` > `# 16. Suggested Project Structure` -> expected backend service and utility locations.
- `README.md` > `### Semantic Retrieval Service` -> current semantic retrieval workflow and `backend/app/services/retrieval_service.py` context.
- `README.md` > `### Graph Configuration, Entity Extraction, Builder, and Persistence Contracts` -> current graph foundation context and graph table helper availability.

## Approved Architecture Summary

Plan 8 approves a backend-only hybrid retrieval layer for the single-user Document QA Agent MVP. It sits after the completed vector indexing, semantic retrieval, and medium GraphRAG groundwork from Plans 5, 6, and 7. It must not introduce a new database schema, frontend retrieval UI, final chat API, answer generation, evidence verification, LangGraph orchestration, or Agent 1 wrapper.

The hybrid retrieval service must call the existing semantic search path for semantic candidates, call a new graph retrieval service for graph candidates, merge candidates by `chunk_id`, fill missing semantic or graph scores with `0.0`, compute additional score components, and sort by the required `final_score` formula. The final response shape must include `semantic_similarity`, `graph_relevance`, `keyword_overlap`, `metadata_match`, `recency_or_position_score`, and `final_score` for each returned candidate.

The graph retrieval service must use persisted `document_entities` and `document_relationships` rows from the Plan 7 graph foundation. It must find candidate chunks from deterministic question terms or entity matches, expand through related graph rows, preserve selected document filtering, compute normalized `graph_relevance`, and tolerate missing graph rows by producing no graph candidates or `0.0` graph scores where appropriate.

The scoring layer must live in `backend/app/utils/scoring.py` and provide focused helpers for clamping, keyword overlap, metadata match, position or recency scoring, and exact final score math. All component scores must be normalized to `0.0` through `1.0`, and the final formula weights must remain exactly `0.45`, `0.25`, `0.15`, `0.10`, and `0.05`.

Rerank support is only a guarded placeholder in this plan. It may be added to `backend/app/services/shopaikey_service.py` or a closely related service helper, but it must return candidates unchanged when disabled and must never call ShopAIKey rerank unless `ENABLE_RERANK` is explicitly enabled and the required rerank model configuration is present. Rerank must not replace later evidence verification.

The existing `/api/retrieval/search` endpoint may optionally accept a `mode` field for `semantic` or `hybrid`, but no new public endpoint is required. If the Execution Agent implements API mode support, `semantic` must remain compatible with the existing Plan 6 behavior unless the source plan is explicitly updated.

## Global Implementation Rules

- Keep `docs/plans/Plan_8.md` as the source of truth for scope, validations, scoring, and out-of-scope boundaries.
- Use `docs/plans/Master_Plan.md` only to clarify the broader approved retrieval architecture, environment variable names, and service locations.
- Use `README.md` only to understand current semantic retrieval and graph foundation context.
- Depend on completed Plans 5, 6, and 7; do not reimplement vector indexing, semantic retrieval, graph building, or graph persistence except for narrow integration needs.
- Do not create or alter database tables.
- Preserve selected document filters and single-user boundaries when calling semantic, graph, Supabase, and Qdrant helper paths.
- Keep retrieval and rerank settings backend-only.
- Use `.env.example` for placeholder names only and never commit real secrets.
- Do not expose `SHOPAIKEY_API_KEY`, `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_RERANK_MODEL`, Supabase service keys, Qdrant keys, or backend-only retrieval settings to frontend code.
- Normalize every score component to `0.0` through `1.0`.
- Clamp invalid score values before final score math.
- Use the exact required final score formula without changing weights.
- Treat missing semantic scores and missing graph scores as `0.0` after candidate merge.
- Return an empty candidate list for empty merged candidate sets.
- Invalid final Top-K values must produce validation errors rather than silent defaults.
- Semantic retrieval failure must fail hybrid retrieval unless a deliberate fallback is implemented and documented.
- Graph retrieval failure may return semantic-only candidates only if graph scores are clearly unavailable or `0.0`; otherwise fail clearly with a safe error.
- Rerank must be disabled by default or guarded by `ENABLE_RERANK`.
- Do not implement Agent 1 wrapper, evidence verification, answer generation, final chat API, or frontend retrieval UI in this plan.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, schemas, settings, services, score components, test fixtures, and errors.
- Keep functions, services, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, Supabase Python client, Qdrant, and HTTP client conventions already present in the backend.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless Plan 8 explicitly requires them.
- Add comments only where they clarify a non-obvious scoring, fallback, or graph expansion decision.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Avoid adding formatters, linters, frameworks, or architecture changes outside Plan 8 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Retrieval Configuration, Schemas, and Scoring Utilities
- Batch02 - Graph Candidate Lookup Service
- Batch03 - Hybrid Candidate Merge and Final Ranking
- Batch04 - Rerank Guard, Failure Handling, and Optional API Mode
- Batch05 - Required Tests, Manual Validation, and Handoff

## Mandatory Batch01 - Retrieval Configuration, Schemas, and Scoring Utilities

### Goal

Prepare backend configuration, retrieval schemas, and scoring utilities required by hybrid retrieval.

### Why this batch exists

Hybrid retrieval cannot be implemented safely until Top-K settings, score component schemas, and exact score math are typed, backend-only, and independently testable.

### Inputs / Dependencies

- `docs/plans/Plan_8.md`
- `docs/plans/Master_Plan.md`
- Existing backend settings pattern from completed Plan 1
- Existing semantic retrieval schemas from completed Plan 6
- Existing backend `.env.example`

### Tasks

- [x] (01A): Add backend-only hybrid retrieval settings
  - Source of Truth: `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Plan_8.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Master_Plan.md` > `# 15. Environment Variables`
  - Source Requirements:
    - Add `RETRIEVAL_GRAPH_TOP_K`, `RETRIEVAL_FINAL_TOP_K`, and `ENABLE_RERANK` to settings and `.env.example`.
    - Preserve `RETRIEVAL_SEMANTIC_TOP_K`.
    - Keep retrieval and rerank settings backend-only.
    - `SHOPAIKEY_RERANK_MODEL` is required only when rerank is enabled.
  - Details: Extend the existing backend config model and example environment file using the repo's current settings style. Use safe placeholder values only.
  - Dependencies: Completed Plan 1 backend configuration pattern.
  - User Action: User must provide real rerank model/provider values only if they intentionally enable rerank locally.
  - Agent Work: Update backend settings and `backend/.env.example`; confirm no frontend env file receives backend-only retrieval or rerank settings.
  - Output: Backend configuration exposes graph Top-K, final Top-K, rerank enablement, and optional rerank model settings safely.
  - Acceptance: Backend imports settings successfully; default values preserve semantic retrieval behavior; `.env.example` contains placeholders only; frontend env files do not expose private retrieval or provider settings.
  - Validation: Run backend config/import tests or targeted retrieval tests after implementation; inspect env diffs for secret exposure.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live rerank validation if rerank is enabled but provider settings are missing.
  - Files: `backend/app/core/config.py`, `backend/.env.example`, optional existing backend config tests

- [x] (01B): Extend retrieval schemas for hybrid candidates and score components
  - Source of Truth: `docs/plans/Plan_8.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_8.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_8.md` > `## 8. API Design`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.6 Agent 1 Output Schema`
  - Source Requirements:
    - Extend `backend/app/schemas/retrieval.py` with hybrid candidate and score component schemas.
    - Hybrid candidates must include chunk, document, metadata, content, score components, final score, and retrieval reason where supported.
    - Optional API mode can be `semantic` or `hybrid`; default can remain `semantic`.
  - Details: Add Pydantic models or fields that fit the current retrieval schema style. Avoid breaking existing semantic search request and response models.
  - Dependencies: (01A), existing Plan 6 retrieval schemas.
  - User Action: None.
  - Agent Work: Add hybrid candidate models, score component models, and optional request mode support only where needed by service or optional API integration.
  - Output: Typed schema support for hybrid retrieval candidates and score components.
  - Acceptance: Existing semantic response schemas remain compatible; hybrid candidates can represent every Plan 8 score component; optional mode validation accepts only approved values if implemented.
  - Validation: Run retrieval schema/import tests and targeted hybrid retrieval tests after later batches exist.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/retrieval.py`, `backend/app/schemas/__init__.py` if needed

- [x] (01C): Implement normalized scoring helpers
  - Source of Truth: `docs/plans/Plan_8.md` > `## 3. Scope`; `docs/plans/Plan_8.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_8.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.4 Scoring Formula`
  - Source Requirements:
    - Create `backend/app/utils/scoring.py`.
    - Implement `clamp_score(value)` returning `0.0` through `1.0`.
    - Implement keyword overlap after lowercasing and removing common punctuation.
    - Implement metadata match scoring for selected document, page, section, or file metadata matches.
    - Implement position or recency scoring for early chunks, title or summary-like sections, or explicit date fields.
    - All component scores must be normalized.
  - Details: Keep helpers deterministic and free of provider calls. Use simple tokenization and explicit bounds so tests can verify exact behavior.
  - Dependencies: Existing utility package conventions.
  - User Action: None.
  - Agent Work: Add scoring helper functions and any small internal data structures needed for punctuation handling or common metadata terms.
  - Output: Reusable scoring utility module for hybrid retrieval.
  - Acceptance: Each helper returns a float between `0.0` and `1.0`; empty or malformed inputs are handled safely; selected document and metadata checks are deterministic.
  - Validation: `cd backend` then run `pytest tests/test_scoring.py -v` after tests are created.
  - Blocked Condition: None.
  - Files: `backend/app/utils/scoring.py`, `backend/app/utils/__init__.py` if needed

- [x] (01D): Implement exact final score formula helper
  - Source of Truth: `docs/plans/Plan_8.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Plan_8.md` > `## 11. Required Tests`; `docs/plans/Plan_8.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.4 Scoring Formula`
  - Source Requirements:
    - Implement `final_score(components)` with exact weights.
    - Formula weights must be `0.45`, `0.25`, `0.15`, `0.10`, and `0.05`.
    - All component values must be clamped before or during final score calculation.
    - All-one components must produce `1.0`; all-zero components must produce `0.0`.
  - Details: Keep formula constants explicit and testable. Avoid rounding that changes exact expected formula behavior unless tests define a stable precision.
  - Dependencies: (01C).
  - User Action: None.
  - Agent Work: Add final score helper and exported constants if useful for tests.
  - Output: Exact Plan 8 formula helper.
  - Acceptance: Final score math matches Plan 8 exactly; invalid component values are clamped; missing component values are treated consistently with the hybrid merge rules.
  - Validation: `cd backend` then run `pytest tests/test_scoring.py -v`.
  - Blocked Condition: None.
  - Files: `backend/app/utils/scoring.py`

### Files or Modules Likely Created or Updated

- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/app/schemas/retrieval.py`
- `backend/app/schemas/__init__.py`
- `backend/app/utils/scoring.py`
- `backend/app/utils/__init__.py`
- `backend/tests/test_scoring.py`

### Required Outputs / Artifacts

- Backend-only hybrid retrieval settings.
- Safe `.env.example` retrieval and rerank placeholders.
- Typed hybrid candidate and score component schemas.
- Scoring helper functions.
- Exact final score helper.

### Acceptance Criteria

- Hybrid retrieval settings are configurable and backend-only.
- Retrieval schemas can represent all five component scores plus `final_score`.
- Scoring helpers normalize all outputs to `0.0` through `1.0`.
- Final score uses the exact required formula.
- Existing semantic search schema compatibility is preserved.

### Required Tests or Validations

- Backend config/import validation.
- `cd backend`
- `pytest tests/test_scoring.py -v` after scoring tests are implemented.
- Changed-file inspection for backend-only setting boundaries and real secret exposure.

### Explicit Non-Goals

- Do not implement graph candidate lookup in this batch.
- Do not implement hybrid merge orchestration in this batch.
- Do not call ShopAIKey rerank in this batch.
- Do not add frontend retrieval UI.
- Do not create database migrations.

## Mandatory Batch02 - Graph Candidate Lookup Service

### Goal

Implement graph candidate lookup from persisted entities and relationships.

### Why this batch exists

Hybrid retrieval needs graph candidates with normalized graph relevance before semantic and graph candidates can be merged and scored together.

### Inputs / Dependencies

- Batch01 scoring and schema contracts
- Completed Plan 7 graph entity and relationship tables
- Existing Supabase helper methods from Plan 7 graph foundation
- `docs/plans/Plan_8.md`

### Tasks

- [x] (02A): Create graph retrieval service module and service contract
  - Source of Truth: `docs/plans/Plan_8.md` > `## 3. Scope`; `docs/plans/Plan_8.md` > `## 5. Dependencies`; `docs/plans/Plan_8.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `README.md` > `### Graph Configuration, Entity Extraction, Builder, and Persistence Contracts`
  - Source Requirements:
    - Create `backend/app/services/graph_retrieval_service.py`.
    - Find related chunks from `document_entities` and `document_relationships`.
    - `find_graph_candidates(question, document_ids, top_k)` must support Plan 8 graph expansion.
    - Plan 7 must be completed for graph candidates.
  - Details: Add a focused service interface that returns graph candidates in a shape the hybrid retrieval service can merge by `chunk_id`. Keep the service backend-only and independent from answer generation.
  - Dependencies: Batch01 schemas; Plan 7 graph helpers and persisted graph rows.
  - User Action: None for mocked tests; user must have graph-built documents for live validation.
  - Agent Work: Create graph retrieval service with injectable or mockable dependencies following existing service patterns.
  - Output: Service module exposing graph candidate lookup.
  - Acceptance: Service can be imported; tests can mock Supabase graph rows; no public graph API is added.
  - Validation: `cd backend` then run `pytest tests/test_graph_retrieval_service.py -v` after graph tests are implemented.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live graph validation if no processed, indexed, graph-built document exists.
  - Files: `backend/app/services/graph_retrieval_service.py`, `backend/tests/test_graph_retrieval_service.py`

- [x] (02B): Extract deterministic question terms and match graph entities
  - Source of Truth: `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.2 Retrieval Steps`
  - Source Requirements:
    - Extract simple question terms or entities using deterministic text matching.
    - Match against `document_entities.entity_name`.
    - Normalize the question before graph expansion.
  - Details: Implement deterministic text normalization and matching that does not call an LLM. Respect selected `document_ids` when loading or filtering entities.
  - Dependencies: (02A), Plan 7 entity persistence.
  - User Action: None.
  - Agent Work: Add term extraction, entity name matching, and document filter handling to graph retrieval.
  - Output: Matched graph entities for a question.
  - Acceptance: Matching is case-insensitive, handles punctuation safely, returns no matches for empty or irrelevant questions, and preserves selected document filters.
  - Validation: Unit tests with matched entities, no matches, punctuation, casing, and document filter scenarios.
  - Blocked Condition: None.
  - Files: `backend/app/services/graph_retrieval_service.py`, `backend/tests/test_graph_retrieval_service.py`

- [x] (02C): Expand matched entities through graph relationships to chunk candidates
  - Source of Truth: `docs/plans/Plan_8.md` > `## 3. Scope`; `docs/plans/Plan_8.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Plan_8.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Expand matching entities to related chunks through `document_relationships`.
    - Missing graph rows should produce graph scores of `0.0`, not a crash.
    - Graph-only candidates can appear if relevant.
    - Selected document filters must still apply.
  - Details: Traverse available graph relationships from matched entities to chunk IDs using the existing graph table shape. Load enough chunk metadata and content to create mergeable candidates.
  - Dependencies: (02B), Plan 7 `document_relationships` rows.
  - User Action: None for mocked tests; graph-built documents are required for live validation.
  - Agent Work: Add relationship lookup, chunk candidate construction, duplicate handling, and empty graph handling.
  - Output: Graph candidate list with chunk IDs, metadata, content where available, and raw graph evidence needed for relevance.
  - Acceptance: Related chunks are found through entity and relationship rows; candidates outside selected documents are excluded; missing rows return empty graph candidates or zero graph score without crashing.
  - Validation: Graph retrieval tests for entity-to-chunk, entity-to-entity-to-chunk, duplicate graph paths, no graph rows, and document filtering.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live graph validation if graph rows are unavailable.
  - Files: `backend/app/services/graph_retrieval_service.py`, `backend/app/services/supabase_service.py` if narrow helper additions are needed, `backend/tests/test_graph_retrieval_service.py`

- [x] (02D): Compute normalized graph relevance
  - Source of Truth: `docs/plans/Plan_8.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.4 Scoring Formula`
  - Source Requirements:
    - Compute `graph_relevance` based on entity match strength, relationship weight, and number of graph paths.
    - `graph_relevance` must be normalized to `0.0` through `1.0`.
    - Score calculation must clamp invalid values.
  - Details: Define a deterministic graph relevance calculation that can combine match strength, relationship weights, and multiple paths without exceeding the normalized bounds.
  - Dependencies: (02C), Batch01 scoring helpers.
  - User Action: None.
  - Agent Work: Add graph relevance calculation and clamping for graph candidates.
  - Output: Each graph candidate includes normalized `graph_relevance`.
  - Acceptance: Graph relevance is stable, clamped, and increases with stronger matches or more relevant paths without exceeding `1.0`.
  - Validation: Graph retrieval tests for weight bounds, multiple paths, weak matches, missing weights, and graph-only candidate score presence.
  - Blocked Condition: None.
  - Files: `backend/app/services/graph_retrieval_service.py`, `backend/app/utils/scoring.py` if shared clamp helper is reused, `backend/tests/test_graph_retrieval_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/graph_retrieval_service.py`
- `backend/app/services/supabase_service.py` if narrow lookup helper additions are needed
- `backend/app/schemas/retrieval.py`
- `backend/app/utils/scoring.py`
- `backend/tests/test_graph_retrieval_service.py`

### Required Outputs / Artifacts

- Graph retrieval service.
- Deterministic question term and entity matching.
- Relationship-based graph expansion.
- Normalized graph relevance scoring.
- Graph retrieval tests.

### Acceptance Criteria

- Graph candidates are found from `document_entities` and `document_relationships`.
- Selected document filters still apply.
- Missing graph rows do not crash retrieval.
- Graph-only candidates can be returned for hybrid merge.
- Graph relevance is normalized to `0.0` through `1.0`.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_graph_retrieval_service.py -v`
- Mocked tests for entity matching, relationship expansion, graph-only candidates, no graph rows, and document filters.

### Explicit Non-Goals

- Do not rebuild graph data in this batch.
- Do not implement hybrid semantic merge in this batch.
- Do not implement Agent 1 wrapper.
- Do not add public graph APIs or frontend graph workflows.
- Do not call LLMs for graph retrieval term extraction.

## Mandatory Batch03 - Hybrid Candidate Merge and Final Ranking

### Goal

Implement the hybrid retrieval service that merges semantic and graph candidates, computes all score components, sorts by final score, and returns final Top-K chunks.

### Why this batch exists

The product needs one retrieval service contract that combines semantic and graph signals into transparent ranked evidence candidates before Agent 1 is built.

### Inputs / Dependencies

- Batch01 settings, schemas, and scoring utilities
- Batch02 graph retrieval service
- Existing semantic retrieval service from completed Plan 6
- Completed Plan 5 Qdrant indexing
- `docs/plans/Plan_8.md`

### Tasks

- [x] (03A): Create hybrid retrieval service and call semantic and graph retrieval
  - Source of Truth: `docs/plans/Plan_8.md` > `## 1. Goal`; `docs/plans/Plan_8.md` > `## 3. Scope`; `docs/plans/Plan_8.md` > `## 5. Dependencies`; `docs/plans/Plan_8.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `README.md` > `### Semantic Retrieval Service`
  - Source Requirements:
    - Create `backend/app/services/hybrid_retrieval_service.py`.
    - Orchestrate semantic search, graph expansion, candidate merge, scoring, and final Top-K.
    - Call semantic search for `semantic_top_k`.
    - Call graph retrieval for `graph_top_k`.
    - Plans 5, 6, and 7 must be completed.
  - Details: Build `retrieve_hybrid(question, document_ids=None, final_top_k=None)` or a locally consistent equivalent. Use existing semantic retrieval service behavior rather than duplicating Qdrant and embedding calls.
  - Dependencies: Batch01, Batch02, existing `backend/app/services/retrieval_service.py`.
  - User Action: None for mocked tests; live validation requires indexed and graph-built documents.
  - Agent Work: Create hybrid retrieval service with dependency boundaries that are easy to mock in tests.
  - Output: Hybrid service calls semantic and graph retrieval using configurable candidate counts.
  - Acceptance: Semantic retrieval is called with semantic Top-K; graph retrieval is called with graph Top-K; document filters are passed through; empty question and invalid Top-K behavior follow validation rules.
  - Validation: `cd backend` then run `pytest tests/test_hybrid_retrieval_service.py -v` after hybrid tests are implemented.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live validation if indexed and graph-built documents are unavailable.
  - Files: `backend/app/services/hybrid_retrieval_service.py`, `backend/tests/test_hybrid_retrieval_service.py`

- [x] (03B): Merge semantic and graph candidates by chunk ID
  - Source of Truth: `docs/plans/Plan_8.md` > `## 3. Scope`; `docs/plans/Plan_8.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Merge semantic and graph candidates by `chunk_id`.
    - Fill missing semantic or graph scores with `0.0`.
    - Graph-only candidates can appear if relevant.
    - Semantic-only candidates can appear if relevant.
  - Details: Preserve the richest available candidate metadata and content when both retrieval paths return the same chunk. Avoid duplicate output rows.
  - Dependencies: (03A).
  - User Action: None.
  - Agent Work: Implement deterministic candidate merge logic and conflict handling for duplicate chunks.
  - Output: Unified candidate collection keyed by `chunk_id`.
  - Acceptance: Duplicate chunks are merged once; semantic-only candidates have `graph_relevance = 0.0`; graph-only candidates have `semantic_similarity = 0.0`; metadata is not lost when one source is sparse.
  - Validation: Hybrid retrieval tests for duplicate merge, semantic-only candidate, graph-only candidate, and metadata precedence.
  - Blocked Condition: None.
  - Files: `backend/app/services/hybrid_retrieval_service.py`, `backend/tests/test_hybrid_retrieval_service.py`

- [x] (03C): Calculate keyword, metadata, position, and final scores for every merged candidate
  - Source of Truth: `docs/plans/Plan_8.md` > `## 1. Goal`; `docs/plans/Plan_8.md` > `## 3. Scope`; `docs/plans/Plan_8.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.4 Scoring Formula`
  - Source Requirements:
    - Return sorted candidates with `semantic_similarity`, `graph_relevance`, `keyword_overlap`, `metadata_match`, `recency_or_position_score`, and `final_score`.
    - Calculate all score components.
    - Apply the exact required formula.
    - All component scores must be normalized to `0.0` through `1.0`.
  - Details: Use Batch01 scoring utilities rather than duplicating formula logic. Ensure candidates with partial metadata still receive valid normalized scores.
  - Dependencies: (03B), Batch01 scoring helpers.
  - User Action: None.
  - Agent Work: Apply score component helpers to every merged candidate and populate the hybrid candidate schema.
  - Output: Fully scored hybrid candidates.
  - Acceptance: Every returned candidate includes all five score components plus `final_score`; all values are normalized; formula math is exact.
  - Validation: Hybrid retrieval tests for score component presence and final formula integration; scoring formula tests.
  - Blocked Condition: None.
  - Files: `backend/app/services/hybrid_retrieval_service.py`, `backend/app/utils/scoring.py`, `backend/tests/test_hybrid_retrieval_service.py`, `backend/tests/test_scoring.py`

- [x] (03D): Sort by final score and return final configurable Top-K
  - Source of Truth: `docs/plans/Plan_8.md` > `## 1. Goal`; `docs/plans/Plan_8.md` > `## 3. Scope`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Plan_8.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.3 Top-K Settings`
  - Source Requirements:
    - Add final Top-K selection.
    - Sort by `final_score desc`.
    - Return the top `RETRIEVAL_FINAL_TOP_K`.
    - Top-K values are configurable.
    - Empty candidate sets return an empty list.
  - Details: Resolve omitted `final_top_k` from configuration, validate bounds consistently with existing retrieval behavior where possible, and keep ordering deterministic for ties.
  - Dependencies: (03C), (01A).
  - User Action: None.
  - Agent Work: Implement final Top-K validation, sorting, and slicing.
  - Output: Final ranked hybrid candidate response.
  - Acceptance: Results are sorted descending by `final_score`; only final Top-K candidates are returned; empty merged sets return `[]`; invalid Top-K values return validation errors.
  - Validation: Hybrid retrieval tests for final ordering, Top-K truncation, empty candidates, and invalid final Top-K values.
  - Blocked Condition: None.
  - Files: `backend/app/services/hybrid_retrieval_service.py`, `backend/tests/test_hybrid_retrieval_service.py`

- [x] (03E): Generate retrieval reasons without answer generation
  - Source of Truth: `docs/plans/Plan_8.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_8.md` > `## 4. Out of Scope`; `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.6 Agent 1 Output Schema`
  - Source Requirements:
    - Hybrid candidate schema includes `retrieval_reason`.
    - Do not implement answer generation.
    - No agent, verification, or answer generation logic is implemented.
  - Details: If a retrieval reason is included, keep it deterministic and limited to why the chunk was retrieved or scored, not a natural-language answer to the user question.
  - Dependencies: (03C).
  - User Action: None.
  - Agent Work: Populate a concise retrieval reason from matched metadata, semantic score, graph match, or keyword overlap when supported by existing data.
  - Output: Optional deterministic retrieval reason on hybrid candidates.
  - Acceptance: Retrieval reasons do not answer the question, cite unverifiable evidence, or invoke an LLM; candidates remain valid if reason is omitted only when schema permits it.
  - Validation: Hybrid retrieval tests or schema tests for retrieval reason behavior.
  - Blocked Condition: None.
  - Files: `backend/app/services/hybrid_retrieval_service.py`, `backend/app/schemas/retrieval.py`, `backend/tests/test_hybrid_retrieval_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/hybrid_retrieval_service.py`
- `backend/app/services/retrieval_service.py` only if a narrow integration change is required
- `backend/app/services/graph_retrieval_service.py`
- `backend/app/schemas/retrieval.py`
- `backend/app/utils/scoring.py`
- `backend/tests/test_hybrid_retrieval_service.py`
- `backend/tests/test_scoring.py`

### Required Outputs / Artifacts

- Hybrid retrieval service.
- Candidate merge logic keyed by `chunk_id`.
- Score component population.
- Final score ranking and Top-K selection.
- Deterministic retrieval reason support where appropriate.

### Acceptance Criteria

- Hybrid retrieval merges semantic and graph candidates.
- Missing semantic or graph scores are filled with `0.0`.
- Graph-only and semantic-only candidates can appear.
- Every returned candidate includes all required score components and `final_score`.
- Final results are sorted descending by `final_score`.
- Final Top-K is configurable and validated.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_hybrid_retrieval_service.py -v`
- Hybrid tests for merge behavior, score presence, formula integration, graph-only candidates, semantic-only candidates, ordering, Top-K, and empty sets.

### Explicit Non-Goals

- Do not implement Agent 1 wrapper.
- Do not implement evidence verification.
- Do not implement answer generation.
- Do not expose a final chat API.
- Do not add frontend retrieval UI.

## Mandatory Batch04 - Rerank Guard, Failure Handling, and Optional API Mode

### Goal

Harden hybrid retrieval around rerank boundaries, safe failure behavior, and optional retrieval API mode support.

### Why this batch exists

Hybrid retrieval must be safe under provider failures, graph gaps, invalid inputs, and disabled rerank before it can be used by future Agent 1 work.

### Inputs / Dependencies

- Batch01 settings and schemas
- Batch02 graph retrieval service
- Batch03 hybrid retrieval service
- Existing ShopAIKey service
- Existing retrieval API if optional mode is implemented

### Tasks

- [x] (04A): Add guarded rerank placeholder that is disabled unless configured
  - Source of Truth: `docs/plans/Plan_8.md` > `## 3. Scope`; `docs/plans/Plan_8.md` > `## 4. Out of Scope`; `docs/plans/Plan_8.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Plan_8.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Master_Plan.md` > `# 10. Agent 1: Retrieval Agent` > `## 10.5 Optional Rerank`
  - Source Requirements:
    - Add optional rerank placeholder that is disabled unless configured.
    - Do not call ShopAIKey rerank unless the code path is explicitly disabled by default or guarded by configuration.
    - Add rerank placeholder helper only if needed and guarded by `ENABLE_RERANK`.
    - Rerank must not replace verification.
  - Details: Implement a helper that returns candidates unchanged when rerank is disabled. If enabled support is added, require safe config validation and provider errors that do not leak secrets.
  - Dependencies: Batch03 hybrid candidate response.
  - User Action: User must explicitly enable rerank and provide required provider/model settings before live rerank validation.
  - Agent Work: Add guarded rerank helper and wire it after initial hybrid scoring only if it does not change Plan 8 boundaries.
  - Output: Rerank placeholder that defaults to unchanged candidates.
  - Acceptance: Disabled rerank makes no provider call and preserves candidates; enabled rerank requires configuration; rerank never replaces evidence verification or removes score component output.
  - Validation: Unit tests proving disabled rerank returns candidates unchanged and no provider call occurs; optional enabled-path tests with mocked provider only.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live enabled rerank validation if API key, base URL, model, or provider setup is missing.
  - Files: `backend/app/services/shopaikey_service.py`, `backend/app/services/hybrid_retrieval_service.py`, `backend/tests/test_hybrid_retrieval_service.py`, optional ShopAIKey service tests

- [x] (04B): Implement safe hybrid retrieval failure handling
  - Source of Truth: `docs/plans/Plan_8.md` > `## 13. Failure Handling`; `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_8.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Semantic retrieval failure should fail hybrid retrieval unless a deliberate fallback is implemented and documented.
    - Graph retrieval failure should be logged and can return semantic-only candidates only if graph scores are unavailable; otherwise fail clearly.
    - Missing graph rows should produce graph scores of `0.0`, not a crash.
    - Score calculation must clamp invalid values.
    - Empty candidate sets return an empty list.
    - Invalid final Top-K values return validation errors.
  - Details: Use the project's existing exception and logging patterns. Error messages must be safe for public API mapping and must not leak provider details, keys, SQL payloads, or internal stack traces.
  - Dependencies: Batch03 hybrid service.
  - User Action: None.
  - Agent Work: Add failure handling, safe errors, graph-unavailable behavior, invalid Top-K validation, and logging around dependency calls.
  - Output: Hardened hybrid retrieval behavior.
  - Acceptance: Semantic dependency failures are not hidden; graph failures follow the documented fallback or failure behavior; invalid scores are clamped; empty and invalid input cases are deterministic.
  - Validation: Hybrid tests for semantic failure, graph failure, missing graph rows, invalid scores, empty candidates, and invalid Top-K.
  - Blocked Condition: None.
  - Files: `backend/app/services/hybrid_retrieval_service.py`, `backend/app/services/graph_retrieval_service.py`, `backend/app/utils/scoring.py`, `backend/tests/test_hybrid_retrieval_service.py`

- [x] (04C): Optionally add `/api/retrieval/search` hybrid mode without changing semantic default
  - Source of Truth: `docs/plans/Plan_8.md` > `## 8. API Design`; `docs/plans/Plan_8.md` > `## 4. Out of Scope`; `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria`; `README.md` > `### Semantic Retrieval API`
  - Source Requirements:
    - No required new public API endpoint exists in this plan.
    - Optionally extend `/api/retrieval/search` with a `mode` field.
    - `mode` can be `semantic` or `hybrid`; default can remain `semantic`.
    - Do not expose final chat API.
    - Do not implement frontend retrieval UI.
  - Details: This task is optional during execution. If the Execution Agent chooses not to implement it, document that no public API mode was added because Plan 8 does not require it. If implemented, preserve existing semantic behavior and error mapping.
  - Dependencies: Batch03 hybrid service and existing retrieval API.
  - User Action: None.
  - Agent Work: Either add optional API mode support and tests, or explicitly report it as intentionally not implemented because it is optional and out of the mandatory service path.
  - Output: Optional hybrid mode on existing retrieval endpoint, or documented non-implementation.
  - Acceptance: If implemented, `mode=semantic` preserves existing behavior, `mode=hybrid` delegates to hybrid retrieval, invalid mode is rejected, and no final chat API or frontend UI is added. If not implemented, the report clearly states this optional API work was not done.
  - Validation: If implemented, run API tests for semantic default, hybrid mode, invalid mode, and error mapping.
  - Blocked Condition: None.
  - Files: `backend/app/api/retrieval.py`, `backend/app/schemas/retrieval.py`, existing retrieval API tests, `backend/tests/test_hybrid_retrieval_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/shopaikey_service.py`
- `backend/app/services/hybrid_retrieval_service.py`
- `backend/app/services/graph_retrieval_service.py`
- `backend/app/api/retrieval.py` only if optional API mode is implemented
- `backend/app/schemas/retrieval.py`
- `backend/tests/test_hybrid_retrieval_service.py`
- Existing retrieval API tests if optional API mode is implemented

### Required Outputs / Artifacts

- Disabled-by-default rerank placeholder.
- Safe hybrid retrieval failure handling.
- Optional API mode implementation or explicit non-implementation note.
- Tests covering fallback, validation, and disabled rerank behavior.

### Acceptance Criteria

- Rerank is guarded by `ENABLE_RERANK` and returns candidates unchanged when disabled.
- Semantic retrieval failures are not hidden unless a documented fallback exists.
- Graph retrieval failures are handled according to Plan 8.
- Missing graph rows and empty candidate sets do not crash.
- Invalid final Top-K values produce validation errors.
- Optional API mode does not break existing semantic search behavior if implemented.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_hybrid_retrieval_service.py -v`
- API tests if optional mode is implemented.
- Tests or inspection proving disabled rerank does not call ShopAIKey.

### Explicit Non-Goals

- Do not implement a final chat API.
- Do not implement frontend retrieval UI.
- Do not call live rerank in tests.
- Do not make rerank required for hybrid retrieval.
- Do not implement evidence verification or answer generation.

## Mandatory Batch05 - Required Tests, Manual Validation, and Handoff

### Goal

Complete required automated tests, manual smoke validation, and execution reporting for Plan 8.

### Why this batch exists

Plan 8 is only complete when score math, graph lookup, candidate merging, final ranking, and scope boundaries are verified with evidence.

### Inputs / Dependencies

- Batch01 through Batch04 implementation
- `docs/plans/Plan_8.md`
- A processed, indexed, graph-built document for manual validation if available

### Tasks

- [x] (05A): Add and run scoring tests
  - Source of Truth: `docs/plans/Plan_8.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_8.md` > `## 11. Required Tests`; `docs/plans/Plan_8.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Add `backend/tests/test_scoring.py`.
    - Test all score components and formula math.
    - Formula components all `1.0` must produce `1.0`.
    - Formula components all `0.0` must produce `0.0`.
    - Confirm formula weights are exactly `0.45`, `0.25`, `0.15`, `0.10`, and `0.05`.
    - Confirm scores are normalized to `0.0` through `1.0`.
  - Details: Cover clamp behavior, keyword overlap, metadata match, position or recency score, exact weighted formula, and invalid score bounds.
  - Dependencies: Batch01 scoring helpers.
  - User Action: None.
  - Agent Work: Create scoring tests and run the required command.
  - Output: Passing scoring test suite.
  - Acceptance: Tests verify formula exactness and normalization behavior.
  - Validation: `cd backend` then run `pytest tests/test_scoring.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_scoring.py`, `backend/app/utils/scoring.py`

- [x] (05B): Add and run graph retrieval service tests
  - Source of Truth: `docs/plans/Plan_8.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Plan_8.md` > `## 11. Required Tests`; `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_8.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Add `backend/tests/test_graph_retrieval_service.py`.
    - Test graph candidate lookup behavior.
    - Test graph-only candidates.
    - Missing graph rows should not crash.
    - Selected document filters still apply.
  - Details: Use mocks or fakes for Supabase graph rows. Avoid requiring live Supabase for automated unit tests.
  - Dependencies: Batch02 graph retrieval service.
  - User Action: None for automated tests.
  - Agent Work: Create graph retrieval tests and run the required command.
  - Output: Passing graph retrieval test suite.
  - Acceptance: Tests prove entity matching, relationship expansion, graph relevance, graph-only candidates, no graph rows, and document filtering.
  - Validation: `cd backend` then run `pytest tests/test_graph_retrieval_service.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_graph_retrieval_service.py`, `backend/app/services/graph_retrieval_service.py`

- [x] (05C): Add and run hybrid retrieval service tests
  - Source of Truth: `docs/plans/Plan_8.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_8.md` > `## 9. Implementation Steps`; `docs/plans/Plan_8.md` > `## 11. Required Tests`; `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_8.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Add `backend/tests/test_hybrid_retrieval_service.py`.
    - Test candidate merge and final ranking.
    - Test semantic-only candidates.
    - Test graph-only candidates.
    - Test final ordering.
    - Test empty candidate sets and invalid Top-K values.
  - Details: Mock semantic retrieval and graph retrieval so the hybrid merge and scoring behavior can be tested deterministically.
  - Dependencies: Batch03 and Batch04.
  - User Action: None for automated tests.
  - Agent Work: Create hybrid retrieval tests and run the required command.
  - Output: Passing hybrid retrieval test suite.
  - Acceptance: Tests prove merge, score population, exact final ranking, Top-K truncation, graph-only and semantic-only candidates, disabled rerank, and failure behavior.
  - Validation: `cd backend` then run `pytest tests/test_hybrid_retrieval_service.py -v`.
  - Blocked Condition: None.
  - Files: `backend/tests/test_hybrid_retrieval_service.py`, `backend/app/services/hybrid_retrieval_service.py`

- [x] (05D): Run manual hybrid retrieval smoke check when data is available
  - Source of Truth: `docs/plans/Plan_8.md` > `## 11. Required Tests`; `docs/plans/Plan_8.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Run hybrid retrieval for a question against a processed, indexed, graph-built document.
    - Confirm results are sorted by `final_score`.
    - Confirm each result includes all five score components.
    - Report one scored candidate example showing all five components and `final_score`.
  - Details: This validation requires local data prepared by previous plans. If no processed, indexed, graph-built document exists, report the manual check as blocked by user/data setup while still reporting automated test results.
  - Dependencies: Batch01 through Batch04; local processed, indexed, graph-built document.
  - User Action: User must provide or confirm an available processed, indexed, graph-built document for live manual validation.
  - Agent Work: Run a local service-level or API-level smoke check using safe sample question text and report one candidate example without secrets.
  - Output: Manual validation result or blocked-by-user status.
  - Acceptance: Results are sorted by `final_score`; each sampled result includes `semantic_similarity`, `graph_relevance`, `keyword_overlap`, `metadata_match`, `recency_or_position_score`, and `final_score`.
  - Validation: Manual hybrid retrieval command or documented local smoke procedure with result summary.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if no processed, indexed, graph-built document or required local service credentials are available.
  - Files: No required file changes beyond tests or optional smoke script if the repo already uses one.

- [x] (05E): Complete execution report and scope boundary review
  - Source of Truth: `docs/plans/Plan_8.md` > `## 4. Out of Scope`; `docs/plans/Plan_8.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_8.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_8.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Report files created, files modified, commands run, test results, known issues, and intentionally out-of-scope work.
    - Include one scored candidate example showing all five components and `final_score`.
    - Reviewer must verify scope, tests, acceptance, secrets, architecture, exact formula weights, score normalization, rerank boundary, and selected document filters.
  - Details: Update this task file progress tracker only for tasks that were actually completed, validated, or blocked with a documented reason.
  - Dependencies: (05A), (05B), (05C), (05D).
  - User Action: None unless manual validation is blocked.
  - Agent Work: Prepare the required Plan 8 execution report and handoff notes for the reviewer.
  - Output: Execution report summary and updated progress tracker.
  - Acceptance: Report includes all required fields, test commands and results, manual check status, scored candidate example or blocked status, out-of-scope confirmation, and known issues.
  - Validation: Review the report against Plan 8 Agent Report Requirement and Reviewer Checklist.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for manual validation items requiring user-provided local data or credentials.
  - Files: `docs/tasks/task_8.md` progress tracker, execution report location chosen by the orchestration workflow

### Files or Modules Likely Created or Updated

- `backend/tests/test_scoring.py`
- `backend/tests/test_graph_retrieval_service.py`
- `backend/tests/test_hybrid_retrieval_service.py`
- `docs/tasks/task_8.md` progress tracker during execution
- Execution report file used by the repo's task orchestration workflow

### Required Outputs / Artifacts

- Passing scoring tests.
- Passing graph retrieval tests.
- Passing hybrid retrieval tests.
- Manual validation result or documented blocked status.
- Scored candidate example with all five components and `final_score`.
- Execution report for reviewer handoff.

### Acceptance Criteria

- Required test commands are run and reported.
- Formula exactness and normalization are verified.
- Graph lookup and candidate merge behavior are verified.
- Final ordering and Top-K behavior are verified.
- Manual smoke check is completed or safely blocked by missing user/data setup.
- Out-of-scope items are explicitly not implemented.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_scoring.py -v`
- `pytest tests/test_graph_retrieval_service.py -v`
- `pytest tests/test_hybrid_retrieval_service.py -v`
- Manual hybrid retrieval smoke check against processed, indexed, graph-built data when available.

### Explicit Non-Goals

- Do not broaden tests into Agent 1, evidence verification, answer generation, or frontend workflows.
- Do not fabricate processed documents, API keys, graph data, or provider success.
- Do not call live rerank unless the user intentionally enables and configures it.
- Do not mark manual validation complete if data or credentials are missing.

## Optional Future Tracks

### Optional Track A - Retrieval API Hybrid Mode

This track is not part of the mandatory MVP batch chain.

Plan 8 allows, but does not require, extending `POST /api/retrieval/search` with `mode = "hybrid"`. If the Execution Agent implements this track, the semantic default must remain compatible with the existing API, invalid modes must be rejected, and no final chat API or frontend retrieval UI may be added.

### Optional Track B - Live ShopAIKey Rerank Integration

This track is not part of the mandatory MVP batch chain.

Plan 8 only requires a guarded rerank placeholder. A live rerank call should remain disabled unless `ENABLE_RERANK` is explicitly enabled and required backend-only ShopAIKey settings are present. Rerank must only improve candidate ordering and must not replace later evidence verification.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05

Optional future tracks are outside the mandatory dependency chain.

## Global Verification Checklist

- [x] `docs/plans/Plan_8.md` remained the scope authority.
- [x] No database schema changes were added.
- [x] No Agent 1 wrapper was implemented.
- [x] No Evidence Verification Agent logic was implemented.
- [x] No answer generation logic was implemented.
- [x] No final chat API was exposed.
- [x] No frontend retrieval UI was implemented.
- [x] Backend-only secrets and provider settings stayed out of frontend code.
- [x] `RETRIEVAL_GRAPH_TOP_K`, `RETRIEVAL_FINAL_TOP_K`, and `ENABLE_RERANK` are backend-only and configurable.
- [x] All score components are normalized to `0.0` through `1.0`.
- [x] Final formula weights are exactly `0.45`, `0.25`, `0.15`, `0.10`, and `0.05`.
- [x] Semantic-only candidates can appear with `graph_relevance = 0.0`.
- [x] Graph-only candidates can appear with `semantic_similarity = 0.0`.
- [x] Final results sort descending by `final_score`.
- [x] Selected document filters still apply to semantic and graph paths.
- [x] Rerank is disabled by default or guarded by `ENABLE_RERANK`.
- [x] Disabled rerank does not call ShopAIKey.
- [x] Empty candidate sets return an empty list.
- [x] Invalid final Top-K values return validation errors.
- [x] `cd backend` then `pytest tests/test_scoring.py -v` was run and reported.
- [x] `cd backend` then `pytest tests/test_graph_retrieval_service.py -v` was run and reported.
- [x] `cd backend` then `pytest tests/test_hybrid_retrieval_service.py -v` was run and reported.
- [x] Manual hybrid retrieval smoke check was completed or marked `BLOCKED_BY_USER_ACTION` with a safe reason.
- [x] Execution report includes one scored candidate example or a blocked reason for manual validation.
- [x] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [x] Batch01 - Retrieval Configuration, Schemas, and Scoring Utilities
- [x] Batch02 - Graph Candidate Lookup Service
- [x] Batch03 - Hybrid Candidate Merge and Final Ranking
- [x] Batch04 - Rerank Guard, Failure Handling, and Optional API Mode
- [x] Batch05 - Required Tests, Manual Validation, and Handoff

### Task IDs

#### Batch01

- [x] (01A): Add backend-only hybrid retrieval settings
- [x] (01B): Extend retrieval schemas for hybrid candidates and score components
- [x] (01C): Implement normalized scoring helpers
- [x] (01D): Implement exact final score formula helper

#### Batch02

- [x] (02A): Create graph retrieval service module and service contract
- [x] (02B): Extract deterministic question terms and match graph entities
- [x] (02C): Expand matched entities through graph relationships to chunk candidates
- [x] (02D): Compute normalized graph relevance

#### Batch03

- [x] (03A): Create hybrid retrieval service and call semantic and graph retrieval
- [x] (03B): Merge semantic and graph candidates by chunk ID
- [x] (03C): Calculate keyword, metadata, position, and final scores for every merged candidate
- [x] (03D): Sort by final score and return final configurable Top-K
- [x] (03E): Generate retrieval reasons without answer generation

#### Batch04

- [x] (04A): Add guarded rerank placeholder that is disabled unless configured
- [x] (04B): Implement safe hybrid retrieval failure handling
- [x] (04C): Optionally add `/api/retrieval/search` hybrid mode without changing semantic default

#### Batch05

- [x] (05A): Add and run scoring tests
- [x] (05B): Add and run graph retrieval service tests
- [x] (05C): Add and run hybrid retrieval service tests
- [x] (05D): Run manual hybrid retrieval smoke check when data is available
- [x] (05E): Complete execution report and scope boundary review

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
- reason: missing API key, missing provider project, missing processed indexed graph-built document, missing manual setup, or other safe summary

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
