# Retrieval Regression Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve strong path-specific retrieval candidates through hybrid fusion and provision Qdrant filter indexes so answerable filtered questions reach reranking and grounded generation.

**Architecture:** Build a shared, configurable rerank candidate-pool selector that unions per-path semantic candidates, per-path keyword candidates, and fused candidates before the provider cap. Add an idempotent Qdrant payload-index manager used non-blockingly at startup and strictly before filtered semantic searches.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic Settings, Qdrant Client, LangGraph, pytest.

---

### Task 1: Configurable Diverse Rerank Candidate Pool

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/score_fusion.py`
- Modify: `backend/app/graphs/query_nodes.py`
- Modify: `backend/app/services/retrieval.py`
- Test: `backend/tests/test_config.py`
- Test: `backend/tests/test_score_fusion.py`
- Test: `backend/tests/test_query_graph.py`

- [ ] **Step 1: Add failing settings tests**

Extend `ALL_SETTINGS_FIELDS` and default assertions with:

```python
"RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K",
"RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K",
"RETRIEVAL_RERANK_FUSED_TOP_K",
```

Assert defaults are positive, configurable, and bounded. The defaults must fit the normal maximum query plan inside `RETRIEVAL_RERANK_CANDIDATE_TOP_K`.

- [ ] **Step 2: Add a failing candidate-pool behavior test**

Add a test calling the wished-for API:

```python
pool = score_fusion.select_rerank_candidates(
    path_candidates={
        "q1:semantic": semantic_q1,
        "q1:keyword": keyword_q1,
        "q2:semantic": semantic_q2,
        "q2:keyword": keyword_q2,
    },
    fused_candidates=fused,
    settings=settings,
)
```

Arrange the strongest answer-bearing semantic candidate below the fused-only cutoff. Assert it is present, duplicate chunk IDs occur once, fused metadata is retained, and semantic/keyword/fused candidates are all represented.

- [ ] **Step 3: Verify RED**

Run:

```powershell
cd backend
python -m pytest tests/test_config.py tests/test_score_fusion.py -q
```

Expected: failure because the new settings and `select_rerank_candidates` do not exist.

- [ ] **Step 4: Implement settings and selector**

Add configurable Pydantic fields to `Settings`:

```python
RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K: int = Field(default=5, ge=1, le=1000)
RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K: int = Field(default=2, ge=1, le=1000)
RETRIEVAL_RERANK_FUSED_TOP_K: int = Field(default=10, ge=1, le=1000)
RETRIEVAL_RERANK_CANDIDATE_TOP_K: int = Field(default=40, ge=1, le=1000)
```

Implement `select_rerank_candidates` so it:

1. reads ordered path lists by path suffix;
2. takes each path-specific quota independently;
3. takes the configured fused quota;
4. substitutes the fused representation by chunk ID when available;
5. deduplicates deterministically;
6. applies the total candidate cap after the union.

- [ ] **Step 5: Add a failing query-pipeline test**

Construct `path_candidates` where an answer-bearing semantic candidate is outside the top fused quota. Run `fuse_candidates_node`, then `jina_rerank_node` with a fake Jina transport. Assert the answer-bearing candidate content appears in Jina's `documents` payload.

- [ ] **Step 6: Verify pipeline RED**

Run:

```powershell
cd backend
python -m pytest tests/test_query_graph.py -k "diverse or rerank_candidate" -q
```

Expected: the answer-bearing candidate is absent before integration.

- [ ] **Step 7: Integrate the shared selector**

Use `select_rerank_candidates` in:

- `query_nodes.fuse_candidates_node` for the production graph;
- `retrieval.retrieve_hybrid_chunks` for compatibility callers.

Keep `fused_candidates` for metrics and deterministic fallback. Set `retrieved_chunks` to the diverse pool that is actually passed to Jina.

- [ ] **Step 8: Verify GREEN**

Run:

```powershell
cd backend
python -m pytest tests/test_config.py tests/test_score_fusion.py tests/test_query_graph.py -q
```

Expected: all targeted candidate-pool tests pass.

### Task 2: Idempotent Qdrant Filter Index Provisioning

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/qdrant_client.py`
- Modify: `backend/app/services/retrieval.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_qdrant_indexes.py`
- Test: `backend/tests/test_query_graph.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Add failing Qdrant index-manager tests**

Create fake collection info with an existing `payload_schema`. Test the wished-for API:

```python
created = ensure_qdrant_payload_indexes(
    client,
    collection_name="document_chunks_v1",
    field_names={"page_start", "page_end"},
)
```

Assert missing fields are created with `PayloadSchemaType.INTEGER`, `wait=True`, and existing fields are skipped.

- [ ] **Step 2: Add a failing filtered-search behavior test**

Use a fake Qdrant client that records `get_collection`, `create_payload_index`, and `query_points`. Call `search_semantic_chunks` with page filters. Assert both numeric indexes exist before `query_points` and the range conditions remain in the query filter.

- [ ] **Step 3: Add a failing startup resilience test**

Add `ENSURE_QDRANT_PAYLOAD_INDEXES_ON_STARTUP` to the settings contract with a production default of `true`. Patch index provisioning to raise a connection error while the setting is enabled, enter `TestClient(create_app(settings))`, and assert `GET /api/health` remains `200`. Add a second assertion that disabled provisioning performs no Qdrant call.

- [ ] **Step 4: Verify RED**

Run:

```powershell
cd backend
python -m pytest tests/test_qdrant_indexes.py tests/test_query_graph.py tests/test_config.py -q
```

Expected: failures because the index registry, provisioning function, and startup hook do not exist.

- [ ] **Step 5: Implement the typed index registry**

In `qdrant_client.py`, define a mapping from current filterable `QdrantPayloadKey` fields to Qdrant schemas:

```python
FILTERABLE_PAYLOAD_INDEXES = {
    QdrantPayloadKey.DOCUMENT_ID: PayloadSchemaType.KEYWORD,
    QdrantPayloadKey.MIME_TYPE: PayloadSchemaType.KEYWORD,
    QdrantPayloadKey.HEADING: PayloadSchemaType.TEXT,
    QdrantPayloadKey.SECTION_PATH: PayloadSchemaType.KEYWORD,
    QdrantPayloadKey.PAGE_START: PayloadSchemaType.INTEGER,
    QdrantPayloadKey.PAGE_END: PayloadSchemaType.INTEGER,
    QdrantPayloadKey.CHUNK_TYPE: PayloadSchemaType.KEYWORD,
}
```

Implement collection schema inspection and missing-index creation without creating the collection itself.

- [ ] **Step 6: Integrate filter-time provisioning**

Before an explicitly metadata-filtered Qdrant query, derive required field names from active metadata filters and call the index manager. Wrap failures as a safe `RetrievalError`; do not remove filters. Document allow-list filtering remains unchanged and receives its index through startup provisioning.

- [ ] **Step 7: Integrate non-blocking startup provisioning**

Add `ENSURE_QDRANT_PAYLOAD_INDEXES_ON_STARTUP: bool = True` and a FastAPI lifespan that attempts to ensure the full registry only when enabled. Catch and log failures, then yield so unfiltered routes remain available. Test/offline callers can disable the operational side effect through configuration rather than a test-only branch.

- [ ] **Step 8: Verify GREEN**

Run:

```powershell
cd backend
python -m pytest tests/test_qdrant_indexes.py tests/test_query_graph.py tests/test_config.py -q
```

Expected: all index and startup tests pass.

### Task 3: Documentation and Existing Safety Behavior

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`
- Test: `backend/tests/test_api_chat.py`
- Test: `backend/tests/test_query_graph.py`

