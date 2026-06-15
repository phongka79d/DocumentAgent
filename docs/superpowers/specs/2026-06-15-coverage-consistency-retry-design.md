# Coverage Consistency Retry Design

## Problem

The evidence coverage reviewer can return populated `selected_evidence` while
also returning `answers_question: false` and `missing_information: true`. Agent
2 currently accepts that contradictory shape and discards evidence that may
directly answer the question, causing Agent 3 to return an uncited
insufficient-information response.

## Design

Treat a coverage review as internally consistent only when:

- `answers_question` and `missing_information` are opposites.
- Answerable reviews contain at least one selected evidence item.
- Non-answerable reviews contain no selected evidence.

If the first coverage response is inconsistent, call the same reviewer once
more with an explicit correction instruction and the original response. The
retry must still use only candidate content and the same public schema. If the
second response remains inconsistent, fail the Agent 2 step through the
existing controlled coverage validation error path.

For quote membership, tolerate only terminal sentence-punctuation variation
after existing whitespace, case, and quotation-mark normalization. This covers
provider output such as changing a source colon to a period while preserving
every evidence word. Word, number, and internal punctuation changes remain
rejected.

If a verified chunk omits `supports_simple_reasoning`, default it to `false`.
This is conservative: omission cannot grant permission for inference, while
the finalized Agent 2 schema still includes the boolean field.

Agent 3 must preserve literal labels, names, titles, identifiers, codes, and
numeric values exactly as written in verified evidence. It may translate the
surrounding explanation, but not those source literals.

Allow one bounded Agent 3 regeneration after any self-check grounding failure,
not only explanatory questions. The retry uses a narrower grounding
instruction and must pass the same citation and claim checks. A second failure
remains a controlled fail-closed result.

Update the coverage prompt so its example is a consistent answerable example
and explicitly states that non-answerable reviews must return an empty
`selected_evidence` list. This reduces provider ambiguity while deterministic
validation remains the enforcement boundary.

## Scope

Modify only:

- `backend/app/agents/schemas.py`
- `backend/app/agents/prompts.py`
- `backend/app/agents/verification_agent.py`
- `backend/tests/test_verification_agent.py`

Public chat, evidence, and agent-log response schemas remain unchanged.

## Verification

- Regression test for a contradictory first response followed by a corrected
  answerable response.
- Failure test for two contradictory responses.
- Prompt and schema consistency tests.
- Terminal sentence-punctuation membership test.
- Missing simple-reasoning permission defaults to `false`.
- Answer-generation prompt preserves source literals verbatim.
- Factual and explanatory answers receive at most one grounding repair retry.
- Full backend test suite.
- Live Alice jar question must return citations for the label and empty jar.
