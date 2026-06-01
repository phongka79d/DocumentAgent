# Plan 12 - LangGraph Full QA Workflow

## 1. Goal

Implement the full LangGraph question-answering workflow from Agent 1 to Agent 2 to Agent 3 and expose it through `/api/chat/ask`, with agent run persistence, step persistence, evidence retrieval, and logs retrieval.

The goal is testable when one API request creates an `agent_runs` row, logs each agent step, returns a grounded final answer, and exposes evidence and logs by `agent_run_id`.

## 2. Why This Plan Exists

The separate agents must be orchestrated into a single reliable backend workflow before the frontend chat page can call it. This plan creates the main backend QA contract.

## 3. Scope

- Create LangGraph workflow in `backend/app/agents/graph.py`.
- Implement workflow state schema.
- Persist `agent_runs`.
- Persist `agent_steps` from each agent.
- Add `POST /api/chat/ask`.
- Add chat session and message persistence.
- Add `GET /api/agent-runs/{agent_run_id}/evidence`.
- Add `GET /api/agent-runs/{agent_run_id}/logs`.
- Handle insufficient evidence and agent failures.
- Add full workflow tests with mocked agents and integration-style tests.

## 4. Out of Scope

- Do not build frontend chat UI.
- Do not add streaming responses.
- Do not add conversation memory beyond storing chat messages.
- Do not add authentication or JWT.
- Do not support multiple users.
- Do not add document deletion.

## 5. Dependencies

- Plan 9 must be completed.
- Plan 10 must be completed.
- Plan 11 must be completed.
- Plan 2 tables must exist.

## 6. Required Files and Folders

```text
backend/app/agents/graph.py
- Defines LangGraph workflow START -> Agent 1 -> Agent 2 -> Agent 3 -> Self-check -> FINAL.

backend/app/api/chat.py
- Contains `/api/chat/ask`.

backend/app/api/agent_runs.py
- Contains evidence and logs endpoints.

backend/app/schemas/chat.py
- Contains chat request and answer response schemas.

backend/app/schemas/agent_runs.py
- Contains evidence and logs response schemas.

backend/app/services/chat_service.py
- Handles chat session, chat message, and agent run persistence.

backend/app/services/agent_run_service.py
- Handles agent run creation, update, evidence lookup, and logs lookup.

backend/app/services/supabase_service.py
- Add helpers for chat_sessions, chat_messages, agent_runs, and agent_steps queries.

backend/app/main.py
- Include chat and agent_runs routers.

backend/tests/test_langgraph_workflow.py
- Tests graph state transitions with mocked agents.

backend/tests/test_chat_api.py
- Tests `/api/chat/ask`.

backend/tests/test_agent_runs_api.py
- Tests evidence and logs endpoints.

backend/requirements.txt
- Add LangGraph dependency if not already present.
```

## 7. Data Model / Schema Changes

No database table changes in this plan.

Use existing tables:

```text
chat_sessions
chat_messages
agent_runs
agent_steps
```

Chat ask request:

```json
{
  "session_id": "uuid",
  "question": "Tôi có thể làm việc chính thức vào tháng mấy?",
  "document_ids": ["uuid"]
}
```

Allow `session_id` to be nullable or omitted. If omitted, create a new chat session.

Chat ask response:

```json
{
  "answer": "Bạn có thể được xét làm việc chính thức vào tháng 8/2026.",
  "confidence": 0.82,
  "citations": [
    {
      "file_name": "contract.pdf",
      "quote": "Thời gian thử việc kéo dài 2 tháng."
    }
  ],
  "agent_run_id": "uuid"
}
```

LangGraph state:

```json
{
  "agent_run_id": "uuid",
  "session_id": "uuid",
  "question": "string",
  "document_ids": ["uuid"],
  "retrieval": null,
  "verification": null,
  "answer": null,
  "error": null
}
```

## 8. API Design

```text
Method: POST
Path: /api/chat/ask
Request body:
{
  "session_id": "uuid or null",
  "question": "string",
  "document_ids": ["uuid"]
}
Response body:
{
  "answer": "string",
  "confidence": 0.82,
  "citations": [],
  "agent_run_id": "uuid"
}
Error responses:
- 400 empty question
- 400 selected document list is empty if the system requires explicit selection
- 404 session_id not found for SINGLE_USER_ID
- 500 workflow failure
Validation rules:
- question must be non-empty.
- document_ids must be valid UUIDs.
- all selected documents must belong to SINGLE_USER_ID.
```

```text
Method: GET
Path: /api/agent-runs/{agent_run_id}/evidence
Request body: none
Response body:
{
  "verified_chunks": [],
  "rejected_chunks": []
}
Error responses:
- 404 agent run not found for SINGLE_USER_ID
```

