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

- Run `docs/database/supabase_schema.sql` in Supabase.
- Create a Supabase Storage bucket named `documents`.
- Create Qdrant collection `document_chunks_v1` with the embedding dimension returned by the configured ShopAIKey embedding model.
- Set the backend environment variables from Master Plan section 22 in `backend/.env` or your shell.
- Keep `ADMIN_API_TOKEN` empty for local-only use, or set it to a long random value and send it as `X-Admin-API-Token` on protected requests.

Live end-to-end validation stays blocked until the schema, bucket, collection, and real API keys are in place.

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

