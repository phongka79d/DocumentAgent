# RagDocument

RagDocument Phase 1 is a personal, single-user document RAG MVP.

This repository is currently through Batch04. The accepted behavior is:

- a FastAPI backend titled `RagDocument API`
- `GET /api/health` returning `{"status": "ok"}`
- a typed settings layer in `backend/app/core/config.py`
- CORS configured from `FRONTEND_ORIGIN`
- an optional `X-Admin-API-Token` gate that is disabled when `ADMIN_API_TOKEN` is empty and enforced when it is set
- a Supabase MVP schema contract in `docs/database/supabase_schema.sql` for `documents`, `document_chunks`, and optional `messages`
- lazy backend service client factories under `backend/app/services/` for Supabase, Qdrant, ShopAIKey, and Jina
- document schemas, SHA-256 upload hashing, and deterministic upload validation for PDF, DOCX, TXT, and Markdown files
- document service functions for listing, lookup, duplicate detection, original-file upload, row creation, and deletion cleanup
- document API routes for upload, list, detail, index, reindex, delete, and chunk inspection under `/api/documents`
- normalized document parsers for PDF, DOCX, TXT, and Markdown under `backend/app/parsing/`
- a parser registry that resolves supported file extensions and MIME types
- a deterministic fixed-token chunker under `backend/app/chunking/` using 500-token chunks, 150-token overlap, and chunk metadata required for ingestion

The current backend uses safe local-development defaults for its settings layer. External service clients are constructed only when their factories are called. Upload route tests use local fakes/mocks; live Supabase, Qdrant, ShopAIKey, and Jina validation still requires real user-provided credentials, and the Supabase SQL and storage bucket must be applied manually before live document workflow validation.

Index and reindex endpoints expose the Batch03 API contract but keep graph execution stubbed until the ingestion graph is implemented. Parser and chunker services are available for that upcoming ingestion graph, but retrieval, chat, frontend UI, and end-to-end workflow validation are not implemented yet.

## Validation

Run the current backend config and service factory checks with:

```bash
cd backend
python -m pytest tests/test_config.py tests/test_hashing.py tests/test_validation.py tests/test_api_documents.py tests/test_parsers.py tests/test_chunker.py -v
```
