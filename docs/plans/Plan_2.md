# RagDocument Phase 2 Usability and Retrieval Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Depends on:** `docs/plans/Master_Plan.md`, `docs/plans/Plan_1.md`, `README.md`
**Master Plan Version:** MVP v1.1
**Scope:** Phase 2 only: usability and retrieval quality improvements on top of the completed Phase 1 MVP.
**Goal:** Improve source inspection, message history, document structure extraction, section-aware chunking, HTML ingestion, and retrieval context quality without adding multi-user or agentic complexity.

**Architecture:** Keep the existing React Vite frontend and FastAPI backend. Extend the current parser, chunker, LangGraph ingestion, retrieval, and API layers in place; preserve the upload/index/query boundaries from Phase 1.

**Tech Stack:** React, Vite, TypeScript, FastAPI, Pydantic, LangGraph, Supabase, Qdrant Cloud, ShopAIKey OpenAI-compatible API, Jina Reranker API, PyMuPDF, python-docx, BeautifulSoup, tiktoken, pytest.

---

## Current Progress Baseline

`README.md` says Phase 1 is complete through Batch08. Treat these as existing behavior, not new Phase 2 work:

- FastAPI backend, settings, optional admin token gate, Supabase schema, external client factories.
- Upload, duplicate detection, document listing/detail, index, reindex, delete, and chunk inspection routes.
- PDF, DOCX, TXT, and Markdown parsing.
- Fixed-token chunking with 500-token chunks and 150-token overlap.
- LangGraph ingestion and query workflows.
- Qdrant retrieval, optional document filtering, Jina reranking, Qdrant-score fallback, neighbor expansion, retrieval hints, grounded answer generation, source citations, and optional message saving.
- React frontend for upload, document list/status, index/reindex/delete, chat, document selection, answer rendering, and source citation labels.
- Backend test suite and frontend build validation.

Phase 2 should enhance these surfaces. Do not rebuild Phase 1.

---

## Master Plan Contract

Implement these Phase 2 items from `docs/plans/Master_Plan.md`:

- Document source viewer panel.
- Message history endpoint and browser UI.
- Smart section chunking.
- Header scoring heuristic.
- Table preservation.
- Neighbor context tuning.
- Optional HTML parsing, included in this plan as a Phase 2 parser.

Preserve these Phase 1 constraints:

- Upload and indexing remain separate.
- LangGraph graphs stay deterministic.
- Supabase Storage remains the original-file store.
- Supabase Postgres remains the metadata/chunk/message store.
- Qdrant remains the vector store.
- ShopAIKey remains the embedding/chat provider.
- Jina remains the reranking provider with fallback.
- Answers must use only retrieved context and return source citations.

Do not add these excluded features:

- Login, signup, OAuth, Supabase Auth, users, profiles, organizations, roles, tenant isolation, access-control tables.
- Query decomposition, relation extraction, `document_relations`, relation graph expansion, grounding verification.
- OCR, PPTX parsing, image/chart captioning, hybrid search, summaries, multi-vector chunks.
- Autonomous agents, multi-agent workflows, complex planning loops.

---

## Target File Structure

Create or modify these files during implementation:

```text
backend/
  pyproject.toml
  app/
    main.py
    core/
      config.py
    models/
      schemas.py
    api/
      routes/
        documents.py
        messages.py
    parsing/
      base.py
      structure.py
      pdf.py
      docx.py
      text.py
      markdown.py
      html.py
      registry.py
    chunking/
      token_chunker.py
      heading_detection.py
      section_chunker.py
    graphs/
      ingestion_nodes.py
      query_nodes.py
    services/
      chunks.py
      messages.py
      retrieval.py
      validation.py
  tests/
    test_api_documents.py
    test_api_messages.py
    test_api_chat.py
    test_validation.py
    test_chunker.py
    test_heading_detection.py
    test_ingestion_graph.py
    test_parsers.py
    test_query_graph.py
frontend/
  package.json
  src/
    App.tsx
    api/
      client.ts
      types.ts
    components/
      ChatPanel.tsx
      ChunkViewerPanel.tsx
      DocumentList.tsx
      MessageHistoryPanel.tsx
      SourceList.tsx
    styles.css
docs/
  plans/
    Plan_2.md
README.md
backend/README.md
```

---

## Batch 1: Backend Source and Message Contracts

### Task 1.1: Add typed chunk inspection responses

**Files:**

- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/chunks.py`
- Modify: `backend/app/api/routes/documents.py`
- Modify: `backend/tests/test_api_documents.py`

- [ ] Add `DocumentChunkResponse` to `backend/app/models/schemas.py`.

Required fields:

```text
id
document_id
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
qdrant_point_id
metadata
created_at
```

- [ ] Add `DocumentChunkListResponse` with:

```text
document_id
chunks
```

- [ ] Add `list_chunks_by_document(document_id)` to `backend/app/services/chunks.py`.

Required behavior:

```text
Fetch document_chunks rows for one document.
Order by chunk_index ascending.
Normalize id and document_id to strings.
Return an empty list when the document has no chunks.
```

- [ ] Update `GET /api/documents/{document_id}/chunks` to use the service and response model.

Verification:

```powershell
cd backend
python -m pytest tests/test_api_documents.py -v
```

Expected:

```text
Chunk inspection returns typed rows ordered by chunk_index.
Unknown document_id still returns 404.
The route does not contact Qdrant or external model providers.
```

### Task 1.2: Add message history service and API

**Files:**

- Create: `backend/app/services/messages.py`
- Create: `backend/app/api/routes/messages.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/schemas.py`
- Create: `backend/tests/test_api_messages.py`
- Modify: `backend/tests/test_query_graph.py`

- [ ] Add `MessageResponse` and `MessageListResponse`.

Required `MessageResponse` fields:

```text
id
question
answer
sources
metadata
created_at
```

- [ ] Implement `list_messages(limit=50)` in `backend/app/services/messages.py`.

Required behavior:

```text
Read from the existing messages table.
Order by created_at descending.
Clamp limit to the range 1..100.
Return normalized rows.
```

- [ ] Add `GET /api/messages`.

Response shape:

```json
{
  "messages": [
    {
      "id": "message-uuid",
      "question": "What does the document say about pricing?",
      "answer": "Pricing is based on usage tiers.",
      "sources": [],
      "metadata": {
        "document_ids": [],
        "prepared_query": "What does the document say about pricing?",
        "context_chunk_count": 2
      },
      "created_at": "2026-06-19T00:00:00Z"
    }
  ]
}
```

- [ ] Update `save_message_optional_node` so `metadata.context_chunk_count` is the length of `context_chunks`.

Verification:

```powershell
cd backend
python -m pytest tests/test_api_messages.py tests/test_query_graph.py -v
```

Expected:

```text
GET /api/messages returns newest messages first.
limit values below 1 become 1.
limit values above 100 become 100.
Saved message metadata records the actual context chunk count.
Message listing failure returns a safe HTTP error.
```

---

## Batch 2: Frontend Source Viewer and Message History

### Task 2.1: Extend frontend API client and types

**Files:**

- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] Add `DocumentChunk`, `DocumentChunkListResponse`, `MessageHistoryItem`, and `MessageListResponse` types.

- [ ] Add client functions:

```text
getDocumentChunks(documentId)
listMessages(limit)
```

- [ ] Keep `X-Admin-API-Token` behavior unchanged.

Verification:

```powershell
cd frontend
npm run build
```

Expected:

```text
TypeScript build passes.
Existing upload, document, and chat client methods remain unchanged.
```

### Task 2.2: Build source chunk viewer panel

**Files:**

- Create: `frontend/src/components/ChunkViewerPanel.tsx`
- Modify: `frontend/src/components/SourceList.tsx`
- Modify: `frontend/src/components/ChatPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] Make each source citation selectable.

- [ ] When a source is selected, load chunks for the source document with `getDocumentChunks(document_id)`.

- [ ] In `ChunkViewerPanel`, show:

```text
file_name
chunk_index
page range when available
heading when available
section_path when available
qdrant_score
rerank_score
chunk content
previous chunk button when chunk_index > 0 and the chunk exists
next chunk button when the next chunk exists
```

- [ ] Cache chunks per document ID in `App.tsx` to avoid repeated fetches when switching sources from the same document.

- [ ] Show clear states:

```text
No source selected
Loading source
Unable to load source
Selected chunk not found
```

Verification:

```powershell
cd frontend
npm run build
```

Expected:

```text
Build passes.
Source citations still render in the existing source label format.
Selecting a source renders the source chunk content and metadata.
Previous and next controls do not shift layout when disabled.
```

### Task 2.3: Build message history panel

**Files:**

