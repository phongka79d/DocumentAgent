# Plan 9 - Agent 1 Retrieval Agent

## 1. Goal

Implement Agent 1 as the Retrieval Agent that receives a user question and selected documents, runs hybrid retrieval, returns structured candidate chunks, and logs its input/output.

The goal is testable when Agent 1 produces the required JSON candidate schema and records a successful `agent_steps` row for retrieval.

## 2. Why This Plan Exists

The full QA workflow needs a dedicated retrieval agent with traceable decisions. This plan wraps the hybrid retrieval service in an agent-compatible contract before evidence verification is added.

## 3. Scope

- Add shared agent schemas.
- Add Agent 1 input and output models.
- Implement Retrieval Agent logic.
- Integrate hybrid retrieval service from Plan 8.
- Produce structured JSON output.
- Create an agent step log for retrieval.
- Add tests for success, empty results, and retrieval failure.

## 4. Out of Scope

- Do not implement Agent 2 verification.
- Do not implement Agent 3 answer generation.
- Do not build the LangGraph workflow yet.
- Do not create `/api/chat/ask`.
- Do not generate final answers.
- Do not let Agent 1 mark chunks as verified.

## 5. Dependencies

- Plan 2 must be completed for `agent_steps`.
- Plan 8 must be completed for hybrid retrieval.

## 6. Required Files and Folders

```text
backend/app/agents/__init__.py
- Marks the agents package.

backend/app/agents/schemas.py
- Contains shared agent Pydantic models.

backend/app/agents/retrieval_agent.py
- Contains Agent 1 Retrieval Agent implementation.

backend/app/services/agent_log_service.py
- Adds helper functions for writing `agent_steps`.

backend/app/services/hybrid_retrieval_service.py
- Reused by Agent 1.

backend/app/services/supabase_service.py
- Add helper for inserting agent step logs if not already present.

backend/tests/test_retrieval_agent.py
- Tests Agent 1 output and logging behavior.
```

## 7. Data Model / Schema Changes

No database schema changes in this plan.

Agent 1 input schema:

```json
{
  "agent_run_id": "uuid",
  "question": "Tôi có thể làm việc chính thức vào tháng mấy?",
  "document_ids": ["uuid"]
}
```

Agent 1 output schema:

```json
{
  "question": "Tôi có thể làm việc chính thức vào tháng mấy?",
  "candidates": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "file_name": "contract.pdf",
      "content": "Sau 2 tháng thử việc, nhân sự sẽ được xét làm việc chính thức theo điều kiện trong hợp đồng.",
      "page_number": 3,
      "section_title": "Thời gian thử việc",
      "semantic_similarity": 0.88,
      "graph_relevance": 0.76,
      "keyword_overlap": 0.64,
      "metadata_match": 0.7,
      "recency_or_position_score": 0.5,
      "final_score": 0.78,
      "retrieval_reason": "Chunk mentions probation period and official employment condition."
    }
  ]
}
```

Agent step log shape:

```json
{
  "agent_run_id": "uuid",
  "step_name": "agent_1_retrieval",
  "agent_name": "retrieval_agent",
  "input": {},
  "output": {},
  "status": "success",
  "error_message": null
}
```

## 8. API Design

No new public API endpoints in this plan.

Internal callable:

```text
Function: run_retrieval_agent(input: RetrievalAgentInput) -> RetrievalAgentOutput
Errors:
- RetrievalAgentError when retrieval fails
- ValidationError when output does not match schema
```

## 9. Implementation Steps

1. Create `backend/app/agents/schemas.py`.
2. Define `RetrievalAgentInput`, `RetrievalCandidate`, and `RetrievalAgentOutput`.
3. Reuse the hybrid candidate fields from Plan 8 exactly.
4. Create `backend/app/services/agent_log_service.py`.
5. Implement `log_agent_step(agent_run_id, step_name, agent_name, input_payload, output_payload, status, error_message=None)`.
6. Create `backend/app/agents/retrieval_agent.py`.
7. Implement `run_retrieval_agent(input_data)`.
8. Validate the input with Pydantic.
9. Call `retrieve_hybrid(question, document_ids, final_top_k)`.
10. Convert retrieval candidates into `RetrievalCandidate` models.
11. Validate the output model before returning.
12. Write an `agent_steps` row with status `success` after output validation.
13. If retrieval fails, write an `agent_steps` row with status `failed` and a safe error message.
14. Re-raise a controlled `RetrievalAgentError` for the workflow layer to handle later.
15. Add tests that mock hybrid retrieval and agent logging.
16. Test that empty results return `candidates: []` with status `success`.
17. Test that retrieval exceptions produce a failed log entry.

## 10. Configuration and Environment Variables

```text
RETRIEVAL_FINAL_TOP_K
- Purpose: Default number of candidate chunks Agent 1 returns.
- Required: No.
- Example: 8
- Scope: Backend-only.

SINGLE_USER_ID
- Purpose: Used by downstream retrieval filters.
- Required: Yes.
- Example: single_user
- Scope: Backend-only.

SUPABASE_URL
- Purpose: Agent step persistence.
- Required: Yes.
- Example: https://example-project.supabase.co
- Scope: Backend-only.

SUPABASE_SERVICE_ROLE_KEY
- Purpose: Insert agent step logs.
- Required: Yes.
- Example: supabase-service-role-placeholder
- Scope: Backend-only.
```

## 11. Required Tests

Unit tests:

```text
cd backend
pytest tests/test_retrieval_agent.py -v
```

Manual check:

```text
Create or reuse an agent_run_id.
Call run_retrieval_agent with a question and selected document IDs.
Confirm output contains candidates with all score fields.
Confirm agent_steps contains one agent_1_retrieval row.
```

Negative checks:

```text
Mock hybrid retrieval failure.
Confirm Agent 1 logs a failed step and raises RetrievalAgentError.
```

## 12. Acceptance Criteria

- Agent 1 has a clear callable function.
- Agent 1 output matches the required structured JSON schema.
- Candidate chunks include all retrieval score components.
- Candidate chunks are sorted by `final_score` as returned by hybrid retrieval.
- Agent 1 logs successful runs to `agent_steps`.
- Agent 1 logs failed runs to `agent_steps`.
- Agent 1 does not verify evidence or generate answers.

## 13. Failure Handling

- Invalid input raises validation error before retrieval.
- Hybrid retrieval failure creates a failed agent step log.
- Agent log insert failure must be logged; it should not silently erase retrieval failure context.
- Empty retrieval results are a valid successful output.
- Candidate schema mismatch must fail before the workflow proceeds.

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

The report must include whether an `agent_steps` row was verified through a live database or mocked test.

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

- Confirm Agent 1 does not call the answer LLM.
- Confirm Agent 1 does not mark chunks verified.
- Confirm output is Pydantic-validated.
- Confirm failures are visible in logs.
