# Plan 5 - ShopAIKey Embeddings and Qdrant Indexing

## 1. Goal

Generate embeddings for persisted document chunks with ShopAIKey, create or verify the Qdrant Cloud collection, upsert chunk vectors with payload metadata, and store each Qdrant point ID back on `document_chunks`.

The goal is testable when ready documents have chunk vectors in Qdrant and each indexed chunk has a non-null `qdrant_point_id`.

## 2. Why This Plan Exists

Semantic retrieval requires vectors. This plan connects the parsed chunk layer to Qdrant through ShopAIKey embeddings while keeping all private API keys backend-only.

## 3. Scope

- Add ShopAIKey embedding client.
- Add Qdrant Cloud client.
- Create or verify Qdrant collection `document_chunks`.
- Generate embeddings for chunks missing `qdrant_point_id`.
- Upsert vectors with the required payload format.
- Update `document_chunks.qdrant_point_id`.
- Add indexing service tests with mocked ShopAIKey and Qdrant.
- Add a connection/indexing smoke test path for development.

## 4. Out of Scope

- Do not implement semantic search API.
- Do not implement GraphRAG.
- Do not implement retrieval scoring.
- Do not call chat completion.
- Do not implement rerank.
- Do not implement agents.
- Do not expose Qdrant or ShopAIKey to frontend.

## 5. Dependencies

- Plan 1 must be completed.
- Plan 2 must be completed.
- Plan 3 must be completed.
- Plan 4 must be completed.
- Supabase must contain `document_chunks` rows.
- Qdrant Cloud project and API key must exist.
- ShopAIKey API key must exist.

## 6. Required Files and Folders

```text
backend/app/services/shopaikey_service.py
- Contains OpenAI-compatible HTTP client functions for embeddings.

backend/app/services/qdrant_service.py
- Contains Qdrant client initialization, collection creation, and vector upsert helpers.

backend/app/services/embedding_service.py
- Orchestrates chunk lookup, embedding generation, Qdrant upsert, and chunk row update.

backend/app/services/supabase_service.py
- Add helpers for listing chunks that need indexing and updating qdrant_point_id.

backend/app/schemas/embeddings.py
- Contains internal models for embedding requests, indexed chunk payloads, and indexing results.

backend/tests/test_shopaikey_service.py
- Tests embedding request construction and error handling with mocked HTTP.

backend/tests/test_qdrant_service.py
- Tests collection creation and payload construction with mocked Qdrant client.

backend/tests/test_embedding_service.py
- Tests indexing orchestration.

backend/requirements.txt
- Add `qdrant-client` and HTTP client dependency if not already present.

backend/.env.example
- Add ShopAIKey and Qdrant variables.
```

## 7. Data Model / Schema Changes

No database table changes in this plan.

Update existing field:

```text
document_chunks.qdrant_point_id
- Before indexing: null
- After indexing: stable point ID string
```

Qdrant collection:

```text
Collection name: document_chunks
Distance: Cosine
Vector size: derived from first ShopAIKey embedding response and then enforced by config/setup
```

Qdrant payload format:

```json
{
  "user_id": "single_user",
  "document_id": "uuid",
  "chunk_id": "uuid",
  "file_name": "contract.pdf",
  "file_type": "pdf",
  "page_number": 3,
  "section_title": "Probation",
  "chunk_index": 0,
  "content_preview": "First 500 characters of the chunk"
}
```

Indexing result schema:

```json
{
  "document_id": "uuid",
  "indexed_count": 12,
  "failed_count": 0,
  "errors": []
}
```

## 8. API Design

No required public API endpoints in this plan.

Optional development-only endpoint if needed:

```text
Method: POST
Path: /api/documents/{document_id}/index
Request body: none
Response body:
{
  "document_id": "uuid",
  "indexed_count": 12,
  "failed_count": 0,
  "errors": []
}
Error responses:
- 404 document not found for SINGLE_USER_ID
- 400 document has no chunks
- 500 ShopAIKey failure
- 500 Qdrant failure
```

If added, the endpoint must be clearly marked development/internal and not used by the frontend yet.

## 9. Implementation Steps

