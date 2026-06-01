# Plan 3 - Document Upload and Metadata

## 1. Goal

Implement backend document upload and metadata APIs for supported file types, storing original files in Supabase Storage and document metadata in Supabase PostgreSQL.

The goal is testable when a PDF, DOCX, TXT, or CSV upload returns a `document_id`, creates a storage object, inserts a `documents` row for `SINGLE_USER_ID`, and can be listed and fetched through document APIs.

## 2. Why This Plan Exists

Parsing, chunking, embedding, and retrieval all need a document record and original stored file. This plan creates the upload entry point and document metadata contract without starting document processing yet.

## 3. Scope

- Add document Pydantic schemas.
- Add supported file type validation for PDF, DOCX, TXT, and CSV.
- Add `POST /api/documents/upload`.
- Add `GET /api/documents`.
- Add `GET /api/documents/{document_id}`.
- Store original uploads at `documents/{SINGLE_USER_ID}/{document_id}/{original_filename}`.
- Insert `documents` row with status `uploaded`.
- Filter all document reads by `SINGLE_USER_ID`.
- Add upload and metadata tests with mocked Supabase service.

## 4. Out of Scope

- Do not parse document content.
- Do not create `document_chunks`.
- Do not update status to `processing` or `ready`.
- Do not generate embeddings.
- Do not call Qdrant or ShopAIKey.
- Do not build frontend upload UI.
- Do not implement document deletion unless explicitly added in a later plan.

## 5. Dependencies

- Plan 1 must be completed.
- Plan 2 must be completed.
- Supabase Storage bucket must exist.
- Supabase schema must include the `documents` table.

## 6. Required Files and Folders

```text
backend/app/api/documents.py
- Contains document upload, list, and detail routes.

backend/app/schemas/__init__.py
- Marks the schemas package.

backend/app/schemas/documents.py
- Contains request and response models for document APIs.

backend/app/services/document_service.py
- Coordinates validation, storage upload, metadata insert, list, and detail operations.

backend/app/services/supabase_service.py
- Add storage upload and document table helper functions.

backend/app/utils/__init__.py
- Marks the utils package.

backend/app/utils/file_validation.py
- Validates file extension, content type, and supported types.

backend/tests/test_document_upload.py
- Tests upload success and validation failures.

backend/tests/test_document_api.py
- Tests list and detail API contracts.

backend/app/main.py
- Include the documents router under `/api/documents`.
```

## 7. Data Model / Schema Changes

No database table changes in this plan.

Use the existing `documents` table from Plan 2.

Document insert shape:

```json
{
  "user_id": "single_user",
  "file_name": "contract.pdf",
  "file_type": "pdf",
  "storage_path": "documents/single_user/<document_id>/contract.pdf",
  "status": "uploaded",
  "chunk_count": 0,
  "error_message": null
}
```

Pydantic response models:

```json
{
  "document_id": "uuid",
  "file_name": "contract.pdf",
  "status": "uploaded"
}
```

```json
{
  "documents": [
    {
      "id": "uuid",
      "file_name": "contract.pdf",
      "file_type": "pdf",
      "status": "uploaded",
      "chunk_count": 0,
      "created_at": "2026-06-01T10:00:00Z",
      "error_message": null
    }
  ]
}
```

```json
{
  "id": "uuid",
  "file_name": "contract.pdf",
  "file_type": "pdf",
  "status": "uploaded",
  "chunk_count": 0,
  "created_at": "2026-06-01T10:00:00Z",
  "updated_at": "2026-06-01T10:00:00Z",
  "error_message": null,
  "chunks": []
}
```

## 8. API Design

```text
Method: POST
Path: /api/documents/upload
Request body: multipart/form-data with field `file`
Response body:
{
  "document_id": "uuid",
  "file_name": "contract.pdf",
  "status": "uploaded"
}
Error responses:
- 400 unsupported file type
- 400 empty file
- 413 file too large if a max size is configured
- 500 Supabase upload failure
- 500 metadata insert failure
Validation rules:
- File extension must be one of .pdf, .docx, .txt, .csv.
- Content type must match the extension when provided.
- Filename must be sanitized before use in storage path.
```

```text
Method: GET
Path: /api/documents
Request body: none
Response body:
{
  "documents": []
}
Error responses:
- 500 metadata query failure
Validation rules:
- Always filter by `user_id = SINGLE_USER_ID`.
```

```text
Method: GET
Path: /api/documents/{document_id}
Request body: none
Response body:
{
  "id": "uuid",
  "file_name": "contract.pdf",
  "file_type": "pdf",
  "status": "uploaded",
  "chunk_count": 0,
  "created_at": "2026-06-01T10:00:00Z",
  "updated_at": "2026-06-01T10:00:00Z",
  "error_message": null,
  "chunks": []
}
Error responses:
- 404 document not found for `SINGLE_USER_ID`
- 422 invalid UUID
- 500 metadata query failure
Validation rules:
- Document lookup must include `user_id = SINGLE_USER_ID`.
```

