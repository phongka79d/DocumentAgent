# Document QA Agent

## Overview

Document QA Agent is a single-user document question-answering application. It lets the configured user upload documents, process them into chunks, index those chunks in Qdrant, and ask grounded questions through a three-agent RAG workflow.

The workspace contains both runtime apps:

- `backend/`: FastAPI API, document processing, Supabase persistence/storage, Qdrant indexing/search, ShopAIKey model calls, and LangGraph agent orchestration.
- `frontend/`: Vite React TypeScript UI for upload, document listing, chat, evidence inspection, deletion logs, and agent logs.
- `docs/`: master plan, implementation plans, task reports, review reports, and design/spec documents.

The target architecture is described in [docs/plans/Master_Plan.md](docs/plans/Master_Plan.md). Treat code as the source of truth for what is currently implemented.

## What This Folder Does

This root folder is a mixed full-stack workspace. There is no root package manager script; run backend and frontend commands from their own folders.

Primary source-of-truth files:

- [backend/app/main.py](backend/app/main.py): FastAPI app creation, CORS, and router registration.
- [backend/app/core/config.py](backend/app/core/config.py): backend environment settings loaded from `backend/.env`.
- [backend/app/api/](backend/app/api): mounted API routers.
- [backend/app/agents/](backend/app/agents): Agent 1 retrieval, Agent 2 evidence verification, Agent 3 answer/self-check, and LangGraph workflow.
- [backend/app/services/](backend/app/services): Supabase, Qdrant, ShopAIKey, document processing, indexing, retrieval, logging, and deletion behavior.
- [frontend/src/App.tsx](frontend/src/App.tsx): client-side routes and navigation.
- [frontend/src/api/](frontend/src/api): frontend API clients using `VITE_API_BASE_URL`.
- [backend/app/db/migrations/](backend/app/db/migrations): Supabase schema migrations.

Do not expose backend secrets to the frontend. Supabase service role, Qdrant API key, and ShopAIKey API key are backend-only.

## Repository Structure

```text
.
|-- backend/
|   |-- app/
|   |   |-- agents/       # Agent schemas, prompts, workflow, retrieval/verification/answer agents
|   |   |-- api/          # FastAPI routers
|   |   |-- core/         # Settings and logging
|   |   |-- db/           # SQL migrations
|   |   |-- schemas/      # API/service Pydantic contracts
|   |   |-- services/     # Supabase, Qdrant, ShopAIKey, processing, retrieval, indexing
|   |   |-- utils/        # File validation and scoring helpers
|   |   `-- main.py       # FastAPI app factory
|   |-- tests/            # Pytest suite and fixtures
|   `-- requirements.txt
|-- frontend/
|   |-- src/
|   |   |-- api/          # Axios clients and typed API functions
|   |   |-- components/   # Reusable UI components
|   |   |-- pages/        # Routed pages
|   |   |-- types/        # Frontend TypeScript contracts
|   |   |-- App.tsx
|   |   `-- main.tsx
|   |-- package.json
|   `-- vite.config.ts
|-- docs/
|   |-- plans/            # Master plan and numbered implementation plans
|   |-- superpowers/      # Specs and implementation plans created during later work
|   |-- tasks/            # Task files
|   |-- reports/          # Execution reports
|   `-- review/           # Review reports
`-- README.md
```

## Main Workflows

### Backend Startup

1. `uvicorn app.main:app --reload` imports [backend/app/main.py](backend/app/main.py).
2. `create_app()` loads settings from [backend/app/core/config.py](backend/app/core/config.py).
3. CORS allows `FRONTEND_ORIGIN`, defaulting to `http://localhost:5173`.
4. Routers are mounted under `/api`.

Mounted backend routes include:

| Route | Purpose |
| --- | --- |
| `GET /api/health` | Health check |
| `POST /api/documents/upload` | Upload document and queue background processing/indexing |
| `GET /api/documents` | List documents for `SINGLE_USER_ID` |
| `GET /api/documents/{document_id}` | Get document detail |
| `DELETE /api/documents/{document_id}` | Hard-delete document data |
| `POST /api/documents/{document_id}/index` | Internal/development indexing trigger |
| `POST /api/retrieval/search` | Semantic or hybrid retrieval search |
| `POST /api/chat/ask` | Run the full QA agent workflow |
| `GET /api/agent-runs/{agent_run_id}/evidence` | Read verified/rejected evidence from a run |
| `GET /api/agent-runs/{agent_run_id}/logs` | Read persisted Agent 1/2/3 step logs |
| `GET /api/deletion-logs` | Inspect deletion logs |

### Document Upload and Processing

