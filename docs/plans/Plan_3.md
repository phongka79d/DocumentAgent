# RagDocument Phase 3 Advanced RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Depends on:** `docs/plans/Master_Plan.md`, `docs/plans/Plan_1.md`, `docs/plans/Plan_2.md`, `README.md`
**Master Plan Version:** MVP v1.1
**Scope:** Phase 3 only: advanced text-based retrieval, reasoning quality, evaluation, observability, and failure recovery on top of completed Phases 1 and 2.
**Goal:** Add decomposed and routed retrieval, hybrid and metadata-aware search, summaries and lightweight document relations, verifiable grounded answers, measurable RAG quality, and recoverable LangGraph workflows without adding authentication, OCR, or autonomous agents.

**Architecture:** Preserve the current React/FastAPI/Supabase/Qdrant/ShopAIKey/Jina stack and the existing upload, ingestion, and query boundaries. Extend the deterministic LangGraph workflows with typed planning and verification nodes; keep retrieval paths independently testable, normalize their candidates into one contract, fuse them deterministically, and persist only compact summaries, relations, and workflow traces.

**Tech Stack:** React, Vite, TypeScript, FastAPI, Pydantic, LangGraph, Supabase Postgres/Storage, Qdrant Cloud, ShopAIKey OpenAI-compatible API, Jina Reranker API, tiktoken, pytest.

---

## Current Progress Baseline

`README.md` and the current repository show Phases 1 and 2 are implemented. Treat the following as existing behavior and do not rebuild it:

- FastAPI settings/security, Supabase and Qdrant clients, ShopAIKey and Jina integrations.
- Upload hashing and validation, duplicate handling, storage, document lifecycle APIs, indexing, reindexing, deletion, and chunk inspection.
- PDF, DOCX, TXT, Markdown, and HTML structured parsing.
- Fixed-token and smart-section chunking with heading scoring, table preservation, section paths, and page metadata.
- Deterministic LangGraph ingestion and query workflows with safe failure routing.
- Qdrant semantic retrieval, document filtering, Jina reranking with score fallback, retrieval hints, boundary expansion, section-aware neighbor expansion, and context caps.
- Grounded answer generation, source citations, optional message saving, message history, and source-chunk inspection.
- React document management, chat, document selection, source viewer, adjacent-chunk navigation, and history restore.
- Backend tests and frontend production-build verification.

Phase 3 extends these surfaces. Existing response fields and Phase 1/2 configuration must remain backward compatible unless this plan explicitly adds an optional field.

---

## Master Plan Contract

Implement every Phase 3 item from `docs/plans/Master_Plan.md`:

- LangGraph query decomposition for complex questions.
- LangGraph retrieval routing across semantic, keyword, metadata-filtered, and relation-aware paths.
- Hybrid search using Qdrant semantic search plus Postgres full-text search and deterministic score fusion.
- Metadata filters for document, MIME/file type, heading, section path, and page range.
- Configurable candidate and reranking stages with deterministic fallbacks.
- Section-boundary-aware context expansion constrained by a token budget.
- Document summaries and section summaries generated only from extracted text.
- A lightweight document relation graph and bounded cross-document reasoning.
- Grounding verification before returning an answer.
- Citation validation against the exact context chunks used for generation.
- A versioned RAG evaluation corpus and checks for retrieval, grounding, citations, and answer quality.
- Retrieval metrics: recall-at-k, precision-at-k, rerank lift, and no-result rate.
- Ingestion and query observability for node timing, attempts, external failures, routes, and retrieval traces.
- Retry and deterministic recovery behavior for retryable ingestion and query failures.

Preserve these constraints:

- Single-user deployment; optional `X-Admin-API-Token` remains the only application gate.
- Upload and indexing remain separate operations.
- LangGraph workflows remain bounded, deterministic, and inspectable.
- Original files remain in Supabase Storage; metadata remains in Supabase Postgres; chunk vectors remain in Qdrant.
- Answers use only validated retrieved context.
- OCR, image extraction, scanned-document processing, and image-only formats remain unsupported.

Do not add:

- Login, signup, OAuth, Supabase Auth, users, profiles, organizations, roles, tenants, or access-control tables.
- Autonomous agents, multi-agent workflows, open-ended tool loops, or unbounded planning loops.
- OCR, screenshots, image/chart captioning, audio/video extraction, or PPTX parsing.
- A general-purpose knowledge graph, graph database, or relation extraction beyond the bounded document-level relation contract in this plan.
- A new vector database, model provider, frontend framework, or background-job platform.

---

## Phase 3 Design Decisions

Use these contracts consistently across all batches:

```text
Retrieval strategy:
  semantic | keyword | hybrid | metadata | relation

Candidate identity:
  chunk_id is the deduplication key across every retrieval path and subquery.

Score fusion:
  reciprocal-rank fusion (RRF), constant 60, with stable chunk_id tie-breaking.

Filter precedence:
  explicit ChatRequest filters override planner-inferred filters;
  selected document_ids are always an allow-list and may never be widened by planning.

Query decomposition:
  at most QUERY_MAX_SUBQUERIES subqueries; planner failure becomes one hybrid query.

Relation expansion:
  one document hop only, bounded by RELATION_MAX_RELATED_DOCUMENTS;
  never bypass explicit document_ids.

Context budget:
  top reranked chunks first, then same-section neighbors, then generic neighbors;
  stop before RETRIEVAL_CONTEXT_MAX_TOKENS or RETRIEVAL_CONTEXT_MAX_CANDIDATES.

Answer verification:
  one deterministic regeneration attempt; then return the safe insufficient-context response.

Retries:
  only timeouts, HTTP 429, and HTTP 5xx are retryable; validation and 4xx contract errors are not.
```

No raw document content, prompt body, API key, or full generated answer may be stored in workflow trace events. Existing optional `messages` persistence remains the only answer-history store.

---

