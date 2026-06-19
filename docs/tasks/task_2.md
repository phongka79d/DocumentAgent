# RagDocument Phase 2 Execution Tasks

## Purpose

This task file converts the approved Phase 2 plan into execution-ready batches for future implementation agents.

Phase 2 improves usability and retrieval quality on top of the completed Phase 1 MVP. It adds typed chunk inspection, message history, a frontend source viewer, structured parsing, HTML support, header scoring, smart section chunking, section-aware retrieval context, richer citations, documentation updates, and final validation.

## Authoritative Source

Primary source:

- `docs/plans/Plan_2.md`

Context sources:

- `docs/plans/Master_Plan.md`
- `README.md`

Use `docs/plans/Plan_2.md` as the source of truth for Phase 2 scope, order, required files, validations, and acceptance criteria. Use `docs/plans/Master_Plan.md` only to clarify architecture constraints. Use `README.md` only to understand completed Phase 1 baseline behavior.

## Source Section Index

- `docs/plans/Plan_2.md` > `## Current Progress Baseline` -> completed Phase 1 behavior that must be preserved.
- `docs/plans/Plan_2.md` > `## Master Plan Contract` -> Phase 2 features to implement and excluded features to avoid.
- `docs/plans/Plan_2.md` > `## Target File Structure` -> expected files and modules for Phase 2.
- `docs/plans/Plan_2.md` > `## Batch 1: Backend Source and Message Contracts` -> typed chunk inspection and message history API work.
- `docs/plans/Plan_2.md` > `## Batch 2: Frontend Source Viewer and Message History` -> frontend API, source viewer, and message history work.
- `docs/plans/Plan_2.md` > `## Batch 3: Structured Parsing and HTML Support` -> parsed blocks, parser structure, and HTML ingestion work.
- `docs/plans/Plan_2.md` > `## Batch 4: Header Scoring and Smart Section Chunking` -> heading scoring, smart section chunker, and ingestion integration.
- `docs/plans/Plan_2.md` > `## Batch 5: Retrieval Context Tuning` -> section-aware neighbor expansion and richer citation metadata.
- `docs/plans/Plan_2.md` > `## Batch 6: Documentation and End-to-End Validation` -> README updates, full automated checks, and manual smoke validation.
- `docs/plans/Plan_2.md` > `## Phase 2 Acceptance Criteria` -> final Phase 2 completion criteria.
- `docs/plans/Plan_2.md` > `## Execution Order` -> required batch order and commit sequence.
- `docs/plans/Master_Plan.md` > `## 1. Project Scope` -> single-user RAG scope and no multi-user SaaS behavior.
- `docs/plans/Master_Plan.md` > `## 2. MVP Design Principles` -> optional admin token gate and practical LangGraph constraints.
- `docs/plans/Master_Plan.md` > `## 8. LangGraph Ingestion Graph` -> deterministic ingestion workflow and chunking metadata.
- `docs/plans/Master_Plan.md` > `## 10. LangGraph Query Graph` -> deterministic query workflow and message saving behavior.
- `docs/plans/Master_Plan.md` > `## 13. Neighbor Context Expansion` -> current neighbor-expansion contract to preserve or extend.
- `docs/plans/Master_Plan.md` > `## 15. Supabase Postgres Schema` -> `documents`, `document_chunks`, and `messages` table contracts.
- `docs/plans/Master_Plan.md` > `## 21. API Endpoints` -> required and optional API endpoint contracts.
- `docs/plans/Master_Plan.md` > `## 26. Source Citation Format` -> existing source citation fields and display format.
- `README.md` > `# RagDocument` -> accepted completed Phase 1 baseline and validation commands.

## Approved Architecture Summary

- Keep the existing React Vite TypeScript frontend and FastAPI backend.
- Extend the current parser, chunker, LangGraph ingestion, retrieval, API, and frontend UI layers in place.
- Preserve Phase 1 upload, index, reindex, delete, chat, retrieval, and source citation behavior.
- Keep upload and indexing separate.
- Keep LangGraph workflows deterministic and practical.
- Keep Supabase Storage as the original-file store.
- Keep Supabase Postgres as the metadata, chunk, and optional message store.
- Keep Qdrant Cloud as the vector store.
- Keep ShopAIKey as the embedding and chat provider.
- Keep Jina as the reranking provider with fallback.
- Answers must use only retrieved context and return source citations.
- Phase 2 may add HTML parsing, structured blocks, smart section chunking, message history, source inspection, and retrieval context tuning.

## Global Implementation Rules

- Do not rebuild completed Phase 1 behavior listed in `README.md`.
- Do not add login, signup, OAuth, Supabase Auth, users, profiles, organizations, roles, tenant isolation, or access-control tables.
- Do not add query decomposition, relation extraction, `document_relations`, relation graph expansion, or grounding verification.
- Do not add OCR, PPTX parsing, image/chart captioning, hybrid search, summaries, section summaries, or multi-vector chunks.
- Do not add autonomous agents, multi-agent workflows, or complex planning loops.
- Preserve `X-Admin-API-Token` behavior exactly: disabled when unset, enforced when configured, and never exposing backend-only secrets to frontend code.
- Preserve existing parser, fixed-token chunker, ingestion graph, query graph, API, and frontend behavior unless Phase 2 explicitly extends it.
- Keep new backend settings environment-driven with safe defaults.
- Keep external credentials user-provided. Execution agents must not fabricate API keys, service projects, storage buckets, or secrets.
- Keep actual secrets out of source files, logs, frontend bundles, task reports, and completion summaries.
- Run the validation commands listed for each batch before marking that batch complete.
- Create a small commit after each completed batch when the repository workflow allows commits.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code.
- Use descriptive names for modules, functions, variables, components, settings, and tests.
- Keep functions, components, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow the standard conventions of the approved stack: FastAPI, Pydantic, LangGraph, pytest, React, Vite, and TypeScript.
- Use clear typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless explicitly required by the plan.
- Add comments only for non-obvious decisions or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Avoid adding formatters, linters, frameworks, or architecture changes outside the source plan unless already present or explicitly requested.

## Batch Map

- Batch01 - Backend Source and Message Contracts
  - (01A): Add typed chunk inspection responses
  - (01B): Add message history service and API
- Batch02 - Frontend Source Viewer and Message History
  - (02A): Extend frontend API client and types
  - (02B): Build source chunk viewer panel
  - (02C): Build message history panel
- Batch03 - Structured Parsing and HTML Support
  - (03A): Add parsed block structure
  - (03B): Emit structure from existing parsers
  - (03C): Add HTML upload validation and parser
- Batch04 - Header Scoring and Smart Section Chunking
  - (04A): Add deterministic header scoring
  - (04B): Add smart section chunker
  - (04C): Integrate chunking strategy into ingestion
- Batch05 - Retrieval Context Tuning
  - (05A): Add section-aware neighbor expansion
  - (05B): Add richer citation metadata
