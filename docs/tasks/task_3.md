# RagDocument Phase 3 Advanced RAG Execution Tasks

## Purpose

This task file converts the approved Phase 3 plan into execution-ready batches for future implementation agents. Phase 3 adds advanced text-only retrieval, bounded query planning, hybrid search, summaries and lightweight relations, citation and grounding verification, evaluation, observability, and deterministic failure recovery on top of completed Phases 1 and 2.

## Authoritative Source

Primary source:

- `docs/plans/Plan_3.md`

Context sources named by the primary plan:

- `docs/plans/Master_Plan.md`
- `docs/plans/Plan_1.md`
- `docs/plans/Plan_2.md`
- `README.md`

Use `docs/plans/Plan_3.md` as the source of truth for Phase 3 scope, architecture, batch order, files, validations, and acceptance criteria. Earlier plans and `README.md` describe the completed baseline only and must not override Phase 3 requirements.

## Source Section Index

- `docs/plans/Plan_3.md` > `## Current Progress Baseline` -> completed Phase 1 and 2 behavior that must be preserved.
- `docs/plans/Plan_3.md` > `## Master Plan Contract` -> required Phase 3 capabilities, preserved constraints, and prohibited scope.
- `docs/plans/Plan_3.md` > `## Phase 3 Design Decisions` -> retrieval, fusion, filter, decomposition, relation, context, verification, retry, and trace contracts.
- `docs/plans/Plan_3.md` > `## Target File Structure` -> expected Phase 3 files and modules.
- `docs/plans/Plan_3.md` > `## Batch 1: Phase 3 Contracts, Settings, and Persistence` -> typed contracts, settings, migration, and persistence services.
- `docs/plans/Plan_3.md` > `## Batch 2: Metadata-Aware Keyword and Hybrid Retrieval` -> filters, Postgres full-text search, and reciprocal-rank fusion.
- `docs/plans/Plan_3.md` > `## Batch 3: Document Summaries and Lightweight Relations` -> extracted-text summaries and bounded document relations.
- `docs/plans/Plan_3.md` > `## Batch 4: Query Decomposition and LangGraph Retrieval Routing` -> bounded planning and retrieval routing.
- `docs/plans/Plan_3.md` > `## Batch 5: Candidate Stages, Reranking, and Context Budgets` -> candidate caps, rerank fallback, and section-aware token budgeting.
- `docs/plans/Plan_3.md` > `## Batch 6: Exact Citations and Grounding Verification` -> citation-key validation and bounded grounding regeneration.
- `docs/plans/Plan_3.md` > `## Batch 7: RAG Evaluation Dataset and Metrics` -> versioned corpus, metric definitions, reports, and gates.
- `docs/plans/Plan_3.md` > `## Batch 8: Workflow Observability and Failure Recovery` -> compact traces, retry classification, and final fallbacks.
- `docs/plans/Plan_3.md` > `## Batch 9: Documentation and End-to-End Validation` -> documentation, automated verification, manual smoke tests, and external evaluation.
- `docs/plans/Plan_3.md` > `## Phase 3 Acceptance Criteria` -> final completion criteria.
- `docs/plans/Plan_3.md` > `## Execution Order` -> mandatory batch order and focused commit sequence.

## Approved Architecture Summary

- Preserve the React/Vite/TypeScript frontend and FastAPI/Pydantic/LangGraph backend.
- Keep Supabase Storage for original files, Supabase Postgres for metadata and compact persistence, and Qdrant Cloud for chunk vectors.
- Keep ShopAIKey as the OpenAI-compatible model provider and Jina as the reranker with deterministic fallback.
- Preserve separate upload and indexing operations and the existing API/workflow boundaries.
- Extend deterministic LangGraph ingestion and query workflows with bounded, typed, inspectable nodes.
- Keep semantic, keyword, and relation retrieval paths independently testable and normalize candidates into one contract.
- Deduplicate by `chunk_id`, fuse with RRF constant 60, and use stable `chunk_id` tie-breaking.
- Treat selected `document_ids` as a strict allow-list that planning and relation expansion may never widen.
- Limit query decomposition to `QUERY_MAX_SUBQUERIES` and relation expansion to one bounded document hop.
- Generate summaries only from extracted text and store only compact summaries, relations, and redacted traces.
- Return factual answers only after exact-context citation validation and grounding verification.

## Global Implementation Rules

- Do not rebuild completed Phase 1 or 2 behavior listed in the current progress baseline.
- Keep existing request and response fields backward compatible unless Phase 3 explicitly adds an optional field.
- Do not add login, signup, OAuth, Supabase Auth, user/profile/organization/role/tenant models, or access-control tables.
- Preserve the optional `X-Admin-API-Token` as the only application gate.
- Do not add autonomous agents, multi-agent workflows, unbounded planning/tool loops, or a general-purpose knowledge graph.
- Do not add OCR, scanned-document processing, image/chart captioning, audio/video extraction, PPTX parsing, or image-only formats.
- Do not add a new vector database, model provider, frontend framework, graph database, or background-job platform.
- Keep upload and indexing separate and preserve safe lifecycle behavior during reindex and failure.
- Use `chunk_id` as the candidate deduplication key everywhere.
- Use RRF with the configured constant and deterministic stable tie-breaking.
- Explicit request filters override planner-inferred filters; explicit document selection is never widened.
- Keep context within configured token and candidate caps except the documented single-top-chunk truncation case.
- Retry only timeouts, connection failures, HTTP 429, and HTTP 5xx; validation and non-retryable 4xx failures execute once.
- Never persist raw chunk or parsed text, prompts, full model responses, full generated answers, authorization headers, API keys, or credential-bearing URLs in workflow traces.
- Never fabricate or commit API keys, provider projects, external resources, or real `.env` values.
- Use `.env.example` only for placeholders if configuration documentation requires it; keep secrets backend-only.
- Run every batch validation before checking off its tasks or batch.
- Create the focused commit named by the source plan after each accepted batch when repository workflow permits commits.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code.
- Use descriptive names for modules, functions, variables, components, settings, and tests.
- Keep functions, components, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow the standard conventions of FastAPI, Pydantic, LangGraph, pytest, React, Vite, and TypeScript.
- Use clear typing where supported.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration unless the plan explicitly requires it.
- Add comments only for non-obvious decisions or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Avoid new formatters, linters, frameworks, or architecture changes outside the approved plan.

## Batch Map

- Batch01 - Phase 3 Contracts, Settings, and Persistence: (01A), (01B)
- Batch02 - Metadata-Aware Keyword and Hybrid Retrieval: (02A), (02B), (02C)
- Batch03 - Document Summaries and Lightweight Relations: (03A), (03B)
- Batch04 - Query Decomposition and LangGraph Retrieval Routing: (04A), (04B)
- Batch05 - Candidate Stages, Reranking, and Context Budgets: (05A), (05B)
- Batch06 - Exact Citations and Grounding Verification: (06A), (06B)
- Batch07 - RAG Evaluation Dataset and Metrics: (07A), (07B)
- Batch08 - Workflow Observability and Failure Recovery: (08A), (08B)
- Batch09 - Documentation and End-to-End Validation: (09A), (09B), (09C)

## Mandatory Batch01 - Phase 3 Contracts, Settings, and Persistence

### Goal

Establish backward-compatible Phase 3 contracts, bounded settings, persistence schema, and data-service foundations.

### Why this batch exists

Every later retrieval, planning, verification, evaluation, and observability feature depends on stable typed state and durable compact storage.

### Inputs / Dependencies

- Completed Phase 1 and 2 repository baseline.
- Existing lazy Supabase client and current schema conventions.
- Phase 3 design decisions and target file structure.

### Tasks

