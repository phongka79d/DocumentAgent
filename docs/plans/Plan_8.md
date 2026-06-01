# Plan 8 - Hybrid Retrieval and Scoring

## 1. Goal

Implement hybrid retrieval that combines semantic candidates and graph candidates, normalizes score components, applies the required scoring formula, and returns final Top-K ranked chunks.

The goal is testable when the retrieval service returns sorted candidates with `semantic_similarity`, `graph_relevance`, `keyword_overlap`, `metadata_match`, `recency_or_position_score`, and `final_score`.

## 2. Why This Plan Exists

Agent 1 needs more than raw vector similarity. This plan combines semantic and graph signals into a transparent scoring layer before wrapping it in an agent.

## 3. Scope

- Add graph candidate lookup from entities and relationships.
- Merge semantic and graph candidates by chunk ID.
- Implement score normalization helpers.
- Implement keyword overlap scoring.
- Implement metadata match scoring.
- Implement recency or position scoring.
- Implement the required final score formula.
- Add optional rerank placeholder that is disabled unless configured.
- Add final Top-K selection.
- Add scoring tests.

## 4. Out of Scope

- Do not implement Agent 1 wrapper.
- Do not implement Evidence Verification Agent.
- Do not implement answer generation.
- Do not call ShopAIKey rerank unless the code path is explicitly disabled by default or guarded by configuration.
- Do not expose final chat API.
- Do not implement frontend retrieval UI.

## 5. Dependencies

- Plan 6 must be completed for semantic candidates.
- Plan 7 must be completed for graph candidates.
- Plan 5 must be completed for vector search.

## 6. Required Files and Folders

```text
backend/app/services/hybrid_retrieval_service.py
- Orchestrates semantic search, graph expansion, candidate merge, scoring, and final Top-K.

backend/app/services/graph_retrieval_service.py
- Finds related chunks from document_entities and document_relationships.

backend/app/utils/scoring.py
- Contains score normalization, keyword overlap, metadata match, position scoring, and final score formula.

backend/app/schemas/retrieval.py
- Extend with hybrid candidate and score component schemas.

backend/app/services/shopaikey_service.py
- Add rerank placeholder helper only if needed and guarded by ENABLE_RERANK.

backend/tests/test_scoring.py
- Tests all score components and formula math.

backend/tests/test_graph_retrieval_service.py
- Tests graph candidate lookup behavior.

backend/tests/test_hybrid_retrieval_service.py
- Tests candidate merge and final ranking.
```

## 7. Data Model / Schema Changes

No database schema changes in this plan.

Hybrid candidate schema:

```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "file_name": "contract.pdf",
  "content": "Chunk text",
  "page_number": 3,
  "section_title": "Probation",
  "semantic_similarity": 0.88,
  "graph_relevance": 0.76,
  "keyword_overlap": 0.64,
  "metadata_match": 0.70,
  "recency_or_position_score": 0.50,
  "final_score": 0.78,
  "retrieval_reason": "Chunk mentions probation period and official employment condition."
}
```

Required scoring formula:

```text
final_score =
  0.45 * semantic_similarity
+ 0.25 * graph_relevance
+ 0.15 * keyword_overlap
+ 0.10 * metadata_match
+ 0.05 * recency_or_position_score
```

All component scores must be normalized:

```text
Minimum: 0.0
Maximum: 1.0
```

## 8. API Design

No required new public API endpoint in this plan.

Optionally extend `/api/retrieval/search` with a mode field:

```text
Method: POST
Path: /api/retrieval/search
Request body:
{
  "question": "string",
  "document_ids": ["uuid"],
  "top_k": 8,
  "mode": "hybrid"
}
Response body:
{
  "question": "string",
  "results": [
    {
      "chunk_id": "uuid",
      "semantic_similarity": 0.88,
      "graph_relevance": 0.76,
      "keyword_overlap": 0.64,
      "metadata_match": 0.70,
      "recency_or_position_score": 0.50,
      "final_score": 0.78
    }
  ]
}
Error responses:
- Same as Plan 6, plus graph lookup failure.
Validation rules:
- `mode` can be `semantic` or `hybrid`; default can remain `semantic` until Agent 1 uses hybrid directly.
```

## 9. Implementation Steps