- Batch06 - Documentation and End-to-End Validation
  - (06A): Update local documentation
  - (06B): Run full automated verification
  - (06C): Run manual Phase 2 smoke test

## Mandatory Batch01 - Backend Source and Message Contracts

### Goal

Add typed backend contracts for chunk inspection and saved message history.

### Why this batch exists

Phase 2 frontend source inspection and message history require stable backend response models and API routes before UI work begins.

### Inputs / Dependencies

- Completed Phase 1 backend from `README.md`.
- Existing `documents`, `document_chunks`, and optional `messages` Supabase tables from `docs/plans/Master_Plan.md`.
- Existing document chunk inspection route and query graph message-saving behavior.

### Tasks

- [x] (01A): Add typed chunk inspection responses
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 1: Backend Source and Message Contracts` > `### Task 1.1: Add typed chunk inspection responses`
  - Source Requirements:
    - Add `DocumentChunkResponse` with chunk row fields needed for inspection.
    - Add `DocumentChunkListResponse` with `document_id` and `chunks`.
    - Add `list_chunks_by_document(document_id)` ordered by `chunk_index` ascending.
    - Update `GET /api/documents/{document_id}/chunks` to use the service and typed response.
    - Unknown `document_id` still returns 404.
    - The route must not contact Qdrant or external model providers.
  - Details: Formalize the chunk inspection API so frontend source viewing can load persisted chunk rows directly from Supabase.
  - Dependencies: Existing document route, chunk table contract, and chunk service conventions from Phase 1.
  - User Action: None.
  - Agent Work: Add Pydantic response models, add a chunk-listing service function, wire the document chunks route to the service, and cover ordering and error behavior with tests.
  - Specific Steps:
    1. Review existing document schemas in `backend/app/models/schemas.py`.
    2. Add `DocumentChunkResponse` fields: `id`, `document_id`, `chunk_index`, `content`, `content_hash`, `token_count`, `chunk_type`, `heading`, `section_path`, `page_start`, `page_end`, `token_start`, `token_end`, `qdrant_point_id`, `metadata`, and `created_at`.
    3. Add `DocumentChunkListResponse` with `document_id` and `chunks`.
    4. Implement `list_chunks_by_document(document_id)` in `backend/app/services/chunks.py`.
    5. Ensure chunk rows are fetched for one document, ordered by `chunk_index` ascending, and normalized with string `id` and `document_id`.
    6. Return an empty chunk list when a known document has no chunks.
    7. Update `GET /api/documents/{document_id}/chunks` to use the service and response model.
    8. Update `backend/tests/test_api_documents.py` for typed rows, ordering, empty results, 404 behavior, and no external provider calls.
  - Output: Typed chunk inspection endpoint backed by `document_chunks`.
  - Acceptance: Chunk inspection returns typed rows ordered by `chunk_index`; unknown documents return 404; no Qdrant, ShopAIKey, or Jina calls are made.
  - Validation: `cd backend && python -m pytest tests/test_api_documents.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/models/schemas.py`, `backend/app/services/chunks.py`, `backend/app/api/routes/documents.py`, `backend/tests/test_api_documents.py`

- [x] (01B): Add message history service and API
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 1: Backend Source and Message Contracts` > `### Task 1.2: Add message history service and API`
  - Source Requirements:
    - Add `MessageResponse` and `MessageListResponse`.
    - Implement `list_messages(limit=50)` using the existing `messages` table.
    - Order messages by `created_at` descending.
    - Clamp `limit` to the range `1..100`.
    - Add `GET /api/messages`.
    - Update saved message metadata so `metadata.context_chunk_count` equals `len(context_chunks)`.
    - Message listing failure returns a safe HTTP error.
  - Details: Add a backend message-history surface so the frontend can display and restore previously saved Q&A rows.
  - Dependencies: Existing optional `messages` table, existing query graph `save_message_optional_node`, and backend route registration.
  - User Action: None.
  - Agent Work: Create message service and route modules, add schemas, register the router, adjust saved-message metadata, and add backend tests.
  - Specific Steps:
    1. Add `MessageResponse` with `id`, `question`, `answer`, `sources`, `metadata`, and `created_at`.
    2. Add `MessageListResponse` with `messages`.
    3. Create `backend/app/services/messages.py` and implement `list_messages(limit=50)`.
    4. Normalize message IDs and JSON fields consistently with existing service patterns.
    5. Create `backend/app/api/routes/messages.py` with `GET /api/messages`.
    6. Register the messages router in `backend/app/main.py`.
    7. Update `save_message_optional_node` so saved metadata records the actual context chunk count.
    8. Create `backend/tests/test_api_messages.py`.
    9. Update `backend/tests/test_query_graph.py` for the metadata count behavior.
  - Output: Message history service, route, schemas, and tests.
  - Acceptance: `GET /api/messages` returns newest messages first, clamps limits below 1 to 1 and above 100 to 100, returns safe HTTP errors on listing failure, and saved message metadata records actual context count.
  - Validation: `cd backend && python -m pytest tests/test_api_messages.py tests/test_query_graph.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/services/messages.py`, `backend/app/api/routes/messages.py`, `backend/app/main.py`, `backend/app/models/schemas.py`, `backend/tests/test_api_messages.py`, `backend/tests/test_query_graph.py`

### Files or Modules Likely Created or Updated

- `backend/app/models/schemas.py`
- `backend/app/services/chunks.py`
- `backend/app/services/messages.py`
- `backend/app/api/routes/documents.py`
- `backend/app/api/routes/messages.py`
- `backend/app/main.py`
- `backend/tests/test_api_documents.py`
- `backend/tests/test_api_messages.py`
- `backend/tests/test_query_graph.py`

### Required Outputs / Artifacts

- Typed chunk response models.
- Message history response models.
- Chunk listing service.
- Message listing service.
- `GET /api/documents/{document_id}/chunks` typed route behavior.
- `GET /api/messages` route.
- Passing backend tests for Batch01.

### Acceptance Criteria

- Existing Phase 1 document API behavior is preserved.
- Chunk inspection returns typed rows ordered by `chunk_index`.
- Unknown document chunk inspection returns 404.
- Chunk inspection remains local to Supabase/Postgres data.
- Message history returns newest saved rows first.
- Message history limit is clamped to `1..100`.
- Saved message metadata includes actual `context_chunk_count`.

### Required Tests or Validations

```powershell
cd backend
python -m pytest tests/test_api_documents.py -v
python -m pytest tests/test_api_messages.py tests/test_query_graph.py -v
```

### Explicit Non-Goals

- Do not build frontend source viewer UI in this batch.
- Do not change Qdrant payload format in this batch.
- Do not add conversations, users, auth, or multi-user message ownership.
- Do not make message saving failure fail chat responses.

## Mandatory Batch02 - Frontend Source Viewer and Message History

### Goal

Add frontend support for chunk inspection, selectable citations, source viewing, and saved message history.

### Why this batch exists

Users need to inspect retrieved source content and restore saved answers without resending questions.

### Inputs / Dependencies