1. `POST /api/documents/upload` receives a multipart file in [backend/app/api/documents.py](backend/app/api/documents.py).
2. [backend/app/services/document_service.py](backend/app/services/document_service.py) validates type and size, stores the original file in Supabase Storage, and inserts document metadata.
3. The route schedules `_process_uploaded_document()` as a FastAPI background task.
4. [backend/app/services/document_processing_service.py](backend/app/services/document_processing_service.py) parses the file, chunks content, stores `document_chunks`, builds graph metadata, and marks status `ready` or `failed`.
5. [backend/app/services/embedding_service.py](backend/app/services/embedding_service.py) embeds chunks through ShopAIKey and upserts vectors to Qdrant.

Supported upload types are PDF, DOCX, TXT, and CSV. Upload validation is implemented in [backend/app/utils/file_validation.py](backend/app/utils/file_validation.py).

### Chat and Agent Workflow

`POST /api/chat/ask` accepts a question, selected `document_ids`, and optional `session_id`.

The workflow in [backend/app/agents/graph.py](backend/app/agents/graph.py) runs:

1. **Agent 1: Retrieval**
   - [backend/app/agents/retrieval_agent.py](backend/app/agents/retrieval_agent.py)
   - Uses hybrid retrieval, semantic retrieval, graph retrieval, scoring, and bounded adjacent context expansion.
2. **Agent 2: Evidence Verification**
   - [backend/app/agents/verification_agent.py](backend/app/agents/verification_agent.py)
   - Verifies candidate membership, exact quote support, requirement-level coverage, missing information, and confidence.
   - Preserves verified chunk source order through `chunk_index` when retrieval candidates provide it.
3. **Agent 3: Answer and Self-Check**
   - [backend/app/agents/answer_agent.py](backend/app/agents/answer_agent.py)
   - Generates the answer from verified evidence only, validates citations, runs claim grounding, and fails safely when evidence is insufficient.
   - Answers supported "Which happened first: A, or B?" questions deterministically from verified `chunk_index` order before calling ShopAIKey.

Run lifecycle and step logs are persisted through [backend/app/services/agent_run_service.py](backend/app/services/agent_run_service.py) and [backend/app/services/agent_log_service.py](backend/app/services/agent_log_service.py).

### Evidence and Agent Logs

The frontend can inspect a run after chat:

- `/evidence/:agentRunId` calls `GET /api/agent-runs/{id}/evidence`.
- `/agent-logs/:agentRunId` calls `GET /api/agent-runs/{id}/logs`.

The logs page renders Agent 1 retrieval candidates, Agent 2 verified/rejected evidence, Agent 3 answer/self-check, and raw input/output JSON.

### Deletion

`DELETE /api/documents/{document_id}` hard-deletes document-related data through [backend/app/services/document_service.py](backend/app/services/document_service.py). Deletion history is exposed by [backend/app/api/deletion_logs.py](backend/app/api/deletion_logs.py).

## Architecture

```text
Frontend React pages
  -> frontend/src/api Axios clients
    -> FastAPI routers in backend/app/api
      -> service layer in backend/app/services
        -> Supabase PostgreSQL / Supabase Storage / Qdrant / ShopAIKey
      -> LangGraph workflow in backend/app/agents/graph.py
        -> Agent 1 retrieval
        -> Agent 2 evidence verification
        -> Agent 3 answer and self-check
```

Important boundaries:

- The frontend never calls Supabase, Qdrant, or ShopAIKey directly.
- Retrieval alone is not trusted as evidence. Agent 2 must verify exact source support.
- Agent 3 receives only verified evidence and must cite exact verified quotes.
- Provider, schema, storage, and persistence failures remain controlled errors instead of being converted into unsupported answers.
- The system is single-user by design through `SINGLE_USER_ID`; there is no JWT/auth system in the MVP.

## Frontend

The frontend is a Vite React TypeScript app.

Routes in [frontend/src/App.tsx](frontend/src/App.tsx):

| Route | Page |
| --- | --- |
| `/upload` | Upload document page |
| `/documents` | Document list page |
| `/chat` | Chat page with document selection, answer, citations, evidence, and logs link |
| `/evidence/:agentRunId` | Direct evidence viewer |
| `/agent-logs` | Agent log lookup |
| `/agent-logs/:agentRunId` | Direct agent log viewer |

API client:

- [frontend/src/api/client.ts](frontend/src/api/client.ts) creates an Axios client using `VITE_API_BASE_URL`.
- [frontend/src/api/documents.ts](frontend/src/api/documents.ts) handles document upload/list/detail/delete calls.
- [frontend/src/api/chat.ts](frontend/src/api/chat.ts) handles chat and evidence calls.
- [frontend/src/api/agentRuns.ts](frontend/src/api/agentRuns.ts) handles agent log calls.

Frontend scripts from [frontend/package.json](frontend/package.json):

```powershell
cd frontend
npm install
npm run dev
npm run build
npm run preview
```

There is currently no frontend test script.

