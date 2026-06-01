# Plan 4 - Document Parsing and Chunking

## 1. Goal

Implement parsing for PDF, DOCX, TXT, and CSV files, split parsed content into chunks, persist chunks in Supabase PostgreSQL, and update document processing status and chunk count.

The goal is testable when each supported file type can be parsed into non-empty chunks with metadata and empty or unreadable documents fail with a clear status and error message.

## 2. Why This Plan Exists

Embeddings, retrieval, GraphRAG, and agents work on chunks, not raw files. This plan converts uploaded files into durable chunk records while preserving document, page, section, and row metadata needed for citations and scoring.

## 3. Scope

- Add parser implementations for PDF, DOCX, TXT, and CSV.
- Add a common parsed document structure.
- Add recursive chunking service.
- Preserve metadata: document ID, file name, page number, section title, chunk index, token count, and CSV row information.
- Insert chunk rows into `document_chunks`.
- Update `documents.chunk_count`.
- Update document status through `processing`, `ready`, or `failed`.
- Add a backend processing function that can be called after upload or manually in tests.
- Add parser and chunking tests with local fixture files.

## 4. Out of Scope

- Do not generate embeddings.
- Do not create Qdrant vectors.
- Do not extract entities or relationships.
- Do not run GraphRAG.
- Do not run retrieval or agents.
- Do not add frontend processing status polling beyond APIs already available.
- Do not support OCR or image-based scanned documents.

## 5. Dependencies

- Plan 1 must be completed.
- Plan 2 must be completed.
- Plan 3 must be completed.
- Uploaded files must exist in Supabase Storage.

## 6. Required Files and Folders

```text
backend/app/services/document_parser.py
- Dispatches parser implementation by file type and returns parsed sections.

backend/app/services/chunking_service.py
- Splits parsed text into chunk records with overlap and token estimates.

backend/app/services/document_processing_service.py
- Orchestrates status updates, storage download, parsing, chunking, chunk insert, and final status update.

backend/app/services/supabase_service.py
- Add helpers for downloading original files, inserting chunks, and updating document status/count.

backend/app/schemas/parsing.py
- Contains ParsedSection and ChunkDraft Pydantic models.

backend/app/api/documents.py
- Optionally call processing after upload, or expose an internal/manual processing route only if needed for development.

backend/tests/fixtures/sample.pdf
- Small PDF fixture with extractable text.

backend/tests/fixtures/sample.docx
- Small DOCX fixture with paragraphs/headings.

backend/tests/fixtures/sample.txt
- Small TXT fixture.

backend/tests/fixtures/sample.csv
- Small CSV fixture with headers and several rows.

backend/tests/test_document_parser.py
- Tests parser outputs for each file type.

backend/tests/test_chunking_service.py
- Tests chunk sizing, overlap, metadata, and empty text behavior.

backend/tests/test_document_processing.py
- Tests processing orchestration with mocked Supabase storage/database.

backend/requirements.txt
- Add parsing dependencies.
```

## 7. Data Model / Schema Changes

No database table changes in this plan.

Use the existing `document_chunks` table.

Chunk insert shape:

```json
{
  "document_id": "uuid",
  "user_id": "single_user",
  "chunk_index": 0,
  "content": "Extracted chunk text",
  "page_number": 1,
  "section_title": "Employment Terms",
  "token_count": 214,
  "qdrant_point_id": null
}
```

Parsed section shape:

```json
{
  "text": "Section text",
  "page_number": 1,
  "section_title": "Section heading",
  "metadata": {
    "source_type": "pdf"
  }
}
```

CSV text conversion rule:

```text
Each row or row group must become readable text that includes column names.
Example:
Row 12:
Name: Nguyen Van A
Start Date: 2026-06-01
Probation Period: 2 months
Official Work Date: 2026-08-01
```

Document status updates:

```text
uploaded -> processing -> ready
uploaded -> processing -> failed
```

## 8. API Design

No required new public API endpoints in this plan.

If processing is triggered from upload:

```text
POST /api/documents/upload still returns:
{
  "document_id": "uuid",
  "file_name": "contract.pdf",
  "status": "uploaded"
}
```

The processing function may run synchronously during development or through FastAPI background tasks. If background tasks are used, document status must change to `processing` before the upload response is returned or immediately after task start.

Optional development-only endpoint if needed:

```text
Method: POST
Path: /api/documents/{document_id}/process
Request body: none
Response body:
{
  "document_id": "uuid",
  "status": "ready",
  "chunk_count": 12
}
Error responses:
- 404 document not found for SINGLE_USER_ID
- 400 document is already ready
- 500 parser or storage failure
```

## 9. Implementation Steps

