# Plan 4 - Document Parsing and Chunking Execution Tasks

## Purpose

Create a detailed execution task file for the approved document parsing and chunking milestone. This task file guides a future Execution Agent to parse PDF, DOCX, TXT, and CSV files, split parsed content into metadata-preserving chunks, persist chunk rows in Supabase PostgreSQL, update document status and chunk count, and validate the behavior required by `docs/plans/Plan_4.md`.

## Authoritative Source

- Primary source: `docs/plans/Plan_4.md`
- Clarification source reviewed: `docs/plans/Master_Plan.md`
- Conflict note: `docs/plans/Master_Plan.md` describes the broader upload pipeline as eventually generating embeddings, storing Qdrant vectors, building GraphRAG metadata, and running retrieval agents. `docs/plans/Plan_4.md` explicitly excludes embeddings, Qdrant, GraphRAG, retrieval, agents, frontend polling, OCR, and image-based scanned document support. `docs/plans/Plan_4.md` is the scope authority for this task file.

## Source Section Index

- `docs/plans/Plan_4.md` > `## 1. Goal` -> parse supported files, create non-empty chunks, persist metadata, and fail empty or unreadable documents clearly.
- `docs/plans/Plan_4.md` > `## 2. Why This Plan Exists` -> chunks are prerequisites for embeddings, retrieval, GraphRAG, and citations.
- `docs/plans/Plan_4.md` > `## 3. Scope` -> parser implementations, parsed structure, recursive chunking, metadata preservation, chunk insert, status updates, processing function, and tests.
- `docs/plans/Plan_4.md` > `## 4. Out of Scope` -> prohibited embeddings, Qdrant, GraphRAG, retrieval, agents, frontend polling, OCR, and scanned document support.
- `docs/plans/Plan_4.md` > `## 5. Dependencies` -> Plan 1, Plan 2, Plan 3, and uploaded Supabase Storage files.
- `docs/plans/Plan_4.md` > `## 6. Required Files and Folders` -> expected parser, chunking, processing, Supabase, schema, API, fixture, test, and dependency files.
- `docs/plans/Plan_4.md` > `## 7. Data Model / Schema Changes` -> no table changes, chunk insert shape, parsed section shape, CSV row text rule, and status transitions.
- `docs/plans/Plan_4.md` > `## 8. API Design` -> no required public endpoint, optional upload/background/manual processing trigger, and optional development process endpoint contract.
- `docs/plans/Plan_4.md` > `## 9. Implementation Steps` -> ordered parser, chunking, processing, persistence, status, and test implementation details.
- `docs/plans/Plan_4.md` > `## 10. Configuration and Environment Variables` -> `CHUNK_SIZE_TOKENS`, `CHUNK_OVERLAP_TOKENS`, `SINGLE_USER_ID`, and `SUPABASE_STORAGE_BUCKET`.
- `docs/plans/Plan_4.md` > `## 11. Required Tests` -> parser, chunking, processing, manual API/storage, and negative checks.
- `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria` -> required parser, chunk insert, chunk count, status, and out-of-scope completion criteria.
- `docs/plans/Plan_4.md` > `## 13. Failure Handling` -> missing storage object, parser failure, empty document, chunk insert failure, unsupported type, and CSV decoding failure behavior.
- `docs/plans/Plan_4.md` > `## 14. Agent Report Requirement` -> required execution report fields and parser test results for each file type.
- `docs/plans/Plan_4.md` > `## 15. Reviewer Checklist` -> scope, tests, acceptance, secrets, architecture, OCR, `SINGLE_USER_ID`, deterministic chunk order, and failed-status checks.
- `docs/plans/Master_Plan.md` > `## 2. Tech Stack` -> Python, FastAPI, LangChain, Pydantic, Supabase Storage, and Supabase PostgreSQL are approved.
- `docs/plans/Master_Plan.md` > `## 3. Authentication Policy` -> single-user MVP and backend-only private secrets.
- `docs/plans/Master_Plan.md` > `## 4. Supported Document Types` -> PDF, DOCX, TXT, and CSV support; no OCR in MVP.
- `docs/plans/Master_Plan.md` > `## 6. Data Storage Design` > `### 6.1 Supabase Storage` -> original uploaded files are stored in Supabase Storage.
- `docs/plans/Master_Plan.md` > `## 6. Data Storage Design` > `## Table: document_chunks` -> chunk metadata fields stored in Supabase PostgreSQL.
- `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.2 Parsing Flow` -> parser choices and CSV row text preservation.
- `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.3 Chunking Strategy` -> recursive text splitting and chunk metadata preservation.
- `docs/plans/Master_Plan.md` > `# 15. Environment Variables` -> backend-only variable names and frontend secret boundary.
- `docs/plans/Master_Plan.md` > `## Phase 3: Parsing and Chunking` -> phase alignment and acceptance criteria.

## Approved Architecture Summary

The approved architecture for this plan is a backend-only parsing and chunking pipeline for the single-user Document QA Agent MVP. Uploaded originals already exist in Supabase Storage from Plan 3. The backend loads a `documents` row filtered by `SINGLE_USER_ID`, changes its status to `processing`, downloads the original file bytes, dispatches parsing by file type, converts parsed sections into recursive text chunks, inserts chunk rows into the existing `document_chunks` table, updates `documents.chunk_count`, and marks the document `ready`. If storage, parsing, empty content, chunking, or chunk insertion fails, the backend must mark the document `failed` and store a safe `error_message`.

No database table changes are approved in this plan. PDF parsing must preserve page numbers when possible. DOCX parsing must extract paragraph text and best-effort headings. TXT parsing must try UTF-8 first and use a safe fallback when needed. CSV parsing must convert rows or row groups into readable text that includes column names and row indexes. Chunk rows must include the document ID, `SINGLE_USER_ID`, deterministic chunk index, content, token count, available page/section metadata, and `qdrant_point_id = null`. This milestone does not generate embeddings, create Qdrant vectors, extract graph entities, build relationships, run retrieval or agents, add OCR, or add frontend status polling.

