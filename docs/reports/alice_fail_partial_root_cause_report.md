# Alice Evaluation Failure / Partial Root Cause Report

Date: 2026-06-23

## Scope

This report covers the current Alice evaluation failure, flaky failure mode, and partial result found during graph tracing.

Passing questions are intentionally excluded.

## Current Findings

| Case | Status | Root Cause |
| --- | --- | --- |
| Q3 | FAIL | Grounding verifier sometimes returns valid JSON wrapped in Markdown fences; strict parser rejects it, causing valid answer suppression |
| Q4 | FLAKY FAIL | Same grounding verifier parser issue; retrieval succeeds, but fenced verifier JSON can cause insufficient-context fallback |
| Q8 | PARTIAL | Retrieval/context returns a grounded subset, but the pipeline does not perform exhaustive coverage for list-all questions |

## Fix Status

Implemented on 2026-06-23:

- `backend/app/services/grounding.py` now extracts the first JSON object from verifier output, so fenced JSON is accepted.
- The grounding verifier call now requests provider JSON mode with `response_format={"type": "json_object"}`.
- `backend/tests/test_grounding.py` includes regression coverage for Markdown-fenced verifier JSON and JSON-mode request options.

Verification:

- `python -m pytest tests/test_grounding.py -q -p no:cacheprovider --basetemp .pytest-tmp-grounding-green`
  - Result: `6 passed`
- Related graph/API grounding tests:
  - Result: `4 passed`
- Q4 live graph rerun:
  - 4/4 runs returned grounded answers.
  - 0/4 runs returned insufficient-context fallback.

## Exact Cross-Cutting Root Cause

The grounding verifier is instructed to return strict JSON, but the model sometimes returns valid JSON inside a Markdown code fence:

````text
```json
{"grounded": true, "score": 0.95, "unsupported_claims": [], "missing_citations": []}
```
````

The content is semantically valid, but `backend/app/services/grounding.py` parses it with strict `json.loads(content)`.

That fails with:

```text
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

The parser then raises `GroundingProviderError`. The graph converts that into:

```text
grounding_provider_failed = True
answer_verified = False
```

Then `finalize_answer_node` replaces the generated answer with the safe insufficient-context response and clears sources.

This means a harmless response-formatting variation becomes a user-visible false failure.

### Direct Verifier Evidence

For Q4, the same cited answer/evidence was sent directly to the grounding verifier 10 times.

Results:

- 6 responses were strict JSON and parsed successfully.
- 4 responses were valid JSON wrapped in Markdown fences and failed strict parsing.
- All 10 responses had the same actual grounding decision: `grounded=true`, `score=0.95`.

This explains why Q4 sometimes works and sometimes returns insufficient context.

### JSON Mode Evidence

The provider accepted OpenAI-style JSON mode:

```python
response_format={"type": "json_object"}
```

With JSON mode enabled in a direct test, the verifier returned strict parseable JSON 5/5 times.

### Why Retry Does Not Save This

`retry_sync` wraps only the provider call. Parsing happens after the provider call returns.

So a malformed-but-recoverable verifier response is not retried as a model-output contract failure. It immediately becomes `GroundingProviderError`, which the graph treats as verification failure.

### Existing Repo Contrast

Another service already handles this class of model-output issue:

- `backend/app/services/relations.py`
  - `_extract_json_object`

That function scans a model response and extracts a JSON object even when extra text appears around it. Grounding does not currently use an equivalent tolerant parser.

## Q3 Failure

Question:

> What happened to Alice every time she ate a piece of the cake or drank from a bottle in the story?

Final user-visible answer:

> The indexed documents do not contain enough verified information to answer this question.

This final answer is incorrect because the retrieval pipeline did find the relevant evidence and the answer generator produced a valid cited answer before finalization.

## Evidence

The current graph trace shows that retrieval succeeded.

Planner:

- Strategy: `hybrid`
- Subquery `q1`: What happened to Alice every time she ate a piece of the cake?
- Subquery `q2`: What happened to Alice every time she drank from a bottle?

Relevant evidence reached retrieval:

- `EAT ME`
- cake
- bottle
- `DRINK ME`
- grow / larger
- smaller

Relevant evidence reached reranking:

- chunk 31: cake, bottle, grow, smaller, larger
- chunk 8: cake, grow, smaller, larger
- chunk 25: `DRINK ME`, bottle, grow, larger
- chunk 7: `EAT ME`, cake, grow, smaller, larger
- chunk 5: `DRINK ME`, bottle, larger

Relevant evidence reached context:

- The final context contained the cake and bottle transformation evidence needed to answer the question.

Generated answer before finalization:

> Every time Alice ate a piece of cake or drank from a bottle, she experienced changes in her size. When she ate a cake that turned from pebbles, she began to shrink directly, allowing her to escape through a door [S1]. Conversely, when she drank from a bottle labeled "DRINK ME," she grew larger, eventually pressing against the ceiling [S3]. Each time, she hoped the effect would help her reach the key to the garden or allow her to enter it [S2][S4].

Citation validation:

- Valid: `true`
- Cited keys: `S1`, `S2`, `S3`, `S4`
- Invalid keys: none
- Missing citations: false

Grounding/finalization:

- `grounding_result`: `None`
- `grounding_provider_failed`: `true`
- `answer_verified`: `false`
- `finalize_answer_node` replaced the valid generated answer with the safe insufficient-context answer.
- Sources were cleared.

## Root Cause

The failure is not caused by retrieval, fusion, reranking, or context selection.

The direct root cause is strict grounding JSON parsing.

The grounding verifier sometimes returns valid JSON wrapped in Markdown fences. The current parser rejects that response, marks grounding as failed, and the graph treats that formatting failure as if the answer itself is unverified.

Because `answer_verified` becomes `false`, `finalize_answer_node` replaces the generated answer with:

> The indexed documents do not contain enough verified information to answer this question.

That behavior is too broad. It conflates two different cases:

- The generated answer is actually unsupported by evidence.
- The grounding verifier returned a valid result with recoverable formatting.

In Q3, the evidence and citations are present. The failure occurs after answer generation, during grounding/finalization.

## Affected Code Path

- `backend/app/services/grounding.py`
  - `_parse_grounding_result`
  - `verify_answer_grounding`
- `backend/app/graphs/query_nodes.py`
  - `verify_grounding_node`
  - `finalize_answer_node`
- `backend/app/graphs/query_graph.py`
  - route after grounding
- `backend/app/core/retry.py`
  - parse failures happen after the provider retry wrapper

## Impact

Any query can produce a false insufficient-context response when:

1. Retrieval succeeds.
2. Reranking/context selection succeeds.
3. Answer generation succeeds.
4. Citation validation succeeds.
5. Grounding verifier returns fenced JSON.
6. Strict parser rejects it.

The user then receives no answer and no sources, even though the system had enough evidence.

## Recommended Fix

Fix strict grounding JSON parsing and separate verifier output-format failure from true ungrounded-answer failure.

Recommended behavior:

- Request JSON mode when calling the verifier, if the provider supports it.
- Add a tolerant JSON object extractor for grounding responses, similar to `relations._extract_json_object`.
- Parse fenced JSON responses before raising `GroundingProviderError`.
- If grounding verifier returns a valid negative result, treat the answer as ungrounded and apply the safe insufficient-context fallback.
- If grounding verifier truly fails operationally, do not automatically claim insufficient document context.
- Preserve the cited answer when citation validation passes, or return a distinct verifier-unavailable error state.

Add regression coverage for:

- Grounding verifier response wrapped in ```json fences.
- A valid generated answer with valid citations where grounding provider fails.
- The final answer must not be converted into an insufficient-context response solely because the verifier provider failed.

## Q4 Flaky Failure

Question:

> What rules did the Queen of Hearts enforce during the croquet game, and what was unusual about the equipment used?

Observed behavior:

- Sometimes the answer is correct and grounded.
- Sometimes the final answer is:

> The indexed documents do not contain enough verified information to answer this question.

This is not a retrieval failure.

Repeated Q4 graph runs showed:

| Run | Retrieval | Citations | Grounding | Final |
| --- | --- | --- | --- | --- |
| 1 | OK | valid | grounded | works |
| 2 | OK | valid | `grounding_provider_failed=True` | insufficient context |
| 3 | OK | valid | `grounding_provider_failed=True` | insufficient context |
| 4 | OK | valid | `grounding_provider_failed=True` | insufficient context |
| 5 | OK | valid | grounded | works |