1. Add `RETRIEVAL_GRAPH_TOP_K`, `RETRIEVAL_FINAL_TOP_K`, and `ENABLE_RERANK` to settings and `.env.example`.
2. Create `backend/app/utils/scoring.py`.
3. Implement `clamp_score(value)` returning `0.0` to `1.0`.
4. Implement `keyword_overlap_score(question, chunk_content)` using normalized token overlap after lowercasing and removing common punctuation.
5. Implement `metadata_match_score(question, candidate, selected_document_ids)` that rewards selected document match and obvious page/section/file metadata matches.
6. Implement `position_score(candidate)` that gives a small normalized bonus for early chunks, title/summary-like sections, or explicit date fields.
7. Implement `final_score(components)` with the exact required formula.
8. Create `graph_retrieval_service.py` with `find_graph_candidates(question, document_ids, top_k)`.
9. Extract simple question terms/entities using deterministic text matching against `document_entities.entity_name`.
10. Expand from matching entities to related chunks through `document_relationships`.
11. Compute `graph_relevance` based on entity match strength, relationship weight, and number of graph paths.
12. Create `hybrid_retrieval_service.py` with `retrieve_hybrid(question, document_ids=None, final_top_k=None)`.
13. Call semantic search for `semantic_top_k`.
14. Call graph retrieval for `graph_top_k`.
15. Merge candidates by `chunk_id`.
16. Fill missing semantic or graph scores with `0.0`.
17. Calculate all other score components.
18. Sort by `final_score desc`.
19. Return the top `RETRIEVAL_FINAL_TOP_K`.
20. Add a rerank placeholder function that clearly returns candidates unchanged when disabled.
21. Add tests for scoring formula exactness, score clamping, candidate merging, graph-only candidates, semantic-only candidates, and final ordering.

## 10. Configuration and Environment Variables

```text
RETRIEVAL_SEMANTIC_TOP_K
- Purpose: Number of semantic candidates before merge.
- Required: No.
- Example: 20
- Scope: Backend-only.

RETRIEVAL_GRAPH_TOP_K
- Purpose: Number of graph candidates before merge.
- Required: No.
- Example: 20
- Scope: Backend-only.

RETRIEVAL_FINAL_TOP_K
- Purpose: Number of final ranked chunks returned.
- Required: No.
- Example: 8
- Scope: Backend-only.

ENABLE_RERANK
- Purpose: Enables optional ShopAIKey rerank after initial hybrid retrieval.
- Required: No.
- Example: false
- Scope: Backend-only.

SHOPAIKEY_RERANK_MODEL
- Purpose: Rerank model name if rerank is enabled later.
- Required: Only if ENABLE_RERANK is true.
- Example: rerank-english-v2.0
- Scope: Backend-only.
```

## 11. Required Tests

Scoring tests:

```text
cd backend
pytest tests/test_scoring.py -v
```

Graph retrieval tests:

```text
cd backend
pytest tests/test_graph_retrieval_service.py -v
```

Hybrid retrieval tests:

```text
cd backend
pytest tests/test_hybrid_retrieval_service.py -v
```

Manual check:

```text
Run hybrid retrieval for a question against a processed, indexed, graph-built document.
Confirm results are sorted by final_score.
Confirm each result includes all five score components.
```

Formula check:

```text
For components 1.0, 1.0, 1.0, 1.0, 1.0, final_score must equal 1.0.
For components 0.0, 0.0, 0.0, 0.0, 0.0, final_score must equal 0.0.
```

## 12. Acceptance Criteria

- Hybrid retrieval merges semantic and graph candidates.
- All score components are present and normalized.
- Final score uses the exact required formula.
- Final results are sorted descending by `final_score`.
- Top-K values are configurable.
- Graph-only candidates can appear if relevant.
- Semantic-only candidates can appear if relevant.
- Rerank is optional and does not replace verification.
- No agent, verification, or answer generation logic is implemented.

## 13. Failure Handling

- Semantic retrieval failure should fail the hybrid request unless a deliberate fallback is implemented and documented.
- Graph retrieval failure should be logged and can return semantic-only candidates only if the response marks graph scores as unavailable; otherwise fail clearly.
- Missing graph rows should produce graph scores of `0.0`, not a crash.
- Score calculation must clamp invalid values.
- Empty candidate sets return an empty list.
- Invalid final Top-K values return validation errors.

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

The report must include one scored candidate example showing all five components and `final_score`.

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

- Confirm the formula weights are exactly `0.45`, `0.25`, `0.15`, `0.10`, and `0.05`.
- Confirm scores are normalized to `0.0` through `1.0`.
- Confirm rerank does not bypass later evidence verification.
- Confirm selected document filters still apply.