1. Add parser dependencies to `backend/requirements.txt`: `pypdf` or `pymupdf`, `python-docx`, and any tokenizer helper chosen by the codebase.
2. Create `ParsedSection` and `ChunkDraft` models in `backend/app/schemas/parsing.py`.
3. Implement `parse_document(file_bytes, file_type, file_name)` in `document_parser.py`.
4. Implement PDF parsing with page-level metadata; each extracted page becomes one or more parsed sections.
5. Implement DOCX parsing with paragraph text and best-effort heading detection from paragraph styles.
6. Implement TXT parsing with UTF-8 first and a safe fallback encoding if needed.
7. Implement CSV parsing with Python `csv` or pandas; convert rows into readable text with column names and row indexes.
8. If parsed text is empty after trimming whitespace, raise `EmptyDocumentError`.
9. Implement `chunk_sections(sections, chunk_size, chunk_overlap)` in `chunking_service.py`.
10. Use configurable chunk size and overlap; default to `1000` tokens and `150` token overlap.
11. Preserve source metadata on each chunk.
12. Estimate token count consistently, even if using a simple word-based approximation in MVP.
13. Implement `process_document(document_id)` in `document_processing_service.py`.
14. In processing, load the document row filtered by `SINGLE_USER_ID`.
15. Update status to `processing` before parsing.
16. Download original file bytes from Supabase Storage.
17. Parse, chunk, and bulk insert chunk rows.
18. Update `documents.chunk_count` and status `ready` on success.
19. On failure, set status `failed` and write `error_message`.
20. Add tests for each parser, chunk overlap, empty documents, and status transitions.

## 10. Configuration and Environment Variables

```text
CHUNK_SIZE_TOKENS
- Purpose: Target chunk size.
- Required: No.
- Example: 1000
- Scope: Backend-only.

CHUNK_OVERLAP_TOKENS
- Purpose: Token overlap between adjacent chunks.
- Required: No.
- Example: 150
- Scope: Backend-only.

SINGLE_USER_ID
- Purpose: Filters the document being processed and owns inserted chunks.
- Required: Yes.
- Example: single_user
- Scope: Backend-only.

SUPABASE_STORAGE_BUCKET
- Purpose: Download original uploaded file.
- Required: Yes.
- Example: documents
- Scope: Backend-only.
```

## 11. Required Tests

Parser tests:

```text
cd backend
pytest tests/test_document_parser.py -v
```

Chunking tests:

```text
cd backend
pytest tests/test_chunking_service.py -v
```

Processing tests:

```text
cd backend
pytest tests/test_document_processing.py -v
```

Manual API/storage check:

```text
Upload a TXT file through /api/documents/upload.
Run the processing function or endpoint.
Call GET /api/documents/{document_id}.
Confirm status is ready and chunk_count is greater than 0.
```

Negative checks:

```text
Process an empty TXT file and expect documents.status = failed.
Process an unsupported file type only if a bad row exists and expect a clear error.
```

## 12. Acceptance Criteria

- PDF text is extracted with page numbers when possible.
- DOCX text is extracted.
- TXT text is extracted.
- CSV rows are converted into readable text with column names.
- Chunks are inserted into `document_chunks`.
- Chunk rows include `document_id`, `user_id`, `chunk_index`, `content`, `token_count`, and available metadata.
- `documents.chunk_count` equals inserted chunk count.
- Successful processing sets document status to `ready`.
- Empty or unreadable documents set status to `failed` with `error_message`.
- No embeddings, Qdrant, GraphRAG, retrieval, or agents are implemented.

## 13. Failure Handling

- Missing storage object sets document status to `failed`.
- Parser exception sets document status to `failed` and stores a safe error message.
- Empty parsed document sets status to `failed`.
- Chunk insert failure sets status to `failed`.
- Unsupported file type should normally be blocked in Plan 3; if encountered, processing fails clearly.
- CSV decoding failure returns a parser error that identifies the file as CSV.

## 14. Agent Report Requirement

The Execution Agent must report:

```text
Files created
Files modified
Commands run
Test results
Known issues
What was intentionally not implemented because it is out of scope
```

The report must include parser test results for PDF, DOCX, TXT, and CSV.

## 15. Reviewer Checklist

The Reviewer Agent must verify:

```text
Scope was followed
Out-of-scope work was not added
Tests were actually run
Acceptance criteria passed
No hardcoded secrets
No fake success
Architecture still matches docs/plans/Master_Plan.md
```

Extra checks:

- Confirm OCR is not implemented.
- Confirm every inserted chunk uses `SINGLE_USER_ID`.
- Confirm chunk index order is deterministic.
- Confirm failed processing does not leave document status stuck at `processing`.