## Global Implementation Rules

- Keep `docs/plans/Plan_4.md` as the source of truth for scope, validation, and out-of-scope boundaries.
- Depend on completed Plan 1, Plan 2, and Plan 3 work; do not reimplement the backend foundation, Supabase schema foundation, or upload metadata APIs unless integration requires a narrow change.
- Do not create or alter database tables; use the existing `documents` and `document_chunks` tables.
- Do not generate embeddings, create Qdrant points, set `qdrant_point_id` to a fake value, extract entities, build GraphRAG relationships, run retrieval, run agents, implement OCR, or add frontend polling.
- Keep `SINGLE_USER_ID`, Supabase service-role credentials, storage bucket names, parser configuration, and chunking configuration backend-only.
- Use `.env.example` for placeholder names only and never commit real secrets.
- Always filter document lookup and chunk inserts by `SINGLE_USER_ID`.
- Update document status to `processing` before parsing starts, `ready` only after chunks are inserted and `chunk_count` is updated, and `failed` with a safe error message on any processing failure.
- Do not leave a document stuck at `processing` when processing fails.
- Make chunk indexes deterministic and sequential for a document processing run.
- Do not claim live Supabase or manual API validation passed unless local credentials, bucket, document rows, and uploaded storage objects were available and the validation was actually run.
- Future Execution Agents must update this task file progress tracker only after validations pass or a blocked condition is documented.

## Execution Agent Coding Style Requirements

- Write clean, idiomatic, readable code that a later maintainer can understand quickly.
- Use descriptive names for modules, functions, variables, settings, routes, schemas, parser helpers, and tests.
- Keep functions, services, parser implementations, and modules focused on one clear responsibility.
- Prefer simple, explicit control flow over clever abstractions.
- Follow standard FastAPI, Pydantic, pytest, Supabase Python client, Python parser library, and text-processing conventions for the approved stack.
- Use clear Python typing where the stack supports it.
- Avoid `any`, broad exception handling, hidden global state, and hardcoded configuration values unless the plan explicitly requires them.
- Add comments only where they clarify a non-obvious decision or behavior.
- Keep frontend code free of backend-only secrets and backend-only configuration names.
- Do not add formatter, linter, framework, or architecture changes outside Plan 4 unless they are already present in the project or explicitly requested.

## Batch Map

- Batch01 - Parser Schemas, Dependencies, and File-Type Implementations
- Batch02 - Chunking Configuration and Metadata-Preserving Splitter
- Batch03 - Supabase Chunk Persistence and Processing Orchestration
- Batch04 - Tests, Manual Validation, and Handoff

## Mandatory Batch01 - Parser Schemas, Dependencies, and File-Type Implementations

### Goal

Create the backend parser foundation that converts supported file bytes into typed parsed sections with source metadata and clear parser failure behavior.

### Why this batch exists

Chunking and processing cannot be implemented safely until each supported document type can produce a consistent parsed section structure and empty or unreadable files fail with an explicit parser outcome.

### Inputs / Dependencies

- `docs/plans/Plan_4.md`
- Completed Plan 1 backend foundation
- Completed Plan 3 upload metadata and storage path behavior
- Existing backend dependency and test patterns

### Tasks

- [x] (01A): Add parser dependencies and fixture-friendly setup
  - Source of Truth: `docs/plans/Plan_4.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.2 Parsing Flow`
  - Source Requirements:
    - Add parser dependencies to `backend/requirements.txt`.
    - Use `pypdf` or `pymupdf` for PDF parsing.
    - Use `python-docx` for DOCX parsing.
    - Use Python `csv` or pandas for CSV parsing.
  - Details: Add the minimal parser dependencies needed for extractable PDF text, DOCX paragraphs/headings, TXT decoding, and CSV reading. Choose between `pypdf` and `pymupdf` based on the existing project style and reliable local test support, then record the choice in the execution report.
  - Dependencies: Completed Plan 1 backend dependency workflow.
  - User Action: None.
  - Agent Work: Update backend dependency declarations without adding embedding, Qdrant, OCR, or frontend packages.
  - Output: Backend dependency file includes parsing libraries required by this milestone.
  - Acceptance: Parser modules and parser tests can import required libraries in the backend test environment.
  - Validation: `cd backend` then run parser import or parser tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/requirements.txt`

- [x] (01B): Add parsed section and chunk draft schemas
  - Source of Truth: `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_4.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`
  - Source Requirements:
    - Add a common parsed document structure.
    - Create `ParsedSection` and `ChunkDraft` Pydantic models.
    - Preserve page number, section title, metadata, chunk index, and token count fields.
  - Details: Define parser and chunk draft models that are shared by parser, chunking, and processing services. Include enough metadata to carry source type, CSV row information, file name, page number, section title, and chunk ordering into chunk insert rows.
  - Dependencies: Completed Plan 1 schema package layout.
  - User Action: None.
  - Agent Work: Create `backend/app/schemas/parsing.py` and export models using the existing schemas package style.
  - Output: Typed `ParsedSection` and `ChunkDraft` models importable by services and tests.
  - Acceptance: Models represent the parsed section shape and chunk draft data needed for insertion into `document_chunks`.
  - Validation: Run backend parser and chunking tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/schemas/parsing.py`, `backend/app/schemas/__init__.py`