- Batch01 completed.
- Existing frontend API client, chat UI, source citation rendering, and document list from Phase 1.
- Existing optional `X-Admin-API-Token` browser session behavior.

### Tasks

- [x] (02A): Extend frontend API client and types
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 2: Frontend Source Viewer and Message History` > `### Task 2.1: Extend frontend API client and types`
  - Source Requirements:
    - Add `DocumentChunk`, `DocumentChunkListResponse`, `MessageHistoryItem`, and `MessageListResponse` types.
    - Add `getDocumentChunks(documentId)` and `listMessages(limit)` client functions.
    - Keep `X-Admin-API-Token` behavior unchanged.
  - Details: Prepare typed frontend access to the Batch01 backend APIs.
  - Dependencies: Batch01 typed API responses.
  - User Action: None.
  - Agent Work: Update TypeScript API types and client methods without changing existing upload, document, or chat methods.
  - Specific Steps:
    1. Inspect existing `frontend/src/api/types.ts` naming and field conventions.
    2. Add types matching the Batch01 backend response models.
    3. Inspect existing `frontend/src/api/client.ts` request helper and admin token handling.
    4. Add `getDocumentChunks(documentId)` using `GET /api/documents/{document_id}/chunks`.
    5. Add `listMessages(limit)` using `GET /api/messages?limit={limit}`.
    6. Confirm existing client functions keep their current behavior and signatures.
  - Output: Frontend API types and client methods for chunks and messages.
  - Acceptance: TypeScript build passes and existing API methods remain unchanged.
  - Validation: `cd frontend && npm run build`
  - Blocked Condition: None.
  - Files: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`

- [x] (02B): Build source chunk viewer panel
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 2: Frontend Source Viewer and Message History` > `### Task 2.2: Build source chunk viewer panel`
  - Source Requirements:
    - Make each source citation selectable.
    - Load chunks for the selected source document using `getDocumentChunks(document_id)`.
    - Show file name, chunk index, page range, heading, section path, scores, content, and previous/next controls.
    - Cache chunks per document ID in `App.tsx`.
    - Show clear states: no source selected, loading source, unable to load source, selected chunk not found.
    - Previous and next controls do not shift layout when disabled.
  - Details: Add an inspection panel that lets users verify the chunk behind each citation and navigate nearby chunks.
  - Dependencies: Task (02A), existing `SourceList`, existing chat response state, and source citation objects.
  - User Action: None.
  - Agent Work: Create `ChunkViewerPanel`, make `SourceList` selection-aware, update app state and styles, and preserve existing citation labels.
  - Specific Steps:
    1. Add selected source state in `App.tsx`.
    2. Add per-document chunk cache state in `App.tsx`.
    3. Update `SourceList` so source citations are selectable while preserving Phase 1 label text.
    4. Load chunks with `getDocumentChunks(document_id)` when a source is selected and missing from cache.
    5. Create `ChunkViewerPanel.tsx`.
    6. Render selected source metadata: `file_name`, `chunk_index`, page range when present, heading when present, section path when present, `qdrant_score`, and `rerank_score`.
    7. Render selected chunk content from the loaded chunk list.
    8. Add previous and next controls that navigate only when matching adjacent chunks exist.
    9. Add stable disabled-control styling so layout does not shift.
    10. Add empty, loading, error, and not-found states.
    11. Ensure source selection clears or updates correctly when a new chat response is shown.
  - Output: Source viewer UI integrated with chat citations.
  - Acceptance: Build passes; source citations still use the Phase 1 label format; selecting a source renders chunk content and metadata; previous/next controls are stable.
  - Validation: `cd frontend && npm run build`
  - Blocked Condition: None.
  - Files: `frontend/src/components/ChunkViewerPanel.tsx`, `frontend/src/components/SourceList.tsx`, `frontend/src/components/ChatPanel.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`

- [x] (02C): Build message history panel
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 2: Frontend Source Viewer and Message History` > `### Task 2.3: Build message history panel`
  - Source Requirements:
    - Load `GET /api/messages?limit=25` on initial render after documents load.
    - Add a refresh control for message history.
    - Render `created_at`, question, short answer preview, and source count.
    - Selecting a message restores its answer and sources into the chat response area without resending the question.
  - Details: Add saved Q&A browsing and restoration to the frontend.
  - Dependencies: Task (02A), Batch01 message route, and existing chat response rendering.
  - User Action: None.
  - Agent Work: Create `MessageHistoryPanel`, wire initial load and refresh, and update app state so selected messages reuse the chat response display.
  - Specific Steps:
    1. Add message history state in `App.tsx`.
    2. Load messages with limit 25 after initial documents load.
    3. Add a refresh handler that reloads message history.
    4. Create `MessageHistoryPanel.tsx`.
    5. Render each row with created time, question, concise answer preview, and source count.
    6. Handle empty and error states without crashing.
    7. On message selection, set the current chat answer and sources from the saved row.
    8. Ensure message selection does not call `POST /api/chat`.
    9. Ensure source citations from selected messages can still be selected for source viewing when chunk data exists.
  - Output: Message history panel integrated with the chat response area.
  - Acceptance: Build passes; empty history renders safely; selecting a saved message displays saved answer and sources without resending the question.
  - Validation: `cd frontend && npm run build`
  - Blocked Condition: None.
  - Files: `frontend/src/components/MessageHistoryPanel.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`

### Files or Modules Likely Created or Updated

- `frontend/src/api/types.ts`
- `frontend/src/api/client.ts`
- `frontend/src/components/ChunkViewerPanel.tsx`
- `frontend/src/components/SourceList.tsx`
- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/components/MessageHistoryPanel.tsx`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`

### Required Outputs / Artifacts

- Typed frontend API support for chunk inspection and message history.
- Selectable source citations.
- Source chunk viewer panel.
- Per-document chunk cache.
- Message history panel.
- Saved answer restoration without a chat request.

### Acceptance Criteria

- Existing upload, document, and chat UI behavior remains intact.
- Source citations remain readable in the established Phase 1 format.
- Source citation selection loads and displays persisted chunk content.
- Previous and next chunk navigation is available when adjacent chunks exist.
- Message history loads after documents load and can be refreshed.
- Saved message selection restores answer and sources without a new chat request.

### Required Tests or Validations

```powershell
cd frontend
npm run build
```

### Explicit Non-Goals

- Do not add frontend authentication or user accounts.
- Do not store backend-only secrets in browser code.
- Do not change the chat request contract beyond consuming existing saved messages.
- Do not implement browser-side parsing or retrieval logic.

## Mandatory Batch03 - Structured Parsing and HTML Support

### Goal

Extend parsing so documents can expose structured blocks and HTML files can be uploaded, parsed, and indexed.

### Why this batch exists

Smart section chunking requires parser-provided structure where available, and Phase 2 includes optional HTML parsing as a supported parser.

### Inputs / Dependencies

- Existing PDF, DOCX, TXT, and Markdown parsers.
- Existing upload validation and parser registry.
- Existing fixed-token chunking must continue to use `ParsedDocument.text`.

