# Document QA Agent

## Overview

Document QA Agent is a single-user document question-answering project. The planned system lets one configured user upload documents, parse and chunk their contents, index chunks with embeddings, retrieve relevant evidence, and eventually answer questions using a multi-agent workflow grounded only in verified document evidence.

This repository is a mixed workspace:

- `backend/` contains the FastAPI API, service layer, Supabase persistence/storage integration, ShopAIKey embedding integration, Qdrant vector indexing, schemas, migrations, and tests.
- `frontend/` contains a Vite React TypeScript application with an Axios API client, typed document API contracts, reusable upload/document display components, routed upload and document list pages, compact navigation, responsive/accessibility styling, and a shared file validation helper.
- `docs/` contains the implementation plan sequence, task reports, review reports, and a visual overview.

The current codebase is not the complete MVP described in `docs/plans/Master_Plan.md`. Implemented backend areas include health, document upload metadata/storage, document listing/detail, parsing, chunking, embedding generation, Qdrant upsert/search primitives, semantic retrieval service orchestration/result mapping, the retrieval search API, a development indexing endpoint, backend graph extraction configuration, validated graph schemas, Supabase graph helper contracts, ShopAIKey chat completion support, a backend entity extraction service with deterministic fallback, graph builder rebuild behavior for `Document -> Section -> Chunk -> Entity` persistence plus validated relationship expansion, graph building wired into the backend document processing service after chunks are persisted, Plan 8 hybrid retrieval configuration, schemas, deterministic scoring utilities, graph candidate lookup, hybrid candidate merge/scoring/final ranking service behavior, guarded rerank placeholder behavior, safe hybrid failure handling, optional hybrid mode routing on the existing retrieval search API, the Plan 9 Batch01 backend agent package with shared Agent 1 input/candidate/output Pydantic schemas, the Plan 9 Batch02 agent step logging service, the Plan 9 Batch03 Agent 1 retrieval callable with hybrid retrieval delegation, validated output conversion, success logging, and controlled failure logging, the Plan 10 Batch01 Agent 2 verification schemas, reusable verification prompt, confidence bounds, and backend-only ShopAIKey chat configuration checks, the Plan 10 Batch02 backend-only Agent 2 verification callable with deterministic empty-candidate handling, compact ShopAIKey verification requests, strict JSON parsing, and Pydantic output validation, the Plan 10 Batch03 Agent 2 deterministic evidence safety checks for candidate membership, quote fidelity, duplicate filtering, contradiction/missing-information adjustment, and final output shape validation, the Plan 10 Batch04 Agent 2 success/failure step logging with safe log-insertion failure visibility, the Plan 11 Batch01 Agent 3 answer contracts with answer output schemas, citation/evidence validation helpers, answer-generation and self-check prompt contracts, deterministic self-check readiness enforcement, and confirmed backend-only ShopAIKey chat configuration boundaries, the Plan 11 Batch02 Agent 3 internal answer callable with controlled errors, deterministic insufficient-evidence output, Agent 2 verification input normalization, verified/rejected evidence lookup, and verified-only ShopAIKey answer-generation payload construction for sufficient evidence, the Plan 11 Batch03 Agent 3 sufficient-evidence draft path with mocked ShopAIKey chat calls, strict JSON/Pydantic draft parsing, citation presence and file-name/quote format enforcement, verified quote membership checks, rejected-evidence rejection, and public output-shape normalization, the Plan 11 Batch04 Agent 3 runtime self-check execution, controlled self-check failure policy, success/failed `agent_steps` logging, and safe log-insertion failure visibility, the Plan 12 Batch01 LangGraph workflow dependency, internal QA workflow state/callable contract, chat ask schemas, and agent-run evidence/log response schemas, the Plan 12 Batch02 service-layer persistence for chat sessions, chat messages, agent run lifecycle, selected document ownership validation, evidence/log lookup, and controlled public error messages, the Plan 12 Batch03 internal LangGraph orchestration that runs Agent 1 -> Agent 2 -> Agent 3, creates and updates an `agent_runs` lifecycle row, returns Agent 3 answer fields, and preserves safe insufficient-evidence behavior, the Plan 12 Batch04 public chat, evidence, and logs APIs with production router registration and chat-message persistence around ask requests, the Plan 12 Batch05 failure-handling and single-user-safety hardening for chat validation, selected-document errors, owned session/run/message/step access, failed-run lifecycle behavior, evidence/log safe errors, and secret-boundary confirmation, and the Plan 12 Batch06 required automated tests for LangGraph workflow success/failure order, insufficient-evidence behavior, chat API behavior, evidence/log API behavior, and targeted validation runs. The routed upload and document list frontend screens are implemented; public graph APIs and frontend retrieval/chat/evidence/log screens remain incomplete or planned.

Plan 10 Batch05 also completed the required automated Agent 2 verification tests for accept/reject behavior, missing-information handling, invalid provider output, unknown chunk IDs, provider failures, quote safety, duplicate filtering, contradictions, confidence bounds, and targeted pytest validation. Plan 10 Batch06 completed manual validation reporting and scope review: a user-authorized live technical Agent 1 -> Agent 2 smoke run succeeded on existing indexed smoke-test data after Agent 2 compact evidence payloads were updated to include `document_id`, while the exact contract-specific start-date/probation/official-work-condition sample remains unavailable until matching indexed document content is provided. Plan 11 Batch05 completed required automated Agent 3 answer tests for grounded simple reasoning, insufficient-evidence refusal, citation enforcement, rejected chunk exclusion, unsupported self-check claims, provider/parsing/logging failures, and targeted pytest validation. Plan 11 Batch06 completed Agent 3 manual validation reporting and scope review: a live synthetic Agent 2-shaped evidence smoke check succeeded after Agent 3 answer-generation and self-check payloads were updated to include explicit JSON-mode instructions, while no real user-provided Agent 2 payload was available.

Plan 12 Batch07 completed live chat, evidence, and logs validation plus final reporting and scope review. The live checks found and repaired two response-boundary mismatches: `/api/chat/ask` now serializes Agent 3 citation models into the public chat citation shape, and agent-run evidence now reads Agent 2 data from the persisted `agent_steps.output` field. Production-shaped regression tests cover both fixes, and the repaired live endpoints returned HTTP 200 with grounded chat output, verified/rejected evidence arrays, and chronologically ordered agent steps.