- [ ] **Step 1: Re-run insufficient-context regression tests**

Run:

```powershell
cd backend
python -m pytest tests/test_api_chat.py -k "insufficient or grounding" -q
python -m pytest tests/test_query_graph.py -k "grounding_failure or insufficient" -q
```

Expected: source-free insufficient-context tests pass unchanged.

- [ ] **Step 2: Document configuration and operations**

Document the three path/fused quota settings, total provider cap, automatic payload-index provisioning, non-blocking startup behavior, and external collection creation requirement.

- [ ] **Step 3: Run documentation consistency searches**

Run:

```powershell
rg "RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K|RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K|RETRIEVAL_RERANK_FUSED_TOP_K|payload index" README.md backend/README.md
```

Expected: both runbooks contain the new settings and index behavior.

### Task 4: Full Verification and Alice Evaluation

**Files:**
- No production edits expected.
- Generated reports remain ignored.

- [ ] **Step 1: Run targeted retrieval tests**

```powershell
cd backend
python -m pytest tests/test_config.py tests/test_score_fusion.py tests/test_qdrant_indexes.py tests/test_query_graph.py tests/test_api_chat.py -q
```

Expected: all pass.

- [ ] **Step 2: Run the full backend suite**

```powershell
cd backend
python -m pytest -q
```

Expected: all pass.

- [ ] **Step 3: Run frontend build**

```powershell
cd frontend
npm run build
```

Expected: exit code 0.

- [ ] **Step 4: Run the ten-question Alice evaluation**

Start the backend using the existing local environment, run the same ten questions and unchanged expected terms, and record:

- pass/fail per case;
- answer and source count;
- jar candidate's semantic, fused, and reranker-pool positions;
- page-filter index provisioning evidence;
- passport answer with zero sources.

- [ ] **Step 5: Compare before and after**

Report the known before score of `6/10` and the fresh after score. Do not claim the pre-existing `EAT ME` or rabbit-hole cases are fixed unless the unchanged evaluation passes them.

- [ ] **Step 6: Review the final diff**

Run:

```powershell
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors and only planned files changed.



