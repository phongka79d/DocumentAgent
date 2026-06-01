# Plan 15 - Agent Logs Debug UI

## 1. Goal

Build the frontend agent logs/debug UI so a developer can inspect agent runs, step inputs and outputs, retrieval scores, verification results, answer self-checks, errors, and timestamps.

The goal is testable when a user can open a known `agent_run_id` and inspect every persisted agent step from the frontend.

## 2. Why This Plan Exists

The system must be debuggable. Agent runs involve retrieval, verification, generation, and self-check; this plan makes those intermediate states visible without exposing private keys or requiring direct database access.

## 3. Scope

- Add frontend API client for agent run logs.
- Add agent logs page.
- Add agent run ID input or links from chat results.
- Add step list and step detail viewer.
- Display raw JSON input/output.
- Display retrieval scores from Agent 1 output.
- Display verification result from Agent 2 output.
- Display final answer and self-check result from Agent 3 output.
- Display error messages and statuses.
- Add route/navigation for debug page.
- Add frontend build and manual UI checks.

## 4. Out of Scope

- Do not implement backend logs endpoint if Plan 12 already did it.
- Do not add admin dashboard or multi-user run browser.
- Do not expose backend environment variables or secrets.
- Do not allow editing agent runs or steps.
- Do not implement graph visualization.
- Do not implement production observability dashboards.

## 5. Dependencies

- Plan 12 must be completed for `GET /api/agent-runs/{agent_run_id}/logs`.
- Plan 14 should be completed so chat can link to logs, but direct ID input can work without it.

## 6. Required Files and Folders

```text
frontend/src/api/agentRuns.ts
- Extend with getAgentRunLogs(agentRunId).

frontend/src/types/agentRuns.ts
- Contains AgentRunLogsResponse and AgentStep types.

frontend/src/pages/AgentLogsPage.tsx
- Contains agent run lookup and logs UI.

frontend/src/components/AgentLogViewer.tsx
- Displays step list and selected step details.

frontend/src/components/JsonViewer.tsx
- Displays raw JSON in a readable preformatted block.

frontend/src/components/RetrievalScoreTable.tsx
- Displays Agent 1 candidate scores if present.

frontend/src/components/VerificationResultPanel.tsx
- Displays Agent 2 verified/rejected/missing/confidence result.

frontend/src/components/SelfCheckPanel.tsx
- Displays Agent 3 self-check booleans.

frontend/src/App.tsx
- Add route/navigation for Agent Logs.

frontend/src/pages/AgentLogsPage.test.tsx
- UI tests if the frontend test runner exists.
```

## 7. Data Model / Schema Changes

No backend database schema changes in this plan.

Frontend logs type:

```ts
export type AgentStep = {
  agent_name: string;
  step_name?: string;
  input: unknown;
  output: unknown;
  status: "success" | "failed" | string;
  created_at: string;
  error_message?: string | null;
};

export type AgentRunLogsResponse = {
  agent_run_id: string;
  steps: AgentStep[];
};
```

Expected step names:

```text
agent_1_retrieval
agent_2_verification
agent_3_answer_self_check
```

## 8. API Design

No new backend APIs in this plan.

Frontend calls:

```text
GET /api/agent-runs/{agent_run_id}/logs
Response:
{
  "agent_run_id": "uuid",
  "steps": [
    {
      "agent_name": "retrieval_agent",
      "step_name": "agent_1_retrieval",
      "input": {},
      "output": {},
      "status": "success",
      "created_at": "2026-06-01T10:00:00Z",
      "error_message": null
    }
  ]
}
```

Frontend validation:

```text
agent_run_id must be non-empty.
If validating format, it must be a UUID.
```

## 9. Implementation Steps

1. Create `frontend/src/types/agentRuns.ts`.
2. Extend `frontend/src/api/agentRuns.ts` with `getAgentRunLogs(agentRunId)`.
3. Create `JsonViewer.tsx` using formatted JSON with wrapping and horizontal scroll for long lines.
4. Create `RetrievalScoreTable.tsx` that reads Agent 1 candidates from step output and displays chunk ID, file name, semantic similarity, graph relevance, keyword overlap, metadata match, position score, and final score.
5. Create `VerificationResultPanel.tsx` that displays Agent 2 `verified_chunks`, `rejected_chunks`, `missing_information`, and `confidence`.
6. Create `SelfCheckPanel.tsx` that displays Agent 3 `self_check` fields.
7. Create `AgentLogViewer.tsx` with a left step list and a detail panel.
8. The step list must show agent name, step name, status, timestamp, and error indicator.
9. The detail panel must show structured panels when the step is recognized and raw JSON for every step.
10. Create `AgentLogsPage.tsx` with an agent run ID input and optional route param support.
11. Add link from Chat answer panel to logs for the last `agent_run_id` if Plan 14 components are present.
12. Add route/navigation in `App.tsx`.
13. Add loading, not found, empty logs, and backend error states.
14. Ensure long JSON and quotes do not overflow the page.
15. Add tests if available.
16. Run `npm run build`.

## 10. Configuration and Environment Variables

```text
VITE_API_BASE_URL
- Purpose: Base URL for FastAPI backend.
- Required: Yes.
- Example: http://localhost:8000
- Scope: Frontend-safe.
```

No backend-only secrets may be added to frontend configuration.

## 11. Required Tests

Frontend build:

```text
cd frontend
npm run build
```

Frontend tests if configured:

```text
cd frontend
npm test
```

Manual UI test:

```text
Run a chat question to obtain agent_run_id.
Open Agent Logs page.
Enter the agent_run_id.
Confirm steps load.
Open Agent 1 step and confirm retrieval scores are visible.
Open Agent 2 step and confirm verified/rejected chunks are visible.
Open Agent 3 step and confirm self-check is visible.
Confirm raw JSON is visible for each step.
```

Negative manual tests:

```text
Enter an invalid ID and confirm validation or not-found message.
Simulate backend failure and confirm error display.
Open logs for a failed run and confirm error messages are visible.
```

## 12. Acceptance Criteria

- Agent Logs page exists.
- User can load logs by `agent_run_id`.
- Step list shows status and timestamps.
- Raw JSON input/output is visible for each step.
- Agent 1 retrieval scores are readable.
- Agent 2 verification results are readable.
- Agent 3 self-check results are readable.
- Failed steps show error messages.
- Frontend build passes.
- No secrets are exposed.

## 13. Failure Handling

- Missing `agent_run_id` blocks fetch.
- Not-found run shows clear message.
- Backend error shows safe error state.
- Empty steps show an empty state.
- Malformed output still renders in raw JSON view.
- Long JSON remains readable and does not break layout.

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

The report must include whether a real or mocked `agent_run_id` was used for manual UI testing.

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

- Confirm logs UI is debug-focused, not an admin dashboard.
- Confirm raw JSON is still available even when specialized panels fail.
- Confirm no API keys or environment secrets are displayed.
- Confirm retrieval scores match Agent 1 output field names.