### Tasks

- [x] (03A): Add parsed block structure
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 3: Structured Parsing and HTML Support` > `### Task 3.1: Add parsed block structure`
  - Source Requirements:
    - Add `ParsedBlock` with type, text, page number, heading level, section path, and metadata fields.
    - Add optional `blocks` to `ParsedDocument`.
    - Keep current `text`, `pages`, and `metadata` fields unchanged for backward compatibility.
    - Add helper functions for text normalization, paragraph blocks, heading blocks, table blocks, and Markdown-style table flattening.
  - Details: Add shared parser structures without breaking existing parser callers.
  - Dependencies: Existing parser base types and parser tests.
  - User Action: None.
  - Agent Work: Create parser structure helpers, update parser base types, and add tests.
  - Specific Steps:
    1. Create `backend/app/parsing/structure.py`.
    2. Define `ParsedBlock` with `type`, `text`, `page_number`, `heading_level`, `section_path`, and `metadata`.
    3. Support block types `paragraph`, `heading`, and `table`.
    4. Add optional `blocks` to `ParsedDocument` in `backend/app/parsing/base.py`.
    5. Preserve existing `text`, `pages`, and `metadata` fields for all callers.
    6. Implement `normalize_block_text(text)`.
    7. Implement `build_paragraph_block(text, page_number)`.
    8. Implement `build_heading_block(text, heading_level, page_number, metadata)`.
    9. Implement `build_table_block(text, page_number, metadata)`.
    10. Implement `flatten_table_to_markdown(rows)` with stable Markdown-style output.
    11. Update `backend/tests/test_parsers.py`.
  - Output: Shared structured parsing primitives.
  - Acceptance: Existing parser tests pass; parsed documents can include blocks; old callers can still use `text` and `pages`; table rows flatten to stable Markdown-style text.
  - Validation: `cd backend && python -m pytest tests/test_parsers.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/parsing/structure.py`, `backend/app/parsing/base.py`, `backend/tests/test_parsers.py`

- [x] (03B): Emit structure from existing parsers
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 3: Structured Parsing and HTML Support` > `### Task 3.2: Emit structure from existing parsers`
  - Source Requirements:
    - TXT parser emits paragraph blocks split by blank lines.
    - Markdown parser emits heading blocks for `#` through `######`, table blocks for pipe-table regions, and paragraph blocks for normal text and list groups.
    - DOCX parser emits heading blocks from Heading 1 through Heading 6 paragraph styles, paragraph blocks, and table blocks.
    - PDF parser emits page-aware paragraph blocks and metadata when PyMuPDF exposes font size, bold state, and bounding box.
    - Preserve `parsed_document["text"]` as full extracted text for fixed-token chunking.
    - Empty extracted text still raises a parse error.
  - Details: Update existing parsers to produce structured blocks while preserving their existing full-text extraction contract.
  - Dependencies: Task (03A) and existing parser implementations.
  - User Action: None.
  - Agent Work: Update TXT, Markdown, DOCX, and PDF parsers to emit useful blocks and add parser tests for each.
  - Specific Steps:
    1. Update `backend/app/parsing/text.py` to split paragraph blocks by blank lines.
    2. Update `backend/app/parsing/markdown.py` to detect ATX headings, pipe table regions, paragraph text, and list groups.
    3. Update `backend/app/parsing/docx.py` to map Heading 1 through Heading 6 styles to heading blocks.
    4. Update DOCX table parsing to emit table blocks using `flatten_table_to_markdown`.
    5. Update `backend/app/parsing/pdf.py` to emit page-aware paragraph blocks.
    6. Include PDF block metadata keys `font_size`, `is_bold`, and `bbox` when available.
    7. Preserve the full extracted `text` output in all parsers.
    8. Preserve current empty-text parse error behavior.
    9. Add tests for Markdown headings and tables, DOCX headings and tables, PDF page numbers, and TXT paragraphs.
  - Output: Structured block emission from existing parsers.
  - Acceptance: TXT, Markdown, DOCX, and PDF parser tests pass; heading and table blocks are detected; PDF blocks include page numbers; full text remains available.
  - Validation: `cd backend && python -m pytest tests/test_parsers.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/parsing/text.py`, `backend/app/parsing/markdown.py`, `backend/app/parsing/docx.py`, `backend/app/parsing/pdf.py`, `backend/tests/test_parsers.py`

- [x] (03C): Add HTML upload validation and parser
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 3: Structured Parsing and HTML Support` > `### Task 3.3: Add HTML upload validation and parser`
  - Source Requirements:
    - Add `beautifulsoup4>=4.12,<5.0`.
    - Accept `.html` and `.htm` upload extensions.
    - Accept `text/html` MIME type.
    - Implement `HtmlParser`.
    - Remove `script`, `style`, `noscript`, and `template` elements.
    - Emit heading, paragraph, and table blocks from visible content.
    - Build full text from emitted blocks.
    - Reject empty visible text.
    - Unsupported extensions remain rejected.
  - Details: Add HTML as a Phase 2 parser with safe visible-text extraction and structured blocks.
  - Dependencies: Task (03A), upload validation service, parser registry, and parser tests.
  - User Action: None.
  - Agent Work: Add dependency, validation support, parser implementation, registry mapping, and tests.
  - Specific Steps:
    1. Add `beautifulsoup4>=4.12,<5.0` to `backend/pyproject.toml`.
    2. Update `backend/app/services/validation.py` to accept `.html`, `.htm`, and `text/html`.
    3. Create `backend/app/parsing/html.py`.
    4. Remove non-visible elements: `script`, `style`, `noscript`, and `template`.
    5. Emit heading blocks for `h1` through `h6`.
    6. Emit paragraph blocks for `p`, `li`, `blockquote`, `pre`, and `code`.
    7. Emit table blocks for `table` elements using Markdown-style flattened text.
    8. Build full parser text from emitted blocks.
    9. Reject empty visible text with the same safe parse error pattern as existing parsers.
    10. Register the HTML parser in `backend/app/parsing/registry.py`.
    11. Add upload validation and parser tests.
  - Output: HTML upload validation and parser support.
  - Acceptance: `.html` and `.htm` uploads with `text/html` are accepted; script/style content is ignored; headings and tables become parsed blocks; unsupported extensions remain rejected.
  - Validation: `cd backend && python -m pytest tests/test_validation.py tests/test_parsers.py -v`
  - Blocked Condition: None.
  - Files: `backend/pyproject.toml`, `backend/app/services/validation.py`, `backend/app/parsing/html.py`, `backend/app/parsing/registry.py`, `backend/tests/test_validation.py`, `backend/tests/test_parsers.py`

### Files or Modules Likely Created or Updated

- `backend/pyproject.toml`
- `backend/app/parsing/base.py`
- `backend/app/parsing/structure.py`
- `backend/app/parsing/text.py`
- `backend/app/parsing/markdown.py`
- `backend/app/parsing/docx.py`
- `backend/app/parsing/pdf.py`
- `backend/app/parsing/html.py`
- `backend/app/parsing/registry.py`
- `backend/app/services/validation.py`
- `backend/tests/test_validation.py`
- `backend/tests/test_parsers.py`