- [x] (01C): Implement parser dispatch and parser errors
  - Source of Truth: `docs/plans/Plan_4.md` > `## 1. Goal`; `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Implement `parse_document(file_bytes, file_type, file_name)`.
    - Dispatch parser implementation by file type.
    - If parsed text is empty after trimming whitespace, raise `EmptyDocumentError`.
    - Unsupported file type should fail clearly if encountered.
  - Details: Create a parser service with a single public dispatch function and explicit parser exception types for empty, unsupported, unreadable, and decoding failures. Keep public error messages safe and avoid logging raw file contents.
  - Dependencies: (01B)
  - User Action: None.
  - Agent Work: Implement parser dispatch and common error handling in `backend/app/services/document_parser.py`.
  - Output: Parser service entrypoint and parser error types.
  - Acceptance: Supported types route to the correct parser; empty or unsupported documents raise clear parser errors.
  - Validation: `cd backend` then `pytest tests/test_document_parser.py -v` in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/services/document_parser.py`

- [x] (01D): Implement PDF, DOCX, and TXT parsers
  - Source of Truth: `docs/plans/Plan_4.md` > `## 1. Goal`; `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.2 Parsing Flow`
  - Source Requirements:
    - PDF text is extracted with page numbers when possible.
    - DOCX text is extracted.
    - DOCX parsing uses paragraph text and best-effort heading detection from paragraph styles.
    - TXT parsing uses UTF-8 first and a safe fallback encoding if needed.
  - Details: Implement extractable-text parsing for PDF pages, DOCX paragraphs/headings, and TXT file bytes. Preserve file name, source type, page number when available, and section title when detected.
  - Dependencies: (01A), (01B), (01C)
  - User Action: None.
  - Agent Work: Add focused parser helpers under `document_parser.py` or adjacent private helpers following the existing service style.
  - Output: PDF, DOCX, and TXT files produce non-empty `ParsedSection` objects when extractable text exists.
  - Acceptance: Parser tests prove non-empty parsed sections for sample PDF, DOCX, and TXT fixtures; empty text fails with `EmptyDocumentError`.
  - Validation: `cd backend` then `pytest tests/test_document_parser.py -v` in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/services/document_parser.py`, `backend/tests/fixtures/sample.pdf`, `backend/tests/fixtures/sample.docx`, `backend/tests/fixtures/sample.txt`

- [x] (01E): Implement CSV parser with row metadata
  - Source of Truth: `docs/plans/Plan_4.md` > `## 1. Goal`; `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_4.md` > `## 13. Failure Handling`; `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.2 Parsing Flow`
  - Source Requirements:
    - CSV rows are converted into readable text with column names.
    - Each row or row group must include row indexes and column names.
    - CSV decoding failure returns a parser error that identifies the file as CSV.
    - Preserve CSV row information in metadata.
  - Details: Implement CSV parsing using Python `csv` or pandas. Convert each row or row group into readable text like `Row 12:` followed by `Column: value` lines. Preserve row index information in the section metadata so chunk records can be traced back to CSV rows.
  - Dependencies: (01A), (01B), (01C)
  - User Action: None.
  - Agent Work: Add CSV parser helper and parser tests with a small fixture containing headers and several rows.
  - Output: CSV files produce readable parsed sections with row metadata.
  - Acceptance: Parser tests prove CSV output includes column names, row indexes, source type, and non-empty text.
  - Validation: `cd backend` then `pytest tests/test_document_parser.py -v` in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/services/document_parser.py`, `backend/tests/fixtures/sample.csv`

### Files or Modules Likely Created or Updated

- `backend/requirements.txt`
- `backend/app/schemas/parsing.py`
- `backend/app/schemas/__init__.py`
- `backend/app/services/document_parser.py`
- `backend/tests/fixtures/sample.pdf`
- `backend/tests/fixtures/sample.docx`
- `backend/tests/fixtures/sample.txt`
- `backend/tests/fixtures/sample.csv`

### Required Outputs / Artifacts

- Parser dependencies installed through the backend dependency workflow.
- `ParsedSection` and `ChunkDraft` schema models.
- Parser dispatch entrypoint and parser exception types.
- PDF, DOCX, TXT, and CSV parser implementations.
- Local fixture files for parser tests.

### Acceptance Criteria

- PDF text is extracted with page numbers when possible.
- DOCX text is extracted and heading information is preserved when available.
- TXT text is extracted with UTF-8-first decoding and safe fallback behavior.
- CSV rows are converted into readable text with column names and row indexes.
- Empty parsed content raises a clear empty-document parser error.
- Unsupported file types fail clearly if encountered during processing.
- No embeddings, Qdrant calls, GraphRAG, retrieval, agents, OCR, or frontend changes are added.

### Required Tests or Validations

- Parser import validation after dependencies are installed.
- `cd backend`
- `pytest tests/test_document_parser.py -v`
- Scope inspection confirming parser dependencies do not include OCR or unrelated pipeline packages.

### Explicit Non-Goals

- Do not parse scanned PDF images with OCR.
- Do not generate embeddings or Qdrant vectors.
- Do not create graph entities or relationships.
- Do not add frontend document processing UI.
- Do not modify database schema.

## Mandatory Batch02 - Chunking Configuration and Metadata-Preserving Splitter

### Goal

Implement configurable recursive chunking that converts parsed sections into deterministic chunk drafts with overlap, token estimates, and source metadata.

### Why this batch exists

Downstream embeddings, retrieval, citations, and processing status depend on durable chunks that preserve document position, page, section, file, and CSV row context.

### Inputs / Dependencies

- Batch01 parser schemas and parsed section outputs
- Existing backend configuration pattern
- Approved chunk settings from Plan 4

### Tasks

- [ ] (02A): Add backend chunking configuration
  - Source of Truth: `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.3 Chunking Strategy`
  - Source Requirements:
    - Use configurable chunk size and overlap.
    - Default chunk size is `1000` tokens.
    - Default chunk overlap is `150` tokens.
    - `CHUNK_SIZE_TOKENS` and `CHUNK_OVERLAP_TOKENS` are backend-only and optional.
  - Details: Extend backend settings and env examples with optional chunk size and overlap values. Validate values enough to prevent nonsensical overlap greater than or equal to chunk size.
  - Dependencies: Completed Plan 1/2 settings pattern.
  - User Action: None.
  - Agent Work: Add typed settings and `.env.example` placeholders using existing config conventions.
  - Output: Backend chunking settings available to the chunking service and tests.
  - Acceptance: App imports without real chunk env values and defaults are applied when values are absent.
  - Validation: Run backend config or chunking tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/core/config.py`, `backend/.env.example`