Retrieval was stable in every run:

- 160 candidates
- 5 reranked chunks
- 8 context chunks
- valid citations

The failure happened only after answer generation, during grounding/finalization.

Direct verifier calls confirmed the source:

- Fenced JSON responses fail strict parsing.
- Strict JSON responses pass.

Q4 is therefore flaky because the verifier output format is nondeterministic, while the parser expects exactly raw JSON.

## Q8 Partial Result

Question:

> What songs or poems appear in Alice's Adventures in Wonderland, and which character recited each one?

Current user-visible behavior:

- The answer is grounded.
- Citations are valid.
- The answer is incomplete for an "all songs or poems" question.

Observed answer includes:

- "Twinkle, Twinkle, Little Bat" / Hatter
- "You Are Old, Father William" / Alice recounting it
- Lobster/sluggard poem fragment / Alice prompted by the Gryphon

The answer does not reliably enumerate every relevant song/poem occurrence in the document.

### Evidence

Planner:

- Strategy: `hybrid`
- The query is decomposed into broad inventory subqueries:
  - What songs appear in Alice's Adventures in Wonderland?
  - What poems appear in Alice's Adventures in Wonderland?
  - Which character recited each song?
  - Which character recited each poem?

Retrieval metrics:

- Raw path candidates: 320
- Fused candidates: 80
- Rerank input candidates: 18
- Final reranked chunks: 5
- Context chunks: 8

Relevant context did include some poem/song evidence:

- chunk 57: `Twinkle, twinkle, little bat`
- chunk 85: `Father William`
- chunk 86: lobster/sluggard material
- neighbor chunks around the Mock Turtle/Gryphon episode

Citation validation:

- Valid: `true`
- Invalid keys: none
- Missing citations: false

Grounding:

- Grounded: `true`
- Score: `0.95`

### Root Cause

The Q8 issue is not an unsupported-answer problem. It is a completeness problem.

The current retrieval pipeline is optimized for focused factual answers. It is not designed to exhaustively enumerate every occurrence across a long document.

The pipeline narrows evidence through several bounded stages:

1. Multiple broad subqueries produce many candidates.
2. Fusion and diverse rerank selection reduce the candidate pool.
3. Jina reranking returns only the top final chunks.
4. Context expansion is capped.
5. Grounding verifies whether the generated claims are supported, but does not verify whether the answer is complete.

Because Q8 asks for "what songs or poems appear" across the book, the system needs exhaustive recall. The current bounded RAG path can produce a supported subset and still pass grounding.

### Affected Code Path

- `backend/app/core/config.py`
  - `QUERY_MAX_SUBQUERIES`
  - `RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K`
  - `RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K`
  - `RETRIEVAL_RERANK_FUSED_TOP_K`
  - `RETRIEVAL_RERANK_CANDIDATE_TOP_K`
  - `RETRIEVAL_CONTEXT_MAX_CANDIDATES`
- `backend/app/services/score_fusion.py`
  - `select_rerank_candidates`
- `backend/app/services/retrieval_context.py`
  - context candidate and token caps
- `backend/app/services/grounding.py`
  - verifies support, not completeness

### Impact

Broad enumeration questions can return answers that are:

- cited,
- grounded,
- plausible,
- but incomplete.

This is risky because users may treat the answer as complete.

### Recommended Fix

Add an enumeration-aware retrieval path for list-all questions.

Recommended behavior:

- Detect inventory prompts such as "all", "which songs", "what poems", "list every", and "appear".
- Retrieve with broader coverage across the document or section range.
- Use iterative retrieval until no new relevant items are found, or use chapter/section scanning for enumeration.
- Add a completeness check separate from grounding.
- Do not rely on grounding alone to validate list-all answers.

Add regression coverage for:

- A list-all question with relevant evidence spread across multiple chunks.
- The test should fail if the answer returns only a supported subset.

## Final Conclusion

Current non-passing / unstable cases:

- Q3: FAIL because grounding verifier fenced JSON can cause answer suppression.
- Q4: FLAKY FAIL because the same grounding parser issue intermittently converts valid answers into insufficient-context answers.
- Q8: PARTIAL because the bounded retrieval/context path returns a grounded subset for an exhaustive enumeration question.