### Required Outputs / Artifacts

- Shared parsed block model and helper functions.
- Structured block support in existing parsers.
- HTML parser.
- HTML upload validation.
- Passing parser and validation tests.

### Acceptance Criteria

- Parser backward compatibility is preserved.
- `ParsedDocument.text` remains the source for fixed-token chunking.
- TXT, Markdown, DOCX, PDF, and HTML parsers emit useful blocks.
- Tables are preserved as stable Markdown-style text.
- HTML parser ignores non-visible script/style/template content.
- Empty extracted or visible text still raises parse errors.

### Required Tests or Validations

```powershell
cd backend
python -m pytest tests/test_parsers.py -v
python -m pytest tests/test_validation.py tests/test_parsers.py -v
```

### Explicit Non-Goals

- Do not add OCR, PPTX parsing, image/chart captioning, summaries, or hybrid search.
- Do not remove or weaken existing PDF, DOCX, TXT, or Markdown parsing behavior.
- Do not make structured blocks mandatory for old parsed documents.

## Mandatory Batch04 - Header Scoring and Smart Section Chunking

### Goal

Add deterministic heading detection and a smart section chunking strategy, then wire strategy selection into ingestion.

### Why this batch exists

Phase 2 retrieval quality depends on chunks carrying heading and section metadata, while Phase 1 fixed-token chunking must remain available.

### Inputs / Dependencies

- Batch03 structured blocks.
- Existing fixed-token chunker.
- Existing ingestion graph and chunk persistence.
- Existing Qdrant upsert payload logic.

### Tasks

- [x] (04A): Add deterministic header scoring
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 4: Header Scoring and Smart Section Chunking` > `### Task 4.1: Add deterministic header scoring`
  - Source Requirements:
    - Implement `score_heading_candidate(block, previous_block, next_block)`.
    - Implement scoring rules for explicit heading type, Markdown marker, numbered pattern, table-of-contents metadata, short no-punctuation text, uppercase text, bold metadata, larger font size, sentence punctuation penalty, and long text penalty.
    - Implement `is_heading_candidate(block, threshold)` with default threshold `4`.
  - Details: Add deterministic heading classification to support smart section paths without LLM calls.
  - Dependencies: Batch03 parsed block shape.
  - User Action: None.
  - Agent Work: Create the heading detection module and tests for explicit, numbered, uppercase, sentence, and long-paragraph cases.
  - Specific Steps:
    1. Create `backend/app/chunking/heading_detection.py`.
    2. Implement score contribution `+5` when `block.type` is `heading`.
    3. Implement score contribution `+4` for Markdown heading markers.
    4. Implement score contribution `+3` for numbered heading patterns such as `1. Overview` or `2.3 Pricing`.
    5. Implement score contribution `+2` when metadata indicates a table-of-contents entry.
    6. Implement score contribution `+1` for text with 12 or fewer words that does not end with punctuation.
    7. Implement score contribution `+1` for uppercase text with at least two letters.
    8. Implement score contribution `+1` for `metadata.is_bold`.
    9. Implement score contribution `+1` when `metadata.font_size` is larger than nearby body text.
    10. Implement penalties `-2` for sentence-ending punctuation and `-3` for more than 18 words.
    11. Implement `is_heading_candidate(block, threshold=4)`.
    12. Add tests in `backend/tests/test_heading_detection.py`.
  - Output: Deterministic heading detection module and tests.
  - Acceptance: Explicit headings, numbered short headings, and uppercase short headings pass threshold; normal sentences and long uppercase paragraphs do not pass threshold.
  - Validation: `cd backend && python -m pytest tests/test_heading_detection.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/chunking/heading_detection.py`, `backend/tests/test_heading_detection.py`

- [x] (04B): Add smart section chunker
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 4: Header Scoring and Smart Section Chunking` > `### Task 4.2: Add smart section chunker`
  - Source Requirements:
    - Add settings `CHUNKING_STRATEGY=smart_section`, `HEADER_SCORE_THRESHOLD=4`, and `TABLE_CHUNK_MAX_TOKENS=500`.
    - Implement `SmartSectionChunker`.
    - Use `parsed_document.blocks` when available.
    - Fall back to `FixedTokenChunker` when blocks are missing.
    - Maintain `section_path` from detected headings.
    - Set `heading` to the nearest active heading.
    - Keep table blocks intact when within `TABLE_CHUNK_MAX_TOKENS`.
    - Split large tables and sections with `FixedTokenChunker` while preserving heading and section path.
    - Emit `chunk_type = "smart_section"` for section chunks and `chunk_type = "table"` for intact table chunks.
    - Keep token and page ranges populated when available.
    - Preserve current fixed-token behavior for `CHUNKING_STRATEGY=fixed_token`.
  - Details: Add an alternate chunker that uses parser structure to produce section-aware chunks.
  - Dependencies: Task (04A), Batch03 block emission, and existing fixed-token chunker behavior.
  - User Action: None.
  - Agent Work: Implement smart section chunking, settings, fixed-token compatibility, and chunker tests.
  - Specific Steps:
    1. Add settings to `backend/app/core/config.py`.
    2. Create `backend/app/chunking/section_chunker.py`.
    3. Implement `SmartSectionChunker` constructor using token sizing, table cap, and header threshold settings.
    4. Use `parsed_document.blocks` when present.
    5. Fall back to `FixedTokenChunker` when blocks are absent.
    6. Maintain active heading and section path from detected heading blocks.
    7. Build section chunks with `chunk_type = "smart_section"`.
    8. Keep table blocks intact with `chunk_type = "table"` when below the table token cap.
    9. Split oversized tables with `FixedTokenChunker` and preserve heading metadata.
    10. Split oversized sections with `FixedTokenChunker` and preserve heading metadata.
    11. Populate `token_start`, `token_end`, `page_start`, and `page_end` when available.
    12. Update `backend/app/chunking/token_chunker.py` only as needed for reuse and compatibility.
    13. Update `backend/tests/test_chunker.py`.
  - Output: Smart section chunker with fixed-token fallback and tests.
  - Acceptance: Smart section chunks carry heading and section path; small tables stay intact; oversized sections split without losing heading metadata; fixed-token tests still pass.
  - Validation: `cd backend && python -m pytest tests/test_chunker.py tests/test_heading_detection.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/chunking/section_chunker.py`, `backend/app/chunking/token_chunker.py`, `backend/app/core/config.py`, `backend/tests/test_chunker.py`

