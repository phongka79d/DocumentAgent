# Plan 16 - End-to-End Testing and Stabilization

## 1. Goal

Run and stabilize the full MVP flow from document upload through parsing, chunking, embedding, graph building, retrieval, verification, answer generation, frontend display, evidence viewing, and agent log inspection.

The goal is testable when the sample question can be answered with verified citations and all MVP success criteria from `docs/plans/Master_Plan.md` are confirmed.

## 2. Why This Plan Exists

The previous plans build the system in layers. This final milestone verifies that those layers work together, fixes integration bugs, adds regression coverage, and documents the completed MVP behavior.

## 3. Scope

- Add sample test document for the required scenario.
- Add backend end-to-end or integration tests with mocked external services where needed.
- Add live smoke test instructions for Supabase, Qdrant, and ShopAIKey.
- Run upload, parse, chunk, embed, graph, retrieve, verify, answer flow.
- Verify frontend upload, document list, chat, evidence viewer, and logs UI.
- Fix bugs found during integration.
- Update README or developer docs with setup and test commands.
- Confirm no Auth/JWT and no private frontend keys.

## 4. Out of Scope

- Do not add new product features beyond stabilizing the MVP.
- Do not add OCR.
- Do not add multi-user auth.
- Do not add payments, admin dashboard, mobile app, browser extension, or fine-tuning.
- Do not redesign the architecture.
- Do not replace Qdrant or ShopAIKey.
- Do not add community-detection GraphRAG.

## 5. Dependencies

- Plans 1 through 15 must be completed.
- Backend and frontend must both run locally.
- Supabase, Qdrant Cloud, and ShopAIKey credentials must be configured for live smoke tests.

## 6. Required Files and Folders

```text
backend/tests/fixtures/official_work_date_sample.txt
- Contains the required Vietnamese sample evidence.

backend/tests/test_end_to_end_workflow.py
- Tests the upload-to-answer workflow with mocked external services or test doubles.

backend/tests/test_mvp_regression.py
- Tests core MVP safety rules such as verified-chunks-only answers and missing information behavior.

docs/TestPlan.md
- Documents local, mocked, and live smoke test procedures.

README.md
- Update with setup, environment variables, run commands, and MVP verification steps.

frontend/src/__tests__/mvp-flow.test.tsx
- Optional frontend flow test if test infrastructure exists.

docs/plans/Plan_16.md
- This plan remains the stabilization checklist source.
```

## 7. Data Model / Schema Changes

No schema changes should be introduced in this plan unless a previous plan is found to be incomplete.

If a schema issue is discovered:

```text
- Document the issue.
- Add the smallest migration needed.
- Update the affected earlier plan file or add a note in docs/TestPlan.md.
- Re-run affected tests.
```

Required sample document content:

```text
Người lao động bắt đầu thử việc từ ngày 01/06/2026.
Thời gian thử việc kéo dài 2 tháng.
Sau khi hoàn thành thử việc, người lao động có thể được xét làm việc chính thức.
```

Required test question:

```text
Tôi có thể làm việc chính thức vào tháng mấy?
```

Expected answer if evidence supports it:

```text
Tháng 8/2026
```

## 8. API Design

No new API endpoints in this plan.

The following existing APIs must be exercised:

```text
GET /api/health
POST /api/documents/upload
GET /api/documents
GET /api/documents/{document_id}
POST /api/retrieval/search
POST /api/chat/ask
GET /api/agent-runs/{agent_run_id}/evidence
GET /api/agent-runs/{agent_run_id}/logs
```

Expected final chat response shape:

```json
{
  "answer": "Bạn có thể được xét làm việc chính thức vào tháng 8/2026.",
  "confidence": 0.82,
  "citations": [
    {
      "file_name": "official_work_date_sample.txt",
      "quote": "Người lao động bắt đầu thử việc từ ngày 01/06/2026."
    },
    {
      "file_name": "official_work_date_sample.txt",
      "quote": "Thời gian thử việc kéo dài 2 tháng."
    }
  ],
  "agent_run_id": "uuid"
}
```

