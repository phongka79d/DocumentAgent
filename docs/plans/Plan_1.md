# RagDocument Phase 1 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Depends on:** `docs/plans/Master_Plan.md`  
**Master Plan Version:** MVP v1.1  
**Scope:** Phase 1 only: Minimal Useful RAG with LangGraph  
**Goal:** Build a personal single-user document RAG MVP with upload, indexing, retrieval, reranking, grounded answers, and source citations.

**Architecture:** A React Vite frontend talks to a FastAPI backend. The backend owns secrets, Supabase Storage/Postgres access, Qdrant vector operations, ShopAIKey embedding/chat calls, Jina reranking, and deterministic LangGraph ingestion/query graphs.

**Tech Stack:** React, Vite, TypeScript, FastAPI, Pydantic, LangGraph, Supabase, Qdrant Cloud, ShopAIKey OpenAI-compatible API, Jina Reranker API, pytest.

---

## Master Plan Contract

This plan must stay aligned with `docs/plans/Master_Plan.md`.

Implement these Master Plan sections in Phase 1:

- Section 6: Upload Flow
- Section 7: Indexing Flow
- Section 8: LangGraph Ingestion Graph
- Section 9: MVP Query Flow
- Section 10: LangGraph Query Graph
- Section 11: Retrieval Configuration
- Section 12: Optional Document Filtering in Chat
- Section 13: Neighbor Context Expansion
- Section 14: Supabase Storage Design
- Section 15: Supabase Postgres Schema
- Section 16: Qdrant Collection and Payload
- Section 17: Chunking
- Section 21.1: Required MVP Endpoints
- Section 22: Environment values
- Section 23: Error Handling
- Section 25: Answer Prompt
- Section 26: Source Citation Format
- Section 29: Final MVP Checklist items that belong to Phase 1

Exclude these Master Plan features from Phase 1:

- Authentication, login, signup, OAuth, user profiles, organizations, roles, tenant isolation
- Query decomposition, query classification, relation extraction, relation graph expansion
- OCR, PPTX parsing, image/chart captioning, hybrid search, summaries, multi-vector chunks
- Autonomous agents, multi-agent workflows, complex planning loops

---

## Target File Structure

Create this structure during implementation:

```text
backend/
  pyproject.toml
  README.md
  app/
    __init__.py
    main.py
    core/
      __init__.py
      config.py
      errors.py
      security.py
    api/
      __init__.py
      routes/
        __init__.py
        documents.py
        chat.py
        health.py
    models/
      __init__.py
      schemas.py
    services/
      __init__.py
      hashing.py
      validation.py
      supabase_client.py
      qdrant_client.py
      shopaikey_client.py
      jina_client.py
      documents.py
      chunks.py
      retrieval.py
    parsing/
      __init__.py
      base.py
      pdf.py
      docx.py
      text.py
      markdown.py
      registry.py
    chunking/
      __init__.py
      token_chunker.py
    graphs/
      __init__.py
      ingestion_state.py
      ingestion_nodes.py
      ingestion_graph.py
      query_state.py
      query_nodes.py
      query_graph.py
  tests/
    conftest.py
    test_config.py
    test_validation.py
    test_hashing.py
    test_chunker.py
    test_parsers.py
    test_ingestion_graph.py
    test_query_graph.py
    test_api_documents.py
    test_api_chat.py
frontend/
  package.json
  index.html
  vite.config.ts
  tsconfig.json
  src/
    main.tsx
    App.tsx
    api/client.ts
    api/types.ts
    components/
      DocumentList.tsx
      UploadPanel.tsx
      ChatPanel.tsx
      SourceList.tsx
    styles.css
docs/
  database/
    supabase_schema.sql
  plans/
    Master_Plan.md
    Plan_1.md
```

---

## Batch 1: Backend Foundation

### Task 1.1: Initialize FastAPI backend package

**Files:**

- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_config.py`

- [ ] Create backend dependencies in `backend/pyproject.toml`.

Required runtime dependencies:

```text
fastapi
uvicorn
pydantic
pydantic-settings
python-multipart
httpx
supabase
qdrant-client
langgraph
openai
jina
pymupdf
python-docx
tiktoken
python-dotenv
```

Required test dependencies:

```text
pytest
pytest-asyncio
respx
```

- [ ] Create FastAPI app in `backend/app/main.py` with `/api/health`.

Required behavior:

```text
GET /api/health returns {"status": "ok"}.
Application title is "RagDocument API".
CORS allows FRONTEND_ORIGIN from settings.
Documents and chat routers are included under /api.
```

- [ ] Add first backend verification.

Run:

```powershell
cd backend
python -m pytest tests/test_config.py -v
```

Expected:

```text
1 or more tests pass.
```

### Task 1.2: Add settings and optional admin token gate

**Files:**

- Create: `backend/app/core/config.py`
- Create: `backend/app/core/security.py`
- Create: `backend/app/core/errors.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_config.py`

- [ ] Implement `Settings` with these fields:

```text
APP_ENV
FRONTEND_ORIGIN
ADMIN_API_TOKEN
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_STORAGE_BUCKET
SHOPAIKEY_API_KEY
SHOPAIKEY_BASE_URL
SHOPAIKEY_CHAT_MODEL
SHOPAIKEY_EMBEDDING_MODEL
QDRANT_URL
QDRANT_API_KEY
QDRANT_COLLECTION
ENABLE_RERANK
JINA_API_KEY
JINA_RERANK_MODEL
RETRIEVAL_SEMANTIC_TOP_K
RETRIEVAL_FINAL_TOP_K
RETRIEVAL_CONTEXT_WINDOW
RETRIEVAL_CONTEXT_MAX_CANDIDATES
CHUNK_SIZE_TOKENS
CHUNK_OVERLAP_TOKENS
MAX_UPLOAD_BYTES
TEMPERATURE
MAX_OUTPUT_TOKENS
```

- [ ] Use default values from Master Plan section 22 when values are optional for local development.

- [ ] Implement `require_admin_token` so empty `ADMIN_API_TOKEN` disables the gate and a non-empty token requires `X-Admin-API-Token`.

Verification:

```powershell
cd backend
python -m pytest tests/test_config.py -v
```

Expected:

```text
Settings load.
Admin token dependency accepts empty local token.
Admin token dependency rejects wrong token when configured.
```

---

## Batch 2: Database and Storage Contract

### Task 2.1: Create Supabase schema document

**Files:**

- Create: `docs/database/supabase_schema.sql`

- [ ] Add SQL for `documents`, `document_chunks`, and optional `messages` exactly matching Master Plan section 15.

- [ ] Include these indexes:

```sql
create index idx_documents_status on documents(status);
create index idx_documents_created_at on documents(created_at desc);
create unique index idx_documents_file_hash on documents(file_hash);
create index idx_document_chunks_document_id on document_chunks(document_id);
create unique index idx_document_chunks_doc_index on document_chunks(document_id, chunk_index);
create index idx_document_chunks_qdrant_point_id on document_chunks(qdrant_point_id);
create index idx_messages_created_at on messages(created_at desc);
```

Verification:

```powershell
Get-Content docs/database/supabase_schema.sql
```

Expected:

```text
The file contains only the three MVP tables and their indexes.
No users, profiles, organizations, roles, conversations, or document_relations table exists.
```

### Task 2.2: Add service clients

**Files:**

- Create: `backend/app/services/supabase_client.py`
- Create: `backend/app/services/qdrant_client.py`
- Create: `backend/app/services/shopaikey_client.py`
- Create: `backend/app/services/jina_client.py`
- Create: `backend/tests/test_config.py`

- [ ] Implement lazy client factories that read from `Settings`.

- [ ] Keep service role keys and API keys backend-only.

- [ ] Add tests that monkeypatch settings and verify factories can be constructed without network calls.

Verification:

```powershell
cd backend
python -m pytest tests/test_config.py -v
```

Expected:

```text
Client factory tests pass without contacting Supabase, Qdrant, ShopAIKey, or Jina.
```

---

## Batch 3: Upload and Document APIs

### Task 3.1: Add schemas, hashing, and validation

**Files:**

- Create: `backend/app/models/schemas.py`
- Create: `backend/app/services/hashing.py`
- Create: `backend/app/services/validation.py`
- Create: `backend/tests/test_hashing.py`
- Create: `backend/tests/test_validation.py`

- [ ] Define request/response schemas:

```text
DocumentResponse
DocumentListResponse
UploadDocumentResponse
ChatRequest
ChatResponse
SourceCitation
```

- [ ] Implement SHA-256 file hash calculation over upload bytes.

- [ ] Validate uploads using these rules:

```text
file is not empty
file size <= MAX_UPLOAD_BYTES
extension is one of .pdf, .docx, .txt, .md, .markdown
mime type is accepted when provided
extension and mime type do not obviously conflict
```

Verification:

```powershell
cd backend
python -m pytest tests/test_hashing.py tests/test_validation.py -v
```

Expected:

```text
Hashing is deterministic.
Empty files are rejected.
Oversized files are rejected.
Unsupported extensions are rejected.
PDF, DOCX, TXT, and Markdown names are accepted.
```

### Task 3.2: Implement document service

**Files:**

- Create: `backend/app/services/documents.py`
- Modify: `backend/tests/test_api_documents.py`

- [ ] Implement service functions:

```text
list_documents()
get_document(document_id)
find_document_by_hash(file_hash)
create_uploaded_document(file_name, mime_type, file_size, file_hash, storage_path, title)
upload_original_file(storage_path, bytes, content_type)
delete_document_and_file(document_id)
```

- [ ] Use storage path format:

```text
documents/{document_id}/original/{file_name}
```

- [ ] Preserve duplicate behavior:

```text
If file_hash already exists, return existing document_id, status, and duplicate=true.
Do not upload a second file.
Do not create a second document row.
```

### Task 3.3: Implement document routes

**Files:**

- Create: `backend/app/api/routes/documents.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api_documents.py`

- [ ] Add endpoints:

```text
POST /api/documents/upload
GET /api/documents
GET /api/documents/{document_id}
POST /api/documents/{document_id}/index
POST /api/documents/{document_id}/reindex
DELETE /api/documents/{document_id}
GET /api/documents/{document_id}/chunks
```

- [ ] Keep upload separate from indexing.

- [ ] Return duplicate upload response in this shape:

```json
{
  "document_id": "existing-document-uuid",
  "status": "ready",
  "duplicate": true
}
```

Verification:

```powershell
cd backend
python -m pytest tests/test_api_documents.py -v
```

Expected:

```text
Upload route validates files.
Duplicate upload returns existing document metadata.
Index route invokes ingestion graph with only document_id.
Delete route deletes Qdrant vectors before document row deletion.
```

---

## Batch 4: Parsing and Chunking

### Task 4.1: Add parser interface and registry

**Files:**

- Create: `backend/app/parsing/base.py`
- Create: `backend/app/parsing/pdf.py`
- Create: `backend/app/parsing/docx.py`
- Create: `backend/app/parsing/text.py`
- Create: `backend/app/parsing/markdown.py`
- Create: `backend/app/parsing/registry.py`
- Create: `backend/tests/test_parsers.py`

- [ ] Normalize parser output to:

```python
{
    "text": "full extracted text",
    "pages": [
        {"page_number": 1, "text": "page text"}
    ],
    "metadata": {
        "parser_name": "parser-name",
        "parser_version": "1.0.0"
    }
}
```

- [ ] Implement PDF with PyMuPDF, DOCX with python-docx, TXT with UTF-8 fallback handling, and Markdown as text.

- [ ] Reject parser output with empty extracted text.

Verification:

```powershell
cd backend
python -m pytest tests/test_parsers.py -v
```

Expected:

```text
TXT and Markdown parser tests pass with in-memory bytes.
Registry maps supported extensions and mime types.
Empty extracted text raises a parse error.
```

### Task 4.2: Add fixed token chunker

**Files:**

- Create: `backend/app/chunking/token_chunker.py`
- Create: `backend/tests/test_chunker.py`

- [ ] Implement `BaseChunker` and `FixedTokenChunker`.

- [ ] Use these defaults from settings:

```text
chunk size = 500 tokens
overlap = 150 tokens
step = 350 tokens
```

- [ ] Return chunk objects with:

```text
chunk_index
content
content_hash
token_count
chunk_type
heading
section_path
page_start
page_end
token_start
token_end
```

Verification:

```powershell
cd backend
python -m pytest tests/test_chunker.py -v
```

Expected:

```text
Chunk indexes are sequential.
Overlap is 150 tokens when multiple chunks are produced.
Empty text produces a clear chunking error.
```

---

## Batch 5: LangGraph Ingestion

### Task 5.1: Add ingestion state and nodes

**Files:**

- Create: `backend/app/graphs/ingestion_state.py`
- Create: `backend/app/graphs/ingestion_nodes.py`
- Create: `backend/tests/test_ingestion_graph.py`

- [ ] Define `IngestionState` with fields from Master Plan section 8.2.

- [ ] Do not include these fields:

```text
original_file_bytes
upload_file_path
large binary data
```

- [ ] Implement nodes:

```text
load_document_record_node
mark_processing_node
parse_document_node
chunk_document_node
save_chunks_node
embed_chunks_node
upsert_qdrant_node
mark_ready_node
mark_failed_node
```

- [ ] Ensure `save_chunks_node` runs before `upsert_qdrant_node`.

- [ ] On fatal errors, set:

```text
status = failed
error_message = clear reason
```

### Task 5.2: Build ingestion graph

**Files:**

- Create: `backend/app/graphs/ingestion_graph.py`
- Modify: `backend/app/api/routes/documents.py`
- Modify: `backend/tests/test_ingestion_graph.py`
- Modify: `backend/tests/test_api_documents.py`

- [ ] Compile graph with this flow:

```text
START
-> load_document_record
-> mark_processing
-> parse_document
-> chunk_document
-> save_chunks
-> embed_chunks
-> upsert_qdrant
-> mark_ready
-> END
```

- [ ] Route fatal failures to `mark_failed`.

- [ ] Make `POST /api/documents/{document_id}/index` call the graph with:

```json
{"document_id": "document-uuid"}
```

- [ ] Make `POST /api/documents/{document_id}/reindex` delete old Qdrant vectors and old chunks before graph invocation.

Verification:

```powershell
cd backend
python -m pytest tests/test_ingestion_graph.py tests/test_api_documents.py -v
```

Expected:

```text
Graph invokes nodes in order.
Index route passes only document_id into graph state.
Failed parse marks document failed.
Ready path stores total_chunks, parser metadata, chunking metadata, embedding metadata, qdrant_collection, and indexed_at.
```

---

## Batch 6: Retrieval and Chat Graph

### Task 6.1: Add retrieval service

**Files:**

- Create: `backend/app/services/chunks.py`
- Create: `backend/app/services/retrieval.py`
- Create: `backend/tests/test_query_graph.py`

- [ ] Implement Qdrant retrieval with:

```text
top_k = RETRIEVAL_SEMANTIC_TOP_K
default = 40
```

- [ ] Support optional document filtering:

```text
If document_ids is omitted or empty, search all ready documents.
If document_ids is provided, apply a Qdrant payload filter on document_id.
```

- [ ] Implement Jina rerank with fallback:

```text
If Jina fails and ENABLE_RERANK=true, sort retrieved chunks by Qdrant score.
```

- [ ] Implement neighbor expansion:

```text
Always keep top reranked chunks.
Add previous and next chunks from the same document.
Deduplicate by chunk_id.
Do not exceed RETRIEVAL_CONTEXT_MAX_CANDIDATES.
Prefer reranked chunks before neighbor chunks.
```

Verification:

```powershell
cd backend
python -m pytest tests/test_query_graph.py -v
```

Expected:

```text
Document filters are passed to Qdrant.
Jina failure falls back to Qdrant scores.
Neighbor expansion caps context at 8 chunks by default.
Duplicate neighbor chunks are removed.
```

### Task 6.2: Add query state, nodes, and graph

**Files:**

- Create: `backend/app/graphs/query_state.py`
- Create: `backend/app/graphs/query_nodes.py`
- Create: `backend/app/graphs/query_graph.py`
- Modify: `backend/tests/test_query_graph.py`

- [ ] Define `QueryState` with fields from Master Plan section 10.2.

- [ ] Implement nodes:

```text
prepare_query_node
retrieve_qdrant_node
jina_rerank_node
expand_neighbor_context_node
generate_answer_node
save_message_optional_node
```

- [ ] Use this answer system prompt:

```text
You are a personal document RAG assistant.