Plan 13 Batch06 completed frontend validation and final scope review for the upload and document list UI. The mandatory `npm run build` passed, no frontend test runner is configured, and live browser checks covered TXT upload, unsupported-file rejection, progress/busy state, recent-document refresh, document list refresh, failed-status error rendering, connection-error handling, keyboard focus, backend API network destinations, and 320px mobile through desktop overflow. A development React StrictMode document-list loading issue was repaired by ignoring stale list responses while allowing the latest load to render.

## What This Folder Does

This root folder owns the full application workspace for the document QA system. It is not only a backend package or only a frontend app.

Authoritative runtime behavior is defined primarily by:

- `backend/app/main.py` for FastAPI app creation and router registration.
- `backend/app/core/config.py` for environment-driven settings.
- `backend/app/api/` for API routes currently exposed by the backend.
- `backend/app/services/` for document, parsing, chunking, embedding, Supabase, ShopAIKey, Qdrant, and semantic retrieval behavior.
- `backend/app/db/migrations/001_initial_schema.sql` for the planned Supabase PostgreSQL schema.
- `frontend/package.json` and `frontend/src/` for the current frontend shell.
- `docs/plans/README.md` and `docs/plans/Master_Plan.md` for the intended implementation roadmap.

Do not treat `docs/plans/Master_Plan.md` as proof that a feature exists in code. It documents the target system. Check the backend routers and services before claiming a workflow is implemented.

## Repository Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers for health and documents
│   │   ├── core/         # Settings and logging setup
│   │   ├── db/           # SQL migrations
│   │   ├── schemas/      # Pydantic API/service contracts
│   │   ├── services/     # Supabase, agent logging, parsing, chunking, embedding, Qdrant logic
│   │   ├── utils/        # Upload validation and retrieval scoring helpers
│   │   └── main.py       # FastAPI application factory and router wiring
│   ├── tests/            # Pytest tests and sample document fixtures
│   └── requirements.txt  # Python dependencies
├── docs/
│   ├── plans/            # Master plan and milestone plans
│   ├── reports/          # Task execution reports
│   ├── review/           # Task review reports
│   ├── tasks/            # Task documents
│   └── visual-overview.html
├── frontend/
│   ├── src/
│   │   ├── api/client.ts # Axios client using VITE_API_BASE_URL
│   │   ├── components/   # Reusable upload, document card, and status badge components
│   │   ├── utils/        # Shared frontend file validation helpers
│   │   ├── App.tsx      # Upload/documents routes and compact navigation
│   │   ├── main.tsx     # React entrypoint and BrowserRouter provider
│   │   └── styles.css   # Responsive application and document UI styling
│   ├── package.json
│   └── vite.config.ts
├── .gitignore
└── README.md
```

## Main Workflows

### Backend Startup

1. `backend/app/main.py` calls `setup_logging()`.
2. `create_app()` loads settings from `backend/app/core/config.py`.
3. The FastAPI app is created with title `Document QA Agent`.
4. CORS allows `settings.frontend_origin`, defaulting to `http://localhost:5173`.
5. Routers are mounted:
   - `GET /api/health`
   - document routes under `/api/documents`
   - `POST /api/retrieval/search`
   - `POST /api/chat/ask`
   - `GET /api/agent-runs/{agent_run_id}/evidence`
   - `GET /api/agent-runs/{agent_run_id}/logs`

### Health Check

1. `GET /api/health` is handled by `backend/app/api/health.py`.
2. The route reads settings with `get_settings()`.
3. It returns `status`, `service`, and `app_env`.

### Document Upload

1. `POST /api/documents/upload` accepts a multipart `file` in `backend/app/api/documents.py`.
2. `backend/app/services/document_service.py` validates the upload through `backend/app/utils/file_validation.py`.
3. Supported extensions are `pdf`, `docx`, `txt`, and `csv`; content type is checked when provided.
4. The service creates a UUID document ID and a Supabase Storage path shaped like `documents/{user_id}/{document_id}/{safe_filename}`.
5. `backend/app/services/supabase_service.py` uploads the original file to the configured Supabase Storage bucket.
6. A `documents` metadata row is inserted with status `uploaded` and `chunk_count` set to `0`.
7. The API returns `document_id`, `file_name`, and `status`.

Important current limitation: upload does not automatically call `process_document()`. Processing exists as a service but is not wired into the upload route.

### Document Listing and Detail

1. `GET /api/documents` calls `document_service.list_documents()`.
2. Supabase metadata is filtered by `settings.single_user_id` and ordered newest first.
3. `GET /api/documents/{document_id}` calls `document_service.get_document_detail()`.
4. Detail responses currently include document metadata and an empty `chunks` list.

### Document Processing Service

`backend/app/services/document_processing_service.py` defines the parse/chunk/persist workflow:

1. Load the document row for the configured single user.
2. Mark the document `processing`.
3. Download the original file from Supabase Storage.
4. Parse bytes with `document_parser.parse_document()`.
5. Enrich parsed sections with document/user/file metadata.
6. Split sections into `ChunkDraft` records with `chunking_service.chunk_sections()`.
7. Insert chunks into Supabase `document_chunks`.
8. Update document `chunk_count`.
9. Build graph rows for the document through `graph_builder.build_document_graph(document_id)`.
10. Mark the document `ready`, or mark it `failed` with a safe error message.

The processing result includes graph entity, relationship, and graph error counts. Graph build failures are mapped to the safe public message `Document graph build failed.` before the document is marked `failed`. This workflow is tested, but no public API route currently triggers it.

### Parsing and Chunking

`backend/app/services/document_parser.py` supports:

- PDF via `pypdf.PdfReader`, preserving page numbers.
- DOCX via `python-docx`, preserving heading-derived section titles and paragraph metadata.
- TXT via UTF-8 with Latin-1 fallback.
- CSV via Python `csv`, converting each non-empty row into readable text with column names and row indexes.