- [x] (01A): Add typed retrieval, planning, verification, and state contracts
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 1: Phase 3 Contracts, Settings, and Persistence` > `### Task 1.1: Add typed retrieval, planning, and verification contracts`
  - Source Requirements:
    - Add the specified retrieval, path, summary, relation, and workflow-status enums.
    - Add validated filters and typed planning, candidate, grounding, citation, and trace models.
    - Extend chat responses, citations, query state, and ingestion state without breaking old clients.
    - Add every bounded Phase 3 setting with its documented default and override behavior.
  - Details: Define the contracts shared by later workflow nodes, services, routes, and frontend types.
  - Dependencies: Completed Phase 2 contracts and graph states.
  - User Action: None.
  - Agent Work: Implement typed models and settings, preserve compatibility, and add validation/state tests.
  - Specific Steps:
    1. Add exact enum values for `RetrievalStrategy`, `RetrievalPath`, `SummaryType`, `RelationType`, and `WorkflowStatus`.
    2. Add `RetrievalFilters`; normalize optional fields and reject negative or reversed page ranges.
    3. Add `QueryPlan`, `QuerySubquery`, `RetrievalCandidate`, `GroundingResult`, `CitationValidationResult`, and `WorkflowTraceEvent` with all required metadata.
    4. Add optional `filters` to `ChatRequest`, optional `trace_id` to `ChatResponse`, and optional fusion/path/key metadata to `SourceCitation`.
    5. Extend query and ingestion states with Phase 3 fields while excluding extra binary data, prompts, and copied text.
    6. Add all documented settings with bounded validation and environment overrides.
    7. Test unknown enum rejection, old request compatibility, filter validation, defaults/overrides, and safe state shape.
  - Output: Typed Phase 3 contracts, state models, settings, and unit coverage.
  - Acceptance: All models enforce the documented contract, old chat payloads validate, and state contains no new unsafe content.
  - Validation: `cd backend; python -m pytest tests/test_config.py tests/test_contracts.py tests/test_query_graph.py tests/test_ingestion_graph.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/core/contracts.py`, `backend/app/core/config.py`, `backend/app/models/schemas.py`, `backend/app/graphs/query_state.py`, `backend/app/graphs/ingestion_state.py`, `backend/tests/test_config.py`, `backend/tests/test_contracts.py`, `backend/tests/test_query_graph.py`, `backend/tests/test_ingestion_graph.py`

- [x] (01B): Add the idempotent Phase 3 schema and persistence services
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 1: Phase 3 Contracts, Settings, and Persistence` > `### Task 1.2: Add idempotent Phase 3 database migration and data services`
  - Source Requirements:
    - Add `documents.error_code`, `document_summaries`, `document_relations`, and `workflow_runs` with exact constraints and indexes.
    - Keep canonical relation pairs, prohibit self-relations, and enforce bounded confidence and allowed values.
    - Make the migration safe for an existing Phase 2 database and keep the fresh schema equivalent.
    - Implement normalized summary, relation, and workflow-run operations with nonfatal trace writes.
  - Details: Add durable storage and services for compact derived data and workflow telemetry.
  - Dependencies: (01A), existing Supabase schema, and lazy client patterns.
  - User Action: Apply `docs/database/phase3_migration.sql` to the configured Phase 2 Supabase project only during the later manual acceptance task; no action is required for unit implementation.
  - Agent Work: Write schema/migration SQL, add normalized services, and test constraints/service behavior without requiring live credentials.
  - Specific Steps:
    1. Add `documents.error_code` and all three tables with documented columns, checks, foreign keys, defaults, uniqueness, and indexes.
    2. Canonicalize relation pairs and enforce no self-relations and unique pair/type rows.
    3. Make migration statements safely repeatable and update the fresh-install schema to the same final structure.
    4. Implement create/list/replace/delete summary and relation operations with normalized UUIDs and deterministic ordering.
    5. Implement workflow-run create/update/list/get behavior and ensure trace persistence failures only log warnings.
    6. Test empty responses, replacement semantics, canonical pairs, ordering, schema equivalence, and nonfatal observability failure.
  - Output: Phase 3 migration, updated fresh schema, data services, and unit tests.
  - Acceptance: Existing Phase 2 databases can migrate safely; fresh databases match; normalized services satisfy all persistence and failure contracts.
  - Validation: `cd backend; python -m pytest tests/test_summaries.py tests/test_relations.py tests/test_observability.py -v`
  - Blocked Condition: None for implementation; `BLOCKED_BY_USER_ACTION` only if live migration validation is attempted before the user configures or authorizes the Supabase project.
  - Files: `docs/database/phase3_migration.sql`, `docs/database/supabase_schema.sql`, `backend/app/core/contracts.py`, `backend/app/services/summaries.py`, `backend/app/services/relations.py`, `backend/app/services/observability.py`, `backend/tests/test_summaries.py`, `backend/tests/test_relations.py`, `backend/tests/test_observability.py`

### Files or Modules Likely Created or Updated

- Core contracts, settings, API schemas, ingestion/query states.
- Supabase fresh schema and Phase 3 migration.
- Summary, relation, and observability services and tests.

### Required Outputs / Artifacts

- Backward-compatible typed Phase 3 foundation.
- Idempotent migration and equivalent fresh-install schema.
- Passing focused Batch01 tests.

### Acceptance Criteria

- Every documented enum, setting, state field, table, constraint, and service exists.
- Old chat payloads remain valid and no unsafe trace/state content is introduced.
- Persistence failures designated as best-effort cannot fail ingestion or chat.

### Required Tests or Validations

- Run the validation commands for (01A) and (01B).
- Review SQL equivalence between migration outcome and fresh schema.

### Explicit Non-Goals

- Do not apply the migration to a live project in this batch.
- Do not implement retrieval, summaries generation, relation generation, tracing instrumentation, or retry orchestration yet.

## Mandatory Batch02 - Metadata-Aware Keyword and Hybrid Retrieval

### Goal

Add equivalent metadata filtering to semantic and keyword paths, then fuse independently retrieved candidates deterministically.

### Why this batch exists

Phase 3 routing requires filter-safe, independently recoverable semantic and keyword retrieval before query planning can orchestrate them.

### Inputs / Dependencies

- Accepted Batch01 contracts, settings, migration, and services.
- Existing Qdrant retrieval and Supabase chunk persistence.
- Existing frontend document selection and chat flow.

### Tasks

- [x] (02A): Add metadata filters to ingestion payloads, chat retrieval, and frontend
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 2: Metadata-Aware Keyword and Hybrid Retrieval` > `### Task 2.1: Add metadata filters to API, Qdrant payloads, and the frontend`
  - Source Requirements:
    - Store `mime_type` in new Qdrant chunk payloads.
    - Build one AND-combined Qdrant filter for document, MIME, heading, section path, and overlapping page range.
    - Pass explicit request filters unchanged and preserve document IDs as a strict allow-list.
    - Add a collapsible frontend filter panel with invalid-page-range blocking.
  - Details: Implement the common metadata-filter contract across API, graph, Qdrant, and frontend surfaces.
  - Dependencies: (01A), existing Phase 2 ingestion/query flows, and current frontend chat state.
  - User Action: Existing indexed documents must be reindexed later to acquire `mime_type` payloads; no action is required for unit implementation.
  - Agent Work: Extend payload/filter creation, pass filters through the graph, build the UI, and cover backend behavior plus frontend compilation.
  - Specific Steps:
    1. Add `mime_type` to every newly generated Qdrant payload.
    2. Replace the document-only filter helper with `build_qdrant_filter(document_ids, filters)`.
    3. Implement equivalent allow-list, MIME, heading, section-segment, and page-overlap conditions with correct unknown-page behavior.
    4. Preserve explicit filters through route and query-state boundaries and normalize empty fields only.
    5. Add typed frontend filter state and API serialization that sends only populated fields.
    6. Add collapsible filter controls and prevent send with an inline invalid page-range message.
    7. Test strict allow-list behavior, backward compatibility, compiled Qdrant conditions, and frontend build.
  - Output: End-to-end metadata filter support and MIME-aware Qdrant payloads.
  - Acceptance: Every populated filter is enforced, old requests behave unchanged, and invalid page ranges cannot be sent from the UI.
  - Validation: `cd backend; python -m pytest tests/test_ingestion_payloads.py tests/test_query_graph.py tests/test_api_chat.py -v`; then `cd ../frontend; npm run build`
  - Blocked Condition: None for implementation; existing document payload migration remains pending reindex in Batch09.
  - Files: `backend/app/graphs/ingestion_payloads.py`, `backend/app/services/retrieval.py`, `backend/app/graphs/query_nodes.py`, `backend/app/api/routes/chat.py`, `backend/tests/test_ingestion_payloads.py`, `backend/tests/test_query_graph.py`, `backend/tests/test_api_chat.py`, `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/components/RetrievalFiltersPanel.tsx`, `frontend/src/components/ChatPanel.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`