## Target File Structure

Create or modify these files during Phase 3 implementation:

```text
backend/
  .gitignore
  pyproject.toml
  app/
    main.py
    core/
      config.py
      contracts.py
      retry.py
    models/
      schemas.py
    api/routes/
      chat.py
      documents.py
      observability.py
    graphs/
      ingestion_state.py
      ingestion_nodes.py
      ingestion_graph.py
      ingestion_payloads.py
      query_state.py
      query_nodes.py
      query_graph.py
      query_prompts.py
      query_formatting.py
    services/
      retrieval.py
      retrieval_context.py
      keyword_search.py
      score_fusion.py
      query_planning.py
      summaries.py
      relations.py
      citation_validation.py
      grounding.py
      observability.py
    evaluation/
      __init__.py
      dataset.py
      metrics.py
      runner.py
    scripts/
      seed_evaluation_corpus.py
      run_rag_evaluation.py
  evaluation/
    datasets/
      phase3_v1.jsonl
    fixtures/
      leave_policy.md
      pricing_policy.md
      security_policy.md
  tests/
    test_config.py
    test_contracts.py
    test_api_chat.py
    test_api_documents.py
    test_api_observability.py
    test_ingestion_graph.py
    test_ingestion_payloads.py
    test_query_graph.py
    test_retrieval_context.py
    test_keyword_search.py
    test_score_fusion.py
    test_query_planning.py
    test_summaries.py
    test_relations.py
    test_citation_validation.py
    test_grounding.py
    test_observability.py
    test_retry.py
    test_evaluation_metrics.py
frontend/
  src/
    App.tsx
    api/
      client.ts
      types.ts
    components/
      ChatPanel.tsx
      SourceList.tsx
      RetrievalFiltersPanel.tsx
    styles.css
docs/
  database/
    supabase_schema.sql
    phase3_migration.sql
  plans/
    Plan_3.md
README.md
backend/README.md
```

---

## Batch 1: Phase 3 Contracts, Settings, and Persistence

### Task 1.1: Add typed retrieval, planning, and verification contracts

**Files:**

- Modify: `backend/app/core/contracts.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/graphs/query_state.py`
- Modify: `backend/app/graphs/ingestion_state.py`
- Modify: `backend/tests/test_config.py`
- Modify: `backend/tests/test_contracts.py`
- Modify: `backend/tests/test_query_graph.py`
- Modify: `backend/tests/test_ingestion_graph.py`

- [ ] Add string enums for `RetrievalStrategy`, `RetrievalPath`, `SummaryType`, `RelationType`, and `WorkflowStatus`.

Required values:

```text
RetrievalStrategy: semantic, keyword, hybrid, metadata, relation
RetrievalPath: semantic, keyword, relation
SummaryType: section, document
RelationType: same_topic, supports, contradicts, references
WorkflowStatus: running, completed, failed
```

- [ ] Add `RetrievalFilters` with optional `mime_types`, `heading`, `section_path`, `page_start`, and `page_end`; reject negative pages and reject `page_start > page_end`.

- [ ] Extend `ChatRequest` with optional `filters: RetrievalFilters`; keep existing clients valid when it is omitted.

- [ ] Add typed internal `QueryPlan`, `QuerySubquery`, `RetrievalCandidate`, `GroundingResult`, `CitationValidationResult`, and `WorkflowTraceEvent` models. `RetrievalCandidate` must retain semantic rank/score, keyword rank/score, fusion score, retrieval paths, subquery IDs, and existing chunk metadata.

- [ ] Extend `ChatResponse` with optional `trace_id`; extend `SourceCitation` with optional `fusion_score`, `retrieval_paths`, and `citation_key`.

- [ ] Extend `QueryState` with filters, query plan, subqueries, route, per-path candidates, fused candidates, grounding state, verification attempt count, trace ID, and compact retrieval metrics.

- [ ] Extend `IngestionState` with summary records, relation-update result, trace ID, and retry-attempt metadata. Do not add file bytes, full prompts, or copied document text beyond the existing parsed/chunk state.

- [ ] Add settings with bounded defaults:

```text
ENABLE_KEYWORD_SEARCH=true
RETRIEVAL_KEYWORD_TOP_K=40
RETRIEVAL_FUSION_TOP_K=40
RETRIEVAL_RRF_CONSTANT=60
RETRIEVAL_RERANK_CANDIDATE_TOP_K=20
RETRIEVAL_CONTEXT_MAX_TOKENS=4000
QUERY_MAX_SUBQUERIES=4
QUERY_PLANNER_TEMPERATURE=0.0
QUERY_PLANNER_MAX_TOKENS=500
ENABLE_SUMMARIES=true
SUMMARY_SECTION_MAX_TOKENS=200
SUMMARY_DOCUMENT_MAX_TOKENS=400
ENABLE_RELATION_RETRIEVAL=true
RELATION_MAX_RELATED_DOCUMENTS=5
GROUNDING_MIN_SCORE=0.80
GROUNDING_MAX_REGENERATIONS=1
WORKFLOW_MAX_ATTEMPTS=3
WORKFLOW_RETRY_BASE_DELAY_SECONDS=0.25
WORKFLOW_RETRY_MAX_DELAY_SECONDS=2.0
ENABLE_WORKFLOW_TRACING=true
```

Verification:

```powershell
cd backend
python -m pytest tests/test_config.py tests/test_contracts.py tests/test_query_graph.py tests/test_ingestion_graph.py -v
```

Expected:

```text
All new enums and models reject unknown values.
Old ChatRequest payloads still validate.
Invalid page ranges fail validation.
Settings load defaults and environment overrides.
State schemas include Phase 3 fields without binary content.
```

### Task 1.2: Add idempotent Phase 3 database migration and data services

**Files:**