`backend/app/services/chunking_service.py` uses a deterministic word-based token estimate, configurable chunk size and overlap, and prefers sentence/newline boundaries when splitting long sections.

### Embedding and Qdrant Indexing

1. `POST /api/documents/{document_id}/index` is a development/internal route in `backend/app/api/documents.py`; the route docstring says the frontend must not call it.
2. `embedding_service.index_document_chunks()` requires the document status to be `ready`.
3. It loads chunks without `qdrant_point_id` from Supabase.
4. Each chunk is embedded through `shopaikey_service.create_embedding()`, which calls an OpenAI-compatible `/embeddings` endpoint.
5. `qdrant_service.ensure_collection()` creates or validates the configured Qdrant collection using cosine distance.
6. The chunk vector is upserted to Qdrant using the chunk UUID as the stable point ID.
7. Supabase `document_chunks.qdrant_point_id` is updated after successful upsert.

Partial failures are collected into `DocumentIndexingResult` instead of stopping all chunks immediately.

### Semantic Retrieval Service

`backend/app/services/retrieval_service.py` defines the current service-level semantic search workflow:

1. `semantic_search(question, document_ids=None, top_k=None)` trims and validates the question.
2. It resolves omitted `top_k` from `RETRIEVAL_SEMANTIC_TOP_K` and enforces the 1 through 50 bounds.
3. It embeds the question with `shopaikey_service.create_embedding()`.
4. It searches Qdrant through `qdrant_service.search_vectors()`, including the existing single-user and optional document filters owned by the Qdrant service.
5. It maps Qdrant payload fields into `RetrievalResult` objects, tolerating malformed optional fields and skipping unsafe points that cannot be identified or scored.
6. If Qdrant only has `content_preview`, it fetches full chunk content from Supabase `document_chunks` with `SINGLE_USER_ID` filtering.
7. No-match searches return `SearchResponse(results=[])`.

ShopAIKey embedding failures are wrapped as `RetrievalDependencyError` with the safe public message `Semantic retrieval is temporarily unavailable.` so the API layer can map the failure without leaking provider details.

### Semantic Retrieval API

`backend/app/api/retrieval.py` exposes `POST /api/retrieval/search`, mounted from `backend/app/main.py` under `/api/retrieval`.

The request schema accepts `question`, optional `document_ids`, optional `top_k`, and optional `mode` values of `semantic` or `hybrid`, defaulting to `semantic`. Omitted `mode` and explicit `mode="semantic"` delegate to `retrieval_service.semantic_search()` and return the normalized `question` plus a semantic `results` list. `mode="hybrid"` delegates to `hybrid_retrieval_service.retrieve_hybrid()` on the same endpoint, maps request `top_k` to the hybrid final Top-K, and returns the normalized `question` plus a hybrid `candidates` list with score components and `final_score`. API-level error behavior is:

- Empty or whitespace-only questions return HTTP 400.
- `top_k` values outside 1 through 50 return HTTP 400.
- Invalid document UUIDs return HTTP 422 through FastAPI/Pydantic validation.
- ShopAIKey and Qdrant dependency failures return HTTP 500 with a safe public message.
- Hybrid validation failures return HTTP 400, and hybrid dependency failures return HTTP 500 with a safe public message.
- No matching indexed chunks return HTTP 200 with an empty `results` list.

### Graph Configuration, Entity Extraction, Builder, and Persistence Contracts

Plan 7 graph groundwork is partially implemented in backend-only code:

1. `backend/app/core/config.py` exposes `SHOPAIKEY_CHAT_MODEL` and `GRAPH_EXTRACTION_ENABLED`.
2. `backend/app/schemas/graph.py` defines allowed graph entity and relationship types, validated extraction output models, persistence draft models, and graph build result/error contracts.
3. `backend/app/services/supabase_service.py` includes helper contracts for graph document lookup, chunk listing, graph row clearing, entity insertion/lookup, and relationship insertion.
4. `backend/app/services/shopaikey_service.py` exposes `chat_completion(messages, response_format=None)` for OpenAI-compatible structured extraction calls.
5. `backend/app/services/entity_extraction_service.py` extracts entities and candidate entity relationships from one chunk, validates LLM JSON with Pydantic before returning drafts, raises controlled chunk-scoped errors for invalid/provider output, and uses deterministic date/repeated-capitalized-term fallback when graph extraction is disabled.
6. `backend/app/services/graph_builder.py` loads one document and its chunks through graph helpers, clears existing graph rows after preconditions pass, derives stable section concepts, extracts and de-duplicates entities, persists `document_entities`, and inserts validated structural, chunk-entity, entity-entity, and strong-overlap chunk-chunk relationships.
7. Graph build results report inserted entity and relationship counts, safe per-chunk extraction errors, and partial-state flags when rows were cleared or a partial rebuild risk exists.
8. The supported graph build path is currently `document_processing_service.process_document()` after chunk persistence.

No public graph build route is mounted yet. Public graph APIs, graph expansion retrieval, and frontend graph workflows are still planned.

### Hybrid Retrieval Configuration, Schemas, Scoring Utilities, Graph Candidates, and API Mode

Plan 8 Batch01 through Batch04 backend retrieval behavior is implemented:

1. `backend/app/core/config.py` exposes backend-only `RETRIEVAL_GRAPH_TOP_K`, `RETRIEVAL_FINAL_TOP_K`, `ENABLE_RERANK`, and optional `SHOPAIKEY_RERANK_MODEL` settings while preserving `RETRIEVAL_SEMANTIC_TOP_K`.
2. `ENABLE_RERANK` defaults to `false`; settings validation requires `SHOPAIKEY_RERANK_MODEL` only when rerank is enabled.
3. `backend/app/schemas/retrieval.py` defines hybrid score component, candidate, and response models that include all five Plan 8 score components plus `final_score` and optional retrieval reason.
4. `backend/app/utils/scoring.py` contains deterministic helpers for score clamping, keyword overlap, metadata matching, recency or position scoring, and the exact Plan 8 final score formula.
5. `backend/app/services/graph_retrieval_service.py` provides backend-only graph candidate lookup through deterministic question term matching, persisted entity/relationship traversal, selected-document filtering, chunk enrichment, normalized `graph_relevance`, and a mockable repository boundary.
6. `backend/app/services/hybrid_retrieval_service.py` calls semantic and graph retrieval with configurable candidate counts, merges candidates by `chunk_id`, fills missing semantic or graph scores with `0.0`, computes deterministic keyword, metadata, position, and final scores, sorts by `final_score` descending, applies configurable final Top-K, can attach optional retrieval-only reasons without answer generation, fails safely on semantic dependency errors, and falls back to semantic-only scoring when graph lookup is unavailable.
7. `backend/app/services/shopaikey_service.py` exposes a guarded rerank placeholder. Disabled rerank returns candidates unchanged and makes no provider call; enabled rerank requires backend rerank configuration and currently fails safely because live rerank is not implemented.
8. `backend/app/api/retrieval.py` supports optional `mode="hybrid"` routing on `POST /api/retrieval/search` while preserving semantic default behavior.
9. No live rerank call or frontend retrieval UI is implemented yet.

## Architecture

The current architecture is layered:

- API layer: `backend/app/api/health.py`, `backend/app/api/documents.py`, `backend/app/api/retrieval.py`, `backend/app/api/chat.py`, and `backend/app/api/agent_runs.py` expose FastAPI routes and map service exceptions to HTTP responses.
- Agent package: `backend/app/agents/` exposes shared Agent 1 retrieval input, candidate, and output schemas, Agent 2 verification input/output schemas and prompt rules, Agent 3 answer input/output schemas, citation/evidence validation helpers, answer-generation and self-check prompts, and deterministic self-check readiness helpers. It also includes the backend-only retrieval agent callable that delegates to hybrid retrieval, returns validated candidates, logs successful steps, and raises a controlled retrieval error after failed-step logging when retrieval fails, plus the backend-only Agent 2 verification callable that validates input, short-circuits empty candidates, calls ShopAIKey chat for non-empty candidates, validates JSON output, applies deterministic evidence safety checks, logs success and controlled failure steps through the agent log service, surfaces log persistence failures through safe warnings, and preserves the final public output shape before returning success. The Agent 3 runtime callable validates Agent 2 verification input, returns deterministic insufficient-evidence output without provider calls, builds verified-only ShopAIKey answer-generation messages for sufficient evidence, calls ShopAIKey, parses draft JSON into `AnswerAgentOutput`, enforces citation presence and format, validates citations against verified evidence, rejects rejected evidence reuse, runs LLM-assisted self-check, rejects non-ready self-check results with controlled `AnswerAgentError`, normalizes the public output shape, and attempts success/failed `agent_steps` logging with safe log persistence warnings. `backend/app/agents/graph.py` defines the LangGraph QA workflow state and `run_qa_workflow(question, document_ids, session_id=None)` contract that creates a running agent run, invokes Agent 1, Agent 2, and Agent 3 in order, marks success/failure through `agent_run_service`, returns Agent 3 answer fields plus `agent_run_id`, and preserves Agent 3 insufficient-evidence handling. The public chat route prepares the session and user message, invokes this workflow, persists the assistant message, and returns the workflow response. Chat and agent-run failure paths now return controlled public errors without exposing provider, Supabase, Qdrant, stack, or secret details.
- `backend/app/schemas/chat.py`: Plan 12 `/api/chat/ask` request/response contracts with optional `session_id`, UUID-validated `document_ids`, non-empty questions, answer confidence, citations, and `agent_run_id`.
- `backend/app/schemas/agent_runs.py`: Plan 12 response contracts for the public agent-run evidence and logs endpoints.
- Configuration layer: `backend/app/core/config.py` centralizes Pydantic settings, default values, and required external-service checks.
- Service layer: `backend/app/services/` owns orchestration, entity extraction, chat persistence preparation, agent-run lifecycle/evidence/log lookup, and provider-specific clients.
- Persistence layer: `supabase_service.py` reads/writes Supabase tables and storage buckets, including chat session/message and agent run helper contracts scoped to `SINGLE_USER_ID`.
- Vector layer: `qdrant_service.py` manages collection setup, vector upsert, and vector search helpers.
- Provider layer: `shopaikey_service.py` calls the embedding and chat completion endpoints.
- Schema layer: `backend/app/schemas/` defines Pydantic request/response and internal contracts, including graph extraction and graph build contracts.
- Frontend layer: `frontend/src/` is a routed React application with an Axios client, typed document upload/list/detail API helpers, upload and document list pages, reusable document display components, compact navigation, responsive/accessibility styling, and shared file validation.

The planned architecture in `docs/plans/Master_Plan.md` also includes public graph APIs and richer frontend pages. The backend now implements the LangGraph agent workflow, chat sessions/messages, agent runs/steps, and public chat, evidence, and logs APIs.

## Frontend

The frontend is a Vite React TypeScript project in `frontend/`.

Evidence:

- `frontend/package.json` defines `dev`, `build`, and `preview` scripts.
- `frontend/package.json` includes `react-router-dom` for upload and document list routing.
- `frontend/src/main.tsx` mounts `<App />` inside `BrowserRouter`.
- `frontend/src/App.tsx` renders compact Upload/Documents navigation, routes `/upload` and `/documents`, and redirects root or unknown paths to `/upload`.
- `frontend/src/api/client.ts` creates an Axios client with `baseURL: import.meta.env.VITE_API_BASE_URL`.
- `frontend/src/api/documents.ts` exposes typed `uploadDocument`, `listDocuments`, and `getDocument` helpers through the backend `/api/documents` routes, along with safe document API error and upload progress contracts.
- `frontend/src/types/documents.ts` defines shared frontend response types for document status, upload, list, and detail responses.
- `frontend/src/components/StatusBadge.tsx`, `frontend/src/components/DocumentCard.tsx`, and `frontend/src/components/UploadBox.tsx` provide reusable document status, document metadata, and file selection UI components.
- `frontend/src/utils/fileValidation.ts` accepts PDF, DOCX, TXT, and CSV files case-insensitively and rejects unsupported or zero-byte files before upload callers receive the file.
- `frontend/src/styles.css` contains responsive application, navigation, focus, busy, error/success, status badge, document card, and upload box styles.