Rules:
- Answer using only the provided context.
- If the context does not contain enough information, say that the indexed documents do not contain enough information.
- Do not invent facts.
- Do not invent sources.
- Cite the source chunks used in the answer.
- Keep the answer clear and practical.
```

- [ ] Return source citations with:

```text
document_id
chunk_id
file_name
chunk_index
page_start
page_end
heading
qdrant_score
rerank_score
```

Verification:

```powershell
cd backend
python -m pytest tests/test_query_graph.py -v
```

Expected:

```text
Empty question returns validation error.
No retrieved chunks returns "No relevant information found in indexed documents."
Answer generation receives only retrieved context.
Sources are returned for grounded answers.
Message saving failure does not fail chat response.
```

### Task 6.3: Add chat route

**Files:**

- Create: `backend/app/api/routes/chat.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_chat.py`

- [ ] Add endpoint:

```text
POST /api/chat
```

- [ ] Accept request:

```json
{
  "question": "What does this document say about pricing?",
  "document_ids": ["uuid-1", "uuid-2"],
  "save_message": true
}
```

- [ ] Return response:

```json
{
  "answer": "The document states that pricing is based on usage tiers.",
  "sources": [
    {
      "document_id": "uuid-1",
      "chunk_id": "chunk-uuid",
      "file_name": "pricing.pdf",
      "chunk_index": 12,
      "page_start": 3,
      "page_end": 4,
      "heading": null,
      "qdrant_score": 0.78,
      "rerank_score": 0.91
    }
  ]
}
```

Verification:

```powershell
cd backend
python -m pytest tests/test_api_chat.py tests/test_query_graph.py -v
```

Expected:

```text
Chat route invokes query graph.
document_ids is optional.
save_message defaults to false.
Response contains answer and sources.
```

---

## Batch 7: Frontend MVP

### Task 7.1: Initialize React Vite frontend

**Files:**

- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`

