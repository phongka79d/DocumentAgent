# Plan 10 - Agent 2 Evidence Verification Agent

## 1. Goal

Implement Agent 2 as the Evidence Verification Agent that reviews Agent 1 candidates, accepts useful evidence, rejects weak evidence, detects missing information, checks contradictions, returns structured JSON, and logs its step.

The goal is testable when Agent 2 returns `verified_chunks`, `rejected_chunks`, `missing_information`, and `confidence` exactly in the required output shape.

## 2. Why This Plan Exists

The final answer must use verified chunks only. This plan creates the evidence gate that prevents answer generation from relying on weak, irrelevant, contradictory, or unsupported chunks.

## 3. Scope

- Add Agent 2 input and output schemas.
- Add verification prompt.
- Add ShopAIKey chat completion call for evidence verification.
- Validate structured JSON with Pydantic.
- Implement deterministic contradiction and duplicate checks where practical.
- Return verified chunks and rejected chunks.
- Set `missing_information` and `confidence`.
- Log Agent 2 input/output to `agent_steps`.
- Add tests for accepted evidence, rejected evidence, missing information, contradictions, invalid JSON, and logging.

## 4. Out of Scope

- Do not generate final answers.
- Do not add citation formatting for users.
- Do not implement Agent 3.
- Do not build the LangGraph workflow.
- Do not retrieve new chunks beyond Agent 1 candidates.
- Do not use rejected chunks in any answer path.

## 5. Dependencies

- Plan 9 must be completed.
- Plan 5 or Plan 7 must have added ShopAIKey chat helper if LLM verification is used.
- Plan 2 must be completed for `agent_steps`.

## 6. Required Files and Folders

```text
backend/app/agents/verification_agent.py
- Contains Agent 2 Evidence Verification Agent implementation.

backend/app/agents/prompts.py
- Contains reusable prompt strings for verification and later answer generation.

backend/app/agents/schemas.py
- Extend with verification input/output schemas.

backend/app/services/shopaikey_service.py
- Reuse or add chat completion helper.

backend/app/services/agent_log_service.py
- Reuse for Agent 2 step persistence.

backend/tests/test_verification_agent.py
- Tests Agent 2 schema, prompt behavior, validation, and logging.
```

## 7. Data Model / Schema Changes

No database schema changes in this plan.

Required Agent 2 output shape:

```json
{
  "verified_chunks": [],
  "rejected_chunks": [],
  "missing_information": false,
  "confidence": 0.82
}
```

Expanded verified chunk shape:

```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "file_name": "contract.pdf",
  "quote": "Thời gian thử việc bắt đầu từ 01/06/2026 và kéo dài 2 tháng.",
  "page_number": 3,
  "verification_reason": "This chunk provides the start date and probation duration needed to infer the official month.",
  "supports_simple_reasoning": true
}
```

Rejected chunk shape:

```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "file_name": "contract.pdf",
  "quote": "Nhân sự cần tuân thủ nội quy công ty.",
  "rejection_reason": "This chunk does not mention official work date, start date, or probation duration."
}
```

Confidence:

```text
Type: float
Range: 0.0 to 1.0
```

## 8. API Design

No new public API endpoints in this plan.

Internal callable:

```text
Function: run_verification_agent(input: VerificationAgentInput) -> VerificationAgentOutput
Input:
{
  "agent_run_id": "uuid",
  "question": "string",
  "candidates": []
}
Output:
{
  "verified_chunks": [],
  "rejected_chunks": [],
  "missing_information": false,
  "confidence": 0.82
}
Errors:
- VerificationAgentError for LLM or validation failures
```

## 9. Implementation Steps