- [ ] (02B): Implement recursive chunking service
  - Source of Truth: `docs/plans/Plan_4.md` > `## 1. Goal`; `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`; `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.3 Chunking Strategy`
  - Source Requirements:
    - Implement `chunk_sections(sections, chunk_size, chunk_overlap)`.
    - Add recursive chunking service.
    - Use configurable chunk size and overlap.
    - Estimate token count consistently, even if using a simple word-based approximation in MVP.
  - Details: Create a service that splits parsed section text into one or more `ChunkDraft` records using recursive text boundaries where possible. Use the existing LangChain stack if it is already available and appropriate, or implement a small explicit splitter that respects the source requirements.
  - Dependencies: (01B), (02A)
  - User Action: None.
  - Agent Work: Implement `backend/app/services/chunking_service.py` with deterministic chunk generation and token estimation.
  - Output: Chunking service converts parsed sections into chunk drafts.
  - Acceptance: Chunking tests prove chunk size, overlap, deterministic order, and token count behavior.
  - Validation: `cd backend` then `pytest tests/test_chunking_service.py -v` in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/services/chunking_service.py`

- [ ] (02C): Preserve source metadata and deterministic chunk indexes
  - Source of Truth: `docs/plans/Plan_4.md` > `## 2. Why This Plan Exists`; `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_4.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 8. Document Processing Pipeline` > `### 8.3 Chunking Strategy`
  - Source Requirements:
    - Preserve document ID, file name, page number, section title, chunk index, token count, and CSV row information.
    - Preserve source metadata on each chunk.
    - Confirm chunk index order is deterministic.
    - Chunk rows include available metadata.
  - Details: Ensure chunk drafts carry section metadata through splitting and assign sequential chunk indexes in stable source order. Preserve CSV row metadata in the chunk draft metadata even when a CSV row group spans multiple chunks.
  - Dependencies: (02B)
  - User Action: None.
  - Agent Work: Extend chunk draft creation and tests to prove metadata is preserved for PDF page, DOCX section, TXT, and CSV row contexts.
  - Output: Metadata-preserving chunk drafts ready for database insertion.
  - Acceptance: Chunking tests verify chunk indexes are sequential, stable, and carry available page/section/CSV metadata.
  - Validation: `cd backend` then `pytest tests/test_chunking_service.py -v` in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/services/chunking_service.py`, `backend/tests/test_chunking_service.py`

- [ ] (02D): Handle empty parsed sections and chunking edge cases
  - Source of Truth: `docs/plans/Plan_4.md` > `## 1. Goal`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 11. Required Tests`; `docs/plans/Plan_4.md` > `## 13. Failure Handling`
  - Source Requirements:
    - Empty or unreadable documents fail with a clear status and error message.
    - Tests must cover empty documents and empty text behavior.
    - Empty parsed document sets status to `failed`.
  - Details: Keep empty-content detection consistent between parser and chunking. The parser should reject fully empty documents; the chunking service should skip empty sections safely and return no chunks only when no usable text remains, so processing can fail clearly.
  - Dependencies: (01C), (02B)
  - User Action: None.
  - Agent Work: Add chunking edge-case handling and tests for whitespace-only sections, empty section lists, and overlap boundaries.
  - Output: Chunking behavior that is predictable for empty and near-empty parsed input.
  - Acceptance: Empty or whitespace-only parsed content cannot silently produce a `ready` document with zero chunks.
  - Validation: `cd backend` then `pytest tests/test_chunking_service.py -v` and processing failure tests in Batch04.
  - Blocked Condition: None.
  - Files: `backend/app/services/chunking_service.py`, `backend/tests/test_chunking_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/app/services/chunking_service.py`
- `backend/app/schemas/parsing.py`
- `backend/tests/test_chunking_service.py`

### Required Outputs / Artifacts

- Backend chunk size and overlap settings.
- Recursive chunking service.
- Stable token count estimation.
- Metadata-preserving chunk draft generation.
- Chunking tests for size, overlap, metadata, and empty behavior.

### Acceptance Criteria