The upload and document list screens are mounted and navigable. Chat, evidence viewer, and agent log frontend screens are not implemented.

## Backend

The backend is a FastAPI project in `backend/`.

Key files:

- `backend/app/main.py`: app factory, CORS setup, route registration.
- `backend/app/agents/schemas.py`: shared Agent 1 retrieval input, candidate, and output Pydantic schemas, Agent 2 verification input/output schemas, and Agent 3 answer/citation/self-check schemas.
- `backend/app/agents/prompts.py`: reusable Agent 2 verification prompt rules, Agent 3 answer-generation and self-check prompt rules, and required output-key metadata.
- `backend/app/agents/retrieval_agent.py`: backend-only Agent 1 callable for hybrid retrieval delegation, output validation, success logging, and controlled retrieval failure handling.
- `backend/app/agents/verification_agent.py`: backend-only Agent 2 callable for verification input validation, empty-candidate missing-information output, compact ShopAIKey chat requests, strict JSON parsing, Pydantic output validation, deterministic candidate membership checks, quote fidelity checks, duplicate filtering, contradiction/missing-information adjustment, success/failed step logging with safe payloads, safe log-insertion failure warnings, and final output shape preservation.
- `backend/app/agents/answer_agent.py`: Agent 3 internal callable, controlled answer error, input normalization, verified/rejected evidence lookup, deterministic insufficient-evidence output, verified-only provider payload/message construction, ShopAIKey draft answer parsing, citation formatting, verified/rejected evidence validation, visible chunk-ID blocking, LLM-assisted self-check execution, output-shape normalization, self-check normalization, ready-state enforcement helpers, and safe success/failed step logging.
- `backend/app/api/health.py`: health endpoint.
- `backend/app/api/documents.py`: upload, list, detail, and development indexing routes.
- `backend/app/api/retrieval.py`: retrieval search endpoint and safe API error mapping.
- `backend/app/core/config.py`: settings and required provider configuration checks.
- `backend/app/services/document_service.py`: upload/list/detail orchestration.
- `backend/app/services/agent_log_service.py`: Agent 1 step log validation and safe persistence wrapper.
- `backend/app/services/chat_service.py`: service-layer chat persistence preparation, selected document ownership validation, owned-session checks before user/assistant message writes, and controlled chat errors for API mapping.
- `backend/app/services/agent_run_service.py`: agent run lifecycle helpers, owned-session checks before run creation, Agent 2 evidence extraction from persisted steps, ordered log response mapping, and controlled agent-run errors for API mapping.
- `backend/app/services/document_processing_service.py`: parse/chunk/persist/graph-build workflow, not exposed through an API route.
- `backend/app/services/document_parser.py`: parsers for PDF, DOCX, TXT, and CSV.
- `backend/app/services/chunking_service.py`: deterministic chunk generation.
- `backend/app/services/embedding_service.py`: document chunk indexing orchestration.
- `backend/app/services/supabase_service.py`: Supabase database and storage operations.
- `backend/tests/test_agent_log_service.py`: mocked coverage for Agent 1 step log persistence and safe failure behavior.
- `backend/tests/test_retrieval_agent.py`: mocked coverage for Agent 1 schema validation, retrieval delegation, validated output conversion, success logging, empty-result success, candidate schema mismatch rejection, invalid-input rejection, controlled retrieval failure logging, and failed-log preservation.
- `backend/tests/test_answer_agent.py`: Agent 3 callable, input normalization, insufficient-evidence, provider payload, draft JSON parsing, citation enforcement, schema, citation/evidence contract, prompt-rule, self-check readiness, controlled self-check failure, success/failed logging, and safe log-persistence failure tests.
- `backend/tests/test_langgraph_workflow.py`: mocked coverage for the internal LangGraph QA workflow state, Agent 1 -> Agent 2 -> Agent 3 execution order, compiled graph order, persisted run lifecycle success/failure handling, Agent 3 final-answer ownership, and insufficient-evidence success behavior.
- `backend/tests/test_chat_api.py`: schema-level coverage for the planned chat ask request/response contracts plus service-level chat persistence and safe error tests.
- `backend/tests/test_agent_runs_api.py`: schema-level coverage for the planned agent-run evidence/log response contracts plus service-level lifecycle, evidence, logs, and safe error tests.
- `backend/app/services/qdrant_service.py`: Qdrant collection, upsert, and search helpers.
- `backend/app/services/shopaikey_service.py`: embedding and chat completion API calls.
- `backend/app/services/retrieval_service.py`: semantic retrieval orchestration, result mapping, Supabase content fallback, and safe dependency failure wrapping.
- `backend/app/services/graph_retrieval_service.py`: backend-only graph candidate lookup over persisted entities, relationships, and chunks.
- `backend/app/services/hybrid_retrieval_service.py`: backend-only hybrid candidate merge, scoring, final ranking, and deterministic retrieval reason generation.
- `backend/app/utils/scoring.py`: deterministic hybrid retrieval score normalization helpers and exact final score formula.

## Data, Storage, and External Services

### Supabase

Supabase is used for PostgreSQL metadata/chunk tables and original document storage. The migration at `backend/app/db/migrations/001_initial_schema.sql` defines:

- `documents`
- `document_chunks`
- `document_entities`
- `document_relationships`
- `chat_sessions`
- `chat_messages`
- `agent_runs`
- `agent_steps`

Only some of these tables are currently used by service code. Document upload/list/detail uses `documents`; processing and indexing use `document_chunks`. Graph helper contracts can read chunks and write `document_entities` and `document_relationships`; the current graph builder writes structural document-section and section-chunk relationships, de-duplicated extracted entities, chunk-entity links, valid entity-entity links, and strong-overlap chunk-chunk links. Agent 1 retrieval, Agent 2 verification, and Agent 3 answer/self-check write `agent_steps` through the backend agent log service. The public chat workflow uses `chat_sessions`, `chat_messages`, and `agent_runs`; evidence and logs APIs read the owned run and persisted Agent 2/all-step data.

### Qdrant