- [x] (04C): Integrate chunking strategy into ingestion
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 4: Header Scoring and Smart Section Chunking` > `### Task 4.3: Integrate chunking strategy into ingestion`
  - Source Requirements:
    - Replace direct `FixedTokenChunker` construction with a strategy resolver.
    - Support `CHUNKING_STRATEGY=fixed_token` and `CHUNKING_STRATEGY=smart_section`.
    - Save `chunking_strategy` and `chunking_version`.
    - Use `v2` for smart section chunking.
    - Keep `save_chunks_node` before `upsert_qdrant_node`.
    - Ensure Qdrant payload includes heading, section path, page range, chunk type, token count, and text for smart section chunks.
  - Details: Make ingestion select the configured chunker and persist smart-section metadata through Supabase and Qdrant.
  - Dependencies: Task (04B), existing ingestion graph, and existing Qdrant payload tests.
  - User Action: None.
  - Agent Work: Add a chunking strategy resolver, update ingestion node metadata, and test both strategies.
  - Specific Steps:
    1. Inspect `backend/app/graphs/ingestion_nodes.py` current `FixedTokenChunker` usage.
    2. Add a resolver that maps `fixed_token` to `FixedTokenChunker`.
    3. Add a resolver mapping that maps `smart_section` to `SmartSectionChunker`.
    4. Set `chunking_strategy = "fixed_token"` and `chunking_version = "v1"` for fixed token mode.
    5. Set `chunking_strategy = "smart_section"` and `chunking_version = "v2"` for smart section mode.
    6. Preserve node order so chunks are saved before Qdrant upsert.
    7. Ensure saved chunks include heading, section path, page range, chunk type, token count, token range, content hash, and metadata as appropriate.
    8. Ensure Qdrant payload includes heading, section path, page start, page end, chunk type, token count, and text.
    9. Update `backend/tests/test_ingestion_graph.py` for both strategies and Qdrant payload metadata.
  - Output: Ingestion strategy selection and smart-section metadata persistence.
  - Acceptance: Ingestion uses smart section chunking when configured, fixed token chunking when configured, stores smart-section `v2` metadata, and includes section metadata in Qdrant payloads.
  - Validation: `cd backend && python -m pytest tests/test_ingestion_graph.py tests/test_chunker.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/graphs/ingestion_nodes.py`, `backend/tests/test_ingestion_graph.py`

### Files or Modules Likely Created or Updated

- `backend/app/chunking/heading_detection.py`
- `backend/app/chunking/section_chunker.py`
- `backend/app/chunking/token_chunker.py`
- `backend/app/core/config.py`
- `backend/app/graphs/ingestion_nodes.py`
- `backend/tests/test_heading_detection.py`
- `backend/tests/test_chunker.py`
- `backend/tests/test_ingestion_graph.py`

### Required Outputs / Artifacts

- Heading detection module.
- Smart section chunker.
- Chunking settings.
- Ingestion chunking strategy resolver.
- Smart-section metadata saved in Supabase and Qdrant payloads.
- Passing chunker, heading detection, and ingestion tests.

### Acceptance Criteria

- Header scoring detects explicit headings, numbered headings, and short title-like lines.
- Header scoring rejects normal sentences and long uppercase paragraphs.
- Smart section chunking stores `heading` and `section_path`.
- Small tables remain intact.
- Oversized tables and sections split without losing heading metadata.
- `CHUNKING_STRATEGY=fixed_token` preserves Phase 1 fixed-token behavior.
- `CHUNKING_STRATEGY=smart_section` stores `chunking_version = v2`.

### Required Tests or Validations

```powershell
cd backend
python -m pytest tests/test_heading_detection.py -v
python -m pytest tests/test_chunker.py tests/test_heading_detection.py -v
python -m pytest tests/test_ingestion_graph.py tests/test_chunker.py -v
```

### Explicit Non-Goals

- Do not use LLM calls for heading detection.
- Do not remove fixed-token chunking.
- Do not add summaries, multi-vector chunks, relation extraction, or hybrid search.

## Mandatory Batch05 - Retrieval Context Tuning

### Goal

Tune retrieval context expansion to prefer same-section neighbors and add richer citation metadata.

### Why this batch exists

Smart section chunks improve retrieval only if query context and citations expose useful section-aware metadata.

### Inputs / Dependencies

- Batch04 smart-section chunk metadata.
- Existing retrieval helpers and query graph.
- Existing source citation schema and frontend source list.

### Tasks

- [x] (05A): Add section-aware neighbor expansion
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 5: Retrieval Context Tuning` > `### Task 5.1: Add section-aware neighbor expansion`
  - Source Requirements:
    - Add settings `RETRIEVAL_CONTEXT_MODE=section_aware` and `RETRIEVAL_SECTION_SIBLING_WINDOW=1`.
    - Update `expand_neighbor_context`.
    - Always keep top reranked chunks first.
    - Add LLM-requested beginning/end boundary chunks when retrieval hints request them.
    - Add previous/next chunks that share `document_id` and `section_path`.
    - Add remaining previous/next chunks by `chunk_index`.
    - Deduplicate by `chunk_id`.
    - Do not exceed `RETRIEVAL_CONTEXT_MAX_CANDIDATES`.
    - Preserve current behavior when `RETRIEVAL_CONTEXT_MODE=neighbor`.
  - Details: Prefer context from the same document section while preserving existing neighbor expansion behavior as a mode.
  - Dependencies: Batch04 chunk metadata and existing retrieval tests.
  - User Action: None.
  - Agent Work: Add retrieval settings, implement section-aware ordering, preserve neighbor mode, and update query graph tests.
  - Specific Steps:
    1. Add settings to `backend/app/core/config.py`.
    2. Inspect `backend/app/services/retrieval.py` current neighbor expansion behavior.
    3. Preserve current behavior under `RETRIEVAL_CONTEXT_MODE=neighbor`.
    4. Add `section_aware` mode.
    5. In section-aware mode, add top reranked chunks to context first.
    6. Add retrieval-hint boundary chunks when requested.
    7. Add previous and next chunks that share both `document_id` and `section_path`.
    8. Add remaining previous and next chunks by `chunk_index`.
    9. Deduplicate by `chunk_id`.
    10. Enforce `RETRIEVAL_CONTEXT_MAX_CANDIDATES`.
    11. Mark added neighbor or boundary chunks so citation metadata can identify them in task (05B).
    12. Update `backend/tests/test_query_graph.py`.
  - Output: Section-aware retrieval context expansion.
  - Acceptance: Top reranked chunks stay first; same-section neighbors are preferred; boundary hints still work; context cap and deduplication hold.
  - Validation: `cd backend && python -m pytest tests/test_query_graph.py -v`
  - Blocked Condition: None.
  - Files: `backend/app/core/config.py`, `backend/app/services/retrieval.py`, `backend/tests/test_query_graph.py`

