# Q8 Partial Retrieval Root Cause and Improvement Report

Date: 2026-06-24

## Executive Summary

Q8 is the only active partial result in the Alice evaluation:

> What songs or poems appear in Alice's Adventures in Wonderland, and which character recited each one?

The answer is grounded but incomplete. This is not a citation failure and not an
insufficient-context failure. It is a coverage failure caused by a pipeline that
optimizes for the highest-ranked evidence rather than preserving distinct evidence
clusters for an inventory-style question.

The latest full evaluation returned examples from only three source chunks. A
diagnostic run showed the same structural issue with a different final source set,
confirming that provider ranking variation changes which subset appears but does not
remove the coverage bottleneck.

The recommended fix is fixed-budget, coverage-aware selection:

1. Keep the current reranker input cardinality and token ceiling.
2. Select candidates from distinct evidence clusters before reranking.
3. Obtain reranker scores for the same candidate set, then choose a relevance and
   diversity-balanced final set locally.
4. Reserve context space for distinct anchors before adding adjacent neighbors.
5. Pack bounded evidence snippets instead of eight complete 500-token chunks.

This approach does not require Alice-specific terms, document IDs, chunk indexes,
expected answers, larger global `top_k` values, or a larger answer context.

## Current Status

| Question range | Status |
| --- | --- |
| Q1-Q7 | PASS |
| Q8 | PARTIAL |
| Q9-Q10 | PASS |

The current `scripts/eval_alice.py` output says `10/10`, but that score is not a
quality result. Lines 90 and 94 classify any answer longer than 20 characters as
`PASS`. The evaluator cannot detect missing list items, unsupported details, or an
insufficient-context answer longer than 20 characters.

## Observed Q8 Behavior

The latest full rerun answered with:

- `Twinkle, twinkle, little bat`, attributed to the Hatter.
- The altered `Tis the Voice of the Sluggard` episode involving Alice and the
  Gryphon.
- The Dormouse's three-sisters narrative, which is not itself a strong answer to the
  song-or-poem inventory.

Returned source chunk indexes were `57`, `86`, and neighbor `58`.

The answer omitted several distant, independently relevant passages. The stored
Alice document contains 117 chunks, and representative evidence is distributed as
follows:

| Evidence | Character or role | Chunk indexes |
| --- | --- | --- |
| `How doth the little crocodile` | Alice recites it | 11 |
| Mouse's long and sad tale | Mouse recites it | 20-21 |
| `You Are Old, Father William` | Alice recites it for the Caterpillar | 35-36 |
| `Speak roughly to your little boy` | Duchess sings it | 46-47 |
| `Twinkle, twinkle, little bat` | Hatter sings/recites it | 56-57 |
| Lobster Quadrille song | Mock Turtle performs it | 80-82 |
| Altered `Tis the Voice of the Sluggard` | Alice recites it | 86-87 |
| `Beautiful Soup` | Mock Turtle sings it | 88-89 |
| Queen of Hearts tart accusation rhyme | White Rabbit reads it | 91 |
| `They told me you had been to her` trial verse | White Rabbit reads it | 100 |

This table documents evidence distribution. It must not be copied into production
retrieval logic. The exact evaluation scope should live only in evaluation data.

## Diagnostic Trace

A direct node-by-node Q8 diagnostic produced this query plan:

```text
strategy=hybrid
q1=What songs appear ... and which character recited each one?
q2=What poems appear ... and which character recited each one?
```

Pipeline counts:

| Stage | Count | Relevant observation |
| --- | ---: | --- |
| Semantic and keyword path results | 160 | 40 results for each of four paths |
| Unique fused candidates | 63 | Many distant candidates are still available here |
| Reranker input pool | 15 | Only chunks 57 and 86 from the mapped evidence survived |
| Reranker output | 5 | Chunks `57, 85, 0, 105, 103` |
| Final context | 8 | Chunks `57, 85, 0, 105, 103, 56, 58, 84` |
| Final context tokens | 4,000 | Entire configured context budget consumed |

Candidate ranks for representative missing evidence show where loss occurs:

| Chunk | Retrieval presence | Why it was lost |
| ---: | --- | --- |
| 11 | Keyword rank 19 | Per-keyword-path pool keeps only top 2 |
| 20 | Keyword rank 21 | Per-keyword-path pool keeps only top 2 |
| 35-36 | Outside top 40 paths in this run | Never reached the fused/rerank pool |
| 46-47 | Outside top 40 paths in this run | Never reached the fused/rerank pool |
| 57 | Semantic ranks 1 and 5 | Reached reranker and was selected |
| 80 | Keyword rank 25 | Per-keyword-path pool keeps only top 2 |
| 86 | Semantic ranks 7 and 4 | Reached reranker at pool position 14, then lost at top 5 |
| 87 | Semantic ranks 9 and 12 | Per-semantic-path pool keeps only top 5 |
| 88 | Semantic ranks 21 and 31 | Per-semantic-path pool keeps only top 5 |
| 89 | Semantic ranks 27/33, keyword rank 26 | Lost before reranking |
| 91 | Semantic ranks 26/25, keyword rank 31 | Lost before reranking |
| 100 | Semantic ranks 23 and 17 | Lost before reranking |

The exact ranks can vary across provider calls. The fixed cutoffs and selection
behavior are deterministic structural bottlenecks even when individual scores vary.

## Root Cause Analysis

### 1. Candidate pool diversity is path-based, not evidence-based

`app/services/score_fusion.py:223` builds the reranker pool in this order:

1. Top fused candidates.
2. Top semantic candidates from each path.
3. Top keyword candidates from each path.
4. Deduplicate by chunk ID and truncate.

This fixed order solved the earlier jar regression because a strong semantic result
can survive a fused cutoff. It does not solve inventory coverage. Multiple candidates
from the same episode can occupy the pool while lower-ranked candidates from distant
episodes are discarded.

Subquery coverage also does not equal evidence coverage. Q8 has one broad `songs`
subquery and one broad `poems` subquery. Most passages match one or both, so preserving
one result per subquery guarantees only two broad categories, not one representative
per distinct work or episode.

### 2. The reranker optimizes point relevance and returns only five chunks

`app/services/retrieval.py:638` sends the pool to Jina and requests:

```text
top_n = RETRIEVAL_FINAL_TOP_K = 5
```

The reranker independently scores each chunk against the broad question. It has no
objective to maximize document-position, section, or evidence-cluster coverage. Even
when chunk 86 survived into the 15-item pool, it was not guaranteed to remain in the
top five.

### 3. Context expansion spends the full budget on complete chunks and neighbors

`app/services/retrieval_context.py:351` limits context to eight candidates and 4,000
tokens. Each Alice chunk in the diagnostic set is 500 tokens, so eight complete chunks
consume the full budget exactly.

The implementation reserves one result per subquery, fills remaining reranked chunks,
then adds neighbors. In the diagnostic run, chunks 56, 58, and 84 were added as
neighbors. Chunk 86, adjacent to selected chunk 85 and containing stronger poem
evidence, did not fit after the earlier neighbors consumed the remaining slots.

For focused questions, neighbor expansion is useful for boundary completion. For an
inventory question, unrestricted neighbor filling reduces the number of distinct
evidence clusters that can be represented.

### 4. Answer generation receives no completeness contract

`app/graphs/query_prompts.py:8` requires grounded citations and forbids invented facts,
but it does not tell the model whether selected context represents an exhaustive set.
Given a partial context, the model correctly produces a supported subset.

The problem therefore cannot be solved reliably by prompt wording alone. The model
cannot enumerate evidence that retrieval removed.

### 5. Grounding checks support, not omission

`app/services/grounding.py:92` verifies the answer only against evidence associated
with citation keys used in the answer. `app/graphs/query_nodes.py:919-972` accepts the
result when cited claims are supported and the grounding score passes the threshold.

This answers:

> Are the claims in the answer supported?

It does not answer:

> Did the answer cover every distinct relevant evidence cluster retrieved or present
> in the document?

Q8 can therefore be grounded, citation-valid, and still partial.

### 6. Runtime variation changes the subset, not the root cause

The full evaluation returned chunks 57, 86, and 58. A later diagnostic selected a
different set that included 57 but omitted 86. Remote planning, embedding, and
reranking providers can vary in scores or outputs. Stable tie-breaking occurs only
after those outputs are received.

A coverage-aware local selector would reduce this variance by preserving distinct
clusters even when their exact ranks move slightly.

## Impact Assessment

### Affected workflows

- Questions asking for all items, examples, events, clauses, people, or occurrences.
- Questions whose evidence is spread across distant sections of a long document.
- Plain-text documents with weak or empty section metadata.
- Documents chunked into overlapping fixed-size windows.

### Unaffected or less affected workflows