Qdrant stores chunk vectors. `qdrant_service.py` creates or validates a collection using cosine distance and stores payload fields including `user_id`, `document_id`, `chunk_id`, `file_name`, `file_type`, page/section metadata, chunk index, and a content preview.

Vector search helpers always include a `user_id = SINGLE_USER_ID` filter and optionally filter by selected document IDs.

For live semantic retrieval checks, the Qdrant collection must support keyword payload filtering on `user_id` and `document_id`; otherwise required filtered searches can fail even when vectors exist.

### ShopAIKey

`shopaikey_service.py` calls OpenAI-compatible endpoints for embeddings and chat completion:

- Embeddings use `{SHOPAIKEY_BASE_URL}/embeddings` and `SHOPAIKEY_EMBEDDING_MODEL`.
- Chat completion uses `{SHOPAIKEY_BASE_URL}/chat/completions` and `SHOPAIKEY_CHAT_MODEL`.

The embedding and chat models are configured through backend settings; they are not hardcoded in the service. ShopAIKey API key, base URL, and chat model values remain backend-only and are not exposed through frontend configuration. Agent 3 sufficient-evidence answer generation now builds verified-only chat messages through the existing backend chat helper, parses provider draft JSON with citation/evidence enforcement, and runs self-check through the same backend chat helper before returning ready output. Guarded rerank configuration exists in backend settings, but no live rerank service call is implemented.

## Configuration

`backend/app/core/config.py` reads environment variables from `backend/.env` because `BACKEND_DIR` resolves to the `backend/` folder. A root `.env` exists in this workspace, but the backend settings code does not read root `.env` by default.

Do not expose or copy secret values into documentation.

| Variable | Required | Purpose | Source |
| --- | --- | --- | --- |
| `APP_ENV` | No | Runtime environment label returned by health and logged at startup. | `backend/app/core/config.py` |
| `SINGLE_USER_ID` | No | Single-user ownership filter for documents, chunks, vectors, and future agent data. | `backend/app/core/config.py` |
| `FRONTEND_ORIGIN` | No | Allowed CORS origin for the backend. Defaults to `http://localhost:5173`. | `backend/app/core/config.py` |
| `SUPABASE_URL` | Yes for Supabase operations | Supabase project URL. | `Settings.require_supabase_settings()` |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes for Supabase operations | Backend-only Supabase service role key. | `Settings.require_supabase_settings()` |
| `SUPABASE_STORAGE_BUCKET` | No | Storage bucket for original uploaded documents. Defaults to `documents`. | `backend/app/core/config.py` |
| `SHOPAIKEY_API_KEY` | Yes for embeddings | Backend-only ShopAIKey API key. | `Settings.require_shopaikey_settings()` |
| `SHOPAIKEY_BASE_URL` | Yes for embeddings | OpenAI-compatible API base URL. | `Settings.require_shopaikey_settings()` |
| `SHOPAIKEY_CHAT_MODEL` | Yes for backend chat completion calls | Chat model used by backend ShopAIKey chat completion callers, including graph extraction and Agent 3 answer/self-check generation. | `backend/app/core/config.py` |
| `SHOPAIKEY_EMBEDDING_MODEL` | Yes for embeddings | Embedding model sent to the `/embeddings` endpoint. | `Settings.require_shopaikey_settings()` |
| `SHOPAIKEY_RERANK_MODEL` | Yes only when `ENABLE_RERANK=true` | Optional rerank model name for guarded rerank placeholder configuration. | `backend/app/core/config.py` |
| `GRAPH_EXTRACTION_ENABLED` | No | Enables future live graph extraction; can be disabled for deterministic fallback tests/local development. Defaults to `true`. | `backend/app/core/config.py` |
| `QDRANT_URL` | Yes for Qdrant operations | Qdrant endpoint URL. | `Settings.require_qdrant_settings()` |
| `QDRANT_API_KEY` | Yes for Qdrant operations | Backend-only Qdrant API key. | `Settings.require_qdrant_settings()` |
| `QDRANT_COLLECTION` | Yes for Qdrant operations | Collection name for chunk vectors. | `Settings.require_qdrant_settings()` |
| `RETRIEVAL_SEMANTIC_TOP_K` | No | Semantic retrieval limit, constrained from 1 to 50. Defaults to `20`. | `backend/app/core/config.py` |
| `RETRIEVAL_GRAPH_TOP_K` | No | Graph candidate limit before hybrid merge, constrained from 1 to 50. Defaults to `20`. | `backend/app/core/config.py` |
| `RETRIEVAL_FINAL_TOP_K` | No | Final ranked hybrid result limit, constrained from 1 to 50. Defaults to `8`. | `backend/app/core/config.py` |
| `ENABLE_RERANK` | No | Enables guarded rerank placeholder behavior only when explicitly true and the rerank model is configured. Defaults to `false`. | `backend/app/core/config.py` |
| `MAX_UPLOAD_BYTES` | No | Upload size limit in bytes. Defaults to `25000000`. | `backend/app/core/config.py` |
| `CHUNK_SIZE_TOKENS` | No | Approximate chunk size. Defaults to `1000`. | `backend/app/core/config.py` |
| `CHUNK_OVERLAP_TOKENS` | No | Approximate chunk overlap. Defaults to `150`; must be less than chunk size. | `backend/app/core/config.py` |
| `VITE_API_BASE_URL` | Yes for frontend API calls | Frontend Axios base URL. | `frontend/src/api/client.ts` |

## Setup

### Backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `backend/.env` with the backend variables listed above. The backend code expects provider secrets to remain backend-only.

Apply the Supabase schema from:

```text
backend/app/db/migrations/001_initial_schema.sql
```

The repository does not include an automated migration runner; apply the SQL using your Supabase workflow.

### Frontend

From the repository root:

```powershell
cd frontend
npm install
```

Create a frontend environment file with:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Use the actual backend URL if it differs.

## Running the Project

### Backend API

From `backend/`:

```powershell
uvicorn app.main:app --reload
```

The expected default URL is `http://localhost:8000` when Uvicorn uses its default port.

Useful endpoints:

```text
GET http://localhost:8000/api/health
POST http://localhost:8000/api/chat/ask
GET http://localhost:8000/api/agent-runs/{agent_run_id}/evidence
GET http://localhost:8000/api/agent-runs/{agent_run_id}/logs
```

### Frontend Dev Server

From `frontend/`:

```powershell
npm run dev
```

Vite commonly serves at `http://localhost:5173`. The backend CORS default is configured for that origin.

### Frontend Document API Client

The frontend document API boundary is implemented in `frontend/src/api/documents.ts`. It calls only the backend document endpoints through `apiClient`: `POST /api/documents/upload`, `GET /api/documents`, and `GET /api/documents/{document_id}`.

Upload progress is normalized so callers can distinguish computable percentages from unknown totals. Document API errors expose safe display messages for backend `detail` text, backend connection failures, and generic request failures.

React Router is mounted through `BrowserRouter`. `App.tsx` exposes `/upload` and `/documents`, with root and unknown paths redirecting to `/upload`.

### Frontend Reusable Document Components

`frontend/src/components/StatusBadge.tsx` renders the approved `uploaded`, `processing`, `ready`, and `failed` document statuses with visible text and distinct styling.

`frontend/src/components/DocumentCard.tsx` renders document list metadata, including file name, type, upload time, status, chunk count, and failed-processing error text when present.

`frontend/src/components/UploadBox.tsx` provides a reusable native file input with optional drag-and-drop behavior. It uses `frontend/src/utils/fileValidation.ts` to accept PDF, DOCX, TXT, and CSV files case-insensitively and reject unsupported or zero-byte files before handing the file to callers.

`frontend/src/pages/UploadDocumentPage.tsx` now combines validated file selection, upload progress, safe upload success/error feedback, and a compact recent-documents section that refreshes through `listDocuments()` after successful uploads.

`frontend/src/pages/DocumentListPage.tsx` fetches documents on page load, renders returned items through `DocumentCard`, distinguishes loading, empty, connection-error, list-error, and stale-list refresh-failure states, and provides a guarded manual Refresh action that re-fetches `GET /api/documents` without polling or calling processing/index endpoints.

The upload and document list pages are mounted in `App.tsx` with compact route-aware navigation. Styling supports visible focus and active states, disabled/busy feedback, long-content wrapping, and narrow layouts down to the 320px minimum viewport.

### Production Frontend Build

From `frontend/`:

```powershell
npm run build
```

This runs `tsc --noEmit` and `vite build` according to `frontend/package.json`.

## Testing and Validation

Backend tests are under `backend/tests/`. From `backend/`:

```powershell
pytest
```

The tests cover settings validation, graph schema validation, entity extraction validation/fallback behavior, health response, upload validation, document metadata services, parser behavior, chunking behavior, processing orchestration, ShopAIKey embedding and chat completion error handling, guarded rerank placeholder behavior, Supabase service behavior including graph, chat, and agent-run helper contracts, Qdrant service behavior, embedding/indexing orchestration, semantic retrieval service behavior, graph retrieval service behavior, hybrid retrieval merge/scoring/ranking/reason/failure behavior, retrieval API semantic and hybrid mode contracts/error behavior, Agent 1 step logging behavior, Agent 1 retrieval callable behavior, Agent 1 schema/output/failure automated-test coverage, Agent 2 verification schema confidence bounds, prompt-content rules, empty-candidate behavior, compact ShopAIKey request construction, strict LLM JSON validation, deterministic evidence safety checks, Agent 2 success/failed step logging, Agent 2 log-insertion failure safety, Agent 3 answer schema/citation/prompt/self-check contracts, Agent 3 callable validation, deterministic insufficient-evidence output, Agent 2 verification input normalization, verified/rejected evidence lookup, verified-only answer-generation provider payloads, draft answer JSON parsing, citation presence and verified-quote enforcement, rejected evidence exclusion, Agent 3 runtime self-check enforcement, Agent 3 success/failed step logging, Agent 3 log-insertion failure safety, Agent 3 public output-shape normalization, Plan 12 chat persistence service behavior, Plan 12 agent-run service behavior, selected document ownership validation, controlled service error public messages, and the development indexing API. Plan 8 Batch05 also completed the required scoring, graph retrieval, and hybrid retrieval test runs plus a service-level hybrid retrieval smoke check against local processed, indexed, graph-built data.

For Plan 10 Agent 2 verification changes, the required targeted backend validation is:

```powershell
cd backend
pytest tests/test_verification_agent.py -v
```

For Plan 11 Agent 3 answer changes, the required targeted backend validation is:

```powershell
cd backend
pytest tests/test_answer_agent.py -v
```

For Plan 12 Batch01 workflow contract and API schema changes, the targeted backend validation is:

```powershell
cd backend
pytest tests/test_langgraph_workflow.py tests/test_chat_api.py tests/test_agent_runs_api.py -v
```

For Plan 12 Batch02 chat and agent-run persistence service changes, the targeted backend validation is:

```powershell
cd backend
pytest tests/test_chat_api.py tests/test_agent_runs_api.py tests/test_supabase_service.py -v
```

For Plan 12 Batch03 LangGraph workflow orchestration changes, the targeted backend validation is:

```powershell
cd backend
pytest tests/test_langgraph_workflow.py -v
```

For Plan 12 Batch04 public API changes, the targeted backend validation is:

```powershell
cd backend
pytest tests/test_chat_api.py tests/test_agent_runs_api.py -v
```

For Plan 12 Batch05 failure handling and single-user safety changes, the targeted backend validation is:

```powershell
cd backend
pytest tests/test_chat_api.py tests/test_agent_runs_api.py tests/test_langgraph_workflow.py tests/test_supabase_service.py -v
```

For Plan 12 Batch06 required automated test changes, the targeted backend validation is:

```powershell
cd backend
pytest tests/test_langgraph_workflow.py -v
pytest tests/test_chat_api.py tests/test_agent_runs_api.py -v
```

Plan 12 Batch07 also completed live validation of `POST /api/chat/ask` and both agent-run inspection endpoints using configured Supabase, Qdrant, ShopAIKey, and indexed document data. The final targeted results were 9 workflow tests, 68 combined chat/agent-run tests, and 55 Supabase service tests passing; the live chat, evidence, and logs requests returned HTTP 200 after the citation and persisted-output repairs.