## Backend

The backend is a FastAPI app using Pydantic, Supabase, Qdrant, ShopAIKey, and LangGraph.

Backend setup:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run backend:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Default Uvicorn URL is `http://127.0.0.1:8000`.

Useful checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
python -m pytest -q
```

## Data, Storage, and External Services

| Service | Used For | Main Code |
| --- | --- | --- |
| Supabase PostgreSQL | documents, chunks, graph rows, chat sessions/messages, agent runs/steps, deletion logs | [backend/app/services/supabase_service.py](backend/app/services/supabase_service.py) |
| Supabase Storage | original uploaded files | [backend/app/services/document_service.py](backend/app/services/document_service.py) |
| Qdrant | vector storage and semantic search | [backend/app/services/qdrant_service.py](backend/app/services/qdrant_service.py) |
| ShopAIKey embeddings | chunk embeddings | [backend/app/services/embedding_service.py](backend/app/services/embedding_service.py) |
| ShopAIKey chat completions | entity extraction, evidence verification, answer generation, self-check | [backend/app/services/shopaikey_service.py](backend/app/services/shopaikey_service.py) |
| LangGraph | Agent 1 -> Agent 2 -> Agent 3 workflow | [backend/app/agents/graph.py](backend/app/agents/graph.py) |

Migrations:

- [backend/app/db/migrations/001_initial_schema.sql](backend/app/db/migrations/001_initial_schema.sql)
- [backend/app/db/migrations/002_document_hard_delete.sql](backend/app/db/migrations/002_document_hard_delete.sql)

## Configuration

Backend settings are loaded from `backend/.env`. Do not commit real secret values.

| Variable | Required | Purpose |
| --- | --- | --- |
| `APP_ENV` | No | Environment label returned by health endpoint |
| `SINGLE_USER_ID` | No | Single-user ownership scope |
| `FRONTEND_ORIGIN` | No | Allowed CORS origin |
| `SUPABASE_URL` | Yes for Supabase operations | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes for Supabase operations | Backend-only Supabase service key |
| `SUPABASE_STORAGE_BUCKET` | No | Storage bucket for source documents |
| `SHOPAIKEY_API_KEY` | Yes for model calls | Backend-only ShopAIKey key |
| `SHOPAIKEY_BASE_URL` | Yes for model calls | OpenAI-compatible ShopAIKey base URL |
| `SHOPAIKEY_CHAT_MODEL` | Yes for chat completions | LLM model for agents/extraction |
| `SHOPAIKEY_EMBEDDING_MODEL` | Yes for embeddings | Embedding model for indexing/search |
| `SHOPAIKEY_RERANK_MODEL` | Only if rerank enabled | Rerank model name |
| `QDRANT_URL` | Yes for vector operations | Qdrant cluster URL |
| `QDRANT_API_KEY` | Yes for vector operations | Backend-only Qdrant key |
| `QDRANT_COLLECTION` | Yes for vector operations | Collection name |
| `GRAPH_EXTRACTION_ENABLED` | No | Enables graph extraction during processing |
| `RETRIEVAL_SEMANTIC_TOP_K` | No | Semantic retrieval breadth |
| `RETRIEVAL_GRAPH_TOP_K` | No | Graph retrieval breadth |
| `RETRIEVAL_FINAL_TOP_K` | No | Final hybrid retrieval result count |
| `RETRIEVAL_CONTEXT_WINDOW` | No | Adjacent chunk window around retrieval anchors |
| `RETRIEVAL_CONTEXT_MAX_CANDIDATES` | No | Max adjacent context candidates |
| `RETRIEVAL_MIN_FINAL_SCORE` | No | Minimum final score for returned hybrid retrieval candidates |
| `RETRIEVAL_CONTEXT_MIN_PARENT_SCORE` | No | Minimum parent candidate score required for adjacent context expansion |
| `AGENT_EVIDENCE_SNIPPET_MAX_CHARS` | No | Max compact evidence snippet size sent to Agent 2 |
| `AGENT_EVIDENCE_SNIPPET_CONTEXT_SENTENCES` | No | Neighbor sentence count for compact snippets |
| `AGENT_VERIFICATION_MAX_CANDIDATES` | No | Candidate cap for Agent 2 verification prompt |
| `AGENT_COVERAGE_MAX_CANDIDATES` | No | Candidate cap for Agent 2 coverage prompt |
| `AGENT_LLM_PAYLOAD_WARN_CHARS` | No | Warning threshold for LLM payload diagnostics |
| `ENABLE_RERANK` | No | Enables rerank path; guarded if model is missing |
| `MAX_UPLOAD_BYTES` | No | Upload size limit |
| `CHUNK_SIZE_TOKENS` | No | Chunk size for processing |
| `CHUNK_OVERLAP_TOKENS` | No | Chunk overlap for processing |

Frontend configuration:

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Yes | Backend API base URL, usually `http://localhost:8000` |