## 9. Implementation Steps

1. Create `backend/tests/fixtures/official_work_date_sample.txt` with the required Vietnamese sample content.
2. Create `docs/TestPlan.md`.
3. Document required environment variables for backend and frontend.
4. Document local startup commands for backend and frontend.
5. Document mocked test commands.
6. Document live smoke test commands and manual Supabase/Qdrant checks.
7. Add backend end-to-end test using mocked Supabase, Qdrant, and ShopAIKey if live services are not suitable for CI.
8. The mocked E2E test must simulate upload, processing, indexing, graph build, retrieval, verification, answer generation, evidence, and logs.
9. Add regression test that Agent 3 cannot use rejected chunks.
10. Add regression test that missing information returns the insufficient-evidence answer.
11. Add regression test that final citations use file name plus quote.
12. Add regression test that frontend-safe env files do not contain private key names.
13. Run all backend tests.
14. Run frontend build.
15. Run frontend tests if configured.
16. Start backend and frontend locally.
17. Upload the sample TXT document through the frontend.
18. Confirm document appears in the document list.
19. Confirm document reaches `ready` after parsing/chunking/indexing/graph build.
20. Ask the required question in the chat UI.
21. Confirm answer says the official work month is August 2026 when evidence supports it.
22. Confirm citations include the sample file name and quoted evidence.
23. Open evidence viewer and confirm verified chunks include start date, probation duration, and official-work condition.
24. Open agent logs and confirm Agent 1 scores, Agent 2 verification, and Agent 3 self-check are visible.
25. Fix integration bugs found during these checks.
26. Re-run affected tests after each fix.
27. Update README with final setup and usage notes.

## 10. Configuration and Environment Variables

Backend variables required for live smoke testing:

```text
APP_ENV
- Purpose: Runtime environment.
- Required: Yes.
- Example: development
- Scope: Backend-only.

SINGLE_USER_ID
- Purpose: MVP data owner.
- Required: Yes.
- Example: single_user
- Scope: Backend-only.

SUPABASE_URL
- Purpose: Supabase project URL.
- Required: Yes.
- Example: https://example-project.supabase.co
- Scope: Backend-only.

SUPABASE_SERVICE_ROLE_KEY
- Purpose: Backend database and storage access.
- Required: Yes.
- Example: supabase-service-role-placeholder
- Scope: Backend-only.

SUPABASE_STORAGE_BUCKET
- Purpose: Original document bucket.
- Required: Yes.
- Example: documents
- Scope: Backend-only.

QDRANT_URL
- Purpose: Qdrant Cloud endpoint.
- Required: Yes.
- Example: https://example-cluster.qdrant.io
- Scope: Backend-only.

QDRANT_API_KEY
- Purpose: Qdrant Cloud authentication.
- Required: Yes.
- Example: qdrant-placeholder
- Scope: Backend-only.

QDRANT_COLLECTION
- Purpose: Chunk vector collection.
- Required: Yes.
- Example: document_chunks
- Scope: Backend-only.

SHOPAIKEY_API_KEY
- Purpose: Chat completion and embedding access.
- Required: Yes.
- Example: shopaikey-placeholder
- Scope: Backend-only.

SHOPAIKEY_BASE_URL
- Purpose: OpenAI-compatible API base URL.
- Required: Yes.
- Example: https://api.shopaikey.com/v1
- Scope: Backend-only.

SHOPAIKEY_CHAT_MODEL
- Purpose: Agent chat completion model.
- Required: Yes.
- Example: gpt-5-mini
- Scope: Backend-only.

SHOPAIKEY_EMBEDDING_MODEL
- Purpose: Embedding model.
- Required: Yes.
- Example: text-embedding-ada-002
- Scope: Backend-only.

RETRIEVAL_SEMANTIC_TOP_K
- Purpose: Semantic candidate count.
- Required: No.
- Example: 20
- Scope: Backend-only.

RETRIEVAL_GRAPH_TOP_K
- Purpose: Graph candidate count.
- Required: No.
- Example: 20
- Scope: Backend-only.

RETRIEVAL_FINAL_TOP_K
- Purpose: Final candidate count.
- Required: No.
- Example: 8
- Scope: Backend-only.

ENABLE_RERANK
- Purpose: Optional rerank toggle.
- Required: No.
- Example: false
- Scope: Backend-only.
```

