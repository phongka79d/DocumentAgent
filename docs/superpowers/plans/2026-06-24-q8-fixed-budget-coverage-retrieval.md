# Fixed-Budget Coverage Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve exhaustive, dispersed-evidence questions such as Alice Q8 without increasing reranker input documents, reranker input text, answer context tokens, or adding document-specific runtime logic.

**Architecture:** Add a local evidence-grouping service and use it to reallocate the existing candidate budget across distinct evidence clusters. Keep the current candidate cardinality, request scores for the same reranker documents, select diverse final anchors locally, and spend existing context slots on uncovered anchors before neighbors. Add local coverage metrics and only proceed to bounded snippet packing if the required fixed-budget batch does not meet the behavioral gate.

**Tech Stack:** Python 3.13, FastAPI, LangGraph, Pydantic, Qdrant, Supabase, Jina reranker, pytest.

---

## Scope and Non-Negotiable Constraints

- Production code must not contain `Alice`, song/poem titles, character names, the Alice document ID, known chunk indexes, question text, or expected answer terms.
- Preserve the existing pool cardinality produced for a request. The observed Q8 pool was 15 documents; it must remain at most 15.
- Preserve `RETRIEVAL_CONTEXT_MAX_TOKENS=4000` and the normal eight-context-item cap in the required batch.
- Preserve `RETRIEVAL_FINAL_TOP_K=5` for primary anchors.
- Do not add an LLM call.
- Keep insufficient-context answers source-free.
- Evaluation-specific expected concepts may exist only under `backend/evaluation/` or `backend/tests/`, never under `backend/app/`.

## File Map

**Create**

- `backend/app/services/retrieval_diversity.py`: generic evidence grouping and stable group-diverse selection.
- `backend/tests/test_retrieval_diversity.py`: unit tests for grouping, ordering, and fixed cardinality.
- `backend/evaluation/datasets/alice_coverage_v1.json`: evaluation-only expected concepts and aliases.

**Modify**

- `backend/app/models/schemas.py`: optional transient `evidence_group_id` on retrieval candidates.
- `backend/app/services/score_fusion.py`: reallocate the existing legacy pool budget across evidence groups.
- `backend/app/services/retrieval.py`: request scores for the unchanged reranker input and select five group-diverse anchors.
- `backend/app/services/retrieval_context.py`: use scored tail candidates before neighbors while respecting eight items and 4,000 tokens.
- `backend/app/graphs/query_state.py`: carry `rerank_scored_chunks`.
- `backend/app/graphs/query_nodes.py`: pass scored chunks to context assembly and publish coverage metrics.
- `backend/app/services/citation_validation.py`: calculate cited evidence-group coverage locally.
- `backend/scripts/eval_alice.py`: replace answer-length scoring with an external evaluation rubric.
- `backend/tests/test_score_fusion.py`: fixed-budget pool regression tests.
- `backend/tests/test_query_graph.py`: reranker, state, grounding, and no-source regressions.
- `backend/tests/test_retrieval_context.py`: anchor-before-neighbor and budget tests.
- `backend/tests/test_citation_validation.py`: local coverage-metric tests.
- `docs/reports/alice_fail_partial_root_cause_report.md`: append verified after-results only after execution.

---

## Batch 1: Required Fixed-Budget Retrieval Changes

### Task 1: Add Generic Evidence Grouping

**Files:**

- Create: `backend/app/services/retrieval_diversity.py`
- Create: `backend/tests/test_retrieval_diversity.py`
- Modify: `backend/app/models/schemas.py:91-112`

- [x] **Step 1: Write failing grouping tests**

Create `backend/tests/test_retrieval_diversity.py` with these behaviors:

```python
from app.core.config import Settings
from app.services import retrieval_diversity


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        RETRIEVAL_CONTEXT_WINDOW=1,
        CHUNK_SIZE_TOKENS=500,
        CHUNK_OVERLAP_TOKENS=150,
    )


def _candidate(chunk_id: str, index: int, content: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": "document-a",
        "chunk_index": index,
        "content": content,
        "section_path": [],
    }


def test_assign_evidence_groups_clusters_adjacent_overlapping_chunks():
    shared = "shared overlap words from a continued paragraph"
    grouped = retrieval_diversity.assign_evidence_groups(
        [
            _candidate("a", 10, f"opening {shared}"),
            _candidate("b", 11, f"{shared} closing"),
            _candidate("c", 30, "independent evidence elsewhere"),
        ],
        settings=_settings(),
    )

    assert grouped[0]["evidence_group_id"] == grouped[1]["evidence_group_id"]
    assert grouped[0]["evidence_group_id"] != grouped[2]["evidence_group_id"]


def test_select_group_diverse_keeps_first_ranked_item_and_distinct_groups():
    candidates = [
        {**_candidate("top", 0, "top"), "evidence_group_id": "g1"},
        {**_candidate("duplicate", 1, "duplicate"), "evidence_group_id": "g1"},
        {**_candidate("second", 20, "second"), "evidence_group_id": "g2"},
        {**_candidate("third", 40, "third"), "evidence_group_id": "g3"},
    ]

    selected = retrieval_diversity.select_group_diverse(candidates, limit=3)

    assert [item["chunk_id"] for item in selected] == ["top", "second", "third"]


def test_select_group_diverse_fills_by_original_rank_after_group_coverage():
    candidates = [
        {**_candidate("a", 0, "a"), "evidence_group_id": "g1"},
        {**_candidate("b", 1, "b"), "evidence_group_id": "g1"},
        {**_candidate("c", 20, "c"), "evidence_group_id": "g2"},
    ]

    selected = retrieval_diversity.select_group_diverse(candidates, limit=3)

    assert [item["chunk_id"] for item in selected] == ["a", "c", "b"]
```

- [x] **Step 2: Run tests and verify RED**

Run:

```powershell
cd backend
python -m pytest tests/test_retrieval_diversity.py -q
```

Expected: collection fails because `app.services.retrieval_diversity` does not exist.

- [x] **Step 3: Implement grouping and stable selection**

Create `backend/app/services/retrieval_diversity.py` with:

```python
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.config import Settings, get_settings

def _tokens(value: Any) -> set[str]:
    text = str(value or "").strip().lower()
    # Unicode-safe: Remove punctuation and split by whitespace
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    return set(text.split())


def _overlap_coefficient(left: Any, right: Any) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    denominator = min(len(left_tokens), len(right_tokens))
    if denominator == 0:
        return 0.0
    return len(left_tokens & right_tokens) / denominator


def _section_path(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    raw = candidate.get("section_path") or []
    if isinstance(raw, (str, bytes)):
        text = str(raw).strip()
        return (text,) if text else ()
    return tuple(str(item).strip() for item in raw if str(item).strip())


def assign_evidence_groups(
    candidates: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    resolved = settings if settings is not None else get_settings()
    overlap_threshold = resolved.CHUNK_OVERLAP_TOKENS / max(1, resolved.CHUNK_SIZE_TOKENS)
    groups: list[list[dict[str, Any]]] = []
    output: list[dict[str, Any]] = []

    for raw_candidate in candidates:
        candidate = dict(raw_candidate)
        existing_group = str(candidate.get("evidence_group_id") or "").strip()
        if existing_group:
            output.append(candidate)
            continue

        document_id = str(candidate.get("document_id") or "")
        chunk_index = int(candidate.get("chunk_index") or 0)
        section_path = _section_path(candidate)
        matched_group: int | None = None

        for group_index, group in enumerate(groups):
            representative = group[-1]
            if str(representative.get("document_id") or "") != document_id:
                continue
            representative_index = int(representative.get("chunk_index") or 0)
            if abs(chunk_index - representative_index) > resolved.RETRIEVAL_CONTEXT_WINDOW:
                continue
            same_section = bool(section_path) and section_path == _section_path(representative)
            overlaps = _overlap_coefficient(
                candidate.get("content"), representative.get("content")
            ) >= overlap_threshold
            if same_section or overlaps:
                matched_group = group_index
                break

        if matched_group is None:
            matched_group = len(groups)
            groups.append([])
        candidate["evidence_group_id"] = f"evidence-{matched_group + 1}"
        groups[matched_group].append(candidate)
        output.append(candidate)

    return output


def select_group_diverse(
    candidates: Sequence[Mapping[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    ordered = [dict(candidate) for candidate in candidates]
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    covered_groups: set[str] = set()

    for candidate in ordered:
        chunk_id = str(candidate.get("chunk_id") or candidate.get("id") or "")
        group_id = str(candidate.get("evidence_group_id") or chunk_id)
        if not chunk_id or chunk_id in selected_ids or group_id in covered_groups:
            continue
        selected.append(candidate)
        selected_ids.add(chunk_id)
        covered_groups.add(group_id)
        if len(selected) >= limit:
            return selected

    for candidate in ordered:
        chunk_id = str(candidate.get("chunk_id") or candidate.get("id") or "")
        if not chunk_id or chunk_id in selected_ids:
            continue
        selected.append(candidate)
        selected_ids.add(chunk_id)
        if len(selected) >= limit:
            break
    return selected
```