- Parsed sections are split into chunks with configured size and overlap.
- Default chunk size is `1000` tokens and default overlap is `150` tokens.
- Chunk indexes are deterministic and sequential.
- Chunk drafts preserve file name, page number, section title, token count, and CSV row metadata where available.
- Empty or whitespace-only input does not produce a false `ready` result.
- No embeddings, Qdrant calls, retrieval, agents, OCR, or frontend changes are added.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_chunking_service.py -v`
- Config/default settings validation if the existing project has dedicated config tests.
- Scope inspection confirming chunking did not write embeddings or Qdrant fields beyond `qdrant_point_id = null`.

### Explicit Non-Goals

- Do not generate embeddings.
- Do not store vectors.
- Do not implement Qdrant collection creation.
- Do not extract graph entities or relationships.
- Do not add frontend processing status polling.

## Mandatory Batch03 - Supabase Chunk Persistence and Processing Orchestration

### Goal

Implement backend processing orchestration that downloads uploaded originals, parses and chunks them, persists chunk rows, and updates document processing status and chunk count.

### Why this batch exists

Plan 4 is complete only when parsed chunks are durable in Supabase PostgreSQL and document metadata accurately reflects `processing`, `ready`, or `failed` states.

### Inputs / Dependencies

- Batch01 parser service
- Batch02 chunking service
- Completed Plan 2 Supabase service foundation
- Completed Plan 3 document metadata and uploaded storage objects
- Existing `documents` and `document_chunks` tables
- User-provided local Supabase credentials for live validation only

### Tasks

- [ ] (03A): Add Supabase helpers for processing and chunk persistence
  - Source of Truth: `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 5. Dependencies`; `docs/plans/Plan_4.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_4.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Master_Plan.md` > `## 6. Data Storage Design` > `## Table: document_chunks`
  - Source Requirements:
    - Uploaded files must exist in Supabase Storage.
    - Add helpers for downloading original files, inserting chunks, and updating document status/count.
    - Insert chunk rows into `document_chunks`.
    - Use the existing `document_chunks` table.
  - Details: Extend the existing Supabase service with mockable helpers for loading a document row by ID and `SINGLE_USER_ID`, downloading original storage bytes, bulk inserting chunk rows, updating status and error message, and updating chunk count.
  - Dependencies: Batch01, Batch02, completed Plan 2/3 Supabase service behavior.
  - User Action: User must provide valid local Supabase credentials, bucket, existing document rows, and uploaded storage objects for live validation; no user action is needed for mocked tests.
  - Agent Work: Add focused helper functions in `backend/app/services/supabase_service.py` without changing database schema or exposing secrets.
  - Output: Supabase helpers needed by document processing service.
  - Acceptance: Helpers are mockable, apply `SINGLE_USER_ID` filters, insert chunks with `qdrant_point_id = null`, and surface failures safely.
  - Validation: Run processing tests with mocked Supabase helpers in Batch04.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` only for live Supabase validation if credentials, bucket, uploaded file, or tables are missing.
  - Files: `backend/app/services/supabase_service.py`

- [ ] (03B): Implement document processing orchestration service
  - Source of Truth: `docs/plans/Plan_4.md` > `## 1. Goal`; `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_4.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`
  - Source Requirements:
    - Implement `process_document(document_id)`.
    - Load the document row filtered by `SINGLE_USER_ID`.
    - Update status to `processing` before parsing.
    - Download original file bytes from Supabase Storage.
    - Parse, chunk, and bulk insert chunk rows.
    - Update `documents.chunk_count` and status `ready` on success.
  - Details: Create `backend/app/services/document_processing_service.py` as the processing orchestrator. It should coordinate Supabase helpers, parser dispatch, chunking settings, chunk row mapping, chunk insert, final count update, and success response data.
  - Dependencies: (03A), Batch01, Batch02.
  - User Action: None for implementation and mocked tests; live validation needs existing upload setup.
  - Agent Work: Implement `process_document(document_id)` with typed inputs/outputs and no external embedding or Qdrant calls.
  - Output: Backend processing function callable after upload or manually in tests.
  - Acceptance: Processing a supported non-empty uploaded document inserts chunks, sets chunk count to inserted row count, and marks status `ready`.
  - Validation: `cd backend` then `pytest tests/test_document_processing.py -v` in Batch04.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` for live processing validation if user-provided Supabase setup or uploaded files are missing.
  - Files: `backend/app/services/document_processing_service.py`

- [ ] (03C): Implement safe failure handling and status transitions
  - Source of Truth: `docs/plans/Plan_4.md` > `## 1. Goal`; `docs/plans/Plan_4.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_4.md` > `## 13. Failure Handling`; `docs/plans/Plan_4.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Document status transitions are `uploaded -> processing -> ready` or `uploaded -> processing -> failed`.
    - On failure, set status `failed` and write `error_message`.
    - Missing storage object sets document status to `failed`.
    - Parser exception sets document status to `failed` and stores a safe error message.
    - Empty parsed document sets status to `failed`.
    - Chunk insert failure sets status to `failed`.
    - Failed processing must not leave document status stuck at `processing`.
  - Details: Add explicit failure paths for missing storage objects, parser errors, empty parsed/chunked content, unsupported type, CSV decoding failure, and chunk insert failures. Keep error messages safe and concise.
  - Dependencies: (03B)
  - User Action: None for mocked tests.
  - Agent Work: Ensure `process_document` catches expected processing exceptions, writes failed status and error message, and re-raises or returns a failed result consistently with existing service patterns.
  - Output: Processing failure behavior that is testable and safe.
  - Acceptance: Processing tests prove each failure path updates status to `failed` and never reports success with zero chunks.
  - Validation: `cd backend` then `pytest tests/test_document_processing.py -v` in Batch04.
  - Blocked Condition: None for mocked tests.
  - Files: `backend/app/services/document_processing_service.py`, `backend/app/services/supabase_service.py`

- [ ] (03D): Add a backend processing trigger only where source-supported
  - Source of Truth: `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_4.md` > `## 8. API Design`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 11. Required Tests`; `docs/plans/Master_Plan.md` > `# 13. Backend API Design` > `## 13.1 Upload Document`
  - Source Requirements:
    - Add a backend processing function that can be called after upload or manually in tests.
    - No required new public API endpoints in this plan.
    - If processing is triggered from upload, `POST /api/documents/upload` still returns `document_id`, `file_name`, and `status`.
    - Optional development endpoint may be added only if needed for development.
  - Details: Keep `process_document(document_id)` directly callable by tests and future pipeline code. If the existing API design requires an integration point, either trigger processing through FastAPI background tasks without changing the upload response contract, or add the optional development-only process endpoint exactly within Plan 4 scope.
  - Dependencies: (03B), completed Plan 3 document API.
  - User Action: None for implementation and mocked tests.
  - Agent Work: Update `backend/app/api/documents.py` only if needed to expose or trigger processing. Preserve existing upload/list/detail behavior and avoid frontend polling additions.
  - Output: Processing entrypoint is available for tests and, if needed, an API/background integration that follows Plan 4.
  - Acceptance: Processing can be invoked manually in tests; any API integration preserves the approved upload response and status behavior.
  - Validation: Run document API regression tests and processing tests in Batch04.
  - Blocked Condition: None for mocked tests; live manual endpoint validation may be `BLOCKED_BY_USER_ACTION` if Supabase setup is missing.
  - Files: `backend/app/api/documents.py`, `backend/app/main.py` if router wiring changes are required, `backend/app/services/document_processing_service.py`