- Create: `docs/database/phase3_migration.sql`
- Modify: `docs/database/supabase_schema.sql`
- Modify: `backend/app/core/contracts.py`
- Create: `backend/app/services/summaries.py`
- Create: `backend/app/services/relations.py`
- Create: `backend/app/services/observability.py`
- Create: `backend/tests/test_summaries.py`
- Create: `backend/tests/test_relations.py`
- Create: `backend/tests/test_observability.py`

- [ ] Add `documents.error_code text` for stable ingestion failure codes.

- [ ] Add `document_summaries`:

```text
id uuid primary key
document_id uuid references documents(id) on delete cascade
summary_type text constrained to section|document
heading text nullable
section_path jsonb default []
content text not null
source_chunk_ids jsonb default []
model text not null
created_at timestamptz
updated_at timestamptz
```

Use one unique document summary per document and one unique section summary per `(document_id, section_path)`. Add document and summary-type indexes.

- [ ] Add `document_relations`:

```text
id uuid primary key
source_document_id uuid references documents(id) on delete cascade
target_document_id uuid references documents(id) on delete cascade
relation_type text constrained to same_topic|supports|contradicts|references
description text not null
evidence_chunk_ids jsonb default []
confidence double precision constrained to 0..1
model text not null
created_at timestamptz
updated_at timestamptz
```

Store pairs canonically with `source_document_id < target_document_id`; prohibit self-relations; enforce uniqueness per canonical pair and relation type; index both document ID columns.

- [ ] Add `workflow_runs`:

```text
id uuid primary key
workflow_type text constrained to ingestion|query
entity_id text nullable
status text constrained to running|completed|failed
trace jsonb default []
error_code text nullable
error_message text nullable
started_at timestamptz
finished_at timestamptz nullable
duration_ms integer nullable
created_at timestamptz
```

Index `created_at desc`, `workflow_type`, and `status`.

- [ ] Make `phase3_migration.sql` safe to run once against an existing Phase 2 database. Update `supabase_schema.sql` so a fresh database contains the same final schema.

- [ ] Implement normalized create/list/replace/delete functions for summaries, relations, and workflow runs using the existing lazy Supabase client pattern. Trace-write failures must log a warning and never fail ingestion or chat.

Verification:

```powershell
cd backend
python -m pytest tests/test_summaries.py tests/test_relations.py tests/test_observability.py -v
```

Expected:

```text
Service tests cover empty responses, normalized UUIDs, deterministic ordering, replacement on reindex, canonical relation pairs, and nonfatal trace persistence failures.
Fresh-install schema and migration define equivalent Phase 3 objects.
```

---

## Batch 2: Metadata-Aware Keyword and Hybrid Retrieval

### Task 2.1: Add metadata filters to API, Qdrant payloads, and the frontend

**Files:**

- Modify: `backend/app/graphs/ingestion_payloads.py`
- Modify: `backend/app/services/retrieval.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Modify: `backend/app/api/routes/chat.py`
- Modify: `backend/tests/test_ingestion_payloads.py`
- Modify: `backend/tests/test_query_graph.py`
- Modify: `backend/tests/test_api_chat.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/components/RetrievalFiltersPanel.tsx`
- Modify: `frontend/src/components/ChatPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] Add `mime_type` to every new Qdrant chunk payload. Existing documents receive it after reindexing.

- [ ] Replace `build_document_id_filter` with `build_qdrant_filter(document_ids, filters)` and combine these conditions with logical AND:

```text
document_id allow-list
mime_type allow-list
heading text match
section_path contains every requested path segment
chunk page range overlaps the requested page range
```

Chunks with unknown page numbers may match only when no page filter was requested.

- [ ] Pass explicit filters unchanged from `ChatRequest` through the route, query state, and retrieval calls. Empty filter fields normalize to `None`/empty lists.

- [ ] Add a collapsible frontend filter panel for MIME/file type, heading text, section path segments, start page, and end page. Keep document selection as the document allow-list. Disable send and show an inline validation message when the page range is invalid.

Verification:

```powershell
cd backend
python -m pytest tests/test_ingestion_payloads.py tests/test_query_graph.py tests/test_api_chat.py -v
cd ..\frontend
npm run build
```

Expected:

```text
Qdrant payloads contain mime_type.
Every filter compiles into the expected Qdrant condition.
Explicit document_ids remain a strict allow-list.
Old requests without filters behave as before.
Frontend sends only populated filter fields and builds successfully.
```

### Task 2.2: Add Postgres full-text keyword retrieval

**Files:**

- Modify: `docs/database/phase3_migration.sql`
- Modify: `docs/database/supabase_schema.sql`
- Create: `backend/app/services/keyword_search.py`
- Create: `backend/tests/test_keyword_search.py`

- [ ] Add a GIN index using the language-neutral `simple` configuration over `coalesce(heading, '') || ' ' || content`.

- [ ] Add a `search_document_chunks_keyword` Postgres function with parameters for query text, result limit, document IDs, MIME types, heading, section path, page start, and page end.

Required behavior:

```text
Use websearch_to_tsquery('simple', query_text).
Join documents so MIME filtering uses documents.mime_type.
Apply the same allow-list and page-overlap semantics as Qdrant.
Return the existing chunk metadata plus keyword_score from ts_rank_cd.
Order by keyword_score desc, document_id asc, chunk_index asc.
Return at most RETRIEVAL_KEYWORD_TOP_K rows.
```

- [ ] Implement `search_keyword_chunks` through `supabase.rpc(...)`; normalize rows into the same candidate shape used by semantic retrieval and set `retrieval_paths = ["keyword"]`.

- [ ] Treat an empty query as a validation error. Treat an unavailable RPC as a retrieval-path failure that the hybrid orchestrator can recover from.

Verification:

```powershell
cd backend
python -m pytest tests/test_keyword_search.py -v
```

Expected:

```text
RPC parameters preserve all explicit filters.
Rows normalize with keyword_score and keyword_rank.
Ordering is deterministic when scores tie.
RPC failure raises a typed KeywordSearchError without exposing credentials.
```

