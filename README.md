# Document QA Agent

## Overview

Document QA Agent is a single-user document question-answering project. The planned system lets one configured user upload documents, parse and chunk their contents, index chunks with embeddings, retrieve relevant evidence, and eventually answer questions using a multi-agent workflow grounded only in verified document evidence.

This repository is a mixed workspace:

- `backend/` contains the FastAPI API, service layer, Supabase persistence/storage integration, ShopAIKey embedding integration, Qdrant vector indexing, schemas, migrations, and tests.
- `frontend/` contains a Vite React TypeScript shell with an Axios API client.
- `docs/` contains the implementation plan sequence, task reports, review reports, and a visual overview.

The current codebase is not the complete MVP described in `docs/plans/Master_Plan.md`. Implemented backend areas include health, document upload metadata/storage, document listing/detail, parsing, chunking, embedding generation, Qdrant upsert/search primitives, semantic retrieval service orchestration/result mapping, the retrieval search API, a development indexing endpoint, backend graph extraction configuration, validated graph schemas, Supabase graph helper contracts, ShopAIKey chat completion support, a backend entity extraction service with deterministic fallback, graph builder rebuild behavior for `Document -> Section -> Chunk -> Entity` persistence plus validated relationship expansion, and graph building wired into the backend document processing service after chunks are persisted. Public graph APIs, chat agents, agent logs APIs, and production frontend screens are still incomplete or planned.

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
│   │   ├── services/     # Supabase, parsing, chunking, embedding, Qdrant logic
│   │   ├── utils/        # Upload validation helpers
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
│   │   ├── App.tsx      # Placeholder app shell
│   │   ├── main.tsx     # React entrypoint
│   │   └── styles.css   # Basic shell styling
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

The route accepts `question`, optional `document_ids`, and optional `top_k`, then delegates to `retrieval_service.semantic_search()`. Successful responses include the normalized `question` and a `results` list. API-level error behavior is:

- Empty or whitespace-only questions return HTTP 400.
- `top_k` values outside 1 through 50 return HTTP 400.
- Invalid document UUIDs return HTTP 422 through FastAPI/Pydantic validation.
- ShopAIKey and Qdrant dependency failures return HTTP 500 with a safe public message.
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

## Architecture

The current architecture is layered:

- API layer: `backend/app/api/health.py`, `backend/app/api/documents.py`, and `backend/app/api/retrieval.py` expose FastAPI routes and map service exceptions to HTTP responses.
- Configuration layer: `backend/app/core/config.py` centralizes Pydantic settings, default values, and required external-service checks.
- Service layer: `backend/app/services/` owns orchestration, entity extraction, and provider-specific clients.
- Persistence layer: `supabase_service.py` reads/writes Supabase tables and storage buckets.
- Vector layer: `qdrant_service.py` manages collection setup, vector upsert, and vector search helpers.
- Provider layer: `shopaikey_service.py` calls the embedding and chat completion endpoints.
- Schema layer: `backend/app/schemas/` defines Pydantic request/response and internal contracts, including graph extraction and graph build contracts.
- Frontend layer: `frontend/src/` is currently a minimal React shell and Axios client.

The planned architecture in `docs/plans/Master_Plan.md` adds GraphRAG, LangGraph agents, chat sessions, agent runs, agent steps, evidence APIs, and richer frontend pages. The database migration already includes tables for those future features, but the runtime code does not yet implement the full agent workflow.

## Frontend

The frontend is a Vite React TypeScript project in `frontend/`.

Evidence:

- `frontend/package.json` defines `dev`, `build`, and `preview` scripts.
- `frontend/src/main.tsx` mounts `<App />` into `#root`.
- `frontend/src/App.tsx` currently renders a centered placeholder with `Document QA Agent` and `Future routes placeholder`.
- `frontend/src/api/client.ts` creates an Axios client with `baseURL: import.meta.env.VITE_API_BASE_URL`.
- `frontend/src/styles.css` contains only basic shell styling.