- [x] (02B): Add Postgres full-text keyword retrieval
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 2: Metadata-Aware Keyword and Hybrid Retrieval` > `### Task 2.2: Add Postgres full-text keyword retrieval`
  - Source Requirements:
    - Add the `simple`-configuration GIN index and `search_document_chunks_keyword` RPC.
    - Match Qdrant document/MIME/heading/section/page filter semantics.
    - Normalize RPC rows into the shared candidate contract with keyword score, rank, and path.
    - Reject empty queries and expose RPC failure as a typed recoverable path error without secrets.
  - Details: Add a deterministic exact-term retrieval path backed by Postgres full-text search.
  - Dependencies: (01B), (02A), shared candidate contracts, and Phase 3 SQL files.
  - User Action: The migration containing the index and RPC must be applied before live keyword retrieval; defer that live action to Batch09.
  - Agent Work: Extend both SQL artifacts, implement the RPC client service, normalize results, and unit-test parameters, ordering, and errors.
  - Specific Steps:
    1. Add the language-neutral GIN expression index to migration and fresh schema.
    2. Implement the RPC with `websearch_to_tsquery('simple', query_text)` and all required parameters.
    3. Join documents for MIME filtering and apply matching allow-list/page-overlap semantics.
    4. Return chunk metadata plus rank score in stable score/document/chunk order and enforce the configured top-k.
    5. Implement `search_keyword_chunks` with normalized candidates and `retrieval_paths = ["keyword"]`.
    6. Raise safe typed errors for empty queries and unavailable RPC behavior.
    7. Unit-test RPC parameters, tie ordering, normalization, and redacted failure behavior.
  - Output: Keyword-search SQL and typed backend service.
  - Acceptance: Keyword results use the shared candidate shape and exact metadata semantics with deterministic ordering and recoverable errors.
  - Validation: `cd backend; python -m pytest tests/test_keyword_search.py -v`
  - Blocked Condition: None for unit implementation; `BLOCKED_BY_USER_ACTION` for live RPC acceptance until the Supabase migration is applied.
  - Files: `docs/database/phase3_migration.sql`, `docs/database/supabase_schema.sql`, `backend/app/services/keyword_search.py`, `backend/tests/test_keyword_search.py`

- [x] (02C): Add deterministic reciprocal-rank fusion and hybrid fallback
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 2: Metadata-Aware Keyword and Hybrid Retrieval` > `### Task 2.3: Add deterministic reciprocal-rank fusion`
  - Source Requirements:
    - Fuse by `chunk_id` using `1 / (RETRIEVAL_RRF_CONSTANT + one_based_rank)` across paths and subqueries.
    - Preserve best scores and ranks while accumulating unique paths and subquery IDs.
    - Apply stable fusion ordering and cap at `RETRIEVAL_FUSION_TOP_K`.
    - Recover with either successful path; fail only when both paths fail.
  - Details: Implement deterministic hybrid retrieval without coupling the success of semantic and keyword providers.
  - Dependencies: (02A), (02B), existing semantic retrieval, and shared candidate contracts.
  - User Action: None.
  - Agent Work: Implement fusion and hybrid orchestration, add stable fallbacks, and test deduplication and ordering.
  - Specific Steps:
    1. Implement RRF contributions for each path/subquery rank using the configured constant.
    2. Merge duplicate chunks, retain best non-null semantic/keyword values, and deduplicate path/subquery metadata.
    3. Sort by fusion score descending, best rank ascending, then chunk ID ascending.
    4. Run enabled semantic and keyword paths independently and fuse successful outputs.
    5. Implement semantic-only, keyword-only, empty-result, both-failed, and keyword-disabled contracts exactly.
    6. Cap fused output and preserve original path metadata in fallbacks.
    7. Test repeated-run stability and typed error behavior.
  - Output: Deterministic fusion service and hybrid retrieval function.
  - Acceptance: Duplicate chunks merge correctly, dual-path evidence gains both contributions, and all fallback cases match the plan.
  - Validation: `cd backend; python -m pytest tests/test_score_fusion.py tests/test_keyword_search.py tests/test_query_graph.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/services/score_fusion.py`, `backend/app/services/retrieval.py`, `backend/tests/test_score_fusion.py`, `backend/tests/test_query_graph.py`

### Files or Modules Likely Created or Updated

- Qdrant ingestion/retrieval, chat graph/API, frontend filters.
- Phase 3 SQL, keyword-search service, fusion service, and tests.

### Required Outputs / Artifacts

- Equivalent semantic/keyword filter behavior.
- Typed keyword retrieval and deterministic hybrid fusion.
- Passing focused backend tests and frontend production build.

### Acceptance Criteria

- Explicit document IDs remain a strict allow-list.
- Semantic and keyword paths use equivalent filter behavior and fail independently.
- RRF output is stable, deduplicated, and capped.

### Required Tests or Validations

- Run all validation commands for (02A), (02B), and (02C).
- Confirm unit tests do not require live external services.

### Explicit Non-Goals

- Do not add query decomposition, relation expansion, summaries, grounding, or observability instrumentation in this batch.
- Do not reindex live documents until Batch09 manual acceptance.

## Mandatory Batch03 - Document Summaries and Lightweight Relations

### Goal

Generate extracted-text-only summaries during ingestion and maintain a bounded, evidence-backed, document-level relation graph.

### Why this batch exists

Relation-aware retrieval requires compact document representations and safe inspection APIs before query routing uses relations.

### Inputs / Dependencies

- Accepted Batch01 persistence contracts and Batch02 retrieval primitives.
- Existing ingestion graph, saved chunks, Qdrant vectors, and document APIs.

### Tasks

- [x] (03A): Generate section and document summaries during ingestion
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 3: Document Summaries and Lightweight Relations` > `### Task 3.1: Generate section and document summaries during ingestion`
  - Source Requirements:
    - Group saved chunks by normalized section path with heading fallback.
    - Generate section summaries only from group text and document summaries only from section summaries.
    - Store exact source chunk IDs and replace summaries atomically only after complete generation.
    - Add the bounded graph node and typed summary inspection endpoint; support disabled summaries.
  - Details: Add compact, attributable summary artifacts without introducing raw binary or external content.
  - Dependencies: (01A), (01B), existing saved chunks and ShopAIKey chat integration.
  - User Action: Configured model credentials are required only for live ingestion acceptance; unit tests must mock providers.
  - Agent Work: Implement grouping, generation, atomic replacement, graph integration, route schemas, and tests.
  - Specific Steps:
    1. Normalize section grouping and use heading only when section path is empty.
    2. Build deterministic temperature-zero prompts constrained to supplied extracted text and configured output limits.
    3. Generate section summaries first, then build the document summary only from those summaries.
    4. Retain exact source chunk IDs, model, heading, and section path for every record.
    5. Replace all document summaries only after successful complete generation.
    6. Insert `summarize_document` after `save_chunks` and before `embed_chunks`; skip calls when disabled.
    7. Add typed summary listing ordered with the document summary first and test all contracts.
  - Output: Summary generation service, ingestion node, endpoint, schemas, and tests.
  - Acceptance: Summaries are extracted-text-only, attributable, atomically replaced, ordered, and safely disabled.
  - Validation: `cd backend; python -m pytest tests/test_summaries.py tests/test_ingestion_graph.py tests/test_api_documents.py -v`
  - Blocked Condition: None for unit implementation; `BLOCKED_BY_USER_ACTION` for live generation if external model configuration is missing.
  - Files: `backend/app/services/summaries.py`, `backend/app/graphs/ingestion_state.py`, `backend/app/graphs/ingestion_nodes.py`, `backend/app/graphs/ingestion_graph.py`, `backend/app/api/routes/documents.py`, `backend/app/models/schemas.py`, `backend/tests/test_summaries.py`, `backend/tests/test_ingestion_graph.py`, `backend/tests/test_api_documents.py`

- [x] (03B): Build and query bounded document relations
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 3: Document Summaries and Lightweight Relations` > `### Task 3.2: Build and query a bounded document relation graph`
  - Source Requirements:
    - Select at most the configured number of ready candidate documents from summary embedding search.
    - Accept only strict, validated relation JSON with allowed documents, types, confidence, and evidence IDs.
    - Canonicalize pairs and replace only relations involving the reindexed document.
    - Keep indexing ready when relation updates exhaust retries and add a normalized inspection endpoint.
  - Details: Add a lightweight one-purpose relation layer for later bounded cross-document retrieval.
  - Dependencies: (03A), relation persistence from (01B), existing Qdrant and ingestion lifecycle.
  - User Action: Configured Qdrant and model services are required only for live acceptance; unit tests must mock them.
  - Agent Work: Implement candidate selection, strict validation, canonical replacement, ingestion integration, API inspection, and failure tests.
  - Specific Steps:
    1. Embed the current document summary, query Qdrant, exclude the source, group by document, and cap ready candidates.
    2. Request strict relation JSON and validate target IDs, types, confidence, and evidence against candidates.
    3. Discard invalid relation entries safely and canonicalize every accepted document pair.
    4. Replace only rows involving the reindexed document and retain at most one row per pair/type.
    5. Insert `update_document_relations` after Qdrant upsert and before ready status, with disabled/no-summary skips.
    6. On exhausted relation update, record a safe warning and retain otherwise valid indexing.
    7. Add bidirectional inspection with normalized `related_document_id` and cover behavior in tests.
  - Output: Bounded relation generation/query service, ingestion node, endpoint, and tests.
  - Acceptance: Relations are canonical, bounded, evidence-backed, safe under invalid model output, and nonfatal to valid indexing.
  - Validation: `cd backend; python -m pytest tests/test_relations.py tests/test_ingestion_graph.py tests/test_api_documents.py -v`
  - Blocked Condition: None for unit implementation; `BLOCKED_BY_USER_ACTION` for live relation generation if required providers are not configured.
  - Files: `backend/app/services/relations.py`, `backend/app/graphs/ingestion_nodes.py`, `backend/app/graphs/ingestion_graph.py`, `backend/app/api/routes/documents.py`, `backend/app/models/schemas.py`, `backend/tests/test_relations.py`, `backend/tests/test_ingestion_graph.py`, `backend/tests/test_api_documents.py`

