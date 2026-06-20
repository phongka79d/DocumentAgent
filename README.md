# RagDocument

RagDocument is a personal, single-user document RAG app.

This repository currently reflects the Phase 2 Batch05 implementation. The accepted behavior is:

- a FastAPI backend titled `RagDocument API`
- `GET /api/health` returning `{"status": "ok"}`
- a typed settings layer in `backend/app/core/config.py`
- CORS configured from `FRONTEND_ORIGIN`
- an optional `X-Admin-API-Token` gate that is disabled when `ADMIN_API_TOKEN` is empty and enforced when it is set
- a Supabase MVP schema contract in `docs/database/supabase_schema.sql` for `documents`, `document_chunks`, and optional `messages`
- lazy backend service client factories under `backend/app/services/` for Supabase, Qdrant, ShopAIKey, and Jina
- document schemas, SHA-256 upload hashing, and deterministic upload validation for PDF, DOCX, TXT, Markdown, and HTML files
- document service functions for listing, lookup, duplicate detection, original-file upload, row creation, and deletion cleanup
- document API routes for upload, list, detail, index, reindex, delete, and typed chunk inspection under `/api/documents`
- normalized document parsers for PDF, DOCX, TXT, Markdown, and HTML under `backend/app/parsing/`, with optional structured block output for paragraphs, headings, tables, and visible HTML blocks
- a parser registry that resolves supported file extensions and MIME types, including `text/html`
- deterministic heading scoring and chunkers under `backend/app/chunking/`, including fixed-token chunking plus smart section chunking with heading/section-path metadata, table preservation, and fixed-token fallback
- chunking settings for `CHUNKING_STRATEGY`, `HEADER_SCORE_THRESHOLD`, `TABLE_CHUNK_MAX_TOKENS`, `CHUNK_SIZE_TOKENS`, and `CHUNK_OVERLAP_TOKENS`
- retrieval context settings for `RETRIEVAL_CONTEXT_MODE` and `RETRIEVAL_SECTION_SIBLING_WINDOW`
- a LangGraph ingestion workflow under `backend/app/graphs/` that loads existing document rows, marks processing, parses, selects the configured chunking strategy, saves chunks, embeds, upserts Qdrant vectors with section metadata, marks ready, and marks fatal failures as failed with clear errors
- index and reindex document routes that invoke the ingestion graph with only the document ID; reindex deletes old Qdrant vectors and old Supabase chunks before rebuilding
- existing documents should be re-indexed after smart section chunking is enabled so stored chunks and source citations receive `heading` and `section_path` metadata
- retrieval helpers that embed questions, query Qdrant with optional document filters, rerank with Jina, fall back to Qdrant scores, and expand neighboring chunks with section-aware same-section preference, boundary hints, deduplication, and context caps
- a LangGraph query workflow under `backend/app/graphs/` that validates questions, retrieves context, reranks, expands neighbors, generates grounded answers with source citations, includes optional section path, content preview, and neighbor-context metadata, and optionally saves messages without failing chat responses
- a `POST /api/chat` route that accepts `question`, optional `document_ids`, and `save_message`, invokes the query graph, and returns `answer` plus `sources`
- a `GET /api/messages` route that returns saved Q&A history from the optional `messages` table, newest first, with bounded limits and safe error responses
- a React Vite TypeScript frontend under `frontend/` that reads `VITE_API_BASE_URL`, keeps backend service secrets out of browser code, and builds with `npm run build`
- a typed frontend API client for upload, list, detail, index, reindex, delete, chat, document chunk inspection, and message history requests, with `X-Admin-API-Token` sent only when configured in browser session state
- browser UI for uploading PDF, DOCX, TXT, and Markdown files, listing documents, refreshing document state, indexing, re-indexing, deleting, and showing failed-document errors
- browser chat UI with optional ready-document selection, answer rendering, selectable richer source citations, source chunk inspection with adjacent chunk navigation, and source citations in the required page-present and page-absent formats
- browser message history UI that loads saved Q&A rows, supports refresh, and restores saved answers and sources into the chat response area without resending the question
- local run documentation in `backend/README.md` covering backend, frontend, Supabase, Qdrant, and required environment setup
- live MVP smoke validation for a TXT document covering upload, duplicate upload, indexing to ready, chat with source citation, delete, and disappearance from the document list

The current backend uses safe local-development defaults for its settings layer. External service clients are constructed only when their factories are called. Upload route tests use local fakes/mocks; live Supabase, Qdrant, ShopAIKey, and Jina validation still requires real user-provided credentials, and the Supabase SQL and storage bucket must be applied manually before live document workflow validation.

Index and reindex endpoints run the ingestion graph against stored originals. Retrieval and chat are implemented with mock-backed tests. The frontend is implemented and build-validated; the Batch08 live smoke test passed against configured external services after the Supabase schema/storage and Qdrant setup were in place.

## Validation

Run the current backend checks with:

```bash
cd backend
python -m pytest tests/test_config.py tests/test_hashing.py tests/test_validation.py tests/test_api_documents.py tests/test_api_messages.py tests/test_parsers.py tests/test_heading_detection.py tests/test_chunker.py tests/test_ingestion_graph.py tests/test_query_graph.py tests/test_api_chat.py -v
```

Run the current frontend build check with:

```bash
cd frontend
npm run build
```