There are no implemented upload, document list, chat, evidence viewer, or agent log screens yet.

## Backend

The backend is a FastAPI project in `backend/`.

Key files:

- `backend/app/main.py`: app factory, CORS setup, route registration.
- `backend/app/api/health.py`: health endpoint.
- `backend/app/api/documents.py`: upload, list, detail, and development indexing routes.
- `backend/app/api/retrieval.py`: retrieval search endpoint and safe API error mapping.
- `backend/app/core/config.py`: settings and required provider configuration checks.
- `backend/app/services/document_service.py`: upload/list/detail orchestration.
- `backend/app/services/document_processing_service.py`: parse/chunk/persist/graph-build workflow, not exposed through an API route.
- `backend/app/services/document_parser.py`: parsers for PDF, DOCX, TXT, and CSV.
- `backend/app/services/chunking_service.py`: deterministic chunk generation.
- `backend/app/services/embedding_service.py`: document chunk indexing orchestration.
- `backend/app/services/supabase_service.py`: Supabase database and storage operations.
- `backend/app/services/qdrant_service.py`: Qdrant collection, upsert, and search helpers.
- `backend/app/services/shopaikey_service.py`: embedding API calls.
- `backend/app/services/retrieval_service.py`: semantic retrieval orchestration, result mapping, Supabase content fallback, and safe dependency failure wrapping.

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

Only some of these tables are currently used by service code. Document upload/list/detail uses `documents`; processing and indexing use `document_chunks`. Graph helper contracts can read chunks and write `document_entities` and `document_relationships`; the current graph builder writes structural document-section and section-chunk relationships, de-duplicated extracted entities, chunk-entity links, valid entity-entity links, and strong-overlap chunk-chunk links. Chat and agent tables are planned but not yet wired into runtime workflows.

### Qdrant

Qdrant stores chunk vectors. `qdrant_service.py` creates or validates a collection using cosine distance and stores payload fields including `user_id`, `document_id`, `chunk_id`, `file_name`, `file_type`, page/section metadata, chunk index, and a content preview.

Vector search helpers always include a `user_id = SINGLE_USER_ID` filter and optionally filter by selected document IDs.

For live semantic retrieval checks, the Qdrant collection must support keyword payload filtering on `user_id` and `document_id`; otherwise required filtered searches can fail even when vectors exist.

### ShopAIKey

`shopaikey_service.py` calls OpenAI-compatible endpoints for embeddings and chat completion:

- Embeddings use `{SHOPAIKEY_BASE_URL}/embeddings` and `SHOPAIKEY_EMBEDDING_MODEL`.
- Chat completion uses `{SHOPAIKEY_BASE_URL}/chat/completions` and `SHOPAIKEY_CHAT_MODEL`.

The embedding and chat models are configured through backend settings; they are not hardcoded in the service. Rerank endpoints are still planned.

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
| `SHOPAIKEY_CHAT_MODEL` | Yes when LLM graph extraction is enabled later | Chat model intended for graph entity extraction. | `backend/app/core/config.py` |
| `SHOPAIKEY_EMBEDDING_MODEL` | Yes for embeddings | Embedding model sent to the `/embeddings` endpoint. | `Settings.require_shopaikey_settings()` |
| `GRAPH_EXTRACTION_ENABLED` | No | Enables future live graph extraction; can be disabled for deterministic fallback tests/local development. Defaults to `true`. | `backend/app/core/config.py` |
| `QDRANT_URL` | Yes for Qdrant operations | Qdrant endpoint URL. | `Settings.require_qdrant_settings()` |
| `QDRANT_API_KEY` | Yes for Qdrant operations | Backend-only Qdrant API key. | `Settings.require_qdrant_settings()` |
| `QDRANT_COLLECTION` | Yes for Qdrant operations | Collection name for chunk vectors. | `Settings.require_qdrant_settings()` |
| `RETRIEVAL_SEMANTIC_TOP_K` | No | Semantic retrieval limit, constrained from 1 to 50. Defaults to `20`. | `backend/app/core/config.py` |
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

