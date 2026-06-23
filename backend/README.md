# Backend Local Run

RagDocument backend runs from `backend/` and expects Python 3.12.

## Backend setup

Run these commands from the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

The backend reads its environment from `backend/.env` when present. Keep that file out of version control and use placeholder values only.

## Frontend setup

Run these commands from the repository root:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

The frontend reads `VITE_API_BASE_URL` and defaults to `http://localhost:8000` if it is not set. If you point the frontend at a different backend, set that variable before starting Vite.

If you use the exact frontend host above (`127.0.0.1`), set `FRONTEND_ORIGIN=http://127.0.0.1:5173` in the backend environment so CORS matches. The plan default `http://localhost:5173` also works if you run Vite on `localhost` instead.

## Required external setup for live E2E

- For a fresh project, run `docs/database/supabase_schema.sql` in Supabase.
- For an existing Phase 2 project, back up the Supabase database first, confirm you are using the intended project, then run `docs/database/phase3_migration.sql` with an authorized service role or SQL editor session. Do not paste service keys into chat, reports, frontend code, or committed files.
- Create a Supabase Storage bucket named `documents`.
- Create Qdrant collection `document_chunks_v1` with the embedding dimension returned by the configured ShopAIKey embedding model.
- Set the backend environment variables from Master Plan section 22 in `backend/.env` or your shell.
- Keep `ADMIN_API_TOKEN` empty for local-only use, or set it to a long random value and send it as `X-Admin-API-Token` on protected requests.

After applying Phase 3 SQL, reindex existing documents with `POST /api/documents/{document_id}/reindex`. Existing vectors and chunks do not have the new MIME payloads, summaries, relations, and Phase 3 metadata until reindexing completes.

Live end-to-end validation stays blocked until the schema, bucket, collection, reindex scope, and real API keys are in place.

## Phase 2 behavior

The backend now supports the Phase 2 settings and parser behavior documented in the master plan.

- `CHUNKING_STRATEGY=smart_section` is the default. It uses detected headings and table boundaries to write `heading` and `section_path` metadata. `CHUNKING_STRATEGY=fixed_token` preserves the Phase 1 chunking path.
- `HEADER_SCORE_THRESHOLD=4` controls when paragraph-like blocks are promoted to headings during smart section chunking.
- `TABLE_CHUNK_MAX_TOKENS=500` keeps small tables intact and lets larger tables fall back to fixed-token splitting.
- `RETRIEVAL_CONTEXT_MODE=section_aware` is the default retrieval mode. `RETRIEVAL_CONTEXT_MODE=neighbor` keeps the older same-document neighbor expansion.
- `RETRIEVAL_SECTION_SIBLING_WINDOW=1` controls how many same-section neighbors are preferred on each side before generic neighbors are added.
- HTML uploads are supported for `.html` and `.htm` files with `text/html`. The parser keeps visible headings, paragraphs, lists, blockquotes, code, and tables, and ignores scripts, styles, and other hidden elements.
- Existing documents indexed before smart section chunking was enabled should be re-indexed so their stored chunks and source citations gain the new heading metadata.

## Backend environment variables

The settings layer keeps backend-only values out of the frontend bundle. Use placeholder values only in local files.

Phase 2 settings:

- `CHUNKING_STRATEGY`: `fixed_token` or `smart_section`. The default is `smart_section`.
- `HEADER_SCORE_THRESHOLD`: integer threshold used by smart section heading scoring. The default is `4`.
- `TABLE_CHUNK_MAX_TOKENS`: maximum size for keeping a table intact before splitting. The default is `500`.
- `RETRIEVAL_CONTEXT_MODE`: `section_aware` or `neighbor`. The default is `section_aware`.
- `RETRIEVAL_SECTION_SIBLING_WINDOW`: number of adjacent chunks to prefer within the same section. The default is `1`.

Phase 3 settings:

| Setting | Default | Purpose |
|---|---:|---|
| `ENABLE_KEYWORD_SEARCH` | `true` | Enables Postgres keyword retrieval inside hybrid search. |
| `RETRIEVAL_KEYWORD_TOP_K` | `40` | Maximum keyword candidates requested from the RPC. |
| `RETRIEVAL_FUSION_TOP_K` | `40` | Maximum fused candidates kept after RRF. |
| `RETRIEVAL_RRF_CONSTANT` | `60` | Reciprocal-rank fusion constant. |
| `RETRIEVAL_RERANK_CANDIDATE_TOP_K` | `20` | Maximum candidates sent to Jina. |
| `RETRIEVAL_CONTEXT_MAX_TOKENS` | `4000` | Prompt context token budget. |
| `QUERY_MAX_SUBQUERIES` | `4` | Maximum planned subqueries. |
| `QUERY_PLANNER_TEMPERATURE` | `0.0` | Planner model temperature. |
| `QUERY_PLANNER_MAX_TOKENS` | `500` | Planner response cap. |
| `ENABLE_SUMMARIES` | `true` | Enables extracted-text-only section and document summaries during indexing. |
| `SUMMARY_SECTION_MAX_TOKENS` | `200` | Section-summary generation cap. |
| `SUMMARY_DOCUMENT_MAX_TOKENS` | `400` | Document-summary generation cap. |
| `ENABLE_RELATION_RETRIEVAL` | `true` | Enables bounded relation generation and relation-aware retrieval. |
| `RELATION_MAX_RELATED_DOCUMENTS` | `5` | Maximum one-hop related documents considered. |
| `GROUNDING_MIN_SCORE` | `0.80` | Minimum verifier score for returning a factual answer. |
| `GROUNDING_MAX_REGENERATIONS` | `1` | Maximum answer regeneration attempts after verification failure. |
| `WORKFLOW_MAX_ATTEMPTS` | `3` | Retry attempts for retryable provider/storage/database/vector operations. |
| `WORKFLOW_RETRY_BASE_DELAY_SECONDS` | `0.25` | Initial retry delay. |
| `WORKFLOW_RETRY_MAX_DELAY_SECONDS` | `2.0` | Maximum retry delay. |
| `ENABLE_WORKFLOW_TRACING` | `true` | Enables compact redacted workflow trace persistence. |

```env
APP_ENV=development
FRONTEND_ORIGIN=http://localhost:5173
ADMIN_API_TOKEN=change-this-long-random-secret

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
SUPABASE_STORAGE_BUCKET=documents

SHOPAIKEY_API_KEY=your-key
SHOPAIKEY_BASE_URL=https://api.shopaikey.com/v1
SHOPAIKEY_CHAT_MODEL=gpt-5-mini
SHOPAIKEY_EMBEDDING_MODEL=text-embedding-3-small

QDRANT_URL=https://your-cluster-url.cloud.qdrant.io
QDRANT_API_KEY=your-qdrant-key
QDRANT_COLLECTION=document_chunks_v1

ENABLE_RERANK=true
JINA_API_KEY=your-jina-key
JINA_RERANK_MODEL=jina-reranker-v2-base-multilingual

RETRIEVAL_SEMANTIC_TOP_K=40
RETRIEVAL_FINAL_TOP_K=5
RETRIEVAL_CONTEXT_WINDOW=1
RETRIEVAL_CONTEXT_MAX_CANDIDATES=8

CHUNK_SIZE_TOKENS=500
CHUNK_OVERLAP_TOKENS=150

MAX_UPLOAD_BYTES=25000000
TEMPERATURE=0.2
MAX_OUTPUT_TOKENS=1200
```

Add these Phase 3 values when overriding defaults:

```env
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

## Phase 3 query and trace architecture

```mermaid
flowchart TD
    A[POST /api/chat] --> B[Create workflow run when tracing is enabled]
    B --> C[Validate question, document allow-list, and filters]
    C --> D[Bounded query plan, max QUERY_MAX_SUBQUERIES]
    D --> E[Resolve one-hop relation scope without widening explicit document_ids]
    E --> F[Parallel semantic Qdrant and keyword Postgres retrieval]
    F --> G[Normalize candidates and dedupe by chunk_id]
    G --> H[RRF fusion with constant RETRIEVAL_RRF_CONSTANT]
    H --> I[Jina rerank up to RETRIEVAL_RERANK_CANDIDATE_TOP_K]
    I --> J[Fallback to deterministic fused ordering if Jina fails or is disabled]
    J --> K[Context budget: top chunks, boundaries, same-section neighbors, generic neighbors]
    K --> L[Generate answer with S1/S2 citation keys]
    L --> M[Validate citations against exact context]
    M --> N[Grounding verifier]
    N --> O{Passes?}
    O -->|yes| P[Return answer, cited sources, optional trace_id]
    O -->|first failure| Q[Regenerate once with compact feedback]
    Q --> M
    O -->|exhausted| R[Safe insufficient-context response with no sources]
    P --> S[Close workflow run]
    R --> S