- [x] (05B): Add richer citation metadata
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 5: Retrieval Context Tuning` > `### Task 5.2: Add richer citation metadata`
  - Source Requirements:
    - Extend `SourceCitation` with optional `section_path`, `content_preview`, and `is_neighbor_context`.
    - Populate `section_path` from context chunks.
    - Populate `content_preview` with the first 240 characters of chunk content.
    - Populate `is_neighbor_context` when a context chunk was added by boundary or neighbor expansion.
    - Keep existing source citation fields unchanged.
    - Frontend accepts richer citation objects.
    - Existing source labels still match the Phase 1 citation format.
  - Details: Add optional metadata used by the source viewer without breaking existing source display.
  - Dependencies: Task (05A), existing `SourceCitation` schema, and frontend source list.
  - User Action: None.
  - Agent Work: Extend backend and frontend citation typing, populate optional fields, preserve display labels, and update tests/build.
  - Specific Steps:
    1. Extend backend `SourceCitation` in `backend/app/models/schemas.py`.
    2. Update `backend/app/graphs/query_nodes.py` source construction to include optional `section_path`.
    3. Add `content_preview` using the first 240 characters of chunk content.
    4. Set `is_neighbor_context` when the context chunk was added by boundary or neighbor expansion.
    5. Preserve existing fields: `document_id`, `chunk_id`, `file_name`, `chunk_index`, `page_start`, `page_end`, `heading`, `qdrant_score`, and `rerank_score`.
    6. Update `backend/tests/test_query_graph.py`.
    7. Extend frontend source citation type in `frontend/src/api/types.ts`.
    8. Update `frontend/src/components/SourceList.tsx` only as needed to accept the richer object while preserving labels.
  - Output: Richer source citation metadata across backend and frontend.
  - Acceptance: Backend source citation tests pass; frontend build accepts richer objects; existing source labels remain Phase 1 compatible.
  - Validation: `cd backend && python -m pytest tests/test_query_graph.py -v`; then `cd frontend && npm run build`
  - Blocked Condition: None.
  - Files: `backend/app/models/schemas.py`, `backend/app/graphs/query_nodes.py`, `backend/tests/test_query_graph.py`, `frontend/src/api/types.ts`, `frontend/src/components/SourceList.tsx`

### Files or Modules Likely Created or Updated

- `backend/app/core/config.py`
- `backend/app/services/retrieval.py`
- `backend/app/models/schemas.py`
- `backend/app/graphs/query_nodes.py`
- `backend/tests/test_query_graph.py`
- `frontend/src/api/types.ts`
- `frontend/src/components/SourceList.tsx`

### Required Outputs / Artifacts

- Section-aware retrieval context mode.
- Retrieval section sibling window setting.
- Rich source citation metadata.
- Backend query graph tests.
- Frontend build validation.

### Acceptance Criteria

- Top reranked chunks remain first in context.
- Same-section neighbors are preferred before generic neighbors.
- Boundary hint chunks are still included when requested.
- Context never exceeds the configured cap.
- Duplicate chunks are removed.
- Source citations include optional `section_path`, `content_preview`, and `is_neighbor_context`.
- Existing source citation labels remain unchanged.

### Required Tests or Validations

```powershell
cd backend
python -m pytest tests/test_query_graph.py -v
cd ..\frontend
npm run build
```

### Explicit Non-Goals

- Do not add query decomposition, relation graph expansion, or grounding verification.
- Do not change the rule that answers use only retrieved context.
- Do not remove Jina fallback behavior.

## Mandatory Batch06 - Documentation and End-to-End Validation

### Goal

Document Phase 2 behavior, run full automated validation, and perform the manual Phase 2 smoke test.

### Why this batch exists

Phase 2 is not complete until docs reflect the new behavior and both automated and browser-level flows have been validated.

### Inputs / Dependencies

- Batches 01 through 05 completed.
- Local backend and frontend environments.
- User-provided external service credentials and live setup for manual smoke validation.

### Tasks

- [ ] (06A): Update local documentation
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 6: Documentation and End-to-End Validation` > `### Task 6.1: Update local documentation`
  - Source Requirements:
    - Update `README.md`.
    - Update `backend/README.md`.
    - Document `CHUNKING_STRATEGY`, `HEADER_SCORE_THRESHOLD`, `TABLE_CHUNK_MAX_TOKENS`, `RETRIEVAL_CONTEXT_MODE`, and `RETRIEVAL_SECTION_SIBLING_WINDOW`.
    - Document HTML parser support.
    - Document source viewer and message history behavior.
    - Document that existing documents should be re-indexed to receive smart section metadata.
  - Details: Bring repository documentation in line with Phase 2 implementation.
  - Dependencies: Completed implementation in Batches 01 through 05.
  - User Action: None.
  - Agent Work: Update user-facing documentation without adding unsupported features or leaking secrets.
  - Specific Steps:
    1. Update `README.md` current progress to include Phase 2 behavior after it is implemented.
    2. Add or update validation commands to include new tests.
    3. Update `backend/README.md` environment variable documentation.
    4. Document HTML upload and parser support.
    5. Document source viewer behavior.
    6. Document message history behavior.
    7. Document re-indexing requirement for existing documents to receive smart section metadata.
    8. Keep secret examples as placeholders only.
  - Output: Updated README documentation.
  - Acceptance: Documentation reflects implemented Phase 2 behavior and settings without adding unsupported claims.
  - Validation: Review changed docs for accuracy against implemented behavior and the Phase 2 plan.
  - Blocked Condition: None.
  - Files: `README.md`, `backend/README.md`

- [ ] (06B): Run full automated verification
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 6: Documentation and End-to-End Validation` > `### Task 6.2: Run full automated verification`
  - Source Requirements:
    - Run the listed backend tests.
    - Run the frontend production build.
    - All backend tests pass.
    - Frontend production build passes.
  - Details: Validate the complete Phase 2 automated test surface.
  - Dependencies: Task (06A) and completed implementation.
  - User Action: None.
  - Agent Work: Run the required backend pytest command and frontend build command, then report exact results.
  - Specific Steps:
    1. Run the full backend test command from the source plan.
    2. If tests fail, use systematic debugging to identify the cause before changing code.
    3. Re-run affected tests after any fix.
    4. Run the frontend production build.
    5. Record commands and outcomes in the batch completion report.
  - Output: Automated validation results.
  - Acceptance: Full backend test list passes and frontend build passes.
  - Validation: `cd backend && python -m pytest tests/test_config.py tests/test_hashing.py tests/test_validation.py tests/test_api_documents.py tests/test_api_messages.py tests/test_parsers.py tests/test_chunker.py tests/test_heading_detection.py tests/test_ingestion_graph.py tests/test_query_graph.py tests/test_api_chat.py -v`; then `cd frontend && npm run build`
  - Blocked Condition: None.
  - Files: No new files expected.