## Setup

1. Install backend dependencies:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create `backend/.env` from [backend/.env.example](backend/.env.example) and fill real backend-only values.

3. Install frontend dependencies:

```powershell
cd frontend
npm install
```

4. Create frontend env config with:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Use the frontend env file pattern expected by Vite, such as `frontend/.env.local`.

## Running the Project

Backend:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm run dev
```

Expected local URLs:

- Backend: `http://127.0.0.1:8000`
- Frontend: Vite default, usually `http://localhost:5173`

## Testing and Validation

Backend:

```powershell
cd backend
python -m pytest -q
```

Focused backend suites:

```powershell
python -m pytest tests/test_answer_agent.py tests/test_verification_agent.py -q
python -m pytest tests/test_langgraph_workflow.py tests/test_chat_api.py tests/test_agent_runs_api.py -q
python -m pytest tests/test_evidence_payload_optimizer.py tests/test_hybrid_retrieval_service.py tests/test_scoring.py -q
```

Frontend:

```powershell
cd frontend
npm run build
```

No frontend test runner is configured in `frontend/package.json`.

## Agent Evidence Payload Optimizer

Agent 2 used to send many full retrieved chunks to ShopAIKey verification and coverage prompts. That can create large `gpt-4o-mini` input-token usage for ordinary RAG questions.

The optimizer in [backend/app/services/evidence_payload_optimizer.py](backend/app/services/evidence_payload_optimizer.py):

- keeps retrieval broad enough for recall,
- compacts candidate text into generic question-term-ranked sentence windows,
- preserves candidate IDs and metadata,
- never invents text,
- keeps source candidates available for exact quote validation,
- limits Agent 2 verification and coverage payloads through bounded settings.

Relevant settings:

```text
AGENT_EVIDENCE_SNIPPET_MAX_CHARS
AGENT_EVIDENCE_SNIPPET_CONTEXT_SENTENCES
AGENT_VERIFICATION_MAX_CANDIDATES
AGENT_COVERAGE_MAX_CANDIDATES
AGENT_LLM_PAYLOAD_WARN_CHARS
```

Tune these cautiously. Reducing candidates too aggressively can hurt multi-part and cross-chunk questions. Prefer compacting payload text before lowering retrieval breadth.

## Development Notes for AI Agents

Read these first:

1. [docs/plans/Master_Plan.md](docs/plans/Master_Plan.md) for target architecture and constraints.
2. [backend/app/main.py](backend/app/main.py) to see actual mounted routes.
3. [backend/app/core/config.py](backend/app/core/config.py) before changing env behavior.
4. [backend/app/agents/schemas.py](backend/app/agents/schemas.py), [backend/app/agents/prompts.py](backend/app/agents/prompts.py), and [backend/app/agents/graph.py](backend/app/agents/graph.py) before changing agent contracts.
5. [backend/app/services/hybrid_retrieval_service.py](backend/app/services/hybrid_retrieval_service.py), [backend/app/services/retrieval_context_service.py](backend/app/services/retrieval_context_service.py), and [backend/app/services/evidence_payload_optimizer.py](backend/app/services/evidence_payload_optimizer.py) before changing retrieval/cost behavior.
6. [frontend/src/api/](frontend/src/api) and [frontend/src/types/](frontend/src/types) before changing API response shapes.

Coordination rules:

- Do not hardcode answers, quotes, document names, or Alice-specific behavior in production code.
- Keep public chat/evidence/log schemas stable unless the task explicitly changes contracts.
- Agent 3 must not use unverified chunks.
- Rejected evidence must not appear in final answers or citations.
- If you change Pydantic schemas, update tests and frontend types where applicable.
- If you add a router, register it in [backend/app/main.py](backend/app/main.py).
- If you change persistence shape, coordinate SQL migrations, Supabase service helpers, schemas, and tests.
- Do not edit generated/dependency folders: `node_modules/`, `dist/`, `build/`, `.pytest_cache/`, `__pycache__/`, `.venv/`, `venv/`.

Before claiming completion:

- Run backend tests for backend changes.
- Run `npm run build` for frontend changes.
- For agent/retrieval changes, include targeted tests plus full `python -m pytest -q`.
- For live validation, report the `agent_run_id` so logs can be inspected.

## Known Gaps or Unclear Areas

- The project is single-user and does not implement full authentication/JWT.
- Rerank support is guarded but live rerank behavior is not implemented as a normal path.
- External services are required for full live behavior: Supabase, Qdrant, and ShopAIKey.
- Frontend has no automated test script.
- There is no root-level command that starts backend and frontend together.
- Public graph visualization/API behavior remains limited; graph data is primarily used by backend retrieval.