```

Trace events store node names, status, attempts, timings, providers, counts, routes, fallbacks, safe error codes, retrieval totals, citation validity, and grounding score. They must not store raw chunk text, parsed text, prompts, full model responses, full generated answers, authorization headers, API keys, or credential-bearing URLs.

## Phase 3 API endpoints

All API paths are prefixed with `/api`.

| Method | Endpoint | Notes |
|---|---|---|
| `GET` | `/documents/{document_id}/summaries` | Lists stored section and document summaries through the documents router; no route-level admin-token dependency is currently applied. |
| `GET` | `/documents/{document_id}/relations` | Lists bounded canonical relations for the document through the documents router; no route-level admin-token dependency is currently applied. |
| `GET` | `/observability/runs?workflow_type=&status=&limit=50` | Requires `X-Admin-API-Token`; limit is clamped to `1..100`; newest first. |
| `GET` | `/observability/runs/{run_id}` | Requires `X-Admin-API-Token`; returns `404` for missing runs. |

When `ADMIN_API_TOKEN` is empty, the application is suitable only for local/private single-user operation. When it is set, observability requests must include `X-Admin-API-Token: <token>`. The summary and relation inspection endpoints currently follow the same exposure as the rest of the documents router.

## Operations

Existing-project upgrade:

1. Back up the Supabase project and confirm the target project.
2. Apply `docs/database/phase3_migration.sql` once through an authorized SQL path.
3. Confirm the `documents.error_code` column, `document_summaries`, `document_relations`, `workflow_runs`, keyword index, and `search_document_chunks_keyword` RPC exist.
4. Reindex existing documents with `POST /api/documents/{document_id}/reindex` so Qdrant MIME payloads, summaries, relations, and metadata are rebuilt.
5. Inspect `/api/documents/{document_id}/summaries`, `/api/documents/{document_id}/relations`, and `/api/observability/runs`.

Fresh setup:

1. Run `docs/database/supabase_schema.sql`.
2. Create the private Supabase Storage bucket and Qdrant collection.
3. Configure backend secrets in `backend/.env`.
4. Upload documents, then index or reindex through the API/UI.

Retryable failures are limited to timeouts, connection failures, HTTP 429, and HTTP 5xx. Validation errors, unsupported files, missing documents, contract errors, and non-retryable 4xx failures run once. Final fallbacks are deterministic: planner failure becomes one original-question hybrid/semantic plan; single retrieval-path failure uses the surviving path; relation failure returns to normal scoped hybrid retrieval; Jina failure uses fused ordering; grounding failure regenerates once and then returns the safe insufficient-context response; message and trace persistence failures log warnings without changing a valid answer.

## Evaluation commands

Dataset validation is local:

```powershell
cd backend
python -m app.evaluation.dataset evaluation/datasets/phase3_v1.jsonl
```

Live seeding and evaluation require configured Supabase, Qdrant, ShopAIKey, and Jina credentials:

```powershell
cd backend
python scripts/seed_evaluation_corpus.py
python scripts/run_rag_evaluation.py --dataset evaluation/datasets/phase3_v1.jsonl
```

Default evaluation gates are `recall_at_5 >= 0.80`, `citation_validity_rate = 1.00`, `grounding_pass_rate >= 0.90`, `unexpected_no_result_rate <= 0.10`, and `forbidden_term_rate = 0.00`. Reports are timestamped JSON files under `backend/evaluation/results/`.

## Limits and security

RagDocument remains a personal single-user system. It does not implement login, signup, OAuth, Supabase Auth, users, organizations, roles, tenants, or access-control tables. Keep it local/private or protect a deployment with `ADMIN_API_TOKEN`, Cloudflare Access, Tailscale, or a private VPN.

Only extractable text is supported. OCR, scanned PDFs, screenshots, image-only documents, image/chart captioning, audio/video extraction, and PPTX parsing are out of scope. Empty extracted text fails with `NO_EXTRACTABLE_TEXT`.