- Create: `frontend/src/components/MessageHistoryPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] Load `GET /api/messages?limit=25` on initial render after documents load.

- [ ] Add a refresh control for message history.

- [ ] Render each history row with:

```text
created_at
question
short answer preview
source count
```

- [ ] Selecting a message restores its answer and sources into the chat response area without resending the question.

Verification:

```powershell
cd frontend
npm run build
```

Expected:

```text
Build passes.
Empty message history renders without crashing.
Selecting a message displays its saved answer and source citations.
```

---

## Batch 3: Structured Parsing and HTML Support

### Task 3.1: Add parsed block structure

**Files:**

- Create: `backend/app/parsing/structure.py`
- Modify: `backend/app/parsing/base.py`
- Modify: `backend/tests/test_parsers.py`

- [ ] Add `ParsedBlock` with these fields:

```text
type: paragraph | heading | table
text
page_number
heading_level
section_path
metadata
```

- [ ] Add optional `blocks` to `ParsedDocument`.

- [ ] Keep current `text`, `pages`, and `metadata` fields unchanged for backward compatibility.

- [ ] Add helpers:

```text
normalize_block_text(text)
build_paragraph_block(text, page_number)
build_heading_block(text, heading_level, page_number, metadata)
build_table_block(text, page_number, metadata)
flatten_table_to_markdown(rows)
```

Verification:

```powershell
cd backend
python -m pytest tests/test_parsers.py -v
```

Expected:

```text
Existing parser tests pass.
ParsedDocument can include blocks while old callers can still use text and pages.
Table rows flatten into stable Markdown-style text.
```

### Task 3.2: Emit structure from existing parsers

**Files:**

- Modify: `backend/app/parsing/text.py`
- Modify: `backend/app/parsing/markdown.py`
- Modify: `backend/app/parsing/docx.py`
- Modify: `backend/app/parsing/pdf.py`
- Modify: `backend/tests/test_parsers.py`

- [ ] TXT parser emits paragraph blocks split by blank lines.

- [ ] Markdown parser emits:

```text
heading blocks for # through ######
table blocks for pipe-table regions
paragraph blocks for normal text and list groups
```

- [ ] DOCX parser emits:

```text
heading blocks from Heading 1 through Heading 6 paragraph styles
paragraph blocks for normal paragraphs
table blocks for document tables
```

- [ ] PDF parser emits page-aware paragraph blocks and includes these metadata keys when PyMuPDF exposes them:

```text
font_size
is_bold
bbox
```

- [ ] Preserve `parsed_document["text"]` as the full extracted text used by fixed-token chunking.

Verification:

```powershell
cd backend
python -m pytest tests/test_parsers.py -v
```

Expected:

```text
TXT, Markdown, DOCX, and PDF parser tests pass.
Markdown heading and table blocks are detected.
DOCX heading styles and tables are preserved.
PDF blocks include page numbers.
Empty extracted text still raises a parse error.
```

### Task 3.3: Add HTML upload validation and parser

**Files:**

- Modify: `backend/pyproject.toml`
- Modify: `backend/app/services/validation.py`
- Create: `backend/app/parsing/html.py`
- Modify: `backend/app/parsing/registry.py`
- Modify: `backend/tests/test_validation.py`
- Modify: `backend/tests/test_parsers.py`

- [ ] Add dependency:

```text
beautifulsoup4>=4.12,<5.0
```

- [ ] Accept upload extensions:

```text
.html
.htm
```

- [ ] Accept MIME type:

```text
text/html
```

- [ ] Implement `HtmlParser`.

Required behavior:

```text
Remove script, style, noscript, and template elements.
Emit heading blocks for h1 through h6.
Emit paragraph blocks for p, li, blockquote, pre, and code.
Emit table blocks for table elements using Markdown-style flattened text.
Build full text from the emitted blocks.
Reject empty visible text.
```

Verification:

```powershell
cd backend
python -m pytest tests/test_validation.py tests/test_parsers.py -v
```

Expected:

```text
.html and .htm uploads are accepted with text/html.
HTML parser ignores script/style content.
HTML headings and tables become parsed blocks.
Unsupported extensions are still rejected.
```

---

## Batch 4: Header Scoring and Smart Section Chunking

### Task 4.1: Add deterministic header scoring

**Files:**

- Create: `backend/app/chunking/heading_detection.py`
- Create: `backend/tests/test_heading_detection.py`

- [ ] Implement `score_heading_candidate(block, previous_block, next_block)`.

Scoring rules:

```text
+5 when block.type is heading.
+4 when text starts with one or more Markdown # heading markers.
+3 when text starts with a numbered heading pattern such as 1. Overview or 2.3 Pricing.
+2 when metadata indicates a table-of-contents entry.
+1 when text has 12 or fewer words and does not end with punctuation.
+1 when text is uppercase and has at least two letters.
+1 when metadata.is_bold is true.
+1 when metadata.font_size is larger than nearby body text.
-2 when text ends with a period, question mark, or exclamation mark.
-3 when text has more than 18 words.
```

- [ ] Implement `is_heading_candidate(block, threshold)`.

Default threshold:

```text
4
```

Verification:

```powershell
cd backend
python -m pytest tests/test_heading_detection.py -v
```

Expected:

```text
Explicit parser heading blocks pass threshold.
Numbered short headings pass threshold.
Normal full sentences do not pass threshold.
Uppercase short headings pass threshold.
Long uppercase paragraphs do not pass threshold.
```

### Task 4.2: Add smart section chunker

**Files:**

- Create: `backend/app/chunking/section_chunker.py`
- Modify: `backend/app/chunking/token_chunker.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/test_chunker.py`

- [ ] Add settings:

```text
CHUNKING_STRATEGY=smart_section
HEADER_SCORE_THRESHOLD=4
TABLE_CHUNK_MAX_TOKENS=500
```

- [ ] Implement `SmartSectionChunker`.

Required behavior:

```text
Use parsed_document.blocks when available.
Fall back to FixedTokenChunker when blocks are missing.
Maintain section_path from detected headings.
Set heading to the nearest active heading.
Keep table blocks intact when token_count <= TABLE_CHUNK_MAX_TOKENS.
For large table blocks, split with FixedTokenChunker but preserve heading and section_path.
For large sections, split with FixedTokenChunker while preserving heading and section_path.
Emit chunk_type = "smart_section" for section chunks.
Emit chunk_type = "table" for intact table chunks.
Keep token_start, token_end, page_start, and page_end populated when available.
```

- [ ] Preserve the current `FixedTokenChunker` behavior for `CHUNKING_STRATEGY=fixed_token`.

Verification:

```powershell
cd backend
python -m pytest tests/test_chunker.py tests/test_heading_detection.py -v
```

Expected:

```text
Smart section chunks carry heading and section_path.
Table chunks stay intact below the table token cap.
Oversized sections are split without losing heading metadata.
Fixed token chunker tests still pass.
```

### Task 4.3: Integrate chunking strategy into ingestion

**Files:**

- Modify: `backend/app/graphs/ingestion_nodes.py`
- Modify: `backend/tests/test_ingestion_graph.py`

- [ ] Replace direct `FixedTokenChunker` construction with a strategy resolver:

```text
CHUNKING_STRATEGY=fixed_token -> FixedTokenChunker
CHUNKING_STRATEGY=smart_section -> SmartSectionChunker
```

- [ ] Save chunking metadata:

```text
chunking_strategy = fixed_token or smart_section
chunking_version = v2 for smart_section
```

- [ ] Keep `save_chunks_node` before `upsert_qdrant_node`.

- [ ] Ensure Qdrant payload includes heading, section_path, page_start, page_end, chunk_type, token_count, and text for smart section chunks.

Verification:

```powershell
cd backend
python -m pytest tests/test_ingestion_graph.py tests/test_chunker.py -v
```

Expected:

```text
Ingestion uses SmartSectionChunker when CHUNKING_STRATEGY=smart_section.
Ingestion uses FixedTokenChunker when CHUNKING_STRATEGY=fixed_token.
Ready documents store smart_section and v2 metadata.
Qdrant payload includes section metadata.
```

---

## Batch 5: Retrieval Context Tuning

### Task 5.1: Add section-aware neighbor expansion

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/retrieval.py`
- Modify: `backend/tests/test_query_graph.py`