Frontend variable:

```text
VITE_API_BASE_URL
- Purpose: FastAPI backend URL.
- Required: Yes.
- Example: http://localhost:8000
- Scope: Frontend-safe.
```

## 11. Required Tests

Backend full test suite:

```text
cd backend
pytest -v
```

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

Live backend checks:

```text
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@backend/tests/fixtures/official_work_date_sample.txt"

curl http://localhost:8000/api/documents

curl -X POST http://localhost:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"Tôi có thể làm việc chính thức vào tháng mấy?\",\"document_ids\":[\"<document_id>\"]}"

curl http://localhost:8000/api/agent-runs/<agent_run_id>/evidence
curl http://localhost:8000/api/agent-runs/<agent_run_id>/logs
```

Manual frontend checks:

```text
Upload sample TXT.
Wait for ready status.
Ask the required question.
Open evidence viewer.
Open agent logs.
Confirm answer, citations, verified evidence, scores, and self-check.
```

Security checks:

```text
Search frontend source for SUPABASE_SERVICE_ROLE_KEY, QDRANT_API_KEY, and SHOPAIKEY_API_KEY.
Confirm none are present except in documentation warning text if intentionally included.
```

## 12. Acceptance Criteria

- Full backend test suite passes or known external-service tests are clearly skipped with reason.
- Frontend build passes.
- User can upload PDF, DOCX, TXT, and CSV files.
- Files are stored in Supabase Storage.
- Document metadata and chunks are stored in Supabase PostgreSQL.
- Chunk embeddings are stored in Qdrant Cloud.
- GraphRAG entities and relationships are stored.
- User can ask a question about uploaded documents.
- Agent 1 retrieves and scores candidate chunks.
- Agent 2 verifies evidence.
- Agent 3 generates a grounded answer with citations.
- Agent 3 self-checks before output.
- Frontend displays answer, evidence, and agent logs.
- No Auth/JWT is required.
- All private keys remain backend-only.
- Sample question returns August 2026 if evidence supports it.

## 13. Failure Handling

- If Supabase credentials are missing, live smoke tests must be skipped with a clear reason and mocked tests must still run.
- If Qdrant credentials are missing, live vector tests must be skipped with a clear reason and mocked tests must still run.
- If ShopAIKey credentials are missing, live LLM tests must be skipped with a clear reason and mocked tests must still run.
- If sample document processing fails, inspect document status and error message before changing code.
- If retrieval returns no chunks, verify Qdrant indexing and selected document filters.
- If Agent 2 rejects all chunks, verify candidate content and prompt output.
- If Agent 3 lacks citations, treat it as a blocking bug.
- If frontend cannot load APIs, verify `VITE_API_BASE_URL` and CORS.

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

The report must also include:

```text
Sample document used
Question asked
Answer returned
Citations returned
Agent run ID
Whether tests were mocked, live, or both
Any skipped live checks and why
```

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

- Confirm the final answer uses verified chunks only.
- Confirm citation format is `file_name: "quoted text"`.
- Confirm unsupported claims are rejected by self-check.
- Confirm no Auth/JWT was added.
- Confirm no private key appears in frontend code.
- Confirm all MVP success criteria in `docs/plans/Master_Plan.md` are satisfied.