### Files or Modules Likely Created or Updated

- Summary and relation services.
- Ingestion state, nodes, graph, document routes/schemas, and tests.

### Required Outputs / Artifacts

- Atomic section/document summary generation.
- Canonical bounded relation generation and inspection.
- Passing focused Batch03 tests.

### Acceptance Criteria

- Summary inputs and outputs remain attributable to extracted text and exact chunk IDs.
- Relation evidence is limited to candidate chunks and one bounded document-level contract.
- Relation failure cannot invalidate otherwise complete indexing.

### Required Tests or Validations

- Run validation commands for (03A) and (03B).
- Verify disabled-feature branches call no external model provider.

### Explicit Non-Goals

- Do not implement a graph database, arbitrary entity graph, multi-hop expansion, or open-ended relation extraction.
- Do not route queries through relations until Batch04.

## Mandatory Batch04 - Query Decomposition and LangGraph Retrieval Routing

### Goal

Add bounded typed query planning and route subqueries through only the allowed semantic, keyword, metadata, and relation retrieval paths.

### Why this batch exists

Complex and cross-document questions require controlled decomposition and path selection while preserving deterministic fallbacks and explicit user scope.

### Inputs / Dependencies

- Accepted Batch02 hybrid retrieval and filter contracts.
- Accepted Batch03 summaries and bounded relations.
- Existing deterministic Phase 2 query graph.

### Tasks

- [x] (04A): Add bounded query planning with deterministic fallback
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 4: Query Decomposition and LangGraph Retrieval Routing` > `### Task 4.1: Add bounded query planning and deterministic fallback`
  - Source Requirements:
    - Request and validate the exact typed plan shape using the configured input model and strict JSON.
    - Normalize duplicate/blank subqueries and cap them at `QUERY_MAX_SUBQUERIES`.
    - Preserve explicit document IDs and let explicit filters override inferred values.
    - Convert every planner failure into one original-question hybrid or semantic subquery.
  - Details: Build a bounded planning service that cannot widen scope or introduce unbounded graph behavior.
  - Dependencies: (01A), (02C), shared filters, and current query prompts.
  - User Action: Configured model credentials are required only for live planning; tests must mock provider responses.
  - Agent Work: Implement strict plan prompting, normalization, precedence, fallback, and unit coverage.
  - Specific Steps:
    1. Define the planning prompt and strict JSON response for complexity, strategy, subqueries, inferred filters, and relation need.
    2. Use `SHOPAIKEY_INPUT_MODEL` with the configured zero temperature and output token cap.
    3. Normalize blank and duplicate subqueries, preserve stable IDs, apply the maximum, and restore the original question if empty.
    4. Merge filters field-by-field with explicit values taking precedence and preserve document IDs exactly.
    5. Map timeout, invalid JSON, unknown strategy, and invalid filters to the documented single-query fallback.
    6. Test simple/complex normalization, cap enforcement, precedence, scope preservation, and every fallback class.
  - Output: Typed `query_planning` service, prompt support, and focused tests.
  - Acceptance: Every plan is bounded and typed; planner output never widens explicit scope; all failures return the deterministic fallback.
  - Validation: `cd backend; python -m pytest tests/test_query_planning.py -v`
  - Blocked Condition: None for unit implementation; `BLOCKED_BY_USER_ACTION` for live planning if model credentials are missing.
  - Files: `backend/app/services/query_planning.py`, `backend/app/graphs/query_prompts.py`, `backend/tests/test_query_planning.py`

- [x] (04B): Route and merge semantic, keyword, metadata, and relation paths
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 4: Query Decomposition and LangGraph Retrieval Routing` > `### Task 4.2: Route and merge semantic, keyword, metadata, and relation paths`
  - Source Requirements:
    - Replace the Phase 2 graph start with the exact ordered Phase 3 query-node flow.
    - Route each strategy only to its allowed paths and require filters for metadata strategy.
    - Limit relation expansion to one hop and never add IDs outside an explicit allow-list.
    - Merge by chunk ID, retain subquery coverage, cap before reranking, and preserve no-result behavior.
  - Details: Integrate planning, scope resolution, retrieval, fusion, and later verification placeholders into one deterministic graph.
  - Dependencies: (04A), (02C), (03B), existing query state/nodes/graph, and Phase 2 insufficient-context behavior.
  - User Action: None.
  - Agent Work: Rewire graph/state, implement route-specific orchestration and scope rules, retain multi-subquery evidence, and add tests.
  - Specific Steps:
    1. Implement the ordered flow from `prepare_query` through `finalize_answer` and optional message saving.
    2. Route semantic, keyword, hybrid, metadata, and relation strategies to exactly the documented retrieval paths.
    3. Resolve at most one relation hop and cap related documents; never widen explicit `document_ids`.
    4. Fuse across paths/subqueries by chunk ID and preserve unique subquery IDs.
    5. Reserve one candidate per contributing subquery for comparison questions when available before filling by fusion score.
    6. Cap candidates before reranking and preserve safe insufficient-context behavior for successful empty paths.
    7. Test graph order, path calls, deduplication, scope, and planner/relation/one-path fallbacks.
  - Output: Phase 3 query graph routing and multi-subquery candidate merging.
  - Acceptance: Every strategy uses only allowed paths, relation expansion remains bounded, and graph behavior is deterministic under failure.
  - Validation: `cd backend; python -m pytest tests/test_query_planning.py tests/test_relations.py tests/test_score_fusion.py tests/test_query_graph.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/graphs/query_state.py`, `backend/app/graphs/query_nodes.py`, `backend/app/graphs/query_graph.py`, `backend/app/services/retrieval.py`, `backend/app/services/relations.py`, `backend/tests/test_query_graph.py`, `backend/tests/test_relations.py`

### Files or Modules Likely Created or Updated

- Query planning service and prompts.
- Query state, nodes, graph, retrieval/relation orchestration, and tests.

### Required Outputs / Artifacts

- Bounded typed planner and deterministic fallback.
- Strategy-specific graph routing and scope-safe multi-subquery merging.

### Acceptance Criteria

- Query plans never exceed configured bounds or override explicit scope.
- Query graph order and route calls match the approved Phase 3 flow.
- Empty and failed paths recover exactly as documented.

### Required Tests or Validations

- Run validation commands for (04A) and (04B).
- Inspect tests for explicit allow-list preservation and one-hop enforcement.

### Explicit Non-Goals

- Do not add autonomous planning, iterative tool loops, multiple relation hops, or planner-controlled document widening.
- Do not finalize citation and grounding behavior until Batch06.

## Mandatory Batch05 - Candidate Stages, Reranking, and Context Budgets

### Goal

Enforce every retrieval-stage cap, deterministic reranking fallback, and section-aware context selection within candidate and token budgets.

### Why this batch exists

Routing alone does not bound cost or context quality; independent caps and predictable selection are required before answer verification.

### Inputs / Dependencies

- Accepted Batch04 planned and routed query graph.
- Existing Jina reranking, neighbor expansion, tokenizer, source formatting, and frontend source list.

### Tasks