Add this optional field to `RetrievalCandidate` in `backend/app/models/schemas.py`:

```python
evidence_group_id: str | None = None
```

- [x] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_retrieval_diversity.py tests/test_contracts.py tests/test_keyword_search.py -q
```

Expected: all selected tests pass.

- [x] **Step 5: Commit Task 1**

```powershell
git add backend/app/services/retrieval_diversity.py backend/app/models/schemas.py backend/tests/test_retrieval_diversity.py
git commit -m "feat: add generic evidence grouping"
```

### Task 2: Reallocate the Existing Reranker Pool

**Files:**

- Modify: `backend/app/services/score_fusion.py:223-293`
- Modify: `backend/tests/test_score_fusion.py:258-331`

- [x] **Step 1: Write a failing fixed-cardinality regression test**

Append to `backend/tests/test_score_fusion.py`:

```python
def test_select_rerank_candidates_improves_group_coverage_without_growing_legacy_pool():
    settings = _settings(
        RETRIEVAL_RERANK_FUSED_TOP_K=3,
        RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K=2,
        RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K=1,
        RETRIEVAL_RERANK_CANDIDATE_TOP_K=10,
        RETRIEVAL_CONTEXT_WINDOW=1,
    )
    near_a = _candidate("near-a", chunk_index=10, content="shared overlap alpha beta gamma")
    near_b = _candidate("near-b", chunk_index=11, content="shared overlap alpha beta gamma continuation")
    far_b = _candidate("far-b", chunk_index=30, content="independent second evidence")
    far_c = _candidate("far-c", chunk_index=60, content="independent third evidence")
    for rank, candidate in enumerate([near_a, near_b, far_b, far_c], start=1):
        candidate.update(
            semantic_rank=rank,
            semantic_score=1.0 / rank,
            retrieval_paths=[RetrievalPath.SEMANTIC],
            subquery_ids=["q1"],
        )

    fused = score_fusion.fuse_candidates(
        [[near_a, near_b, far_b, far_c]],
        settings=settings.model_copy(update={"RETRIEVAL_FUSION_TOP_K": 10}),
    )
    selected = score_fusion.select_rerank_candidates(
        {"q1:semantic": [near_a, near_b, far_b, far_c]},
        fused_candidates=fused,
        settings=settings,
    )

    assert len(selected) == 3
    assert selected[0]["chunk_id"] == fused[0]["chunk_id"]
    assert {item["chunk_id"] for item in selected} == {"near-a", "far-b", "far-c"}
    assert len({item["evidence_group_id"] for item in selected}) == 3
```

- [x] **Step 2: Run test and verify RED**

Run:

```powershell
python -m pytest tests/test_score_fusion.py::test_select_rerank_candidates_improves_group_coverage_without_growing_legacy_pool -q
```

Expected: FAIL because current selection returns candidates by fused/path order and does not assign evidence groups.

- [x] **Step 3: Modify pool construction without changing its size**

In `select_rerank_candidates`:

1. Keep the current ordered construction exactly long enough to calculate
   `legacy_pool = ordered[:RETRIEVAL_RERANK_CANDIDATE_TOP_K]`.
2. Set `pool_budget = len(legacy_pool)`. This is the critical no-growth invariant.
3. Build a deduplicated universe in this order: legacy pool, then every fused candidate.
4. Call `assign_evidence_groups(universe, settings=resolved_settings)`.
5. Return `select_group_diverse(grouped, limit=pool_budget)`.

Use these imports:

```python
from app.services import retrieval_diversity
```

Replace the final return with:

```python
legacy_pool = ordered[: resolved_settings.RETRIEVAL_RERANK_CANDIDATE_TOP_K]
pool_budget = len(legacy_pool)