- Focused fact questions supported by one or two nearby chunks.
- Citation validity for claims that are actually returned.
- Insufficient-context behavior and source removal.

### Severity

Severity is medium. The answer is usually factually grounded, so it is not a
hallucination or data-integrity failure. However, it can silently omit important items
while appearing complete, which is material for legal, policy, audit, and comparison
workflows.

## Requirements for the Fix

The implementation should satisfy all of these constraints:

- No Alice-specific words, document IDs, chunk indexes, characters, titles, or answer
  lists in production code.
- No global increase to `RETRIEVAL_RERANK_CANDIDATE_TOP_K`.
- No increase to the actual reranker input count used by Q8, which was 15 in the
  diagnostic run.
- No increase to `RETRIEVAL_CONTEXT_MAX_TOKENS`, currently 4,000.
- No extra LLM planning or answer-generation call.
- Preserve focused-question relevance, citation validation, and empty sources for
  insufficient-context answers.

## Recommended Fixed-Budget Design

### Phase A: Coverage-aware reranker pool selection

Replace ordered concatenation with a fixed-cardinality local selector. Its input is
the already retrieved candidate universe, so it adds no provider tokens.

Recommended behavior:

1. Preserve the highest fused candidate as the relevance anchor.
2. Group near-duplicate candidates using document ID, section path, chunk adjacency,
   and local content similarity.
3. Allocate remaining slots round-robin across subqueries, retrieval paths, and
   distinct groups.
4. Fill any unused slots by fused rank.
5. Deduplicate by chunk ID exactly as today.

Use local token shingles, TF-IDF, or MinHash for content similarity. These operate on
candidate text already in memory and do not consume model tokens. Derive adjacency
behavior from existing chunk overlap metadata where possible rather than adding an
Alice-tuned distance.

The selected pool size must be the same size the old algorithm would have produced,
bounded by the existing setting. For the observed Q8 trace, the new pool must contain
at most 15 chunks, not 40.

Primary file:

- `backend/app/services/score_fusion.py`

### Phase B: Score all existing candidates, then select five diverse results locally

Keep the same reranker documents and therefore the same reranker input tokens. Request
scores for the existing pool instead of only five results, then locally choose five
using rerank score plus evidence-group coverage.

Changing `top_n` from 5 to the existing pool length changes response metadata, not the
documents sent to the reranker. It does not increase reranker input tokens.

Selection order should be:

1. Best rerank score overall.
2. Best remaining candidate from each uncovered evidence group.
3. Remaining candidates by rerank score until five are selected.

Primary files:

- `backend/app/services/retrieval.py`
- `backend/app/graphs/query_nodes.py`

### Phase C: Reserve distinct anchors before neighbor expansion

Context assembly should first reserve one selected anchor per distinct evidence group.
Only after anchors are placed should it add same-section or adjacent neighbors.

Neighbors should be admitted when they complete a boundary-spanning passage, not
merely because they are adjacent. A local overlap/content-continuation check can make
this decision without another model call.

Primary file:

- `backend/app/services/retrieval_context.py`

### Phase D: Pack evidence spans within the existing 4,000-token budget

Do not send eight full 500-token chunks when the relevant passage is one stanza or a
few sentences. Build `prompt_content` from bounded spans around locally scored
sentences or paragraphs while retaining the original chunk ID for citation.

Requirements:

- Total serialized context remains at or below 4,000 tokens.
- The full original chunk remains available server-side for source display.
- Span boundaries preserve complete sentences or verse blocks.
- Multiple spans from the same chunk share one citation key unless they contain
  independently cited evidence units.

The current context prompt also includes file name, chunk UUID, chunk index, and page
metadata for every source. The answer model needs the citation key and evidence text;
most remaining metadata is already retained server-side. Compacting prompt metadata
can fund a short completeness instruction while keeping total input tokens equal to
or lower than the current prompt.

Primary files:

- `backend/app/services/retrieval_context.py`
- `backend/app/graphs/query_formatting.py`

### Phase E: Track completeness locally

Assign a transient evidence-group ID during selection. After generation, compare the
answer's citation keys with the selected evidence groups.

This check should not call another model. It should produce an observable metric such
as:

```text
selected_evidence_group_count
cited_evidence_group_count
evidence_group_coverage_rate
```

For a coverage-oriented response, the answer formatter should request one concise row
per selected group. Any additional instruction tokens should be offset by compacting
the per-source metadata so the complete prompt does not grow.

Primary files:

- `backend/app/graphs/query_nodes.py`
- `backend/app/graphs/query_formatting.py`
- `backend/app/services/citation_validation.py`

Grounding should remain focused on factual support. Mixing omission detection into
the grounding score would make its contract ambiguous.

## Why This Is General and Not Hardcoded

The proposed selector uses only generic retrieval properties:

- relevance ranks and scores,
- retrieval path and subquery membership,
- document and section identity,
- chunk position and overlap,
- local text similarity,
- citation coverage.

It does not inspect `Alice`, `song`, `poem`, character names, expected phrases, or
known chunk numbers. The same behavior applies to a policy document asking for all
exceptions, a contract asking for all termination clauses, or a report asking for all
incidents and owners.

## Token and Cost Impact

| Component | Current Q8 | Proposed ceiling |
| --- | ---: | ---: |
| Retrieval paths | 160 candidates | Unchanged |
| Reranker documents | 15 chunks | At most 15 chunks |
| Reranker input text | 15 full candidate texts | Same or lower |
| Final selected anchors | 5 | 5 |
| Answer context | 4,000 tokens | At most 4,000 tokens |
| Planner calls | 1 | 1 |
| Answer-generation calls | 1 normally | 1 normally |
| Grounding calls | Existing behavior | Unchanged |

The improvement comes from allocating the same budget across more distinct evidence,
not from increasing retrieval or prompt volume.

## Test Plan

### Unit tests

Add tests that use synthetic, document-neutral content:

1. A fixed-size pool preserves candidates from distant evidence groups.
2. Near-duplicate adjacent chunks do not consume multiple diversity slots before
   uncovered groups.
3. Pool cardinality and serialized reranker input tokens do not exceed the old
   algorithm for the same candidates.
4. Post-rerank selection keeps the configured final count while covering distinct
   groups.
5. Context reserves distinct anchors before optional neighbors.
6. Evidence snippets remain within the configured 4,000-token ceiling.
7. Focused queries still keep the strongest result first.
8. Insufficient-context answers still return no sources.

Suggested test files:

- `backend/tests/test_score_fusion.py`
- `backend/tests/test_query_graph.py`
- `backend/tests/test_retrieval_context.py`
- `backend/tests/test_citation_validation.py`

### Behavioral evaluation

Add an evaluation fixture with an inventory question whose answer items are spread
across distant chunks. Expected concepts belong in test/evaluation data, not runtime
code.

For Alice Q8, report both:

- grounding and citation validity,
- item coverage against the agreed evaluation inventory.

Update `scripts/eval_alice.py` so answer length alone cannot report `PASS`. This is an
evaluation correctness fix and does not affect retrieval token usage.

### Stability verification

Run Q8 at least four times and record:

- query plan,
- reranker input chunk indexes,
- final selected groups,
- context token count,
- cited group coverage.

The exact provider scores may vary. Distinct-group coverage should remain stable.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Diversity lowers precision for focused questions | Always keep the top relevance anchor and use relevance-first fill when groups are exhausted |
| Local similarity groups unrelated passages | Combine text similarity with document/section/position signals and expose thresholds as normal configuration |
| Snippets remove necessary context | Preserve sentence/verse boundaries and allow one adjacent continuation span within the same budget |
| More reranker score metadata increases latency | Keep document input unchanged, measure provider latency, and fall back to deterministic fused ordering |
| Plain text has weak section metadata | Use local similarity and overlap-aware position grouping as fallback |

## Open Questions

1. What is the authoritative Q8 inventory? Songs, poems, nursery rhymes, recited
   verses, and the Mouse's shaped tale can be classified differently.
2. Does the Jina endpoint reliably return scores for all 15 candidates when
   `top_n=15`?
3. Should evidence-group coverage be user-visible or observability-only?
4. Can ingestion store source offsets or overlap metadata to make grouping more
   reliable without query-time model work?

## Conclusion

Q8 is partial because distinct evidence is removed at three bounded stages:

1. Path/fused selection retains relevance but not evidence-cluster diversity.
2. The reranker returns five independently relevant chunks without a coverage goal.
3. Full-chunk context and neighbor expansion spend all 4,000 tokens on too few
   distinct passages.

Grounding then correctly verifies the supported subset but cannot detect omission.

The strongest solution is a fixed-budget coverage-aware selector, all-candidate score
return, anchor-before-neighbor context assembly, and bounded evidence spans. This
improves exhaustive questions without larger model inputs and without any Alice- or
test-specific production logic.