- [ ] Use React with TypeScript.

- [ ] Set API base URL from:

```text
VITE_API_BASE_URL
```

- [ ] Keep secrets out of frontend files.

Verification:

```powershell
cd frontend
npm install
npm run build
```

Expected:

```text
Vite build completes.
No Supabase, Qdrant, ShopAIKey, or Jina secret appears in frontend source.
```

### Task 7.2: Add API client and types

**Files:**

- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`

- [ ] Implement functions:

```text
uploadDocument(file)
listDocuments()
getDocument(documentId)
indexDocument(documentId)
reindexDocument(documentId)
deleteDocument(documentId)
sendChatMessage(request)
```

- [ ] Include `X-Admin-API-Token` only when configured by the user in the browser session.

### Task 7.3: Build upload and document list UI

**Files:**

- Create: `frontend/src/components/UploadPanel.tsx`
- Create: `frontend/src/components/DocumentList.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] Show upload control for PDF, DOCX, TXT, and Markdown.

- [ ] Show document rows with:

```text
file_name
status
total_chunks
created_at
indexed_at
error_message when failed
```

- [ ] Add actions:

```text
Index
Re-index
Delete
Refresh
```

Verification:

```powershell
cd frontend
npm run build
```

Expected:

```text
Build passes.
Document list renders empty state without crashing.
```