1. Extend `backend/app/agents/schemas.py` with `VerificationAgentInput`, `VerifiedChunk`, `RejectedChunk`, and `VerificationAgentOutput`.
2. Add strict validators that clamp or reject invalid confidence values outside `0.0` to `1.0`.
3. Create verification prompt in `backend/app/agents/prompts.py`.
4. Prompt rules must instruct Agent 2 to reject chunks that are loosely related, duplicated, contradicted, unclear, or from the wrong document.
5. Prompt rules must instruct Agent 2 to accept chunks that directly answer or provide necessary date, period, condition, or definition evidence.
6. Prompt rules must instruct Agent 2 to return only valid JSON in the required shape.
7. Implement `run_verification_agent(input_data)` in `verification_agent.py`.
8. If `candidates` is empty, return no verified chunks, no rejected chunks, `missing_information=true`, and confidence `0.0` without calling the LLM.
9. Prepare a compact evidence list for the LLM containing chunk ID, file name, page number, section title, score, and content.
10. Call ShopAIKey chat completion with low temperature if supported.
11. Parse response JSON.
12. Validate it with Pydantic.
13. Confirm every returned `chunk_id` exists in Agent 1 candidates.
14. Ensure quotes are substrings or faithful excerpts from the candidate content.
15. Add deterministic duplicate filtering so repeated chunks are not verified twice.
16. Add basic contradiction check for conflicting dates or mutually incompatible claims when clear from verified chunks.
17. If no verified chunk remains, set `missing_information=true`.
18. Log Agent 2 step with status `success` or `failed`.
19. Add tests for all required output branches.

## 10. Configuration and Environment Variables

```text
SHOPAIKEY_API_KEY
- Purpose: Evidence verification chat completion.
- Required: Yes.
- Example: shopaikey-placeholder
- Scope: Backend-only.

SHOPAIKEY_BASE_URL
- Purpose: OpenAI-compatible API base URL.
- Required: Yes.
- Example: https://api.shopaikey.com/v1
- Scope: Backend-only.

SHOPAIKEY_CHAT_MODEL
- Purpose: Model used for verification.
- Required: Yes.
- Example: gpt-5-mini
- Scope: Backend-only.

SINGLE_USER_ID
- Purpose: Indirectly scopes retrieved candidate chunks.
- Required: Yes.
- Example: single_user
- Scope: Backend-only.
```

## 11. Required Tests

Unit tests:

```text
cd backend
pytest tests/test_verification_agent.py -v
```

Concrete test cases:

```text
Candidate directly states the answer -> appears in verified_chunks.
Candidate is loosely related -> appears in rejected_chunks.
No candidates -> missing_information true.
LLM returns invalid JSON -> VerificationAgentError and failed log.
LLM returns unknown chunk_id -> validation failure.
Verified chunks conflict on a date -> missing_information true or lower confidence with contradiction reason.
```

Manual check:

```text
Run Agent 1 for the sample question.
Pass Agent 1 output into Agent 2.
Confirm Agent 2 verifies chunks with start date, probation duration, and official work condition.
```

## 12. Acceptance Criteria

- Agent 2 returns exactly `verified_chunks`, `rejected_chunks`, `missing_information`, and `confidence`.
- Agent 2 output is Pydantic-validated.
- `confidence` is between `0.0` and `1.0`.
- Irrelevant chunks are rejected with reasons.
- Missing evidence sets `missing_information=true`.
- Contradictions are detected or reported when clear.
- Agent 2 logs success and failure steps.
- Agent 2 does not generate final answers.

## 13. Failure Handling

- Empty candidates return a safe missing-information result.
- ShopAIKey failure logs a failed Agent 2 step and raises `VerificationAgentError`.
- Invalid LLM JSON is rejected and logged.
- Unknown chunk IDs in LLM output are rejected.
- Quotes not found in source content must be rejected or corrected to a source excerpt.
- Contradictory verified chunks must reduce confidence and set missing information if unresolved.

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

The report must include an example Agent 2 output containing verified and rejected chunks.

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

- Confirm Agent 2 cannot verify chunks not returned by Agent 1.
- Confirm invalid JSON is not accepted.
- Confirm missing-information behavior is safe.
- Confirm rejected chunks are not passed as verified evidence.