- [x] (05A): Add configurable candidate stages and stable reranking fallback
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 5: Candidate Stages, Reranking, and Context Budgets` > `### Task 5.1: Add configurable candidate stages and stable reranking fallback`
  - Source Requirements:
    - Enforce per-path, fused, rerank-candidate, final reranked, and context-stage caps independently in order.
    - Send only the configured candidate count to Jina and request the configured final count.
    - Use deterministic fusion/Qdrant/keyword/chunk-ID ordering for every Jina fallback.
    - Carry optional fusion, path, and citation metadata through backend and frontend sources.
  - Details: Make candidate volume and fallback ranking explicit, testable, and backward compatible.
  - Dependencies: (02C), (04B), existing Jina integration and source citation UI.
  - User Action: None.
  - Agent Work: Add independent caps, deterministic fallback sorting, metadata propagation, tests, and frontend display.
  - Specific Steps:
    1. Apply caps in the exact order: per path, fused, rerank input, final reranked, then context expansion.
    2. Slice only `RETRIEVAL_RERANK_CANDIDATE_TOP_K` candidates into Jina and request `RETRIEVAL_FINAL_TOP_K` outputs.
    3. Validate provider indexes and ignore provider response position as an implicit rank.
    4. For disabled, timeout, invalid, or exhausted Jina behavior, sort by fusion score, Qdrant score, keyword score, then chunk ID.
    5. Preserve Phase 2 source fields while adding optional fusion score, paths, and citation key.
    6. Extend frontend types and source details to tolerate both Phase 2 and Phase 3 saved data.
    7. Test every cap and fallback order and run the frontend production build.
  - Output: Bounded reranking pipeline and backward-compatible retrieval metadata UI.
  - Acceptance: Every stage cap is independent, Jina input/output counts are correct, and all fallback ranks are stable.
  - Validation: `cd backend; python -m pytest tests/test_query_graph.py tests/test_score_fusion.py -v`; then `cd ../frontend; npm run build`
  - Blocked Condition: None.
  - Files: `backend/app/services/retrieval.py`, `backend/app/graphs/query_nodes.py`, `backend/app/graphs/query_formatting.py`, `backend/app/models/schemas.py`, `backend/tests/test_query_graph.py`, `frontend/src/api/types.ts`, `frontend/src/components/SourceList.tsx`

- [x] (05B): Enforce section boundaries and token-budgeted context
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 5: Candidate Stages, Reranking, and Context Budgets` > `### Task 5.2: Enforce section boundaries and a token context budget`
  - Source Requirements:
    - Use stored token counts or the chunking tokenizer fallback.
    - Preserve the exact ranked/boundary/same-section/generic-neighbor selection order.
    - Enforce token and candidate caps with only the documented top-chunk truncation exception.
    - Reserve multi-subquery coverage, deduplicate stably, and record compact selection metrics.
  - Details: Build final answer context predictably without mutating stored content or citation identity.
  - Dependencies: (05A), current retrieval context expansion and tokenizer behavior.
  - User Action: None.
  - Agent Work: Refactor context selection, implement budget checks and prompt-only truncation, capture metrics, and test boundaries.
  - Specific Steps:
    1. Resolve token cost from `token_count` or the same tokenizer used by ingestion chunking.
    2. Select final ranked chunks first, then requested boundary chunks, exact-section neighbors, and generic same-document neighbors.
    3. Reserve one available top candidate per subquery before neighbor filling.
    4. Deduplicate by chunk ID while keeping the first selected position stable.
    5. Enforce token and candidate caps before each addition.
    6. If the highest-ranked chunk alone exceeds tokens, retain citation identity and stored content while truncating only its prompt copy and marking it.
    7. Record selected tokens/candidates/neighbors and per-subquery coverage and test every edge case.
  - Output: Section-aware, token-budgeted context selector with compact metrics.
  - Acceptance: Context obeys configured caps and ordering, coverage is preserved when possible, and prompt truncation never alters source identity or persistence.
  - Validation: `cd backend; python -m pytest tests/test_retrieval_context.py tests/test_query_graph.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/services/retrieval_context.py`, `backend/app/graphs/query_formatting.py`, `backend/tests/test_retrieval_context.py`, `backend/tests/test_query_graph.py`

### Files or Modules Likely Created or Updated

- Retrieval/reranking, query nodes/formatting, schemas, context selection, frontend source details, and tests.

### Required Outputs / Artifacts

- Independently capped candidate pipeline.
- Stable reranking fallback.
- Section-aware, token-budgeted context with coverage metrics.

### Acceptance Criteria

- All caps are enforced at the correct stage.
- Jina failure cannot make ordering nondeterministic.
- Context selection and truncation follow the exact documented order and exception.

### Required Tests or Validations

- Run validation commands for (05A) and (05B).
- Confirm frontend compatibility with missing optional Phase 3 fields.

### Explicit Non-Goals

- Do not change stored chunk content or citation identity during prompt truncation.
- Do not add model-driven context expansion or unbounded neighbor traversal.

## Mandatory Batch06 - Exact Citations and Grounding Verification

### Goal

Return factual answers only when citation keys map to the exact generation context and a bounded grounding gate passes.

### Why this batch exists

Retrieved context alone does not prove that generated claims are cited and supported; a strict validation and regeneration boundary is required.

### Inputs / Dependencies

- Accepted Batch05 final context ordering and source metadata.
- Existing answer generation and optional message persistence.

### Tasks

- [x] (06A): Generate and validate exact chunk-keyed citations
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 6: Exact Citations and Grounding Verification` > `### Task 6.1: Generate and validate chunk-keyed citations`
  - Source Requirements:
    - Assign stable prompt-local `S1`, `S2`, and later keys after final context ordering.
    - Require `[S<number>]` factual citations and accept only keys present in generation context.
    - Return only cited exact chunks in first-citation order and reject substitute labels.
    - Store compact validation results in query/message state without the full validation prompt.
  - Details: Bind answer citations to exact chunk identities and prevent uncited context from appearing as returned support.
  - Dependencies: (05B), query prompts/formatting/nodes, and existing message metadata.
  - User Action: None.
  - Agent Work: Add citation-key formatting, marker extraction and validation, source filtering, state persistence, and tests.
  - Specific Steps:
    1. Assign sequential keys after the final stable context order and include each key beside the exact chunk ID in the prompt context.
    2. Update answer instructions to require `[S1]`-style factual citations except for the safe insufficient-context response.
    3. Extract valid markers, reject unknown or malformed markers, and map accepted keys to exact chunk IDs.
    4. Treat a non-empty factual answer without a valid citation as invalid.
    5. Return cited sources only, deduplicated in first-citation order; reject document IDs/headings/invented labels as substitutes.
    6. Store the compact validation result and ensure optional saved-message sources match returned sources.
    7. Test valid, unknown, malformed, absent, duplicate, and uncited-context behavior.
  - Output: Citation validation service and exact source-selection pipeline.
  - Acceptance: Every returned citation maps to an exact context chunk, and uncited or invented sources never reach the response.
  - Validation: `cd backend; python -m pytest tests/test_citation_validation.py tests/test_query_graph.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/services/citation_validation.py`, `backend/app/graphs/query_prompts.py`, `backend/app/graphs/query_formatting.py`, `backend/app/graphs/query_nodes.py`, `backend/tests/test_citation_validation.py`, `backend/tests/test_query_graph.py`

- [x] (06B): Verify grounding with one bounded regeneration
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 6: Exact Citations and Grounding Verification` > `### Task 6.2: Verify grounding and perform one bounded regeneration`
  - Source Requirements:
    - Verify the generated answer only against exact cited chunk text using the strict grounding JSON contract.
    - Accept only valid citations, `grounded=true`, and score at or above `GROUNDING_MIN_SCORE`.
    - Regenerate once by default with compact feedback, then revalidate and reverify.
    - On repeated or provider verification failure, return the exact safe response with no sources and never expose the draft.
  - Details: Add a fail-closed answer gate to the query graph.
  - Dependencies: (06A), existing answer generation, graph routing, and retry-aware provider client behavior.
  - User Action: Configured model credentials are required for live grounding acceptance; tests must mock provider responses.
  - Agent Work: Implement grounding service/prompt, conditional graph transitions, regeneration, safe finalization, and API/message tests.
  - Specific Steps:
    1. Request strict grounding JSON containing `grounded`, score, unsupported claims, and missing citations.
    2. Limit verifier evidence to the exact cited chunk texts from the generation context.
    3. Combine citation validity and grounding threshold into one answer-acceptance decision.
    4. On first failure, call a dedicated regeneration node once with original context and compact verifier feedback.
    5. Re-run citation validation and grounding after regeneration.
    6. After the configured maximum or grounding-provider failure, return the exact safe insufficient-context sentence and empty sources.
    7. Test pass, one regeneration, repeated failure, provider failure, and absence of unverified drafts in responses/messages.
  - Output: Grounding service and fail-closed bounded verification graph.
  - Acceptance: No answer reaches `ChatResponse` or message persistence unless it passes citation and grounding gates; failed verification returns only the safe response.
  - Validation: `cd backend; python -m pytest tests/test_grounding.py tests/test_citation_validation.py tests/test_query_graph.py tests/test_api_chat.py -v`
  - Blocked Condition: None for unit implementation; `BLOCKED_BY_USER_ACTION` for live verification if the model provider is not configured.
  - Files: `backend/app/services/grounding.py`, `backend/app/graphs/query_prompts.py`, `backend/app/graphs/query_nodes.py`, `backend/app/graphs/query_graph.py`, `backend/tests/test_grounding.py`, `backend/tests/test_query_graph.py`, `backend/tests/test_api_chat.py`

