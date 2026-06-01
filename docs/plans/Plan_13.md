# Plan 13 - Frontend Upload and Document List

## 1. Goal

Build the frontend upload and document list experience so the user can upload supported files, see upload progress, view uploaded documents, inspect processing status, and see upload or processing errors.

The goal is testable when the browser can upload PDF, DOCX, TXT, and CSV files through the backend and display the resulting document list.

## 2. Why This Plan Exists

The backend can accept and process documents, but the user needs a usable frontend entry point before chat and evidence viewing are useful. This plan creates the document management UI without adding chat yet.

## 3. Scope

- Add frontend API client functions for document upload, list, and detail.
- Add upload page.
- Add document list page.
- Add upload progress display.
- Add supported file validation before upload.
- Add status display for `uploaded`, `processing`, `ready`, and `failed`.
- Add error display for rejected uploads and failed processing.
- Add basic routing/navigation for upload and document list.
- Add frontend build and component tests where available.

## 4. Out of Scope

- Do not implement chat UI.
- Do not implement evidence viewer.
- Do not implement agent logs UI.
- Do not expose Supabase, Qdrant, or ShopAIKey keys in frontend.
- Do not implement login or JWT.
- Do not implement document deletion unless already present in backend and explicitly approved.

## 5. Dependencies

- Plan 1 must be completed.
- Plan 3 must be completed for document upload/list/detail APIs.
- Plan 4 and Plan 5 can be completed for meaningful status values, but the UI must work even if documents remain `uploaded`.

## 6. Required Files and Folders

```text
frontend/src/api/client.ts
- Existing Axios client configured with VITE_API_BASE_URL.

frontend/src/api/documents.ts
- Contains uploadDocument, listDocuments, and getDocument functions.

frontend/src/types/documents.ts
- Contains frontend TypeScript types for document API responses.

frontend/src/pages/UploadDocumentPage.tsx
- Contains upload UI, file validation, progress display, and errors.

frontend/src/pages/DocumentListPage.tsx
- Contains document list UI and status display.

frontend/src/components/UploadBox.tsx
- Reusable file input/dropzone component.

frontend/src/components/DocumentCard.tsx
- Reusable document row/card with status and metadata.

frontend/src/components/StatusBadge.tsx
- Reusable status display for uploaded, processing, ready, and failed.

frontend/src/App.tsx
- Add routing/navigation for upload and document list.

frontend/src/main.tsx
- Ensure router provider is mounted if using React Router.

frontend/src/styles.css
- Add or adjust styles consistent with the existing frontend setup.

frontend/package.json
- Add routing/test dependencies if needed.

frontend/src/api/documents.test.ts
- API client tests if a frontend test runner exists.

frontend/src/pages/UploadDocumentPage.test.tsx
- UI tests if testing infrastructure exists.
```

## 7. Data Model / Schema Changes

No backend database schema changes in this plan.

Frontend document type:

```ts
export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export type DocumentListItem = {
  id: string;
  file_name: string;
  file_type: string;
  status: DocumentStatus;
  chunk_count: number;
  created_at: string;
  error_message?: string | null;
};
```

Upload response type:

```ts
export type DocumentUploadResponse = {
  document_id: string;
  file_name: string;
  status: DocumentStatus;
};
```

## 8. API Design

No new backend APIs in this plan.

Frontend calls existing APIs:

```text
POST /api/documents/upload
- multipart/form-data with file
- returns document_id, file_name, status
```

```text
GET /api/documents
- returns { documents: DocumentListItem[] }
```

```text
GET /api/documents/{document_id}
- returns document detail
```

Frontend validation rules:

```text
Accepted extensions: .pdf, .docx, .txt, .csv
Reject empty file before upload if browser exposes file size.
Show backend error message when upload fails.
```

## 9. Implementation Steps

1. Add React Router if the app does not already have routing.
2. Create `frontend/src/types/documents.ts`.
3. Create `frontend/src/api/documents.ts`.
4. Implement `uploadDocument(file, onUploadProgress)` using multipart `FormData`.
5. Implement `listDocuments()` and `getDocument(documentId)`.
6. Create `StatusBadge.tsx` with distinct visual states for uploaded, processing, ready, and failed.
7. Create `DocumentCard.tsx` showing file name, file type, upload time, status, chunk count, and error message when present.
8. Create `UploadBox.tsx` using a file input and optional drag-and-drop behavior.
9. Validate selected file extension before calling backend.
10. Show upload progress while upload is in flight.
11. Disable duplicate submit while uploading.
12. After upload success, refresh the document list.
13. Create `UploadDocumentPage.tsx` that combines upload and recent document feedback.
14. Create `DocumentListPage.tsx` that fetches documents on load and provides a refresh action.
15. Add simple navigation between Upload and Documents in `App.tsx`.
16. Keep the UI work-focused and compact; do not create a marketing landing page.
17. Add tests for file validation and API client if the frontend test stack exists.
18. Run build and fix TypeScript errors.

## 10. Configuration and Environment Variables

```text
VITE_API_BASE_URL
- Purpose: Base URL for FastAPI backend.
- Required: Yes.
- Example: http://localhost:8000
- Scope: Frontend-safe.
```

Do not add any of these frontend variables:

```text
SUPABASE_SERVICE_ROLE_KEY
QDRANT_API_KEY
SHOPAIKEY_API_KEY
```

## 11. Required Tests

Frontend build:

```text
cd frontend
npm run build
```

Frontend tests if configured:

```text
cd frontend
npm test
```

Manual UI checks:

```text
Start backend on http://localhost:8000.
Start frontend on http://localhost:5173.
Open Upload page.
Upload a TXT file.
Confirm progress is shown.
Confirm the uploaded document appears in the list.
Upload an unsupported file and confirm a clear error.
Refresh document list and confirm existing documents load.
```

Backend compatibility checks:

```text
GET /api/documents is called through VITE_API_BASE_URL.
No frontend network call goes directly to Supabase, Qdrant, or ShopAIKey.
```

## 12. Acceptance Criteria

- Frontend has upload and document list pages.
- Upload supports PDF, DOCX, TXT, and CSV.
- Unsupported file types are rejected before upload or shown as backend errors.
- Upload progress is visible.
- Document list displays file name, type, created time, status, chunk count, and error message.
- User can refresh the list.
- Frontend build passes.
- No private keys are exposed in frontend code.
- No chat, evidence viewer, or agent logs UI is implemented.

## 13. Failure Handling

- Backend unavailable shows a clear connection error.
- Unsupported file type shows a clear supported-types message.
- Upload failure shows backend error text when safe.
- Failed document status shows `error_message`.
- Empty document list shows an empty state.
- Slow uploads keep submit disabled until completion or failure.

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

The report must include whether manual browser testing was performed.

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

- Confirm upload form is usable on desktop and mobile widths.
- Confirm button labels and status text do not overflow.
- Confirm no landing page was added instead of the actual tool UI.
- Confirm frontend uses backend APIs only.