### Files or Modules Likely Created or Updated

- `backend/app/services/supabase_service.py`
- `backend/app/services/document_processing_service.py`
- `backend/app/api/documents.py` if processing integration is needed
- `backend/app/main.py` if router wiring changes are required
- `backend/app/core/config.py`
- `backend/app/services/document_parser.py`
- `backend/app/services/chunking_service.py`

### Required Outputs / Artifacts

- Supabase helpers for document lookup, storage download, chunk insert, status update, error update, and chunk count update.
- Document processing service with `process_document(document_id)`.
- Safe processing failure handling.
- Optional API/background processing trigger only if needed and source-supported.
- Mocked processing tests.

### Acceptance Criteria

- Processing loads document rows filtered by `SINGLE_USER_ID`.
- Processing sets status to `processing` before parsing.
- Original file bytes are downloaded from Supabase Storage.
- Parsed chunks are inserted into `document_chunks`.
- Inserted chunk rows include `document_id`, `user_id`, `chunk_index`, `content`, `token_count`, available metadata, and `qdrant_point_id = null`.
- `documents.chunk_count` equals inserted chunk count.
- Successful processing sets status to `ready`.
- Empty, unreadable, missing storage, unsupported type, parser error, CSV decoding error, and chunk insert failure paths set status to `failed` with a safe error message.
- No document remains stuck at `processing` after a handled failure.
- No embeddings, Qdrant vectors, GraphRAG, retrieval, agents, OCR, or frontend polling are implemented.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_document_processing.py -v`
- Existing document API regression tests if `backend/app/api/documents.py` changes.
- Scope inspection confirming no embeddings, Qdrant calls, graph entity extraction, retrieval, agents, OCR, or frontend polling were added.
- Live manual processing check only when user setup is available.

### Explicit Non-Goals

- Do not add database migrations.
- Do not create or recreate Supabase buckets from code unless an existing project helper already does safe checks.
- Do not create embeddings or Qdrant vectors.
- Do not create graph entities or relationships.
- Do not call ShopAIKey.
- Do not add frontend processing status polling.
- Do not fabricate live Supabase validation results.

## Mandatory Batch04 - Tests, Manual Validation, and Handoff

### Goal

Prove parser, chunking, processing, status transition, and scope behavior with focused tests, manual validation when setup exists, and an honest execution report.

### Why this batch exists

Plan 4 completion depends on evidence that each supported file type parses into chunks, failure cases update status safely, and out-of-scope pipeline work was not added.

### Inputs / Dependencies

- Batch01 parser implementations and fixtures
- Batch02 chunking service
- Batch03 processing orchestration
- Local backend test environment
- Optional real Supabase credentials, bucket, uploaded files, and document rows for live checks

### Tasks

- [ ] (04A): Add parser fixture tests for PDF, DOCX, TXT, CSV, and empty input
  - Source of Truth: `docs/plans/Plan_4.md` > `## 1. Goal`; `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 6. Required Files and Folders`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 11. Required Tests`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_4.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Add parser tests with local fixture files.
    - Test parser outputs for each file type.
    - Report parser test results for PDF, DOCX, TXT, and CSV.
    - Empty or unreadable documents fail with a clear status and error message.
  - Details: Create fixtures and parser tests that verify non-empty parsed output and metadata for PDF, DOCX, TXT, and CSV. Include empty TXT or whitespace input coverage for empty document behavior.
  - Dependencies: Batch01.
  - User Action: None.
  - Agent Work: Add fixture files and `backend/tests/test_document_parser.py` using deterministic local data.
  - Output: Parser test coverage for supported file types and empty input.
  - Acceptance: Parser tests prove all four file types parse into non-empty sections with expected metadata and empty input fails clearly.
  - Validation: `cd backend` then `pytest tests/test_document_parser.py -v`
  - Blocked Condition: None.
  - Files: `backend/tests/test_document_parser.py`, `backend/tests/fixtures/sample.pdf`, `backend/tests/fixtures/sample.docx`, `backend/tests/fixtures/sample.txt`, `backend/tests/fixtures/sample.csv`

- [ ] (04B): Add chunking service tests for sizing, overlap, metadata, and empty behavior
  - Source of Truth: `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 11. Required Tests`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_4.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Add chunking tests.
    - Test chunk sizing, overlap, metadata, and empty text behavior.
    - Confirm chunk index order is deterministic.
    - Chunks include metadata and token count.
  - Details: Add tests that cover small sections, long sections requiring multiple chunks, configured overlap, deterministic index ordering, page/section metadata, CSV row metadata, and empty/whitespace input.
  - Dependencies: Batch02.
  - User Action: None.
  - Agent Work: Create or update `backend/tests/test_chunking_service.py` with focused unit tests.
  - Output: Chunking test coverage.
  - Acceptance: Tests prove chunking behavior and metadata preservation without relying on external services.
  - Validation: `cd backend` then `pytest tests/test_chunking_service.py -v`
  - Blocked Condition: None.
  - Files: `backend/tests/test_chunking_service.py`