1. Add `SHOPAIKEY_API_KEY`, `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_EMBEDDING_MODEL`, `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION` to backend settings and `.env.example`.
2. Create `shopaikey_service.py` with `create_embedding(text: str) -> list[float]`.
3. Use ShopAIKey OpenAI-compatible endpoint `POST {SHOPAIKEY_BASE_URL}/embeddings`.
4. Send model from `SHOPAIKEY_EMBEDDING_MODEL`; do not hardcode it inside business logic.
5. Handle HTTP timeout, non-2xx response, malformed JSON, and missing embedding vector.
6. Create `qdrant_service.py` with `get_qdrant_client()`, `ensure_collection(vector_size)`, and `upsert_chunk_vector(point_id, vector, payload)`.
7. Use cosine distance for Qdrant collection.
8. Create deterministic point IDs such as the chunk UUID string.
9. Build Qdrant payload with all required metadata and a safe content preview.
10. Create `embedding_service.py` with `index_document_chunks(document_id)`.
11. Fetch document and chunks filtered by `SINGLE_USER_ID`.
12. Reject indexing if document status is not `ready`.
13. For each chunk missing `qdrant_point_id`, generate an embedding, ensure collection, upsert the point, and update the chunk row.
14. Skip chunks that already have `qdrant_point_id` unless an explicit reindex flag is later added.
15. Record per-chunk errors in the indexing result instead of hiding partial failures.
16. Add mocked tests for embedding request payloads, Qdrant payloads, successful indexing, already-indexed chunks, and API failure behavior.

## 10. Configuration and Environment Variables

```text
SHOPAIKEY_API_KEY
- Purpose: Authenticates ShopAIKey embedding requests.
- Required: Yes.
- Example: shopaikey-placeholder
- Scope: Backend-only.

SHOPAIKEY_BASE_URL
- Purpose: OpenAI-compatible API base URL.
- Required: Yes.
- Example: https://api.shopaikey.com/v1
- Scope: Backend-only.

SHOPAIKEY_EMBEDDING_MODEL
- Purpose: Embedding model name.
- Required: Yes.
- Example: text-embedding-ada-002
- Scope: Backend-only.

QDRANT_URL
- Purpose: Qdrant Cloud endpoint.
- Required: Yes.
- Example: https://example-cluster.qdrant.io
- Scope: Backend-only.

QDRANT_API_KEY
- Purpose: Authenticates Qdrant Cloud requests.
- Required: Yes.
- Example: qdrant-placeholder
- Scope: Backend-only.

QDRANT_COLLECTION
- Purpose: Stores chunk vectors.
- Required: Yes.
- Example: document_chunks
- Scope: Backend-only.
```

## 11. Required Tests

Unit tests:

```text
cd backend
pytest tests/test_shopaikey_service.py tests/test_qdrant_service.py tests/test_embedding_service.py -v
```

Manual indexing smoke test:

```text
Upload and process a TXT document.
Run the indexing function or endpoint for that document.
Confirm indexed_count equals document chunk_count.
```

Qdrant manual check:

```text
Open Qdrant dashboard.
Confirm collection document_chunks exists.
Confirm points include payload user_id, document_id, chunk_id, file_name, and content_preview.
```

Database check:

```text
select id, qdrant_point_id from document_chunks where document_id = '<document_id>';
```

## 12. Acceptance Criteria

- ShopAIKey embeddings client sends requests to `/embeddings`.
- Embedding model is configurable.
- Qdrant collection is created or verified with cosine distance.
- Each indexed chunk creates one Qdrant point.
- Qdrant payload includes required metadata.
- `document_chunks.qdrant_point_id` is updated after successful upsert.
- Already-indexed chunks are not duplicated by default.
- ShopAIKey and Qdrant keys are backend-only.
- No semantic search endpoint or agent logic is implemented.

## 13. Failure Handling

- Missing ShopAIKey config produces a clear backend error.
- ShopAIKey timeout records an indexing error for the chunk.
- ShopAIKey malformed response raises a clear embedding error.
- Qdrant connection failure records an indexing error and does not update `qdrant_point_id`.
- Qdrant vector-size mismatch must fail loudly and instruct the agent to verify collection setup.
- Document with no chunks returns a clear no-work result or error.

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

The report must include whether live ShopAIKey/Qdrant checks were run or only mocked tests were run.

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

- Confirm no frontend file references Qdrant or ShopAIKey secrets.
- Confirm point IDs are stable and traceable to chunk IDs.
- Confirm payload filtering fields are present.
- Confirm errors do not mark a chunk indexed when Qdrant upsert failed.