- [ ] Add settings:

```text
RETRIEVAL_CONTEXT_MODE=section_aware
RETRIEVAL_SECTION_SIBLING_WINDOW=1
```

- [ ] Update `expand_neighbor_context`.

Required selection order:

```text
1. Always keep top reranked chunks first.
2. Add LLM-requested beginning/end boundary chunks when retrieval hints request them.
3. Add previous/next chunks that share the same document_id and section_path.
4. Add remaining previous/next chunks by chunk_index.
5. Deduplicate by chunk_id.
6. Do not exceed RETRIEVAL_CONTEXT_MAX_CANDIDATES.
```

- [ ] Preserve current behavior when `RETRIEVAL_CONTEXT_MODE=neighbor`.

Verification:

```powershell
cd backend
python -m pytest tests/test_query_graph.py -v
```

Expected:

```text
Top reranked chunks stay first.
Same-section neighbors are preferred before generic neighbors.
Boundary hint chunks are still included when requested.
Context never exceeds the configured cap.
Duplicate chunks are removed.
```

### Task 5.2: Add richer citation metadata

**Files:**

- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Modify: `backend/tests/test_query_graph.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/components/SourceList.tsx`

- [ ] Extend `SourceCitation` with optional fields:

```text
section_path
content_preview
is_neighbor_context
```