Useful endpoint:

```text
GET http://localhost:8000/api/health
```

### Frontend Dev Server

From `frontend/`:

```powershell
npm run dev
```

Vite commonly serves at `http://localhost:5173`. The backend CORS default is configured for that origin.

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

The tests cover settings validation, graph schema validation, entity extraction validation/fallback behavior, health response, upload validation, document metadata services, parser behavior, chunking behavior, processing orchestration, ShopAIKey embedding and chat completion error handling, Supabase service behavior including graph helper contracts, Qdrant service behavior, embedding/indexing orchestration, semantic retrieval service behavior, retrieval API contract/error behavior, and the development indexing API.

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
- `backend/app/services/entity_extraction_service.py` and `backend/app/schemas/graph.py` before changing graph extraction behavior.
- `backend/app/db/migrations/001_initial_schema.sql` before changing persistence contracts.

Important coordination rules:

- Keep `SINGLE_USER_ID` filtering intact unless the project explicitly moves to multi-user auth. The MVP plan says no Auth/JWT.
- Never move backend-only secrets into frontend code. Supabase service role, Qdrant key, and ShopAIKey key must remain backend-only.
- If you add API routes, update `backend/app/main.py`; adding a router file alone does not expose it.
- If you change document/chunk schemas, coordinate Pydantic schemas, Supabase SQL, service row builders, tests, and any Qdrant payload expectations.
- If you wire processing into upload, account for status transitions: `uploaded`, `processing`, `ready`, `failed`.
- If you change retrieval API behavior, keep `backend/app/api/retrieval.py` thin, preserve safe error responses, and keep semantic retrieval orchestration in `backend/app/services/retrieval_service.py`.
- If you implement frontend features, expand beyond the current placeholder in `frontend/src/App.tsx` and keep `frontend/src/api/client.ts` aligned with backend routes.
- Ignore generated and dependency folders such as `node_modules/`, `__pycache__/`, `.pytest_cache/`, `dist/`, `build/`, `.venv/`, and `venv/`.

Validation before claiming completion:

- Run `pytest` from `backend/` for backend changes.
- Run `npm run build` from `frontend/` for frontend changes.
- For provider integrations, prefer mocked tests unless the task explicitly requires live Supabase, Qdrant, or ShopAIKey validation.
- Do not claim GraphRAG, LangGraph agents, chat, evidence viewer, or agent logs are implemented unless corresponding routes/services/tests exist in code.

## Known Gaps or Unclear Areas

- The backend reads `backend/.env`, but this workspace currently has a root `.env`; root `.env` is not loaded by `SettingsConfigDict` in `backend/app/core/config.py`.
- Upload stores the original file and metadata but does not automatically trigger parsing/chunking.
- `document_processing_service.process_document()` exists, builds graph rows after chunk persistence, and is tested, but is not exposed through a route or background worker.
- The development indexing route exists at `POST /api/documents/{document_id}/index`; its docstring says the frontend must not call it.
- `backend/app/api/retrieval.py` is mounted in `backend/app/main.py` and exposes `POST /api/retrieval/search`, but there is still no frontend retrieval or chat UI.
- Graph schemas, graph entity extraction, Supabase graph helper contracts, entity persistence, graph relationship expansion, count reporting, safe extraction failure summaries, and processing-service graph build integration exist in backend code. Public graph APIs, graph expansion retrieval, LangGraph agent orchestration, chat APIs, evidence APIs, and agent log APIs are planned but not present in runtime code.
- The database migration includes future chat/agent/graph tables; current services only partially use the graph tables through helper contracts.
- The frontend is currently a placeholder shell, not a working upload/chat UI.
- No root-level package manager or unified dev command exists; backend and frontend commands must be run from their own folders.