- [ ] (06C): Run manual Phase 2 smoke test
  - Source of Truth: `docs/plans/Plan_2.md` > `## Batch 6: Documentation and End-to-End Validation` > `### Task 6.3: Run manual Phase 2 smoke test`
  - Source Requirements:
    - Start backend with `uvicorn app.main:app --reload --port 8000`.
    - Start frontend with `npm run dev -- --host 127.0.0.1 --port 5173`.
    - Verify Markdown smart-section ingestion with headings and a table.
    - Confirm ready status, table-grounded answer, source citations, source viewer metadata, and scores.
    - Ask a second question with `save_message=true`.
    - Refresh message history and restore the saved answer without resending the question.
    - Upload, index, query, and inspect an HTML document.
  - Details: Manually validate the end-to-end Phase 2 user workflow in the browser.
  - Dependencies: Task (06B), running backend/frontend, and live external services.
  - User Action: User must provide valid local environment values for Supabase, Qdrant, ShopAIKey, Jina if reranking is enabled, storage bucket setup, database schema, and any required service availability. The agent must not create or reveal real secrets.
  - Agent Work: Start local services, exercise the browser flows, collect safe validation results, and stop only after sessions are no longer needed.
  - Specific Steps:
    1. Confirm required local `.env` values are present without printing secret values.
    2. Start backend from `backend` with `uvicorn app.main:app --reload --port 8000`.
    3. Start frontend from `frontend` with `npm run dev -- --host 127.0.0.1 --port 5173`.
    4. Open `http://127.0.0.1:5173`.
    5. Upload a Markdown file containing headings and a table.
    6. Index the document with `CHUNKING_STRATEGY=smart_section`.
    7. Confirm document status becomes ready.
    8. Ask a question answered by the table.
    9. Confirm the answer includes source citations.
    10. Select a source and confirm the source viewer shows chunk content, heading, section path, and scores.
    11. Ask a second question with message saving enabled.
    12. Refresh message history and select the saved message.
    13. Confirm saved answer and sources restore without a new chat request.
    14. Upload an HTML file with headings and visible text.
    15. Index the HTML document.
    16. Ask a question answered by the HTML document.
    17. Confirm sources are shown and can be inspected.
    18. Record safe observations and any failures in the completion report.
  - Output: Manual smoke validation result.
  - Acceptance: The app completes smart-section Markdown ingestion, table-grounded chat, source inspection, message history restore, and HTML ingestion.
  - Validation: Manual browser smoke test described above.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if required live credentials, Supabase schema/storage, Qdrant collection, or provider access are missing.
  - Files: No new files expected.

### Files or Modules Likely Created or Updated

- `README.md`
- `backend/README.md`

### Required Outputs / Artifacts

- Updated local documentation.
- Full backend test result.
- Frontend build result.
- Manual smoke test result or safe blocked-by-user report.

### Acceptance Criteria

- New settings and Phase 2 behavior are documented.
- Existing documents re-index requirement is documented.
- Full backend automated verification passes.
- Frontend build passes.
- Manual smoke test validates smart-section Markdown ingestion, table-grounded chat, source inspection, message history restore, and HTML ingestion.

### Required Tests or Validations

```powershell
cd backend
python -m pytest tests/test_config.py tests/test_hashing.py tests/test_validation.py tests/test_api_documents.py tests/test_api_messages.py tests/test_parsers.py tests/test_chunker.py tests/test_heading_detection.py tests/test_ingestion_graph.py tests/test_query_graph.py tests/test_api_chat.py -v
cd ..\frontend
npm run build
```

Manual validation:

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### Explicit Non-Goals

- Do not claim manual smoke completion when live credentials or service setup are missing.
- Do not print or commit secret values.
- Do not add unsupported Phase 3 features during final validation.

## Optional Future Tracks

The following tracks are not part of the mandatory MVP Phase 2 batch chain:

- Query decomposition.
- LLM-based chunk relationship extraction.
- `document_relations` table.
- Relation graph expansion.
- Grounding verification.
- Hybrid search.
- OCR.
- PPTX support.
- Image/chart captioning.
- Document summaries.
- Section summaries.
- Multi-vector chunks.
- RAG evaluation dataset.
- Retrieval quality metrics.
- Answer faithfulness metrics.

These items appear in `docs/plans/Master_Plan.md` as Phase 3 or future work and must not be implemented as part of this task file.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04
- Batch04 -> Batch05
- Batch05 -> Batch06

Optional future tracks are outside the mandatory chain.

## Global Verification Checklist

- [ ] Batch01 backend chunk and message contract tests pass.
- [ ] Batch02 frontend build passes.
- [ ] Batch03 parser and validation tests pass.
- [ ] Batch04 heading detection, chunker, and ingestion tests pass.
- [ ] Batch05 query graph tests and frontend build pass.
- [ ] Batch06 full backend test list passes.
- [ ] Batch06 frontend production build passes.
- [ ] Manual Phase 2 smoke test passes or is reported as `BLOCKED_BY_USER_ACTION` with a safe reason.
- [ ] Existing Phase 1 upload, indexing, reindex, delete, chat, retrieval, and source citation behavior is preserved.
- [ ] No excluded authentication, multi-user, relation graph, OCR, PPTX, hybrid search, summary, multi-vector, or autonomous-agent features are introduced.
- [ ] Backend-only secrets remain backend-only and are never logged, committed, or exposed to frontend code.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [ ] Batch01 - Backend Source and Message Contracts
- [ ] Batch02 - Frontend Source Viewer and Message History
- [ ] Batch03 - Structured Parsing and HTML Support
- [ ] Batch04 - Header Scoring and Smart Section Chunking
- [ ] Batch05 - Retrieval Context Tuning
- [ ] Batch06 - Documentation and End-to-End Validation

### Task IDs

#### Batch01

- [x] (01A): Add typed chunk inspection responses
- [x] (01B): Add message history service and API

#### Batch02

- [x] (02A): Extend frontend API client and types
- [x] (02B): Build source chunk viewer panel
- [x] (02C): Build message history panel

#### Batch03

- [x] (03A): Add parsed block structure
- [x] (03B): Emit structure from existing parsers
- [x] (03C): Add HTML upload validation and parser

#### Batch04

- [x] (04A): Add deterministic header scoring
- [x] (04B): Add smart section chunker
- [x] (04C): Integrate chunking strategy into ingestion

#### Batch05

- [x] (05A): Add section-aware neighbor expansion
- [x] (05B): Add richer citation metadata

#### Batch06

- [ ] (06A): Update local documentation
- [ ] (06B): Run full automated verification
- [ ] (06C): Run manual Phase 2 smoke test

## Completion Reporting Rules for Future Execution Agents

### BatchXX Execution Result

#### Completed Task IDs

- (XXA): complete / partial / blocked

#### Files Created or Modified

- path

#### Tests or Validations Run

- command: result

#### User Actions Required

- action: completed / pending / not required
- details: safe summary only, never include secrets

#### Blocked-by-User Status

- status: none / BLOCKED_BY_USER_ACTION
- reason: missing API key, missing provider project, missing manual setup, or other safe summary

#### Validation Responsibility

- user-provided setup confirmed: yes / no / not required
- agent validation run after setup: yes / no
- validation command: result

#### Acceptance Criteria Check

- criterion: satisfied / not satisfied / blocked

#### Artifacts Produced

- artifact

#### Progress Tracker Update

- task IDs updated

#### Key Implementation Decisions

- decision

#### Risks or Open Issues

- issue

#### Notes for Next Batch

- handoff notes