universe: list[dict[str, Any]] = []
universe_seen: set[str] = set()
for candidate in [*legacy_pool, *fused_candidates]:
    chunk_id = _normalize_text(candidate.get("chunk_id") or candidate.get("id"))
    if chunk_id is None or chunk_id in universe_seen:
        continue
    universe.append(dict(candidate))
    universe_seen.add(chunk_id)

grouped = retrieval_diversity.assign_evidence_groups(
    universe,
    settings=resolved_settings,
)
return retrieval_diversity.select_group_diverse(grouped, limit=pool_budget)
```

- [x] **Step 4: Run pool tests**

Run:

```powershell
python -m pytest tests/test_score_fusion.py tests/test_query_graph.py::test_fuse_candidates_node_preserves_strong_semantic_candidate_below_fused_cutoff -q
```

Expected: score-fusion tests pass, and the existing strong-semantic/jar regression remains green.

- [x] **Step 5: Add a pool-size metric assertion**

Extend the query-graph fusion test to assert:

```python
assert result["retrieval_metrics"]["rerank_candidate_count"] == len(
    result["retrieved_chunks"]
)
assert len(result["retrieved_chunks"]) <= settings.RETRIEVAL_RERANK_CANDIDATE_TOP_K
```

Run:

```powershell
python -m pytest tests/test_score_fusion.py tests/test_query_graph.py -q
```

Expected: all tests pass.

- [x] **Step 6: Commit Task 2**

```powershell
git add backend/app/services/score_fusion.py backend/tests/test_score_fusion.py backend/tests/test_query_graph.py
git commit -m "fix: preserve evidence diversity in rerank pool"
```

### Task 3: Score the Same Inputs and Select Five Diverse Anchors

**Files:**

- Modify: `backend/app/services/retrieval.py:638-720`
- Modify: `backend/app/graphs/query_nodes.py:604-640`
- Modify: `backend/app/graphs/query_state.py:25-27`
- Modify: `backend/tests/test_query_graph.py:1090-1250`

- [x] **Step 1: Write the failing reranker test**

Change the reranker test fixture to return scores for all three submitted documents,
with the two highest scores in one evidence group:

```python
def test_jina_rerank_scores_unchanged_input_and_selects_distinct_groups():
    settings = _test_settings().model_copy(
        update={
            "RETRIEVAL_RERANK_CANDIDATE_TOP_K": 3,
            "RETRIEVAL_FINAL_TOP_K": 2,
        }
    )
    retrieved_chunks = [
        {
            "chunk_id": "near-a",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 10,
            "content": "near a",
            "evidence_group_id": "group-near",
        },
        {
            "chunk_id": "near-b",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 11,
            "content": "near b",
            "evidence_group_id": "group-near",
        },
        {
            "chunk_id": "far",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 40,
            "content": "far evidence",
            "evidence_group_id": "group-far",
        },
    ]
    fake_jina_client = SimpleNamespace(
        http_client=FakeHttpClient(
            response=FakeHttpResponse(
                {
                    "results": [
                        {"index": 0, "relevance_score": 0.99},
                        {"index": 1, "relevance_score": 0.98},
                        {"index": 2, "relevance_score": 0.80},
                    ]
                }
            )
        ),
        model=settings.JINA_RERANK_MODEL,
    )

    result = query_nodes.jina_rerank_node(
        {
            "prepared_query": "Which controls and owners are listed?",
            "retrieved_chunks": retrieved_chunks,
            "retrieval_metrics": {},
        },
        settings=settings,
        jina_client=fake_jina_client,
    )

    request = fake_jina_client.http_client.post_calls[0]["json"]
    assert request["documents"] == ["near a", "near b", "far evidence"]
    assert request["top_n"] == 3
    assert [item["chunk_id"] for item in result["reranked_chunks"]] == [
        "near-a",
        "far",
    ]
    assert len(result["rerank_scored_chunks"]) == 3