- [ ] (04C): Add processing orchestration tests with mocked Supabase
  - Source of Truth: `docs/plans/Plan_4.md` > `## 1. Goal`; `docs/plans/Plan_4.md` > `## 3. Scope`; `docs/plans/Plan_4.md` > `## 7. Data Model / Schema Changes`; `docs/plans/Plan_4.md` > `## 9. Implementation Steps`; `docs/plans/Plan_4.md` > `## 11. Required Tests`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_4.md` > `## 13. Failure Handling`; `docs/plans/Plan_4.md` > `## 15. Reviewer Checklist`
  - Source Requirements:
    - Add processing tests with mocked Supabase storage/database.
    - Test status transitions.
    - Test chunk insertion and chunk count update.
    - Process an empty TXT file and expect status `failed`.
    - Missing storage, parser exception, empty document, chunk insert failure, unsupported type, and CSV decoding failure must fail clearly.
    - Confirm every inserted chunk uses `SINGLE_USER_ID`.
  - Details: Add mocked service tests for successful processing and representative failure paths. Prove `processing`, `ready`, and `failed` status updates happen in the correct order and chunk insert payloads are shaped correctly.
  - Dependencies: Batch03.
  - User Action: None.
  - Agent Work: Create `backend/tests/test_document_processing.py` with deterministic mocks for Supabase, parser, and chunking behavior where appropriate.
  - Output: Processing orchestration test coverage.
  - Acceptance: Tests verify successful chunk persistence, chunk count update, safe failure status, safe error messages, and `SINGLE_USER_ID` chunk ownership.
  - Validation: `cd backend` then `pytest tests/test_document_processing.py -v`
  - Blocked Condition: None.
  - Files: `backend/tests/test_document_processing.py`

- [ ] (04D): Run required backend tests and scope checks
  - Source of Truth: `docs/plans/Plan_4.md` > `## 4. Out of Scope`; `docs/plans/Plan_4.md` > `## 11. Required Tests`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_4.md` > `## 14. Agent Report Requirement`; `docs/plans/Plan_4.md` > `## 15. Reviewer Checklist`; `docs/plans/Master_Plan.md` > `## 3. Authentication Policy`
  - Source Requirements:
    - Run parser, chunking, and processing tests.
    - Confirm scope was followed and out-of-scope work was not added.
    - Confirm no hardcoded secrets.
    - Confirm architecture still matches `docs/plans/Master_Plan.md`.
    - Confirm OCR is not implemented.
  - Details: Run the required backend pytest commands and inspect changed files for secret exposure, frontend changes, OCR libraries, embeddings/Qdrant/GraphRAG work, retrieval, agents, and hardcoded configuration values.
  - Dependencies: (04A), (04B), (04C)
  - User Action: None.
  - Agent Work: Run tests, search for out-of-scope additions, inspect changed file list, and report results honestly.
  - Output: Verification evidence for the execution report.
  - Acceptance: Required tests pass or failures are reported honestly; no hardcoded secrets or out-of-scope work is found.
  - Validation: `cd backend` then `pytest tests/test_document_parser.py tests/test_chunking_service.py tests/test_document_processing.py -v`; run existing backend regression tests affected by changed config/API/service code.
  - Blocked Condition: None for mocked/local tests.
  - Files: Test files and changed implementation files for inspection

- [ ] (04E): Perform manual API and Supabase checks when user setup is available
  - Source of Truth: `docs/plans/Plan_4.md` > `## 1. Goal`; `docs/plans/Plan_4.md` > `## 5. Dependencies`; `docs/plans/Plan_4.md` > `## 8. API Design`; `docs/plans/Plan_4.md` > `## 10. Configuration and Environment Variables`; `docs/plans/Plan_4.md` > `## 11. Required Tests`; `docs/plans/Plan_4.md` > `## 12. Acceptance Criteria`; `docs/plans/Plan_4.md` > `## 14. Agent Report Requirement`
  - Source Requirements:
    - Upload a TXT file through `/api/documents/upload`.
    - Run the processing function or endpoint.
    - Call `GET /api/documents/{document_id}`.
    - Confirm status is `ready` and `chunk_count` is greater than 0.
    - Process an empty TXT file and expect `documents.status = failed`.
  - Details: Validate against a real local backend and Supabase only when the user has provided required local setup outside tracked files. Use the processing function directly or the optional endpoint if it was added in Batch03.
  - Dependencies: (04D)
  - User Action: User must provide valid local `.env` values, Supabase Storage bucket, existing `documents` and `document_chunks` tables, and uploaded test files before live checks can pass.
  - Agent Work: Run upload, processing, detail, and negative checks when setup is available; otherwise report live validation as blocked by missing user setup.
  - Output: Live validation evidence or clear blocked-by-user status.
  - Acceptance: Supported TXT processing yields `ready` status and `chunk_count > 0`; empty TXT processing yields `failed` with safe `error_message`; storage and database checks are confirmed when setup exists.
  - Validation: Manual API/storage checks from Plan 4.
  - Blocked Condition: `BLOCKED_BY_USER_ACTION` if real Supabase credentials, bucket, tables, uploaded files, local backend, or manual confirmation are missing.
  - Files: No tracked files required unless the Execution Agent writes a report artifact.

### Files or Modules Likely Created or Updated

- `backend/tests/test_document_parser.py`
- `backend/tests/test_chunking_service.py`
- `backend/tests/test_document_processing.py`
- `backend/tests/fixtures/sample.pdf`
- `backend/tests/fixtures/sample.docx`
- `backend/tests/fixtures/sample.txt`
- `backend/tests/fixtures/sample.csv`
- Execution report artifact created by the future Execution Agent

### Required Outputs / Artifacts

- Parser fixture tests for PDF, DOCX, TXT, CSV, and empty input.
- Chunking tests for size, overlap, metadata, token count, deterministic index order, and empty behavior.
- Processing tests with mocked Supabase storage/database.
- Required backend test command results.
- Scope and secret validation notes.
- Manual Supabase/API validation result or blocked-by-user status.
- Execution report with files created, files modified, commands run, test results, known issues, and out-of-scope notes.

### Acceptance Criteria

- `pytest tests/test_document_parser.py -v` passes or failures are reported honestly.
- `pytest tests/test_chunking_service.py -v` passes or failures are reported honestly.
- `pytest tests/test_document_processing.py -v` passes or failures are reported honestly.
- Parser test results include PDF, DOCX, TXT, and CSV.
- Processing tests prove status transitions and failure handling.
- Inserted chunk payloads use `SINGLE_USER_ID`.
- Chunk index order is deterministic.
- Failed processing does not leave documents stuck at `processing`.
- No hardcoded secrets are introduced.
- No OCR, embeddings, Qdrant, GraphRAG, retrieval, agents, or frontend polling are implemented.
- Live checks are completed only when user setup exists; otherwise the blocked condition is documented.