## 9. Implementation Steps

1. Create `backend/app/utils/file_validation.py` with `SUPPORTED_DOCUMENT_TYPES = {"pdf", "docx", "txt", "csv"}`.
2. Implement `get_file_type(filename)` by lowercasing the suffix and rejecting unknown extensions.
3. Implement `validate_upload_file(upload_file, max_bytes)` that checks filename, extension, optional content type, and non-empty bytes.
4. Add `MAX_UPLOAD_BYTES` to backend settings with a conservative default such as `25_000_000`.
5. Create `backend/app/schemas/documents.py` with `DocumentUploadResponse`, `DocumentListItem`, `DocumentListResponse`, and `DocumentDetailResponse`.
6. Create `backend/app/services/document_service.py`.
7. In `document_service.py`, generate a UUID before storage upload so it can be used in the storage path.
8. Sanitize the original filename by removing path separators and control characters.
9. Upload bytes to Supabase Storage using bucket `SUPABASE_STORAGE_BUCKET` and path `documents/{SINGLE_USER_ID}/{document_id}/{safe_filename}`.
10. Insert the `documents` row with status `uploaded`.
11. If metadata insert fails after upload succeeds, report the failure clearly; do not pretend the upload completed.
12. Implement list documents ordered by `created_at desc`.
13. Implement document detail lookup with empty `chunks` because chunking is out of scope.
14. Register `documents.py` router in `backend/app/main.py`.
15. Write API tests using FastAPI `TestClient` and mocked document service.
16. Write service tests with mocked Supabase helpers for upload success, unsupported type, empty file, upload failure, and insert failure.

## 10. Configuration and Environment Variables

```text
SINGLE_USER_ID
- Purpose: Owner ID stored on every document row.
- Required: Yes.
- Example: single_user
- Scope: Backend-only.

SUPABASE_URL
- Purpose: Supabase project URL.
- Required: Yes.
- Example: https://example-project.supabase.co
- Scope: Backend-only.

SUPABASE_SERVICE_ROLE_KEY
- Purpose: Upload files and insert metadata through backend.
- Required: Yes.
- Example: supabase-service-role-placeholder
- Scope: Backend-only.

SUPABASE_STORAGE_BUCKET
- Purpose: Bucket for original documents.
- Required: Yes.
- Example: documents
- Scope: Backend-only.

MAX_UPLOAD_BYTES
- Purpose: Prevent oversized uploads.
- Required: No.
- Example: 25000000
- Scope: Backend-only.
```

## 11. Required Tests

Backend unit tests:

```text
cd backend
pytest tests/test_document_upload.py tests/test_document_api.py -v
```

API checks:

```text
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@sample.pdf"

curl http://localhost:8000/api/documents

curl http://localhost:8000/api/documents/<document_id>
```

Manual Supabase checks:

```text
Confirm original file exists in Supabase Storage.
Confirm a documents row exists with user_id = SINGLE_USER_ID.
Confirm status is uploaded and chunk_count is 0.
```

Negative checks:

```text
Upload .exe and expect HTTP 400.
Upload an empty .txt and expect HTTP 400.
Request a random document UUID and expect HTTP 404.
```

## 12. Acceptance Criteria

- Uploading PDF, DOCX, TXT, and CSV files returns HTTP 200 and `document_id`.
- Unsupported file type returns HTTP 400.
- Empty file returns HTTP 400.
- Uploaded file exists in Supabase Storage.
- A row exists in `documents`.
- Document row uses `user_id = SINGLE_USER_ID`.
- Document row status is `uploaded`.
- `GET /api/documents` returns only documents for `SINGLE_USER_ID`.
- `GET /api/documents/{document_id}` returns HTTP 404 for unknown IDs.
- No parsing, chunking, embeddings, Qdrant, or agents are implemented.

## 13. Failure Handling

- Invalid file type returns HTTP 400 with a clear supported-types message.
- Empty file returns HTTP 400.
- Supabase Storage upload failure returns HTTP 500 and does not insert a success row.
- Metadata insert failure returns HTTP 500 and includes a clear log entry.
- Missing Supabase configuration returns HTTP 500 during upload with a safe public message.
- Storage path must not include unsafe path separators from the original filename.

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

The report must include at least one successful upload test and one unsupported-file negative test.

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

- Confirm all document queries filter by `SINGLE_USER_ID`.
- Confirm the storage path follows `documents/{SINGLE_USER_ID}/{document_id}/{original_filename}`.
- Confirm frontend was not changed except shared config if truly necessary.
- Confirm service-role key remains backend-only.