```

- [x] **Step 2: Run test and verify RED**

Run:

```powershell
python -m pytest tests/test_query_graph.py::test_jina_rerank_scores_unchanged_input_and_selects_distinct_groups -q
```

Expected: FAIL because current code requests `top_n=2` and returns no
`rerank_scored_chunks`.

- [x] **Step 3: Add a structured rerank result**

In `backend/app/services/retrieval.py`, add:

```python
def rerank_chunks_result(
    question: str,
    chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
    jina_client: Any | None = None,
    retry_attempts: list[RetryAttempt] | None = None,
) -> dict[str, list[dict[str, Any]]]:
```

Move current reranking into this function and make these behavioral changes:

```python
"top_n": len(documents)
```

After validating all returned indexes, attach `rerank_score` to every scored chunk,
preserve provider score order in `scored_chunks`, and select final anchors with:

```python
reranked_chunks = retrieval_diversity.select_group_diverse(
    scored_chunks,
    limit=resolved_settings.RETRIEVAL_FINAL_TOP_K,
)
return {
    "reranked_chunks": reranked_chunks,
    "rerank_scored_chunks": scored_chunks,
}
```

Keep `rerank_chunks(...)` as a compatibility wrapper:

```python
def rerank_chunks(...existing signature...) -> list[dict[str, Any]]:
    return rerank_chunks_result(
        question,
        chunks,
        settings=settings,
        jina_client=jina_client,
        retry_attempts=retry_attempts,
    )["reranked_chunks"]
```

On provider failure, return the existing deterministic fallback as both
`reranked_chunks` and `rerank_scored_chunks`; do not issue another provider request.

- [x] **Step 4: Carry scored chunks through the graph**

Add to `QueryState`:

```python
rerank_scored_chunks: list[dict[str, Any]]
```

Update `jina_rerank_node` to call `rerank_chunks_result`, return both lists, and add:

```python
metrics["rerank_scored_count"] = len(rerank_result["rerank_scored_chunks"])
```

- [x] **Step 5: Run reranker and fallback tests**

Run:

```powershell
python -m pytest tests/test_query_graph.py -k "rerank or jina or fusion" -q
```

Expected: all selected tests pass. Confirm every request's `documents` list is
unchanged and only `top_n` response cardinality changes.

- [x] **Step 6: Commit Task 3**

```powershell
git add backend/app/services/retrieval.py backend/app/graphs/query_nodes.py backend/app/graphs/query_state.py backend/tests/test_query_graph.py
git commit -m "feat: select diverse anchors from full rerank scores"
```

### Task 4: Spend Existing Context Slots on Uncovered Anchors Before Neighbors

**Files:**

- Modify: `backend/app/services/retrieval_context.py:351-614`
- Modify: `backend/app/graphs/query_nodes.py:666-689`
- Modify: `backend/tests/test_retrieval_context.py:162-309`
- Modify: `backend/tests/test_query_graph.py:1629-1765`

- [ ] **Step 1: Write the failing context-priority test**

Append to `backend/tests/test_retrieval_context.py`:

```python
def test_context_uses_uncovered_scored_anchors_before_neighbors(monkeypatch):
    from app.services import retrieval_context

    monkeypatch.setattr(
        retrieval_context.chunk_service,
        "get_chunks_by_document_and_indexes",
        lambda *args, **kwargs: [
            {
                "id": "neighbor",
                "document_id": DOC_A,
                "chunk_index": 1,
                "content": "neighbor",
                "token_count": 1,
            }
        ],
    )
    primary = [
        {
            "chunk_id": "primary",
            "document_id": DOC_A,
            "file_name": "doc.pdf",
            "chunk_index": 2,
            "content": "primary",
            "token_count": 1,
            "evidence_group_id": "g1",
        }
    ]
    scored = [
        *primary,
        {
            "chunk_id": "coverage-a",
            "document_id": DOC_A,
            "file_name": "doc.pdf",
            "chunk_index": 20,
            "content": "coverage a",
            "token_count": 1,
            "evidence_group_id": "g2",
        },
        {
            "chunk_id": "coverage-b",
            "document_id": DOC_A,
            "file_name": "doc.pdf",
            "chunk_index": 40,
            "content": "coverage b",
            "token_count": 1,
            "evidence_group_id": "g3",
        },
    ]

    result = retrieval_context.expand_neighbor_context_result(
        primary,
        coverage_chunks=scored,
        settings=_settings(context_max_candidates=3, context_max_tokens=3),
    )

    assert [item["chunk_id"] for item in result["context_chunks"]] == [
        "primary",
        "coverage-a",
        "coverage-b",
    ]
    assert result["retrieval_metrics"]["context_neighbor_count"] == 0
    assert result["retrieval_metrics"]["context_evidence_group_count"] == 3
    assert result["retrieval_metrics"]["context_token_count"] == 3
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
python -m pytest tests/test_retrieval_context.py::test_context_uses_uncovered_scored_anchors_before_neighbors -q
```

Expected: FAIL because `coverage_chunks` is not accepted.

- [ ] **Step 3: Add fixed-budget coverage filling**

Add this optional argument to both context functions:

```python
coverage_chunks: Sequence[Mapping[str, Any]] | None = None
```

After adding primary reranked chunks and before querying or appending neighbors:

```python
covered_groups = {
    str(chunk.get("evidence_group_id") or chunk.get("chunk_id"))
    for chunk in selected
}
for chunk in coverage_chunks or []:
    group_id = str(chunk.get("evidence_group_id") or chunk.get("chunk_id"))
    if group_id in covered_groups:
        continue
    if not try_add_chunk(chunk):
        continue
    covered_groups.add(group_id)
    if not can_select_more():
        break
