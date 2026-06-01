# Plan 11 - Agent 3 Answer Generation and Self-Check Agent

## 1. Goal

Implement Agent 3 to generate a grounded final answer from verified chunks only, include citations in the required file-name plus quote format, handle insufficient evidence safely, run a self-check, and log the step.

The goal is testable when Agent 3 refuses unsupported answers and produces validated output with citations only from Agent 2 verified chunks.

## 2. Why This Plan Exists

The system's central quality rule is that final answers must be based only on verified document evidence. This plan enforces that rule at the answer generation stage before the full workflow is exposed through chat.

## 3. Scope

- Add Agent 3 input and output schemas.
- Add answer generation prompt.
- Add self-check schema and prompt/rules.
- Generate answers from verified chunks only.
- Implement citation format: `file_name: "quoted text"`.
- Allow simple reasoning only when evidence clearly supports it.
- Return insufficient-evidence answer when `missing_information=true` or verified chunks are empty.
- Log Agent 3 answer and self-check outputs.
- Add tests for grounded answer, insufficient evidence, citation enforcement, rejected chunk exclusion, and self-check failure.

## 4. Out of Scope

- Do not implement LangGraph orchestration.
- Do not implement `/api/chat/ask`.
- Do not implement frontend chat.
- Do not retrieve additional chunks.
- Do not use rejected chunks.
- Do not add conversation memory beyond output schemas.

## 5. Dependencies

- Plan 10 must be completed.
- Plan 2 must be completed for `agent_steps`.
- ShopAIKey chat completion helper must exist.

## 6. Required Files and Folders

```text
backend/app/agents/answer_agent.py
- Contains Agent 3 answer generation and self-check implementation.

backend/app/agents/prompts.py
- Extend with answer generation and self-check prompts.

backend/app/agents/schemas.py
- Extend with answer input, citation, self-check, and final answer schemas.

backend/app/services/shopaikey_service.py
- Reuse chat completion helper.

backend/app/services/agent_log_service.py
- Reuse for Agent 3 logging.

backend/tests/test_answer_agent.py
- Tests grounded answer behavior, insufficient evidence behavior, citations, and logging.
```

## 7. Data Model / Schema Changes

No database schema changes in this plan.

Agent 3 output schema:

```json
{
  "final_answer": "Bạn có thể làm việc chính thức vào tháng 8/2026.",
  "citations": [
    {
      "file_name": "contract.pdf",
      "quote": "Thời gian thử việc bắt đầu từ 01/06/2026 và kéo dài 2 tháng."
    }
  ],
  "reasoning_summary": "Start date is 01/06/2026 and probation lasts 2 months, so the official month is 08/2026.",
  "confidence": 0.82,
  "self_check": {
    "uses_only_verified_chunks": true,
    "has_citation": true,
    "has_unsupported_claims": false,
    "is_ready": true
  }
}
```

Insufficient evidence answer text:

```text
Tài liệu hiện tại chưa cung cấp đủ thông tin để xác định câu trả lời.
```

Citation object:

```json
{
  "file_name": "contract.pdf",
  "quote": "Exact quote from verified chunk"
}
```

## 8. API Design

No new public API endpoints in this plan.

Internal callable:

```text
Function: run_answer_agent(input: AnswerAgentInput) -> AnswerAgentOutput
Input:
{
  "agent_run_id": "uuid",
  "question": "string",
  "verification": {
    "verified_chunks": [],
    "rejected_chunks": [],
    "missing_information": false,
    "confidence": 0.82
  }
}
Output:
{
  "final_answer": "string",
  "citations": [],
  "reasoning_summary": "string",
  "confidence": 0.82,
  "self_check": {}
}
Errors:
- AnswerAgentError for LLM, validation, or self-check failure
```

## 9. Implementation Steps