### Files or Modules Likely Created or Updated

- Citation and grounding services.
- Query prompts, formatting, nodes, graph, API tests, and message metadata behavior.

### Required Outputs / Artifacts

- Exact chunk-keyed citations.
- Fail-closed grounding gate with at most the configured regeneration count.

### Acceptance Criteria

- Returned sources are only valid cited context chunks.
- Every factual answer passes both gates.
- Repeated verification failure exposes no unchecked draft and returns no sources.

### Required Tests or Validations

- Run validation commands for (06A) and (06B).
- Inspect saved-message assertions for exact parity with returned validated sources.

### Explicit Non-Goals

- Do not persist full verifier prompts, full model responses, or unverified answer drafts in traces.
- Do not add unbounded regeneration or allow provider failure to bypass verification.

## Mandatory Batch07 - RAG Evaluation Dataset and Metrics

### Goal

Add a versioned deterministic text-only corpus, exact evaluation metrics, timestamped reports, and enforceable quality gates.

### Why this batch exists

Phase 3 retrieval and grounding quality must be measurable with reproducible cases rather than inferred from unit behavior alone.

### Inputs / Dependencies

- Accepted production query workflow through Batch06.
- Existing upload/index services and current document formats.

### Tasks

- [x] (07A): Add a versioned text-only evaluation corpus and dataset contract
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 7: RAG Evaluation Dataset and Metrics` > `### Task 7.1: Add a versioned text-only evaluation corpus and dataset contract`
  - Source Requirements:
    - Define the exact JSONL row fields and validate row consistency and fixture references.
    - Include at least twelve deterministic cases covering every named retrieval and answer-quality scenario.
    - Use small original text-only fixtures with uniquely attributable evidence except explicit cross-document cases.
    - Seed through existing services, reuse duplicates, wait for ready status, and never print credentials.
  - Details: Create reproducible evaluation inputs that exercise production ingestion and query contracts.
  - Dependencies: Accepted Batch06, existing upload/index lifecycle, and configured document formats.
  - User Action: For live seeding, the user must configure and authorize Supabase, Qdrant, ShopAIKey, and Jina credentials/resources in local `.env`; no secret values belong in source or reports.
  - Agent Work: Add fixtures, dataset, validator, seed script, and deterministic unit tests.
  - Specific Steps:
    1. Implement the dataset row contract with question, titles, evidence, answer terms, no-result flag, filters, and tags.
    2. Write three small original Markdown policy fixtures with deliberately unique evidence phrases.
    3. Add at least twelve cases for semantic, keyword, each filter class, decomposition, comparison, relations, citations, insufficient context, and conflict.
    4. Validate JSONL syntax, unique case IDs, known titles, and positive/no-result evidence rules.
    5. Implement a seed script that calls existing upload and index services, handles duplicate hashes, waits for ready, and prints safe title-to-ID mappings.
    6. Keep credentials and raw secret-bearing errors out of output.
    7. Test dataset validation and run the module CLI.
  - Output: Versioned evaluation fixtures, JSONL dataset, validator, seed script, and tests.
  - Acceptance: The dataset validates, contains at least twelve unique deterministic cases, and seeding uses production application services safely.
  - Validation: `cd backend; python -m pytest tests/test_evaluation_metrics.py -v; python -m app.evaluation.dataset evaluation/datasets/phase3_v1.jsonl`
  - Blocked Condition: None for dataset/unit implementation; `BLOCKED_BY_USER_ACTION` for live seeding until required external services and credentials are configured.
  - Files: `backend/app/evaluation/__init__.py`, `backend/app/evaluation/dataset.py`, `backend/evaluation/fixtures/leave_policy.md`, `backend/evaluation/fixtures/pricing_policy.md`, `backend/evaluation/fixtures/security_policy.md`, `backend/evaluation/datasets/phase3_v1.jsonl`, `backend/scripts/seed_evaluation_corpus.py`, `backend/tests/test_evaluation_metrics.py`

- [x] (07B): Implement retrieval, citation, grounding, and answer metrics
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 7: RAG Evaluation Dataset and Metrics` > `### Task 7.2: Implement retrieval, grounding, citation, and answer metrics`
  - Source Requirements:
    - Implement every exact metric formula from the plan, including empty/fewer-than-k handling.
    - Capture all evaluation fields through production query logic without bypassing retrieval.
    - Write ignored timestamped JSON reports and expose CLI thresholds with nonzero failure exits.
    - Use the documented default gates and hand-calculated unit fixtures.
  - Details: Turn runtime outputs into auditable quality measurements and CI-friendly gates.
  - Dependencies: (07A), accepted Batch06 query workflow and compact workflow outputs.
  - User Action: Live evaluation requires the evaluation corpus to be seeded and all external services configured.
  - Agent Work: Implement formulas, runner/reporting, CLI/gates, git ignore, and comprehensive metric tests.
  - Specific Steps:
    1. Implement recall-at-k, precision-at-k, rerank lift, no-result rates, citation validity, grounding pass, answer coverage, and forbidden-term rate exactly.
    2. Define safe behavior for empty datasets, fewer-than-k results, expected no-result cases, and absent term denominators.
    3. Capture pre/post-rerank, context, answer, sources, grounding, route, and latency from production workflow execution.
    4. Write timestamped JSON under `backend/evaluation/results/` and ignore generated reports.
    5. Add CLI dataset/output/k/threshold options and exact default gates.
    6. Return nonzero when any threshold fails and document all options in `--help`.
    7. Unit-test formulas with hand-calculated examples and verify the CLI help path requires no live network.
  - Output: Evaluation metrics library, runner, CLI, reports contract, ignore rule, and tests.
  - Acceptance: Unit metrics match hand calculations, reports capture production workflow results, and threshold violations fail the CLI.
  - Validation: `cd backend; python -m pytest tests/test_evaluation_metrics.py -v; python scripts/run_rag_evaluation.py --help`
  - Blocked Condition: None for unit/CLI implementation; `BLOCKED_BY_USER_ACTION` for the external acceptance run until seeding and provider configuration are complete.
  - Files: `backend/app/evaluation/metrics.py`, `backend/app/evaluation/runner.py`, `backend/scripts/run_rag_evaluation.py`, `backend/.gitignore`, `backend/tests/test_evaluation_metrics.py`

### Files or Modules Likely Created or Updated

- Evaluation package, fixtures, dataset, seeding/evaluation scripts, generated-results ignore rule, and tests.

### Required Outputs / Artifacts

- Valid `phase3_v1.jsonl` with at least twelve cases.
- Exact metric implementation and threshold CLI.
- Timestamped report format for later live acceptance.

### Acceptance Criteria

- Dataset and fixtures are deterministic, original, and text-only.
- Metrics follow the plan formulas exactly and are tested against hand calculations.
- Runner uses production retrieval/query logic and threshold failure is machine-detectable.

### Required Tests or Validations

- Run validation commands for (07A) and (07B).
- Defer the external-service evaluation command to (09C).

### Explicit Non-Goals

- Do not commit generated result reports.
- Do not include external copyrighted datasets, credentials, or a separate evaluation-only retrieval implementation.

## Mandatory Batch08 - Workflow Observability and Failure Recovery

### Goal

Persist compact redacted workflow traces and add bounded retries with exact deterministic recovery behavior.

### Why this batch exists

Advanced workflows require inspectable timing/failure evidence and controlled transient-failure handling without leaking content or changing valid API outcomes.

### Inputs / Dependencies

- Accepted workflow and services from Batches01 through 07.
- Workflow persistence foundation from (01B).

### Tasks