### Task 7.4: Build chat and sources UI

**Files:**

- Create: `frontend/src/components/ChatPanel.tsx`
- Create: `frontend/src/components/SourceList.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] Allow question entry.

- [ ] Allow optional selected documents.

- [ ] Show answer text.

- [ ] Show sources as:

```text
Source 1: report.pdf, chunk 12, pages 3-4
```

- [ ] If page numbers are unavailable, show:

```text
Source 1: report.pdf, chunk 12
```

Verification:

```powershell
cd frontend
npm run build
```

Expected:

```text
Build passes.
Answer and citation components render from mock data.
```

---

## Batch 8: End-to-End Verification

### Task 8.1: Add local run documentation

**Files:**

- Create: `backend/README.md`
- Modify: `docs/plans/Plan_1.md` only when implementation discoveries change task commands or paths.

- [ ] Document local backend commands:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

- [ ] Document local frontend commands:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

- [ ] Document required external setup:

```text
Run docs/database/supabase_schema.sql in Supabase.
Create Supabase Storage bucket named documents.
Create Qdrant collection document_chunks_v1 with the embedding dimension returned by ShopAIKey.
Set backend environment variables from Master Plan section 22.
```

### Task 8.2: Run full automated verification

**Files:**

- No new files.

- [ ] Run backend tests:

```powershell
cd backend
python -m pytest -v
```

Expected:

```text
All backend tests pass.
```

- [ ] Run frontend build:

```powershell
cd frontend
npm run build
```

Expected:

```text
Frontend production build passes.
```

### Task 8.3: Run manual MVP smoke test

**Files:**

- No new files.

- [ ] Start backend:

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

- [ ] Start frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

- [ ] Verify these browser flows:

```text
Open http://127.0.0.1:5173.
Upload a TXT file.
Confirm duplicate upload returns the existing document.
Index the uploaded document.
Confirm document status becomes ready.
Ask a question that is answered by the document.
Confirm answer includes at least one source citation.
Delete the document.
Confirm document no longer appears in the list.
```

Expected:

```text
The app completes the upload, index, chat, cite, and delete flow for a TXT document.
```

---

## Phase 1 Acceptance Criteria

- [ ] Upload and indexing are separate.
- [ ] Upload validates file size, file type, empty files, and computes `file_hash`.
- [ ] Duplicate upload returns existing `document_id` and does not create duplicate rows, files, chunks, or vectors.
- [ ] Original file is stored in Supabase Storage under `documents/{document_id}/original/{file_name}`.
- [ ] Document row is created with `status = uploaded`.
- [ ] Index endpoint starts LangGraph ingestion graph from an existing document row.
- [ ] Ingestion graph state does not carry large binary file data.
- [ ] Document is marked `processing` during indexing.
- [ ] PDF, DOCX, TXT, and Markdown parsing work.
- [ ] Fixed token chunking uses 500 tokens and 150 overlap.
- [ ] Chunks are saved in Supabase before vectors are upserted.
- [ ] Embeddings are generated through ShopAIKey.
- [ ] Qdrant vectors are upserted with required payload fields.
- [ ] Document is marked `ready` after successful indexing.
- [ ] Fatal ingestion errors mark document as `failed` with clear `error_message`.
- [ ] Chat endpoint supports optional `document_ids`.
- [ ] Query graph embeds the question.
- [ ] Qdrant retrieves Top 40 candidates.
- [ ] Qdrant filtering by document ID works.
- [ ] Jina reranks to Top 5.
- [ ] Jina failure falls back to Qdrant score sorting.
- [ ] Neighbor expansion can add chunks up to max context 8.
- [ ] Answer uses only retrieved context.
- [ ] Answer returns source citations.
- [ ] Delete endpoint removes Qdrant vectors, original file, document row, and chunks.
- [ ] Re-index endpoint rebuilds chunks and vectors from the original file.
- [ ] No authentication, multi-user, tenant, relation graph, OCR, PPTX, hybrid search, or autonomous-agent features are introduced.

---

## Execution Order

Implement batches in order:

```text
Batch 1 -> Batch 2 -> Batch 3 -> Batch 4 -> Batch 5 -> Batch 6 -> Batch 7 -> Batch 8
```

Create a small commit after each batch:

```text
feat: add backend foundation
feat: add database and external clients
feat: add document upload APIs
feat: add parsers and chunker
feat: add ingestion graph
feat: add query graph and chat API
feat: add frontend MVP
test: verify phase 1 MVP
```