### Task 2.3: Add deterministic reciprocal-rank fusion

**Files:**

- Create: `backend/app/services/score_fusion.py`
- Modify: `backend/app/services/retrieval.py`
- Create: `backend/tests/test_score_fusion.py`
- Modify: `backend/tests/test_query_graph.py`

- [ ] Implement reciprocal-rank fusion by `chunk_id`:

```text
contribution = 1 / (RETRIEVAL_RRF_CONSTANT + one_based_rank)
fusion_score = sum of semantic and keyword contributions across paths/subqueries
```

- [ ] Preserve the best non-null semantic/Qdrant and keyword scores, accumulate retrieval paths and subquery IDs without duplicates, and order by `fusion_score desc`, best rank asc, then `chunk_id asc`.

- [ ] Add a hybrid retrieval function that runs enabled semantic and keyword paths independently, fuses successful results, and caps output at `RETRIEVAL_FUSION_TOP_K`.

Fallback contract:

```text
semantic fails + keyword succeeds -> keyword candidates
keyword fails + semantic succeeds -> semantic candidates
both return no rows -> empty result
both fail -> typed RetrievalError
ENABLE_KEYWORD_SEARCH=false -> semantic-only behavior
```

Verification:

```powershell
cd backend
python -m pytest tests/test_score_fusion.py tests/test_keyword_search.py tests/test_query_graph.py -v
```

Expected:

```text
Duplicate chunks merge by chunk_id.
Chunks found by both paths rank above equivalent single-path chunks.
Fusion order is stable across repeated runs.
Single-path fallbacks retain their original metadata.
```

---

## Batch 3: Document Summaries and Lightweight Relations

### Task 3.1: Generate section and document summaries during ingestion

**Files:**

- Modify: `backend/app/services/summaries.py`
- Modify: `backend/app/graphs/ingestion_state.py`
- Modify: `backend/app/graphs/ingestion_nodes.py`
- Modify: `backend/app/graphs/ingestion_graph.py`
- Modify: `backend/app/api/routes/documents.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/tests/test_summaries.py`
- Modify: `backend/tests/test_ingestion_graph.py`
- Modify: `backend/tests/test_api_documents.py`

- [ ] Group saved chunks by normalized `section_path`; use the heading as a fallback group key when a section path is empty.

- [ ] Generate one section summary per group only from that group's chunk content. Generate the document summary only from the section summaries. Use temperature `0`, configured output limits, and prompts that prohibit facts not present in the supplied text.

- [ ] Store the exact source chunk IDs, model name, heading, and section path with each summary. Replace all summaries for the document only after every summary has been generated successfully so failed reindexing does not leave a partial set.

- [ ] Add `summarize_document` after `save_chunks` and before `embed_chunks`. When `ENABLE_SUMMARIES=false`, return an empty summary set without calling the model.

- [ ] Add typed `GET /api/documents/{document_id}/summaries`, ordered with the document summary first and section summaries by section path.

Verification:

```powershell
cd backend
python -m pytest tests/test_summaries.py tests/test_ingestion_graph.py tests/test_api_documents.py -v
```

Expected:

```text
Summary prompts contain extracted chunk text only.
Section summaries retain exact source chunk IDs.
Document summary input contains section summaries, not the original binary or arbitrary external text.
Disabled summaries preserve Phase 2 ingestion order.
Reindex replaces summaries atomically at the service boundary.
```

### Task 3.2: Build and query a bounded document relation graph

**Files:**

- Modify: `backend/app/services/relations.py`
- Modify: `backend/app/graphs/ingestion_nodes.py`
- Modify: `backend/app/graphs/ingestion_graph.py`
- Modify: `backend/app/api/routes/documents.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/tests/test_relations.py`
- Modify: `backend/tests/test_ingestion_graph.py`
- Modify: `backend/tests/test_api_documents.py`

- [ ] Retrieve relation candidates by embedding the current document summary, querying Qdrant, excluding the current document, grouping results by document, and retaining at most `RELATION_MAX_RELATED_DOCUMENTS` ready documents.

- [ ] Ask the chat model for strict JSON containing zero or more relations with `target_document_id`, allowed relation type, description, evidence chunk IDs, and confidence. Reject unknown documents, unknown relation types, confidence outside `0..1`, and evidence IDs not present in the candidate set.

- [ ] Canonicalize document pairs and replace only relations involving the reindexed document. Keep at most one row per pair and relation type.

- [ ] Add `update_document_relations` after `upsert_qdrant` and before `mark_ready`. With relation retrieval disabled or no document summary, skip it. A relation-update failure after configured retries records a trace warning but does not invalidate otherwise complete chunk indexing.

- [ ] Add typed `GET /api/documents/{document_id}/relations` for inspection; return both directions with `related_document_id` normalized for the requested document.

Verification:

```powershell
cd backend
python -m pytest tests/test_relations.py tests/test_ingestion_graph.py tests/test_api_documents.py -v
```

Expected:

```text
Candidate documents are bounded and exclude the source document.
Invalid model relation JSON is discarded safely.
Evidence IDs always refer to candidate chunks.
Relation pairs are canonical and duplicate-free.
Relation failure does not delete valid chunks or vectors.
```

---

## Batch 4: Query Decomposition and LangGraph Retrieval Routing

### Task 4.1: Add bounded query planning and deterministic fallback

**Files:**

- Create: `backend/app/services/query_planning.py`
- Modify: `backend/app/graphs/query_prompts.py`
- Create: `backend/tests/test_query_planning.py`

- [ ] Implement `plan_query(question, document_ids, explicit_filters)` using `SHOPAIKEY_INPUT_MODEL` and strict JSON.

Required plan shape:

```json
{
  "is_complex": true,
  "strategy": "hybrid",
  "subqueries": [
    {"id": "q1", "text": "first focused question"},
    {"id": "q2", "text": "second focused question"}
  ],
  "inferred_filters": {
    "mime_types": [],
    "heading": null,
    "section_path": [],
    "page_start": null,
    "page_end": null
  },
  "needs_relations": false
}
```

- [ ] Normalize duplicate/blank subqueries, cap them at `QUERY_MAX_SUBQUERIES`, and replace an empty plan with one subquery containing the original question.

- [ ] Explicit request filters override inferred fields. Explicit `document_ids` remain unchanged and may not be widened or removed by the planner.

- [ ] Planner timeout, invalid JSON, unknown strategy, or invalid filters returns a deterministic plan with one original-question subquery and `hybrid` when keyword search is enabled, otherwise `semantic`.

Verification:

```powershell
cd backend
python -m pytest tests/test_query_planning.py -v
```

Expected:

```text
Simple and complex plans normalize to the same typed contract.
Subquery count is bounded.
Explicit filters and document IDs cannot be overridden.
Every planner failure produces the documented fallback plan.
```

### Task 4.2: Route and merge semantic, keyword, metadata, and relation paths

**Files:**

- Modify: `backend/app/graphs/query_state.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Modify: `backend/app/graphs/query_graph.py`
- Modify: `backend/app/services/retrieval.py`
- Modify: `backend/app/services/relations.py`
- Modify: `backend/tests/test_query_graph.py`
- Modify: `backend/tests/test_relations.py`

- [ ] Replace the Phase 2 query start with:

```text
START
-> prepare_query
-> plan_query
-> resolve_relation_scope
-> retrieve_candidates
-> fuse_candidates
-> rerank_candidates
-> expand_context
-> generate_answer
-> validate_citations
-> verify_grounding
-> finalize_answer
-> save_message_optional
-> END
```

- [ ] Route each subquery by its plan:

```text
semantic -> Qdrant only
keyword -> Postgres full-text only
hybrid -> both paths then RRF
metadata -> hybrid with at least one active metadata filter
relation -> one-hop related-document expansion followed by hybrid retrieval
```

- [ ] For relation retrieval, load only one hop and at most `RELATION_MAX_RELATED_DOCUMENTS`. If explicit `document_ids` were supplied, relation lookup may reorder or connect those documents but may not add document IDs outside the allow-list.

- [ ] Fuse candidates across paths and subqueries by `chunk_id`, preserve subquery IDs, and cap before reranking. Cross-document comparison questions must retain at least one candidate per contributing subquery when available before filling remaining slots by fusion score.

- [ ] Preserve the Phase 2 insufficient-context response when all successful paths return no candidates.

Verification:

```powershell
cd backend
python -m pytest tests/test_query_planning.py tests/test_relations.py tests/test_score_fusion.py tests/test_query_graph.py -v
```

Expected:

```text
Graph node order matches the Phase 3 flow.
Every strategy calls only its allowed retrieval paths.
Multiple subqueries merge without duplicate chunks.
Relation expansion is bounded and respects explicit document selection.
Planner, relation, or one-path failures use deterministic fallbacks.
```

---

## Batch 5: Candidate Stages, Reranking, and Context Budgets

### Task 5.1: Add configurable candidate stages and stable reranking fallback

**Files:**

- Modify: `backend/app/services/retrieval.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Modify: `backend/app/graphs/query_formatting.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/tests/test_query_graph.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/components/SourceList.tsx`

- [ ] Enforce candidate stages in this order:

```text
per-path top-k
-> fused top-k
-> rerank candidate top-k
-> final reranked top-k
-> context expansion budget
```

- [ ] Send only `RETRIEVAL_RERANK_CANDIDATE_TOP_K` candidates to Jina and request `RETRIEVAL_FINAL_TOP_K` results.

- [ ] When reranking is disabled, times out, returns invalid indexes, or fails after retries, order by `fusion_score`, then Qdrant score, then keyword score, then chunk ID. Never silently reorder by provider response position alone.

- [ ] Carry `fusion_score`, retrieval paths, and citation key into source citations and frontend source details without removing Phase 2 fields.

Verification:

```powershell
cd backend
python -m pytest tests/test_query_graph.py tests/test_score_fusion.py -v
cd ..\frontend
npm run build
```

Expected:

```text
Every configured cap is independently enforced.
Jina receives the configured candidate count.
Fallback order is deterministic.
Frontend displays optional retrieval metadata and remains compatible with saved Phase 2 messages.
```

### Task 5.2: Enforce section boundaries and a token context budget

**Files:**

- Modify: `backend/app/services/retrieval_context.py`
- Modify: `backend/app/graphs/query_formatting.py`
- Modify: `backend/tests/test_retrieval_context.py`
- Modify: `backend/tests/test_query_graph.py`

- [ ] Calculate context cost from stored `token_count`; when it is absent, count with the same tokenizer used by chunking.

- [ ] Preserve this selection order:

```text
1. Top final reranked chunks, in rank order.
2. Requested beginning/end boundary chunks.
3. Previous/next chunks sharing document_id and exact section_path.
4. Remaining previous/next chunks in the same document.
```

- [ ] Before adding a chunk, enforce both `RETRIEVAL_CONTEXT_MAX_TOKENS` and `RETRIEVAL_CONTEXT_MAX_CANDIDATES`. Always retain the highest-ranked chunk if it alone exceeds the token budget; mark it `context_truncated=true` and truncate only the prompt copy, never stored chunk content or citation metadata.

- [ ] For multi-subquery plans, reserve one top chunk per subquery when available before adding neighbors. Deduplicate by chunk ID and keep the first selected position stable.

- [ ] Record selected token count, candidate count, neighbor count, and per-subquery coverage in compact retrieval metrics.

Verification:

```powershell
cd backend
python -m pytest tests/test_retrieval_context.py tests/test_query_graph.py -v
```