- [x] (08A): Persist compact ingestion and query traces
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 8: Workflow Observability and Failure Recovery` > `### Task 8.1: Persist compact ingestion and query traces`
  - Source Requirements:
    - Create/close workflow runs at API boundaries and instrument every graph node with exact compact event fields.
    - Record aggregate retrieval route/count/token/grounding/citation/latency data.
    - Redact all source text, prompts, model responses, secrets, headers, and credential-bearing URLs.
    - Keep writes best-effort and add protected, bounded list/detail inspection endpoints.
  - Details: Make successful and failed workflows diagnosable through compact safe telemetry.
  - Dependencies: (01B), completed ingestion/query graphs, API token dependency, and retrieval metrics.
  - User Action: Live trace persistence requires the Phase 3 migration and configured Supabase project; unit tests must mock persistence.
  - Agent Work: Instrument API/graphs, enforce redaction and lifecycle closure, add endpoints/routes, and test failure isolation.
  - Specific Steps:
    1. Create a run at ingestion/chat invocation and close it completed or failed on every graph exit.
    2. Wrap every graph node with name, status, attempt, timestamps, duration, optional provider, counts, route/fallback, and safe code.
    3. Add aggregate subquery, path, fusion, rerank, context, token, grounding, citation, and latency totals.
    4. Centralize redaction so raw content, prompts, full model answers, authorization, keys, and credential URLs cannot persist.
    5. Catch and warn on every observability write failure without altering the primary API result.
    6. Add admin-token-protected list and detail routes with `1..100` limit clamping, newest-first order, and 404 behavior.
    7. Test success/failure closure, duration/attempt events, safe traces, route protection, and persistence failure isolation.
  - Output: Redacted workflow tracing, lifecycle instrumentation, inspection API, and tests.
  - Acceptance: Every workflow is closed when persistence is available; traces contain useful counts/routes but no prohibited content; trace failure is nonfatal.
  - Validation: `cd backend; python -m pytest tests/test_observability.py tests/test_api_observability.py tests/test_ingestion_graph.py tests/test_query_graph.py -v`
  - Blocked Condition: None for unit implementation; `BLOCKED_BY_USER_ACTION` for live trace persistence until migration and Supabase configuration are complete.
  - Files: `backend/app/services/observability.py`, `backend/app/graphs/ingestion_graph.py`, `backend/app/graphs/query_graph.py`, `backend/app/api/routes/chat.py`, `backend/app/api/routes/documents.py`, `backend/app/api/routes/observability.py`, `backend/app/main.py`, `backend/tests/test_api_observability.py`, `backend/tests/test_observability.py`, `backend/tests/test_ingestion_graph.py`, `backend/tests/test_query_graph.py`

- [x] (08B): Add retry classification and deterministic recovery
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 8: Workflow Observability and Failure Recovery` > `### Task 8.2: Add retry classification and deterministic recovery`
  - Source Requirements:
    - Implement injectable synchronous exponential backoff bounded by configured attempts and maximum delay.
    - Retry only timeouts, connections, HTTP 429, and HTTP 5xx; run contract and specified 4xx failures once.
    - Apply retries to every listed storage/model/database/vector/rerank operation.
    - Record attempts and enforce the exact planner/path/relation/Jina/grounding/persistence/ingestion fallbacks.
  - Details: Add reusable transient-failure handling without hiding contract failures or waiting in tests.
  - Dependencies: (08A), all external-service call sites, and configured retry settings from (01A).
  - User Action: None for unit implementation.
  - Agent Work: Implement retry helper/classification, wrap specified call sites, wire stable error codes/fallbacks, trace attempts, and test with no-op sleep.
  - Specific Steps:
    1. Build a synchronous helper with injectable sleep and monotonic clock and capped exponential delay.
    2. Classify timeout, connection, 429, and 5xx errors as retryable and all documented validation/4xx/contract cases as single-attempt.
    3. Apply the helper to storage, embeddings, Qdrant operations, keyword RPC, Jina, summary/relation generation, answer generation, and grounding.
    4. Record every attempt and final route/fallback in compact traces.
    5. Implement the exact planner, semantic/keyword, relation, Jina, grounding, and persistence recovery contracts.
    6. On exhausted retryable ingestion failure, mark failed with a stable `error_code`; keep ready indexing after exhausted relation updates.
    7. Test delay caps, classifications, attempts, recovery, final failures, and no real sleeping.
  - Output: Reusable retry module, wrapped provider operations, stable fallbacks/error codes, and tests.
  - Acceptance: Retryable failures recover within bounds, non-retryable failures run once, and final outcomes exactly match the plan.
  - Validation: `cd backend; python -m pytest tests/test_retry.py tests/test_ingestion_graph.py tests/test_query_graph.py tests/test_observability.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/core/retry.py`, `backend/app/graphs/ingestion_nodes.py`, `backend/app/graphs/query_nodes.py`, `backend/app/services/retrieval.py`, `backend/app/services/keyword_search.py`, `backend/app/services/summaries.py`, `backend/app/services/relations.py`, `backend/app/services/grounding.py`, `backend/tests/test_retry.py`, `backend/tests/test_ingestion_graph.py`, `backend/tests/test_query_graph.py`

### Files or Modules Likely Created or Updated

- Observability service, graph/API instrumentation, observability routes, retry helper, provider call sites, and tests.

### Required Outputs / Artifacts

- Compact redacted workflow runs and inspection APIs.
- Bounded retry behavior and exact deterministic recovery.

### Acceptance Criteria

- Successful and failed workflows close traces without storing prohibited data.
- Best-effort persistence cannot change a valid ingestion/chat result.
- Attempt counts, backoff, stable error codes, and final fallbacks are testable and exact.

### Required Tests or Validations

- Run validation commands for (08A) and (08B).
- Confirm tests inject no-op sleep and make no live network calls.

### Explicit Non-Goals

- Do not persist request/response bodies, source content, secrets, or full generated answers in traces.
- Do not retry all exceptions, add asynchronous job infrastructure, or make retries unbounded.

## Mandatory Batch09 - Documentation and End-to-End Validation

### Goal

Document Phase 3 operations and prove the complete implementation through automated, manual, and external-service validation.

### Why this batch exists

The milestone is incomplete until migration/reindex operations, settings, safety constraints, and end-to-end quality gates are documented and verified.

### Inputs / Dependencies

- All accepted implementation Batches01 through 08.
- User-configured external services for the manual migration, reindex, smoke, seed, and evaluation steps.

### Tasks

- [ ] (09A): Update Phase 3 setup, migration, architecture, and operations documentation
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 9: Documentation and End-to-End Validation` > `### Task 9.1: Update setup, migration, architecture, and operations documentation`
  - Source Requirements:
    - Document the complete Phase 3 query and trace architecture.
    - Document every new setting/default and both existing-project migration and fresh-project schema paths.
    - Document required reindexing, inspection endpoints, evaluation commands/gates, retries, and trace redaction.
    - Preserve text-only and single-user security limitations.
  - Details: Make installation, upgrade, operation, diagnosis, and evaluation reproducible for maintainers.
  - Dependencies: Accepted Batches01 through 08 and final implemented behavior.
  - User Action: None.
  - Agent Work: Update root/backend READMEs with accurate commands, diagrams, settings, endpoints, constraints, and operational sequences.
  - Specific Steps:
    1. Update architecture diagrams for planning, parallel retrieval, RRF, relation scope, reranking, context budgeting, citation, grounding, and tracing.
    2. Document every Phase 3 setting and exact default.
    3. Document existing-project migration versus fresh schema setup, including backup/authorization cautions.
    4. State that existing documents require reindex for MIME payloads, summaries, relations, and metadata.
    5. Document summary/relation/observability endpoints and admin-token behavior.
    6. Document evaluation seed/run/report/gate behavior and bounded retry/fallback rules.
    7. Preserve text-extraction-only limitations, secret handling, and single-user warnings.
  - Output: Updated root and backend documentation.
  - Acceptance: Documentation matches implemented Phase 3 behavior and provides complete safe upgrade, reindex, inspection, and evaluation instructions.
  - Validation: Manually review `README.md` and `backend/README.md` against every new setting, endpoint, command, limitation, and architecture stage in the source plan.
  - Blocked Condition: None.
  - Files: `README.md`, `backend/README.md`

- [ ] (09B): Run full automated verification
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 9: Documentation and End-to-End Validation` > `### Task 9.2: Run full automated verification`
  - Source Requirements:
    - Run the complete backend pytest suite with no network required by unit tests.
    - Run the frontend TypeScript/Vite production build.
    - Validate the Phase 3 evaluation dataset through its module CLI.
  - Details: Prove repository-level regression safety before any live mutation or external smoke test.
  - Dependencies: (09A) and all code/test tasks through (08B).
  - User Action: None.
  - Agent Work: Run all commands, fix in-scope failures, record exact results, and check off only after every command passes.
  - Specific Steps:
    1. From `backend`, run `python -m pytest -v`.
    2. Confirm tests use mocks/fakes and do not require network access.
    3. From `frontend`, run `npm run build`.
    4. From `backend`, run the dataset validation module against `phase3_v1.jsonl`.
    5. Record commands, exit results, and any resolved failures in the execution report.
  - Output: Complete automated verification evidence.
  - Acceptance: Backend tests, frontend build, and dataset validation all exit successfully.
  - Validation: `cd backend; python -m pytest -v`; then `cd ../frontend; npm run build`; then `cd ../backend; python -m app.evaluation.dataset evaluation/datasets/phase3_v1.jsonl`
  - Blocked Condition: None; a failing command is incomplete/failed, not complete.
  - Files: No new files; only in-scope fixes discovered by verification may be updated.