Frontend validation commands from `frontend/package.json`:

```powershell
npm run build
npm run preview
```

There is no frontend test script in `frontend/package.json`.

## Development Notes for AI Agents

Read these first:

- `docs/plans/README.md` for the milestone order and planned scope.
- `docs/plans/Master_Plan.md` for target architecture and non-goals.
- `backend/app/main.py` to see what API routes are actually mounted.
- `backend/app/core/config.py` before changing environment behavior.
- `backend/app/api/documents.py` and `backend/app/services/document_service.py` before changing upload/list/detail behavior.
- `backend/app/services/document_processing_service.py`, `document_parser.py`, and `chunking_service.py` before changing parsing or chunk persistence.
- `backend/app/services/embedding_service.py`, `shopaikey_service.py`, `qdrant_service.py`, and `retrieval_service.py` before changing indexing or retrieval behavior.
- `backend/app/services/hybrid_retrieval_service.py` and `backend/app/utils/scoring.py` before changing hybrid retrieval merge, score component, final ranking, or retrieval reason behavior.
- `backend/app/agents/schemas.py`, `backend/app/agents/prompts.py`, `backend/app/agents/retrieval_agent.py`, `backend/app/agents/verification_agent.py`, `backend/app/agents/answer_agent.py`, and `backend/app/agents/graph.py` before changing Agent 1 workflow contracts, Agent 2 verification contracts, Agent 3 answer contracts, prompt rules, retrieval-agent behavior, verification-agent behavior, answer evidence/self-check behavior, or LangGraph orchestration contracts.
- `backend/app/schemas/chat.py` and `backend/app/schemas/agent_runs.py` before changing chat, evidence, or agent-log API response contracts.
- `backend/app/services/entity_extraction_service.py` and `backend/app/schemas/graph.py` before changing graph extraction behavior.
- `backend/app/db/migrations/001_initial_schema.sql` before changing persistence contracts.

Important coordination rules:

- Keep `SINGLE_USER_ID` filtering intact unless the project explicitly moves to multi-user auth. The MVP plan says no Auth/JWT.
- Never move backend-only secrets into frontend code. Supabase service role, Qdrant key, and ShopAIKey key must remain backend-only.
- If you add API routes, update `backend/app/main.py`; adding a router file alone does not expose it.
- If you change document/chunk schemas, coordinate Pydantic schemas, Supabase SQL, service row builders, tests, and any Qdrant payload expectations.
- If you wire processing into upload, account for status transitions: `uploaded`, `processing`, `ready`, `failed`.
- If you change retrieval API behavior, keep `backend/app/api/retrieval.py` thin, preserve safe error responses, and keep semantic retrieval orchestration in `backend/app/services/retrieval_service.py`. The `mode` request field supports `semantic` and `hybrid`; semantic mode remains the default, while hybrid mode delegates to `backend/app/services/hybrid_retrieval_service.py`.
- If you implement frontend features, preserve the existing routed upload/documents shell and keep `frontend/src/api/client.ts` aligned with backend routes.
- Ignore generated and dependency folders such as `node_modules/`, `__pycache__/`, `.pytest_cache/`, `dist/`, `build/`, `.venv/`, and `venv/`.

Validation before claiming completion:

- Run `pytest` from `backend/` for backend changes.
- Run `npm run build` from `frontend/` for frontend changes.
- For provider integrations, prefer mocked tests unless the task explicitly requires live Supabase, Qdrant, or ShopAIKey validation.
- Do not claim GraphRAG, public LangGraph chat API wiring, chat API routes, evidence viewer, or agent log APIs are implemented unless corresponding routes/services/tests exist in code.

## Known Gaps or Unclear Areas

- The backend reads `backend/.env`, but this workspace currently has a root `.env`; root `.env` is not loaded by `SettingsConfigDict` in `backend/app/core/config.py`.
- Upload stores the original file and metadata but does not automatically trigger parsing/chunking.
- `document_processing_service.process_document()` exists, builds graph rows after chunk persistence, and is tested, but is not exposed through a route or background worker.
- The development indexing route exists at `POST /api/documents/{document_id}/index`; its docstring says the frontend must not call it.
- `backend/app/api/retrieval.py` is mounted in `backend/app/main.py` and exposes `POST /api/retrieval/search`, but there is still no frontend retrieval or chat UI.
- Graph schemas, graph entity extraction, Supabase graph helper contracts, entity persistence, graph relationship expansion, count reporting, safe extraction failure summaries, processing-service graph build integration, and backend-only graph candidate lookup exist in backend code. Public graph APIs are still planned; public chat, evidence, and agent log APIs are mounted.
- Hybrid retrieval settings, schemas, scoring utilities, graph candidate lookup, candidate merge/scoring/ranking orchestration, deterministic retrieval reasons, guarded rerank behavior, safe hybrid failure handling, and hybrid API mode handling exist. Live rerank provider calls are still not implemented.
- Agent 1, Agent 2, and Agent 3 runtime callables, validation, evidence safety, self-check behavior, and step logging are implemented. `backend/app/agents/graph.py` executes Agent 1 -> Agent 2 -> Agent 3, owns the `agent_runs` lifecycle, returns Agent 3 answer fields, marks created runs failed on Agent 1/2/3 failures, and preserves the insufficient-evidence path. `POST /api/chat/ask` now provides route-level error mapping, pre-workflow request and selected-document validation, owned-session protections, and user/assistant message persistence around that workflow.
- `backend/app/schemas/chat.py` and `backend/app/schemas/agent_runs.py` define the mounted chat, evidence, and logs API contracts. `backend/app/api/chat.py` and `backend/app/api/agent_runs.py` expose those contracts through the production application.
- The database migration includes future chat/agent/graph tables; current services only partially use the graph tables through helper contracts.
- The frontend now mounts routed upload and document list screens with compact navigation and responsive/accessibility styling. Chat, retrieval, evidence, and agent-log UI remain planned.
- No root-level package manager or unified dev command exists; backend and frontend commands must be run from their own folders.