```text
Method: GET
Path: /api/agent-runs/{agent_run_id}/logs
Request body: none
Response body:
{
  "agent_run_id": "uuid",
  "steps": [
    {
      "agent_name": "retrieval_agent",
      "input": {},
      "output": {},
      "status": "success",
      "created_at": "2026-06-01T10:00:00Z"
    }
  ]
}
Error responses:
- 404 agent run not found for SINGLE_USER_ID
```

## 9. Implementation Steps

1. Add LangGraph to `backend/requirements.txt`.
2. Create chat and agent run schemas.
3. Create `chat_service.py` with helpers to create or fetch chat sessions and persist user/assistant messages.
4. Create `agent_run_service.py` with helpers to create an `agent_runs` row, mark it succeeded, mark it failed, fetch evidence, and fetch logs.
5. Validate that all `document_ids` belong to `SINGLE_USER_ID` before starting the workflow.
6. Create `backend/app/agents/graph.py`.
7. Define workflow state model.
8. Add node `agent_1_retrieval` calling `run_retrieval_agent`.
9. Add node `agent_2_verification` calling `run_verification_agent`.
10. Add node `agent_3_answer_self_check` calling `run_answer_agent`.
11. Compile graph with order `START -> Agent 1 -> Agent 2 -> Agent 3 -> FINAL`.
12. Ensure Agent 3 contains the self-check, matching the required logical path `START -> Agent 1 -> Agent 2 -> Agent 3 -> Self-check -> FINAL`.
13. Implement `run_qa_workflow(question, document_ids, session_id=None)`.
14. Create `agent_runs` row with status `running` before invoking graph.
15. Persist user question in `chat_messages`.
16. On success, update `agent_runs` with status `success`, final answer, and confidence.
17. Persist assistant answer in `chat_messages`.
18. On failure, update `agent_runs` with status `failed` and error message.
19. Implement `/api/chat/ask`.
20. Implement evidence endpoint by reading Agent 2 output from `agent_steps`.
21. Implement logs endpoint by reading all `agent_steps` for the run ordered by `created_at`.
22. Add tests with mocked agent functions so workflow behavior is deterministic.
23. Add error-path tests for Agent 1, Agent 2, and Agent 3 failures.

## 10. Configuration and Environment Variables

```text
SINGLE_USER_ID
- Purpose: Owner for sessions, messages, agent runs, and selected document checks.
- Required: Yes.
- Example: single_user
- Scope: Backend-only.

SUPABASE_URL
- Purpose: Persistence for chat and agent run tables.
- Required: Yes.
- Example: https://example-project.supabase.co
- Scope: Backend-only.

SUPABASE_SERVICE_ROLE_KEY
- Purpose: Backend persistence writes.
- Required: Yes.
- Example: supabase-service-role-placeholder
- Scope: Backend-only.

RETRIEVAL_FINAL_TOP_K
- Purpose: Downstream Agent 1 retrieval count.
- Required: No.
- Example: 8
- Scope: Backend-only.
```

## 11. Required Tests

Workflow tests:

```text
cd backend
pytest tests/test_langgraph_workflow.py -v
```

API tests:

```text
cd backend
pytest tests/test_chat_api.py tests/test_agent_runs_api.py -v
```

Manual API check:

```text
curl -X POST http://localhost:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"Tôi có thể làm việc chính thức vào tháng mấy?\",\"document_ids\":[\"<document_id>\"]}"
```

Evidence/log checks:

```text
curl http://localhost:8000/api/agent-runs/<agent_run_id>/evidence
curl http://localhost:8000/api/agent-runs/<agent_run_id>/logs
```

Failure checks:

```text
Mock Agent 2 missing_information true and confirm safe answer.
Mock Agent 3 failure and confirm agent_runs.status = failed.
```

## 12. Acceptance Criteria

- `/api/chat/ask` exists.
- One question creates an `agent_runs` row.
- Workflow runs Agent 1, Agent 2, and Agent 3 in order.
- Agent steps are persisted and retrievable.
- Final answer and confidence are stored on `agent_runs`.
- User and assistant messages are stored in `chat_messages`.
- Evidence endpoint returns verified and rejected chunks.
- Logs endpoint returns each agent step.
- Errors mark the agent run as `failed`.
- No frontend UI is implemented in this plan.

## 13. Failure Handling

- Empty question returns HTTP 400.
- Unknown selected document returns HTTP 404 or HTTP 400 before workflow starts.
- Agent 1 failure marks run failed.
- Agent 2 failure marks run failed.
- Agent 3 failure marks run failed.
- Agent 2 missing information should still allow Agent 3 to return safe insufficient-evidence answer.
- Agent step log query failure returns HTTP 500 with safe public message.

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

The report must include the shape of one successful `/api/chat/ask` response and one verified logs response.

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

- Confirm workflow order matches `START -> Agent 1 -> Agent 2 -> Agent 3 -> Self-check -> FINAL`.
- Confirm all run/session/message queries are scoped by `SINGLE_USER_ID`.
- Confirm final answers come from Agent 3 output.
- Confirm evidence endpoint reads Agent 2 output, not unverified retrieval candidates.