- [ ] (09C): Run manual Phase 3 smoke and evaluation acceptance
  - Source of Truth: `docs/plans/Plan_3.md` > `## Batch 9: Documentation and End-to-End Validation` > `### Task 9.3: Run manual Phase 3 smoke and evaluation tests`
  - Source Requirements:
    - Apply the migration and reindex existing test documents before live Phase 3 checks.
    - Start backend/frontend and exercise every named retrieval, filtering, planning, relation, fallback, context, citation, grounding, endpoint, trace, and retry flow.
    - Seed and run the evaluation suite through production services.
    - Require all default evaluation gates and a timestamped JSON report.
  - Details: Validate the full milestone against real configured providers and user-owned infrastructure.
  - Dependencies: (09B), configured external services, applied database migration, and test documents safe to reindex.
  - User Action: User must authorize/apply the database migration, supply real local credentials without sharing them in chat or reports, confirm target Supabase/Qdrant resources, and permit reindexing/seeding against those resources.
  - Agent Work: After user confirmation, apply only the authorized migration workflow, reindex test data, start services, execute the complete smoke checklist, seed fixtures, run evaluation, and record safe results.
  - Specific Steps:
    1. Confirm the target project/resources and required environment variables without printing secret values.
    2. Apply `docs/database/phase3_migration.sql` using the user's authorized process and confirm schema objects safely.
    3. Reindex selected existing test documents to populate MIME payloads, summaries, relations, and Phase 3 metadata.
    4. Start backend on port 8000 and frontend on `127.0.0.1:5173`.
    5. Execute exact-term, paraphrase, all filters, decomposition, comparison, relation scope, Jina fallback, context-budget, citation, grounding, endpoint, redaction, and retry checks.
    6. Run `python scripts/seed_evaluation_corpus.py` and record safe title-to-ID mappings.
    7. Run the evaluation CLI, verify every default gate, and record the timestamped report path without including secrets or raw sensitive content.
  - Output: Manual smoke evidence, seeded evaluation corpus, and passing timestamped evaluation report.
  - Acceptance: Every manual flow passes, trace redaction is confirmed, and all default evaluation gates pass.
  - Validation: Start commands from the source plan; then `cd backend; python scripts/seed_evaluation_corpus.py; python scripts/run_rag_evaluation.py --dataset evaluation/datasets/phase3_v1.jsonl`
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` until the user supplies/authorizes external setup, migration target, reindex scope, and credentials locally; missing credentials or provider projects must never be fabricated.
  - Files: No required source changes; generated report under `backend/evaluation/results/` remains ignored.

### Files or Modules Likely Created or Updated

- `README.md`, `backend/README.md`.
- In-scope source/test fixes found during automated verification.
- Ignored evaluation result artifact from live acceptance.

### Required Outputs / Artifacts

- Complete Phase 3 documentation.
- Passing backend suite, frontend build, and dataset validation.
- Authorized live smoke evidence and passing evaluation report.

### Acceptance Criteria

- All Phase 1 and 2 behavior remains passing and backward compatible.
- Every Phase 3 acceptance criterion from the source plan is satisfied.
- Live database/provider actions are completed only with explicit user configuration and authorization.

### Required Tests or Validations

- Run (09B) commands before live actions.
- Complete every (09C) flow and default evaluation gate after user setup.
- Record safe command results and artifact paths in the execution report.

### Explicit Non-Goals

- Do not fabricate live credentials, projects, document IDs, smoke results, or evaluation results.
- Do not introduce new features during final validation except in-scope corrections required to satisfy the approved plan.

## Optional Future Tracks

No optional future track is defined by `docs/plans/Plan_3.md`. Authentication, multi-user SaaS behavior, OCR/image processing, autonomous agents, unbounded graph behavior, general knowledge graphs, new providers/databases/frameworks, and unsupported file formats remain out of scope rather than optional Phase 3 work.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05
- Batch05 -> Batch06
- Batch06 -> Batch07
- Batch07 -> Batch08
- Batch08 -> Batch09

There are no optional tracks outside this mandatory chain.

## Global Verification Checklist

- [ ] All twenty task IDs are complete and every mandatory batch is accepted in order.
- [ ] All Phase 1 and Phase 2 backend tests still pass.
- [ ] Existing requests without Phase 3 filters and saved Phase 2 messages remain compatible.
- [ ] Planning is typed, bounded, and deterministic under failure.
- [ ] Explicit document selection is never widened by planning or relations.
- [ ] Semantic and keyword paths share filter semantics and fuse deterministically by chunk ID.
- [ ] Candidate, rerank, final, context-count, and context-token caps are independently enforced.
- [ ] Summaries use extracted text only and retain exact source chunk IDs.
- [ ] Relations are bounded, canonical, evidence-backed, one-hop, and limited to allowed types.
- [ ] Returned sources are only cited chunks from the exact answer context.
- [ ] Every factual answer passes citation and grounding verification; no unchecked draft is returned or saved.
- [ ] Evaluation data covers all required scenarios and metric formulas match the source plan.
- [ ] Workflow traces contain timing, counts, attempts, routes, and safe errors but no prohibited content or secrets.
- [ ] Retry classifications, capped backoff, stable ingestion errors, and query fallbacks match the plan.
- [ ] Full backend tests, frontend build, and dataset validation pass without unit-test network access.
- [ ] Authorized manual smoke checks and external evaluation gates pass.
- [ ] Documentation covers architecture, settings, migration, reindex, endpoints, evaluation, retries, redaction, security, and limitations.
- [ ] No authentication, multi-user, OCR, image processing, autonomous-agent, general graph, new provider, or unbounded workflow feature was introduced.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [x] Batch01 - Phase 3 Contracts, Settings, and Persistence
- [x] Batch02 - Metadata-Aware Keyword and Hybrid Retrieval
- [x] Batch03 - Document Summaries and Lightweight Relations
- [x] Batch04 - Query Decomposition and LangGraph Retrieval Routing
- [x] Batch05 - Candidate Stages, Reranking, and Context Budgets
- [x] Batch06 - Exact Citations and Grounding Verification
- [x] Batch07 - RAG Evaluation Dataset and Metrics
- [ ] Batch08 - Workflow Observability and Failure Recovery
- [ ] Batch09 - Documentation and End-to-End Validation

### Task IDs

#### Batch01

- [x] (01A): Add typed retrieval, planning, verification, and state contracts
- [x] (01B): Add the idempotent Phase 3 schema and persistence services

#### Batch02

- [x] (02A): Add metadata filters to ingestion payloads, chat retrieval, and frontend
- [x] (02B): Add Postgres full-text keyword retrieval
- [x] (02C): Add deterministic reciprocal-rank fusion and hybrid fallback

#### Batch03

- [x] (03A): Generate section and document summaries during ingestion
- [x] (03B): Build and query bounded document relations

#### Batch04

- [x] (04A): Add bounded query planning with deterministic fallback
- [x] (04B): Route and merge semantic, keyword, metadata, and relation paths

#### Batch05

- [x] (05A): Add configurable candidate stages and stable reranking fallback
- [x] (05B): Enforce section boundaries and token-budgeted context

#### Batch06

- [x] (06A): Generate and validate exact chunk-keyed citations
- [x] (06B): Verify grounding with one bounded regeneration

#### Batch07

- [x] (07A): Add a versioned text-only evaluation corpus and dataset contract
- [x] (07B): Implement retrieval, citation, grounding, and answer metrics

#### Batch08

- [x] (08A): Persist compact ingestion and query traces
- [x] (08B): Add retry classification and deterministic recovery

#### Batch09

- [ ] (09A): Update Phase 3 setup, migration, architecture, and operations documentation
- [ ] (09B): Run full automated verification
- [ ] (09C): Run manual Phase 3 smoke and evaluation acceptance

## Completion Reporting Rules for Future Execution Agents

Future execution agents must not claim completion unless the task validations and acceptance criteria are satisfied. Update the detailed task checkbox, matching progress-tracker checkbox, and batch checkbox only after evidence exists. Use the following template after each batch:

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
- reason: missing API key, missing provider project, missing migration authorization, missing manual setup, or other safe summary

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

Create the source-plan commit for an accepted batch only after its task report has been reviewed and accepted:

- Batch01: `feat: add phase 3 contracts and persistence`
- Batch02: `feat: add metadata-aware hybrid retrieval`
- Batch03: `feat: add summaries and document relations`
- Batch04: `feat: add query planning and retrieval routing`
- Batch05: `feat: tune candidate reranking and context budgets`
- Batch06: `feat: validate citations and answer grounding`
- Batch07: `test: add rag evaluation dataset and metrics`
- Batch08: `feat: add workflow tracing and failure recovery`
- Batch09: `docs: document and verify phase 3 advanced rag`