```

Only after this loop should the existing neighbor logic run. Keep both existing caps
unchanged.

Add this metric:

```python
"context_evidence_group_count": len(
    {
        str(chunk.get("evidence_group_id") or chunk.get("chunk_id"))
        for chunk in selected
    }
),
```

- [ ] **Step 4: Pass scored candidates from the graph node**

In `expand_neighbor_context_node`, call:

```python
context_result = retrieval_context.expand_neighbor_context_result(
    reranked_chunks,
    coverage_chunks=state.get("rerank_scored_chunks") or reranked_chunks,
    settings=resolved_settings,
    supabase_client=supabase_client,
    retrieval_hints=state.get("retrieval_hints"),
    document_ids=_normalize_document_ids(state.get("document_ids")),
)
```

- [ ] **Step 5: Run context and source regressions**

Run:

```powershell
python -m pytest tests/test_retrieval_context.py tests/test_query_graph.py -k "context or source or insufficient" -q
```

Expected: all selected tests pass. Existing neighbor tests may need expected ordering
updated only where a supplied scored tail now correctly precedes neighbors; do not
weaken count, token, or source assertions.

- [ ] **Step 6: Commit Task 4**

```powershell
git add backend/app/services/retrieval_context.py backend/app/graphs/query_nodes.py backend/tests/test_retrieval_context.py backend/tests/test_query_graph.py
git commit -m "fix: prioritize uncovered evidence before neighbors"
```

### Task 5: Add Local Evidence-Group Coverage Metrics

**Files:**

- Modify: `backend/app/services/citation_validation.py`
- Modify: `backend/app/graphs/query_nodes.py:879-887`
- Modify: `backend/tests/test_citation_validation.py`

- [ ] **Step 1: Write a failing metric test**

Add:

```python
def test_cited_evidence_group_coverage_counts_distinct_groups():
    context = [
        {"chunk_id": "a", "citation_key": "S1", "evidence_group_id": "g1"},
        {"chunk_id": "b", "citation_key": "S2", "evidence_group_id": "g1"},
        {"chunk_id": "c", "citation_key": "S3", "evidence_group_id": "g2"},
    ]

    metrics = citation_validation.evidence_group_coverage(
        context_chunks=context,
        cited_keys=["S1", "S2"],
    )

    assert metrics == {
        "selected_evidence_group_count": 2,
        "cited_evidence_group_count": 1,
        "evidence_group_coverage_rate": 0.5,
    }
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
python -m pytest tests/test_citation_validation.py::test_cited_evidence_group_coverage_counts_distinct_groups -q
```

Expected: FAIL because the helper does not exist.

- [ ] **Step 3: Implement the pure local metric**

Add `evidence_group_coverage(context_chunks, cited_keys)` to
`citation_validation.py`:

```python
def evidence_group_coverage(
    *,
    context_chunks: Sequence[Mapping[str, Any]],
    cited_keys: Sequence[str],
) -> dict[str, int | float]:
    keyed_context = assign_citation_keys(context_chunks)
    key_to_group = {
        str(chunk["citation_key"]): str(
            chunk.get("evidence_group_id")
            or chunk.get("chunk_id")
            or chunk.get("id")
        )
        for chunk in keyed_context
    }
    selected_groups = set(key_to_group.values())
    cited_groups = {
        key_to_group[key]
        for key in cited_keys
        if key in key_to_group
    }
    selected_count = len(selected_groups)
    return {
        "selected_evidence_group_count": selected_count,
        "cited_evidence_group_count": len(cited_groups),
        "evidence_group_coverage_rate": (
            len(cited_groups) / selected_count if selected_count else 0.0
        ),
    }