### Required Tests or Validations

- `cd backend`
- `pytest tests/test_document_parser.py -v`
- `pytest tests/test_chunking_service.py -v`
- `pytest tests/test_document_processing.py -v`
- `pytest tests/test_document_parser.py tests/test_chunking_service.py tests/test_document_processing.py -v`
- Existing backend regression tests affected by changed config, API, or service code.
- Manual upload/process/detail check with TXT file when local backend and Supabase setup are available.
- Manual empty TXT processing negative check when local backend and Supabase setup are available.
- Repository search for backend-only secrets in frontend files if frontend files changed.
- Repository search or changed-file inspection for out-of-scope OCR, embeddings, Qdrant, GraphRAG, retrieval, or agent work.

### Explicit Non-Goals

- Do not fabricate Supabase project setup, credentials, bucket existence, uploaded object existence, or manual check results.
- Do not commit `.env` or real secrets.
- Do not weaken tests to avoid failures.
- Do not claim completion for live validation when blocked by missing user setup.
- Do not implement optional future pipeline stages during validation.

## Optional Future Tracks

- Embeddings and Qdrant indexing: This track is not part of the mandatory MVP batch chain. Later plans may generate embeddings, store vectors, and update `qdrant_point_id`.
- Medium GraphRAG construction: This track is not part of the mandatory MVP batch chain. Later plans may extract entities, create relationships, and support graph retrieval.
- Retrieval and agents: This track is not part of the mandatory MVP batch chain. Later plans may implement semantic search, scoring, verification, answer generation, and LangGraph orchestration.
- OCR and scanned document support: This track is not part of the mandatory MVP batch chain and must not be implemented in Plan 4.
- Frontend processing status polling: This track is not part of the mandatory MVP batch chain and must not be added unless a later frontend plan requires it.

## Dependency Chain

- Batch01 -> Batch02
- Batch02 -> Batch03
- Batch03 -> Batch04

Optional future tracks are outside the mandatory chain.

## Global Verification Checklist

- [ ] PDF text is extracted with page numbers when possible.
- [ ] DOCX text is extracted with best-effort heading metadata.
- [ ] TXT text is extracted with UTF-8-first and safe fallback decoding.
- [ ] CSV rows are converted into readable text with column names and row indexes.
- [ ] Empty or unreadable documents fail clearly.
- [ ] `CHUNK_SIZE_TOKENS` and `CHUNK_OVERLAP_TOKENS` are optional backend-only settings with defaults.
- [ ] Chunks are created with deterministic sequential indexes.
- [ ] Chunk token count is estimated consistently.
- [ ] Chunk metadata preserves document ID, file name, page number, section title, and CSV row information where available.
- [ ] Processing loads document rows filtered by `SINGLE_USER_ID`.
- [ ] Processing sets document status to `processing` before parsing.
- [ ] Chunk rows are inserted into `document_chunks`.
- [ ] Inserted chunk rows include `document_id`, `user_id`, `chunk_index`, `content`, `token_count`, available metadata, and `qdrant_point_id = null`.
- [ ] `documents.chunk_count` equals inserted chunk count.
- [ ] Successful processing sets document status to `ready`.
- [ ] Missing storage object sets document status to `failed`.
- [ ] Parser exception sets document status to `failed` with safe `error_message`.
- [ ] Empty parsed or chunked content sets document status to `failed`.
- [ ] Chunk insert failure sets document status to `failed`.
- [ ] Unsupported file type fails clearly if encountered.
- [ ] CSV decoding failure returns a safe parser error identifying CSV.
- [ ] Failed processing does not leave document status stuck at `processing`.
- [ ] Required parser, chunking, and processing tests were run and results were reported honestly.
- [ ] Parser test results include PDF, DOCX, TXT, and CSV.
- [ ] No hardcoded secrets are introduced.
- [ ] Service-role key remains backend-only and is not exposed to frontend.
- [ ] No embeddings, Qdrant vectors, GraphRAG, retrieval, agents, OCR, image-based scanned document support, or frontend polling were implemented.
- [ ] Implementation code is clean, idiomatic, typed where appropriate, and easy to understand.

## Progress Tracker

### Batches

- [x] Batch01 - Parser Schemas, Dependencies, and File-Type Implementations
- [ ] Batch02 - Chunking Configuration and Metadata-Preserving Splitter
- [ ] Batch03 - Supabase Chunk Persistence and Processing Orchestration
- [ ] Batch04 - Tests, Manual Validation, and Handoff

### Task IDs

#### Batch01
- [x] (01A): Add parser dependencies and fixture-friendly setup
- [x] (01B): Add parsed section and chunk draft schemas
- [x] (01C): Implement parser dispatch and parser errors
- [x] (01D): Implement PDF, DOCX, and TXT parsers
- [x] (01E): Implement CSV parser with row metadata

#### Batch02
- [ ] (02A): Add backend chunking configuration
- [ ] (02B): Implement recursive chunking service
- [ ] (02C): Preserve source metadata and deterministic chunk indexes
- [ ] (02D): Handle empty parsed sections and chunking edge cases

#### Batch03
- [ ] (03A): Add Supabase helpers for processing and chunk persistence
- [ ] (03B): Implement document processing orchestration service
- [ ] (03C): Implement safe failure handling and status transitions
- [ ] (03D): Add a backend processing trigger only where source-supported

#### Batch04
- [ ] (04A): Add parser fixture tests for PDF, DOCX, TXT, CSV, and empty input
- [ ] (04B): Add chunking service tests for sizing, overlap, metadata, and empty behavior
- [ ] (04C): Add processing orchestration tests with mocked Supabase
- [ ] (04D): Run required backend tests and scope checks
- [ ] (04E): Perform manual API and Supabase checks when user setup is available

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
