# RagDocument

RagDocument Phase 1 is a personal, single-user document RAG MVP.

This repository is currently through Batch02. The accepted behavior is:

- a FastAPI backend titled `RagDocument API`
- `GET /api/health` returning `{"status": "ok"}`
- a typed settings layer in `backend/app/core/config.py`
- CORS configured from `FRONTEND_ORIGIN`
- an optional `X-Admin-API-Token` gate that is disabled when `ADMIN_API_TOKEN` is empty and enforced when it is set
- a Supabase MVP schema contract in `docs/database/supabase_schema.sql` for `documents`, `document_chunks`, and optional `messages`
- lazy backend service client factories under `backend/app/services/` for Supabase, Qdrant, ShopAIKey, and Jina

The current backend uses safe local-development defaults for its settings layer. External service clients are constructed only when their factories are called. Live Supabase, Qdrant, ShopAIKey, and Jina validation still requires real user-provided credentials, and the Supabase SQL must be applied manually before live database validation.

It does not implement upload, indexing, retrieval, chat, frontend UI, or end-to-end workflow validation yet.

## Validation

Run the current backend config and service factory checks with:

```bash
cd backend
python -m pytest tests/test_config.py -v
```