```

In `validate_citations_node`, merge the returned values into `retrieval_metrics`.
Do not change grounding acceptance, regeneration, or final source behavior in this
task.

- [ ] **Step 4: Run citation and insufficient-context tests**

Run:

```powershell
python -m pytest tests/test_citation_validation.py tests/test_grounding.py tests/test_api_chat.py -q
```

Expected: all tests pass, including insufficient-context responses with `sources=[]`.

- [ ] **Step 5: Commit Task 5**

```powershell
git add backend/app/services/citation_validation.py backend/app/graphs/query_nodes.py backend/tests/test_citation_validation.py
git commit -m "feat: report cited evidence group coverage"
```

---

## Batch 1 Verification Gate

### Task 6: Verify Behavior and Token Invariants

**Files:**

- Modify: `backend/scripts/eval_alice.py`
- Create: `backend/evaluation/datasets/alice_coverage_v1.json`
- Modify: `docs/reports/alice_fail_partial_root_cause_report.md`

- [ ] **Step 1: Add evaluation-only rubric data**

Create `backend/evaluation/datasets/alice_coverage_v1.json` with the Q8 evaluation
policy below. Alice-specific terms remain evaluation data and do not enter
`backend/app/`:

```json
{
  "8": {
    "positive_question": true,
    "required_groups": [
      {"id": "crocodile", "description": "The poem 'How doth the little crocodile' recited by Alice"},
      {"id": "mouse_tale", "description": "The Mouse's long and sad tale"},
      {"id": "father_william", "description": "The poem 'You Are Old, Father William' recited by Alice"},
      {"id": "duchess_lullaby", "description": "The lullaby 'Speak roughly to your little boy' sung by the Duchess"},
      {"id": "twinkle_bat", "description": "The song/poem 'Twinkle, twinkle, little bat' sung by the Hatter"},
      {"id": "lobster_quadrille", "description": "The Lobster Quadrille song performed by the Mock Turtle"},
      {"id": "sluggard_variant", "description": "The altered poem 'Tis the Voice of the Sluggard' recited by Alice"},
      {"id": "beautiful_soup", "description": "The song 'Beautiful Soup' sung by the Mock Turtle"},
      {"id": "queen_tarts", "description": "The tart accusation rhyme/poem read by the White Rabbit"},
      {"id": "trial_verse", "description": "The trial verse/poem 'They told me you had been to her' read by the White Rabbit"}
    ]
  }
}
```

This policy explicitly describes the expected evidence items for LLM semantic evaluation. If the
product owner chooses a narrower literary definition, change only this dataset before
the first post-change evaluation and record that decision in the report.

- [ ] **Step 2: Replace answer-length scoring**

Refactor `scripts/eval_alice.py` so scoring reads the rubric file and returns:

```python
def status_for_coverage(*, matched_groups: int, required_groups: int) -> str:
    if required_groups == 0:
        return "PASS"
    if matched_groups == required_groups:
        return "PASS"
    if matched_groups > 0:
        return "PARTIAL"
    return "FAIL"
```

Explicitly classify `SAFE_INSUFFICIENT_CONTEXT_MESSAGE` as `FAIL` for positive
questions. Keep negative-question no-source assertions separate.

Add the command-line filter directly rather than relying on a later adjustment:

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--question", choices=[item[0] for item in QUESTIONS])
args = parser.parse_args()
selected_questions = [
    item for item in QUESTIONS if args.question is None or item[0] == args.question
]
```

Replace `for num, question in QUESTIONS:` with:

```python
for num, question in selected_questions:
```

For rubric-backed questions, call the LLM Judge to check semantic coverage of the required
groups against the answer, and call `status_for_coverage` using the count of matched groups.
For other questions, print `UNSCORED` in the script and use the existing behavioral test suite;
do not fall back to answer-length `PASS`.

Below is the LLM Judge evaluation prompt design and implementation:

```python
def evaluate_coverage_with_llm(answer: str, required_groups: list[dict], api_client: Any) -> list[str]:
    prompt = (
        "You are an expert quality evaluator. Read the following RAG system answer and determine which "
        "of the required information items are present in the text.\\n\\n"
        f"Answer to evaluate:\\n\\\"\\\"\\\"\\n{answer}\\n\\\"\\\"\\\"\\n\\n"
        "Required Items to check:\\n"
        + "\\n".join(f"- [{item['id']}]: {item['description']}" for item in required_groups)
        + "\\n\\nReturn strict JSON only with a 'matched_ids' string array containing only the IDs of items present in the text. "
        "Do not include items that are missing or only partially guessed without correct character mapping."
    )
    # Use the existing backend client configuration
    response = api_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    try:
        result = json.loads(response.choices[0].message.content)
        return list(result.get("matched_ids", []))
    except Exception:
        return []
```

- [ ] **Step 3: Run the full automated test suite**

Run:

```powershell
cd backend
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 4: Run Alice Q8 four times**

Ensure port 8000 is free:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
```

No output means free. Then run:

```powershell
1..4 | ForEach-Object {
    Write-Host "Q8 run $_"
    python scripts/eval_alice.py --question 8
}
```

For every run, record:

- reranker input count at most the pre-change count of 15,
- final primary anchor count at most 5,
- context candidate count at most 8,
- context token count at most 4,000,
- distinct context evidence groups,
- cited evidence-group coverage,
- Q8 rubric status.

- [ ] **Step 5: Run all ten Alice questions once**

Run:

```powershell
python scripts/eval_alice.py
```

Required result:

- Q1-Q7 and Q9-Q10 remain `PASS`.
- Q8 improves against the evaluation rubric.
- The passport/negative case remains insufficient-context with no sources.
- No page-filter Qdrant index error appears.

- [ ] **Step 6: Decide the Batch 2 gate from evidence**

Proceed to Batch 2 only when Q8 remains `PARTIAL` because relevant distinct groups
reach `rerank_scored_chunks` but cannot fit into eight full context chunks under the
4,000-token budget.

Do not proceed when the missing groups never enter the reranker pool; return to Task 2
and correct generic pool allocation while preserving the same pool size.

- [ ] **Step 7: Update the report with measured after-results**

Append the four-run table, before/after group counts, candidate counts, token counts,
and any remaining omissions to:

```text
docs/reports/alice_fail_partial_root_cause_report.md
```

Do not claim full resolution from `scripts/eval_alice.py` answer-length output.

- [ ] **Step 8: Commit Batch 1 verification artifacts**

```powershell
git add backend/scripts/eval_alice.py backend/evaluation/datasets/alice_coverage_v1.json docs/reports/alice_fail_partial_root_cause_report.md
git commit -m "test: evaluate fixed-budget coverage retrieval"
```

---

## Gated Follow-Up: Bounded Evidence Spans

Bounded span packing is intentionally not implemented by this plan. If Task 6 proves
that relevant groups reach `rerank_scored_chunks` but eight complete chunks cannot
meet the agreed Q8 rubric, stop after Batch 1 and write a separate TDD plan for span
packing. That plan must preserve full source content server-side, cap the complete
serialized answer context at 4,000 tokens, and use only local sentence/paragraph
selection. This gate prevents an unmeasured compression subsystem from being bundled
into the primary retrieval fix.

---

## Final Verification

- [ ] Run `python -m pytest -q` from `backend/` and confirm zero failures.
- [ ] Run Q8 four times and all ten questions once.
- [ ] Confirm reranker document count did not exceed the before value for identical
  plans.
- [ ] Confirm answer context did not exceed 4,000 tokens.
- [ ] Confirm Q1-Q7 and Q9-Q10 remain passing.
- [ ] Confirm insufficient-context answers return `sources=[]`.
- [ ] Confirm citations still resolve to original chunk IDs after grouping or spans.
- [ ] Run `git diff --check`.
- [ ] Review `git diff --stat` and verify no secrets, `.env`, generated evaluation
  results, or unrelated files are staged.

## Expected Outcome

The implementation should improve Q8 by reallocating existing model input toward
distinct evidence rather than increasing input. This plan is complete when eight
distinct full-chunk anchors meet the agreed rubric. If they do not, the measured gate
produces a separate, evidence-based span-packing plan rather than expanding this
scope.
