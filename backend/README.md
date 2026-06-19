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

## Backend environment variables

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

