# Retrieval Regression Fix Design

**Date:** 2026-06-23
**Baseline:** `36ae00f1405c7715556200ba477fd53be49804ba` (`CHECKPOINT5`)

## Problem

Phase 3 hybrid retrieval introduced two regressions after `CHECKPOINT5`:

1. Reciprocal-rank fusion can push a strong semantic candidate below the global rerank candidate cutoff. The candidate is retrieved but never reaches Jina, so an adjacent, less relevant passage can produce a grounded but incorrect answer.
2. Metadata filters use Qdrant numeric range conditions without provisioning the required payload indexes. Existing collections therefore reject page filters before semantic retrieval runs.

The fix must remain document- and query-agnostic. It must preserve citation validation, grounding verification, deterministic fallbacks, and source-free insufficient-context responses.

## Candidate Pool Design

Add a shared candidate-pool selector in `backend/app/services/score_fusion.py`. It will accept the ordered per-path candidates and ordered fused candidates, then construct the pool sent to the reranker from three configurable sources:

- top semantic candidates from every semantic subquery/path;
- top keyword candidates from every keyword subquery/path;
- top candidates in fused RRF order.

The selector will:

1. take each path-specific quota independently so one subquery cannot consume another subquery's allowance;
2. use the fused candidate representation when available so merged ranks, scores, paths, and subquery IDs are retained;
3. deduplicate by chunk ID;
4. preserve deterministic source and rank ordering;
5. enforce the existing total rerank candidate cap only after diversity selection.

New settings will control semantic-per-path, keyword-per-path, and fused pool quotas. The existing rerank candidate setting remains the final provider-cost cap. Defaults will support all paths produced by the default maximum subquery count without relying on a document-specific rank.

`fuse_candidates_node` and the compatibility hybrid retrieval helper will both use the shared selector. RRF remains responsible for fused ordering and deterministic fallback ranking, but it no longer has exclusive control over which evidence reaches the reranker.

## Qdrant Payload Index Design

Add a typed payload-index registry in `backend/app/services/qdrant_client.py`. The registry will cover every payload field currently used by retrieval filters, including integer indexes for `page_start` and `page_end` and appropriate keyword/text indexes for categorical/text fields.

The index manager will inspect the existing collection schema and create only missing indexes with `wait=True`. It will be safe for existing collections and repeat calls.

Provisioning has two entry points:

1. Application startup attempts to ensure all configured filter indexes. Failures are logged without preventing unfiltered API availability.
2. Filtered semantic retrieval ensures the indexes required by that request before submitting the query. If provisioning still fails, the semantic path reports an explicit safe retrieval error. Filters are never dropped or weakened. A surviving keyword path may still answer because it applies the same filters in Postgres.

This handles collections created before the migration as well as collections created after the process starts.

## Error Handling

- Startup index failures are non-fatal and observable through logs.
- Filter-time index failures remain explicit path failures and participate in the existing hybrid fallback metrics.
- Missing collections are not created implicitly because vector dimension and distance configuration remain deployment-owned.
- Existing citation and grounding finalization remains unchanged, including removal of sources from failed or insufficient-context answers.

## Testing

Tests will be written before production changes and must fail for the expected missing behavior.

1. Candidate-pool unit test: a strong semantic candidate below the fused-only cutoff survives and is deduplicated with fused metadata.
2. Query-pipeline regression test: the preserved semantic candidate is included in the documents sent to Jina.
3. Qdrant index tests: missing numeric indexes are created, existing indexes are skipped, and requested schemas are correct.
4. Filtered semantic retrieval test: page range filters execute only after index readiness and are still present in the Qdrant query.
5. Existing insufficient-context graph test remains source-free.
6. Targeted and full backend tests run after implementation.
7. The same ten-question Alice evaluation runs before and after, with candidate-stage evidence recorded for the jar and page-filter cases.

## Documentation

Update root and backend README configuration tables and operations guidance with:

- the new candidate-pool quota settings;
- the distinction between path quotas and the total reranker cap;
- automatic Qdrant payload-index provisioning and its non-blocking startup behavior;
- the requirement that the Qdrant collection itself still be created with the correct vector dimension.

## Non-Goals

- No document-, question-, phrase-, chunk-index-, or expected-answer-specific logic.
- No changes to answer prompts or expected terms solely to improve the Alice score.
- No disabling filters, reranking, citations, grounding, or negative-answer source suppression.
- No implicit Qdrant collection creation.
- No broad chunking redesign. Adjacent-chunk evidence improvements are limited to benefits naturally produced by the diversified pool.

## Success Criteria

- Strong semantic candidates selected by configured per-path quotas reach the reranker even when their fused rank is below the fused quota.
- Page filters run without missing-payload-index errors on existing collections after automatic provisioning.
- Existing successful retrieval, citation, grounding, and insufficient-context behavior remains intact.
- Regression and full backend tests pass.
- The Alice jar and page-filter cases pass without special-case logic, and the before/after report shows the relevant candidate and index evidence.
