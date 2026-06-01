# Plan 6 - Basic Semantic Retrieval

## 1. Goal

Implement semantic retrieval by embedding the user question with ShopAIKey, searching Qdrant with cosine similarity, and returning Top-K chunk results through `/api/retrieval/search`.

The goal is testable when a question returns scored chunk results filtered by `SINGLE_USER_ID` and optional selected document IDs.

## 2. Why This Plan Exists

Agent retrieval needs a reliable semantic search primitive before GraphRAG and hybrid scoring are added. This plan creates the basic vector search contract and result schema.

## 3. Scope

- Add semantic retrieval service.
- Add question embedding using existing ShopAIKey embedding client.
- Add Qdrant search with `user_id` filter.
- Add optional document ID filter.
- Add configurable `semantic_top_k`.
- Add `/api/retrieval/search`.
- Return chunk content and metadata from Supabase/Qdrant payload.
- Add retrieval tests with mocked ShopAIKey and Qdrant.

## 4. Out of Scope

- Do not implement GraphRAG expansion.
- Do not implement hybrid scoring formula.
- Do not implement Agent 1.
- Do not implement rerank.
- Do not implement chat or LangGraph.
- Do not implement frontend search UI.

## 5. Dependencies

- Plan 1 must be completed.
- Plan 2 must be completed.
- Plan 4 must be completed.
- Plan 5 must be completed.
- Chunks must already be indexed into Qdrant.

## 6. Required Files and Folders

```text
backend/app/api/retrieval.py
- Contains `/api/retrieval/search`.

backend/app/services/retrieval_service.py
- Contains semantic search orchestration.

backend/app/services/qdrant_service.py
- Add Qdrant search helper with filters.

backend/app/services/shopaikey_service.py
- Reuse embedding function for question embeddings.

backend/app/schemas/retrieval.py
- Contains retrieval request and response models.

backend/app/main.py
- Include retrieval router under `/api/retrieval`.

backend/tests/test_retrieval_service.py
- Tests semantic retrieval behavior with mocked dependencies.

backend/tests/test_retrieval_api.py
- Tests API validation and response contract.
```

## 7. Data Model / Schema Changes

No database schema changes in this plan.

Request schema:

```json
{
  "question": "What does the contract say about probation?",
  "document_ids": ["uuid"],
  "top_k": 8
}
```

Response schema:

```json
{
  "question": "What does the contract say about probation?",
  "results": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "file_name": "contract.pdf",
      "file_type": "pdf",
      "content": "Full chunk content if available",
      "content_preview": "Preview from Qdrant payload",
      "page_number": 3,
      "section_title": "Probation",
      "chunk_index": 4,
      "semantic_similarity": 0.88
    }
  ]
}
```

Qdrant filter requirements:

```text
Always filter by user_id = SINGLE_USER_ID.
If document_ids is provided, filter document_id in the provided list.
```

## 8. API Design

```text
Method: POST
Path: /api/retrieval/search
Request body:
{
  "question": "string",
  "document_ids": ["uuid"],
  "top_k": 8
}
Response body:
{
  "question": "string",
  "results": []
}
Error responses:
- 400 empty question
- 400 top_k outside allowed range
- 422 invalid document UUID
- 500 ShopAIKey embedding failure
- 500 Qdrant search failure
Validation rules:
- question must be non-empty after trimming.
- top_k defaults to RETRIEVAL_SEMANTIC_TOP_K.
- top_k must be between 1 and 50.
- document_ids can be omitted or empty for all documents owned by SINGLE_USER_ID.
```

## 9. Implementation Steps

1. Add `RETRIEVAL_SEMANTIC_TOP_K` to backend settings and `.env.example`.
2. Create `SearchRequest`, `RetrievalResult`, and `SearchResponse` models in `backend/app/schemas/retrieval.py`.
3. Create `retrieval_service.py` with `semantic_search(question, document_ids=None, top_k=None)`.
4. Trim and validate the question before embedding.
5. Call `create_embedding(question)` from `shopaikey_service.py`.
6. Add `search_vectors(query_vector, top_k, document_ids)` in `qdrant_service.py`.
7. Build Qdrant filters for `user_id` and optional document IDs.
8. Convert Qdrant scores to `semantic_similarity`; if Qdrant returns distance instead of similarity, normalize consistently and document the conversion.
9. Return Qdrant payload fields in the response.
10. If full chunk content is not stored in Qdrant payload, fetch it from Supabase by `chunk_id`; otherwise return payload preview plus content from database.
11. Implement `/api/retrieval/search` in `backend/app/api/retrieval.py`.
12. Register retrieval router in `backend/app/main.py`.
13. Add tests for empty question, default top_k, top_k bounds, document filter, Qdrant result mapping, and dependency errors.

## 10. Configuration and Environment Variables

```text
RETRIEVAL_SEMANTIC_TOP_K
- Purpose: Default semantic search result count.
- Required: No.
- Example: 20
- Scope: Backend-only.

SINGLE_USER_ID
- Purpose: Required Qdrant payload filter.
- Required: Yes.
- Example: single_user
- Scope: Backend-only.

SHOPAIKEY_API_KEY
- Purpose: Question embedding generation.
- Required: Yes.
- Example: shopaikey-placeholder
- Scope: Backend-only.

QDRANT_URL
- Purpose: Qdrant vector search.
- Required: Yes.
- Example: https://example-cluster.qdrant.io
- Scope: Backend-only.

QDRANT_API_KEY
- Purpose: Qdrant authentication.
- Required: Yes.
- Example: qdrant-placeholder
- Scope: Backend-only.

QDRANT_COLLECTION
- Purpose: Collection searched for chunk vectors.
- Required: Yes.
- Example: document_chunks
- Scope: Backend-only.
```

## 11. Required Tests

Unit tests:

```text
cd backend
pytest tests/test_retrieval_service.py tests/test_retrieval_api.py -v
```

API check:

```text
curl -X POST http://localhost:8000/api/retrieval/search \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What is the probation period?\",\"top_k\":5}"
```

Selected document check:

```text
curl -X POST http://localhost:8000/api/retrieval/search \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What is the probation period?\",\"document_ids\":[\"<document_id>\"],\"top_k\":5}"
```

Negative checks:

```text
Empty question returns HTTP 400.
top_k = 0 returns HTTP 400.
top_k = 1000 returns HTTP 400.
```

## 12. Acceptance Criteria

- `/api/retrieval/search` exists.
- Question embedding uses ShopAIKey embedding service.
- Qdrant search always filters by `SINGLE_USER_ID`.
- Optional document ID filtering works.
- Results include chunk ID, document ID, file name, content or preview, metadata, and `semantic_similarity`.
- Top-K is configurable and validated.
- Empty questions are rejected.
- No GraphRAG, hybrid scoring, rerank, LangGraph, or agents are implemented.

## 13. Failure Handling

- Empty or whitespace question returns HTTP 400.
- Invalid `top_k` returns HTTP 400.
- ShopAIKey failure returns HTTP 500 with a safe public message and detailed backend log.
- Qdrant failure returns HTTP 500 with a safe public message and detailed backend log.
- Missing indexed chunks returns HTTP 200 with an empty results list.
- Missing payload fields should not crash response mapping; use nulls where the schema allows them and log the malformed point.

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

The report must include one example semantic search response or a note that only mocked tests were run.

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

- Confirm Qdrant is never queried without the user filter.
- Confirm document filters use payload `document_id`.
- Confirm score semantics are documented.
- Confirm no final answer generation was added.