- [ ] Populate `section_path` from context chunks.

- [ ] Populate `content_preview` with the first 240 characters of chunk content.

- [ ] Populate `is_neighbor_context` when the context chunk was added by boundary or neighbor expansion.

- [ ] Keep existing fields unchanged:

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
cd ..\frontend
npm run build
```

Expected:

```text
Backend source citation tests pass.
Frontend accepts richer citation objects.
Existing source labels still match the Phase 1 citation format.
```

---

## Batch 6: Documentation and End-to-End Validation

### Task 6.1: Update local documentation

**Files:**

- Modify: `README.md`
- Modify: `backend/README.md`

- [ ] Document new backend settings:

```text
CHUNKING_STRATEGY
HEADER_SCORE_THRESHOLD
TABLE_CHUNK_MAX_TOKENS
RETRIEVAL_CONTEXT_MODE
RETRIEVAL_SECTION_SIBLING_WINDOW
```

- [ ] Document HTML parser support.

- [ ] Document source viewer and message history behavior.

- [ ] Document that existing documents should be re-indexed to receive smart section metadata.

### Task 6.2: Run full automated verification

**Files:**

- No new files.

- [ ] Run backend tests:

```powershell
cd backend
python -m pytest tests/test_config.py tests/test_hashing.py tests/test_validation.py tests/test_api_documents.py tests/test_api_messages.py tests/test_parsers.py tests/test_chunker.py tests/test_heading_detection.py tests/test_ingestion_graph.py tests/test_query_graph.py tests/test_api_chat.py -v
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

### Task 6.3: Run manual Phase 2 smoke test

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
Upload a Markdown file with headings and a table.
Index the document with CHUNKING_STRATEGY=smart_section.
Confirm document status becomes ready.
Ask a question answered by the table.
Confirm answer includes source citations.
Select a source and confirm the source viewer shows chunk content, heading, section path, and scores.
Ask a second question with save_message=true.
Refresh message history and select the saved message.
Confirm the saved answer and sources are restored without resending the question.
Upload an HTML file with headings and visible text.
Index the HTML document.
Ask a question answered by the HTML document.
Confirm sources are shown and can be inspected.
```

Expected:

```text
The app completes smart-section Markdown ingestion, table-grounded chat, source inspection, message history restore, and HTML ingestion.
```

---

## Phase 2 Acceptance Criteria

- [ ] Existing Phase 1 tests still pass.
- [ ] `GET /api/documents/{document_id}/chunks` returns typed chunk rows ordered by `chunk_index`.
- [ ] `GET /api/messages` returns saved messages ordered newest first.
- [ ] Frontend source citations can be selected.
- [ ] Source viewer displays source chunk content and metadata.
- [ ] Source viewer supports previous and next chunk navigation.
- [ ] Message history displays saved Q&A rows.
- [ ] Selecting a saved message restores its answer and sources without a new chat request.
- [ ] Parsed documents can include structured blocks while preserving existing `text`, `pages`, and `metadata`.
- [ ] TXT, Markdown, DOCX, PDF, and HTML parsers emit useful blocks.
- [ ] Tables are preserved as stable Markdown-style text in parser blocks and chunks.
- [ ] Header scoring detects explicit headings, numbered headings, and short title-like lines.
- [ ] Smart section chunking stores `heading` and `section_path`.
- [ ] Smart section chunking keeps small tables intact.
- [ ] Ingestion supports both `CHUNKING_STRATEGY=smart_section` and `CHUNKING_STRATEGY=fixed_token`.
- [ ] Qdrant payloads include section metadata for smart section chunks.
- [ ] Retrieval prefers same-section neighbors before generic neighbors when section-aware mode is enabled.
- [ ] Source citations include optional `section_path`, `content_preview`, and `is_neighbor_context`.
- [ ] HTML upload validation accepts `.html`, `.htm`, and `text/html`.
- [ ] No authentication, multi-user, relation graph, OCR, PPTX, hybrid search, summary, or autonomous-agent features are introduced.

---

## Execution Order

Implement batches in order:

```text
Batch 1 -> Batch 2 -> Batch 3 -> Batch 4 -> Batch 5 -> Batch 6
```

Create a small commit after each batch:

```text
feat: add source and message contracts
feat: add source viewer and message history UI
feat: add structured parsers and html support
feat: add smart section chunking
feat: tune retrieval context expansion
test: verify phase 2 usability and retrieval
```