Expected:

```text
Context never exceeds configured caps except the documented single-top-chunk case.
Same-section neighbors remain preferred.
Multi-subquery coverage is preserved when candidates exist.
Prompt truncation does not alter source identity or stored content.
```

---

## Batch 6: Exact Citations and Grounding Verification

### Task 6.1: Generate and validate chunk-keyed citations

**Files:**

- Create: `backend/app/services/citation_validation.py`
- Modify: `backend/app/graphs/query_prompts.py`
- Modify: `backend/app/graphs/query_formatting.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Create: `backend/tests/test_citation_validation.py`
- Modify: `backend/tests/test_query_graph.py`

- [ ] Assign stable prompt-local citation keys `S1`, `S2`, ... after final context ordering. Include each key beside the exact chunk ID in the answer context.

- [ ] Require factual answer claims to cite one or more keys using `[S1]` syntax. The insufficient-context response requires no citation.

- [ ] Implement citation validation that:

```text
extracts every [S<number>] marker
rejects markers absent from the exact generation context
maps valid markers to exact chunk IDs
returns sources only for cited chunks, in first-citation order
flags a non-empty factual answer with no valid citation
does not accept document IDs, headings, or model-invented source labels as substitutes
```

- [ ] Store the citation validation result in query state and message metadata. Do not persist the full validation prompt.

Verification:

```powershell
cd backend
python -m pytest tests/test_citation_validation.py tests/test_query_graph.py -v
```

Expected:

```text
Valid citation keys map to exact context chunk IDs.
Unknown and malformed keys fail validation.
Uncited context chunks are excluded from returned sources.
Saved source citations match the returned validated sources.
```

### Task 6.2: Verify grounding and perform one bounded regeneration

**Files:**

- Create: `backend/app/services/grounding.py`
- Modify: `backend/app/graphs/query_prompts.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Modify: `backend/app/graphs/query_graph.py`
- Create: `backend/tests/test_grounding.py`
- Modify: `backend/tests/test_query_graph.py`
- Modify: `backend/tests/test_api_chat.py`

- [ ] Verify only the generated answer against the exact cited chunk texts. Request strict JSON:

```json
{
  "grounded": true,
  "score": 0.95,
  "unsupported_claims": [],
  "missing_citations": []
}
```

- [ ] Treat the answer as valid only when citation validation passes, `grounded=true`, and score is at least `GROUNDING_MIN_SCORE`.

- [ ] On the first failure, call a dedicated regeneration node once with the original context plus compact verifier feedback. Re-run citation validation and grounding verification.

- [ ] After `GROUNDING_MAX_REGENERATIONS`, return:

```text
The indexed documents do not contain enough verified information to answer this question.
```

Return no sources for that safe response. Never return the unverified draft.

- [ ] Grounding-provider failure after retries is a verification failure, not permission to return an unchecked answer.

Verification:

```powershell
cd backend
python -m pytest tests/test_grounding.py tests/test_citation_validation.py tests/test_query_graph.py tests/test_api_chat.py -v
```

Expected:

```text
Valid grounded answers pass without regeneration.
Invalid citations and unsupported claims trigger exactly one regeneration by default.
Repeated failure returns the safe response and empty sources.
No unverified draft reaches ChatResponse or messages.
```

---

## Batch 7: RAG Evaluation Dataset and Metrics

### Task 7.1: Add a versioned text-only evaluation corpus and dataset contract

**Files:**

- Create: `backend/app/evaluation/__init__.py`
- Create: `backend/app/evaluation/dataset.py`
- Create: `backend/evaluation/fixtures/leave_policy.md`
- Create: `backend/evaluation/fixtures/pricing_policy.md`
- Create: `backend/evaluation/fixtures/security_policy.md`
- Create: `backend/evaluation/datasets/phase3_v1.jsonl`
- Create: `backend/scripts/seed_evaluation_corpus.py`
- Create: `backend/tests/test_evaluation_metrics.py`

- [ ] Define dataset rows with:

```text
case_id
question
document_titles
expected_chunk_contains
required_answer_terms
forbidden_answer_terms
expected_no_result
filters
tags
```

- [ ] Add at least twelve deterministic cases covering semantic paraphrase, exact keyword lookup, MIME/heading/section/page filters, a decomposed two-part question, cross-document comparison, relation-aware retrieval, citation selection, insufficient context, and conflicting evidence.

- [ ] Keep fixtures small, text-only, and free of external copyrighted content. Each expected evidence phrase must appear verbatim in exactly one intended fixture section unless the case explicitly tests cross-document evidence.

- [ ] Implement a seed script that uploads/indexes the three fixtures through existing application services, reuses duplicate hashes safely, waits for ready status, and prints title-to-document-ID mappings. It must require configured external services and must not embed credentials in output.

- [ ] Validate JSONL rows, unique case IDs, known fixture titles, non-empty expected evidence for positive cases, and empty expected evidence for `expected_no_result=true`.

Verification:

```powershell
cd backend
python -m pytest tests/test_evaluation_metrics.py -v
python -m app.evaluation.dataset evaluation/datasets/phase3_v1.jsonl
```

Expected:

```text
Dataset validation passes.
All twelve or more cases have unique IDs and valid expectations.
Fixture evidence is deterministic and text-only.
```

### Task 7.2: Implement retrieval, grounding, citation, and answer metrics

**Files:**

- Create: `backend/app/evaluation/metrics.py`
- Create: `backend/app/evaluation/runner.py`
- Create: `backend/scripts/run_rag_evaluation.py`
- Modify: `backend/.gitignore`
- Modify: `backend/tests/test_evaluation_metrics.py`

- [ ] Implement exact metric definitions:

```text
recall_at_k = relevant chunks in first k / total expected relevant chunks
precision_at_k = relevant chunks in first k / k, using actual result count when fewer than k
rerank_lift = recall_at_final_k after rerank - recall_at_final_k before rerank
no_result_rate = cases with zero retrieved chunks / all cases
unexpected_no_result_rate = positive cases with zero retrieved chunks / positive cases
citation_validity_rate = answers whose cited chunk IDs are all in generation context / answered cases
grounding_pass_rate = answers passing the runtime grounding gate / answered cases
answer_term_coverage = required terms present / total required terms
forbidden_term_rate = forbidden terms present / total forbidden terms
```

- [ ] Capture pre-rerank, post-rerank, context, answer, source, grounding, route, and latency fields from the query workflow without bypassing production retrieval logic.

- [ ] Write timestamped JSON reports under `backend/evaluation/results/`; ignore generated reports in git.

- [ ] Add CLI thresholds and nonzero exit behavior. Default gates:

```text
recall_at_5 >= 0.80
citation_validity_rate = 1.00
grounding_pass_rate >= 0.90
unexpected_no_result_rate <= 0.10
forbidden_term_rate = 0.00
```

- [ ] Unit-test every metric with hand-calculated fixtures, including empty datasets, fewer-than-k results, expected no-result cases, and before/after rerank differences.

Verification:

```powershell
cd backend
python -m pytest tests/test_evaluation_metrics.py -v
python scripts/run_rag_evaluation.py --help
```

Expected:

```text
Metric unit tests match hand calculations.
CLI documents dataset, output, k, and threshold options.
Threshold failure returns a nonzero exit code.
```

External-service acceptance command after seeding:

```powershell
cd backend
python scripts/run_rag_evaluation.py --dataset evaluation/datasets/phase3_v1.jsonl
```

Expected:

```text
A JSON report is created and all default gates pass.
```

---

## Batch 8: Workflow Observability and Failure Recovery

### Task 8.1: Persist compact ingestion and query traces

**Files:**

- Modify: `backend/app/services/observability.py`
- Modify: `backend/app/graphs/ingestion_graph.py`
- Modify: `backend/app/graphs/query_graph.py`
- Modify: `backend/app/api/routes/chat.py`
- Modify: `backend/app/api/routes/documents.py`
- Create: `backend/app/api/routes/observability.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_observability.py`
- Modify: `backend/tests/test_observability.py`
- Modify: `backend/tests/test_ingestion_graph.py`
- Modify: `backend/tests/test_query_graph.py`

- [ ] Create a workflow run at API invocation and instrument every graph node with:

```text
node_name
status
attempt
started_at
finished_at
duration_ms
provider when applicable
input/output counts only
route/fallback name when applicable
safe error code when applicable
```

- [ ] Add retrieval trace totals for subquery count, semantic/keyword/fused/reranked/context counts, selected strategy, fallback path, context tokens, grounding score, citation validity, and total query latency.

- [ ] Redact raw chunk text, parsed text, prompts, model responses, authorization headers, URLs containing credentials, and API keys before persistence.

- [ ] Mark runs completed or failed on every graph exit. Observability writes are best-effort: log a warning and continue when Supabase trace persistence is unavailable.

- [ ] Add admin-token-protected endpoints:

```text
GET /api/observability/runs?workflow_type=&status=&limit=50
GET /api/observability/runs/{run_id}
```

Clamp list limits to `1..100`; return newest first; return 404 for unknown IDs.

Verification:

```powershell
cd backend
python -m pytest tests/test_observability.py tests/test_api_observability.py tests/test_ingestion_graph.py tests/test_query_graph.py -v
```

Expected:

```text
Successful and failed workflows close their runs.
Node durations and attempts are recorded.
Retrieval traces contain counts and routes but no source text or secrets.
Trace persistence failure does not alter API success or failure behavior.
```

### Task 8.2: Add retry classification and deterministic recovery

**Files:**