1. Extend `backend/app/agents/schemas.py` with `Citation`, `AnswerSelfCheck`, `AnswerAgentInput`, and `AnswerAgentOutput`.
2. Add validators that require every citation quote to come from a verified chunk quote.
3. Add validators that reject citations from rejected chunks.
4. Write answer generation prompt in `prompts.py`.
5. Prompt rules must state: use verified chunks only, never use rejected chunks, never use outside knowledge, include citations, answer in Vietnamese by default, and only perform simple reasoning when evidence is clear.
6. Write self-check prompt or deterministic self-check function.
7. Implement `run_answer_agent(input_data)`.
8. If `missing_information=true` or `verified_chunks` is empty, return the insufficient-evidence answer without asking the model to invent an answer.
9. For sufficient evidence, send question and verified chunks to ShopAIKey chat completion.
10. Require JSON output matching `AnswerAgentOutput` without the final self-check or with a draft self-check that will be revalidated.
11. Parse and validate the draft answer.
12. Run self-check to confirm the answer uses only verified chunks, includes citations, avoids rejected chunks, has no unsupported claims, and is ready.
13. If self-check fails, return an insufficient-evidence answer or raise `AnswerAgentError`; do not return unsupported content.
14. Log answer generation and self-check in `agent_steps` with step name `agent_3_answer_self_check`.
15. Add tests for normal answer, insufficient evidence, missing citation, citation not in verified quote, use of rejected chunk, and self-check failure.

## 10. Configuration and Environment Variables

```text
SHOPAIKEY_API_KEY
- Purpose: Answer generation chat completion.
- Required: Yes for grounded answer generation.
- Example: shopaikey-placeholder
- Scope: Backend-only.

SHOPAIKEY_BASE_URL
- Purpose: OpenAI-compatible API base URL.
- Required: Yes.
- Example: https://api.shopaikey.com/v1
- Scope: Backend-only.

SHOPAIKEY_CHAT_MODEL
- Purpose: Model used for answer generation and self-check.
- Required: Yes.
- Example: gpt-5-mini
- Scope: Backend-only.

SINGLE_USER_ID
- Purpose: Indirect ownership scope from previous retrieval and verification.
- Required: Yes.
- Example: single_user
- Scope: Backend-only.
```

## 11. Required Tests

Unit tests:

```text
cd backend
pytest tests/test_answer_agent.py -v
```

Concrete test cases:

```text
Verified chunks include start date and probation duration -> answer may infer August 2026.
missing_information true -> insufficient-evidence answer.
No verified chunks -> insufficient-evidence answer.
LLM citation not present in verified quote -> fail validation.
LLM uses rejected chunk -> fail self-check.
Self-check has_unsupported_claims true -> do not return answer as ready.
```

Manual check:

```text
Pass sample Agent 2 output to Agent 3.
Confirm final answer includes citations in `file_name: "quoted text"` form.
Confirm no chunk IDs are shown to normal users.
```

## 12. Acceptance Criteria

- Agent 3 uses verified chunks only.
- Agent 3 never uses rejected chunks.
- Agent 3 includes citations with file name and quote.
- Agent 3 handles insufficient evidence safely.
- Agent 3 allows simple reasoning only when verified evidence clearly supports it.
- Agent 3 self-checks before returning a ready answer.
- Output is Pydantic-validated.
- Agent 3 logs answer and self-check output.

## 13. Failure Handling

- Missing verified chunks returns insufficient-evidence answer.
- ShopAIKey failure logs failed step and raises `AnswerAgentError`.
- Invalid JSON response is rejected.
- Missing citation fails validation.
- Citation quote not present in verified evidence fails validation.
- Unsupported claim detected by self-check prevents final answer from being marked ready.

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

The report must include one grounded answer example and one insufficient-evidence example.

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

- Confirm citation format is file name plus quoted text.
- Confirm normal user output does not expose chunk IDs.
- Confirm simple reasoning is limited and evidence-based.
- Confirm self-check failure is not ignored.