- Create: `backend/app/core/retry.py`
- Modify: `backend/app/graphs/ingestion_nodes.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Modify: `backend/app/services/retrieval.py`
- Modify: `backend/app/services/keyword_search.py`
- Modify: `backend/app/services/summaries.py`
- Modify: `backend/app/services/relations.py`
- Modify: `backend/app/services/grounding.py`
- Create: `backend/tests/test_retry.py`
- Modify: `backend/tests/test_ingestion_graph.py`
- Modify: `backend/tests/test_query_graph.py`

- [ ] Implement a reusable synchronous retry helper with injectable sleep and monotonic clock. Delay is exponential from the configured base and capped by the configured maximum.

- [ ] Retry only provider timeouts, connection errors, HTTP 429, and HTTP 5xx. Do not retry schema validation, unsupported file types, `NO_EXTRACTABLE_TEXT`, missing documents, HTTP 400/401/403/404, or invalid model JSON after it has been normalized to a contract error.

- [ ] Apply retry behavior to storage download, embedding, Qdrant search/upsert/delete, Postgres keyword RPC, Jina rerank, summary generation, relation generation, answer generation, and grounding verification.

- [ ] Enforce final recovery behavior:

```text
planner failure -> one original-question hybrid/semantic plan
semantic path failure -> keyword-only when available
keyword path failure -> semantic-only when available
relation failure -> normal hybrid retrieval in the original scope
Jina failure -> deterministic fused-score order
grounding failure -> one regeneration, then safe insufficient-context response
message or trace persistence failure -> log warning, return valid answer
retryable ingestion failure after max attempts -> mark document failed with stable error_code
relation-update failure after max attempts -> trace warning, keep otherwise valid index ready
```

- [ ] Record each attempt and final fallback in workflow traces. Tests must inject a no-op sleep and never wait in real time.

Verification:

```powershell
cd backend
python -m pytest tests/test_retry.py tests/test_ingestion_graph.py tests/test_query_graph.py tests/test_observability.py -v
```

Expected:

```text
Retryable failures recover within the configured attempt count.
Non-retryable failures execute once.
Backoff is capped and testable without sleeping.
Final fallbacks exactly match the Phase 3 recovery contract.
```

---

## Batch 9: Documentation and End-to-End Validation

### Task 9.1: Update setup, migration, architecture, and operations documentation

**Files:**

- Modify: `README.md`
- Modify: `backend/README.md`

- [ ] Update the architecture diagrams with query planning, parallel semantic/keyword retrieval, RRF, relation expansion, reranking, context budgeting, citation validation, grounding verification, and trace persistence.

- [ ] Document every new Phase 3 setting and its default.

- [ ] Document how to apply `docs/database/phase3_migration.sql` to an existing Phase 2 Supabase project and how to use the final schema for a fresh project.

- [ ] Document that existing documents must be reindexed to populate MIME payloads, summaries, relations, and Phase 3 metadata.

- [ ] Document summary/relation and observability endpoints, evaluation seeding/running commands, threshold meanings, retry behavior, and safe trace redaction.

- [ ] Preserve the extractable-text-only limitation and all single-user security warnings.

### Task 9.2: Run full automated verification

**Files:**

- No new files.

- [ ] Run all backend tests:

```powershell
cd backend
python -m pytest -v
```

Expected:

```text
All backend tests pass with no network access required by unit tests.
```

- [ ] Run the frontend production build:

```powershell
cd frontend
npm run build
```

Expected:

```text
TypeScript checks and Vite production build pass.
```

- [ ] Validate the evaluation dataset:

```powershell
cd backend
python -m app.evaluation.dataset evaluation/datasets/phase3_v1.jsonl
```

Expected:

```text
Dataset validation passes.
```

### Task 9.3: Run manual Phase 3 smoke and evaluation tests

**Files:**

- No new files.

- [ ] Apply the Phase 3 migration to the configured Supabase project and reindex existing test documents.

- [ ] Start backend and frontend:

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

- [ ] Verify these flows:

```text
Ask an exact-term question and confirm keyword retrieval contributes.
Ask a paraphrased question and confirm semantic retrieval contributes.
Apply MIME, heading, section, and page filters and confirm every returned source satisfies them.
Ask a two-part question and confirm bounded decomposition covers both parts.
Ask a cross-document comparison and confirm one-hop relation retrieval remains inside selected documents.
Confirm Jina failure falls back to stable fused ordering.
Confirm context respects candidate and token budgets.
Confirm returned sources are only chunks cited by the answer.
Force a grounding rejection and confirm one regeneration, then the safe response on repeated failure.
Inspect summary, relation, and observability endpoints.
Confirm traces contain timing/counts but no chunk content, prompts, keys, or credentials.
Force one retryable provider failure and confirm recovery and attempt tracing.
```

- [ ] Seed and run the evaluation suite:

```powershell
cd backend
python scripts/seed_evaluation_corpus.py
python scripts/run_rag_evaluation.py --dataset evaluation/datasets/phase3_v1.jsonl
```

Expected:

```text
All default evaluation gates pass and a timestamped JSON report is written.
```

---

## Phase 3 Acceptance Criteria

- [ ] All Phase 1 and Phase 2 backend tests still pass.
- [ ] Existing frontend requests without Phase 3 filters remain valid.
- [ ] Complex questions decompose into no more than `QUERY_MAX_SUBQUERIES` focused subqueries.
- [ ] Planner failure deterministically falls back to one original-question query.
- [ ] Retrieval routes support semantic, keyword, hybrid, metadata, and one-hop relation strategies.
- [ ] Explicit document selection is never widened by planning or relation expansion.
- [ ] Qdrant semantic search and Postgres full-text search use equivalent metadata filter semantics.
- [ ] Hybrid candidates use deterministic reciprocal-rank fusion and deduplicate by chunk ID.
- [ ] Candidate, rerank, final, context-count, and context-token caps are independently enforced.
- [ ] Jina failure falls back to deterministic fused ordering.
- [ ] Same-section neighbors are preferred and context expansion respects section and token budgets.
- [ ] Section and document summaries are derived only from extracted text and retain source chunk IDs.
- [ ] Relation rows are bounded, canonical, evidence-backed, and limited to allowed relation types.
- [ ] Cross-document reasoning is bounded to selected documents and one relation hop.
- [ ] Every returned factual answer passes exact citation validation and grounding verification.
- [ ] Returned sources contain only cited chunks from the exact generation context.
- [ ] Failed verification never returns an unchecked draft.
- [ ] Evaluation data covers retrieval, filters, decomposition, relations, grounding, citations, no-result behavior, and answer quality.
- [ ] Recall-at-k, precision-at-k, rerank lift, no-result rate, citation validity, grounding, and answer-term metrics use documented formulas.
- [ ] Ingestion and query traces record node timing, attempts, failures, routes, and retrieval counts.
- [ ] Traces never store source text, prompts, model responses, secrets, or credentials.
- [ ] Retryable failures use bounded retries; non-retryable failures execute once.
- [ ] Ingestion exhaustion marks a stable `error_code`; query fallbacks follow the documented recovery contract.
- [ ] `python -m pytest -v`, `npm run build`, dataset validation, manual smoke tests, and evaluation gates pass.
- [ ] No authentication, multi-user, OCR, image processing, autonomous-agent, or unbounded graph features are introduced.

---

## Execution Order

Implement batches in order:

```text
Batch 1 -> Batch 2 -> Batch 3 -> Batch 4 -> Batch 5 -> Batch 6 -> Batch 7 -> Batch 8 -> Batch 9
```

Create a focused commit after each batch:

```text
feat: add phase 3 contracts and persistence
feat: add metadata-aware hybrid retrieval
feat: add summaries and document relations
feat: add query planning and retrieval routing
feat: tune candidate reranking and context budgets
feat: validate citations and answer grounding
test: add rag evaluation dataset and metrics
feat: add workflow tracing and failure recovery
docs: document and verify phase 3 advanced rag
```
