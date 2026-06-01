# Plan 14 - Frontend Chat and Evidence Viewer

## 1. Goal

Build the frontend chat experience so the user can select ready documents, ask a question, see the grounded answer, view confidence and citations, and inspect verified and rejected evidence.

The goal is testable when a user can ask a question through `/api/chat/ask` and open evidence for the returned `agent_run_id`.

## 2. Why This Plan Exists

The backend workflow is complete, but users need a clear interface for document QA and evidence inspection. This plan exposes the main value of the system while preserving the verified-evidence rule.

## 3. Scope

- Add chat API client.
- Add agent runs API client for evidence.
- Add document selector using ready documents.
- Add question input form.
- Add answer display.
- Add confidence display.
- Add citation display.
- Add evidence viewer for verified and rejected chunks.
- Add loading, empty, and error states.
- Add frontend tests/build checks.

## 4. Out of Scope

- Do not implement agent logs/debug UI.
- Do not implement streaming chat responses.
- Do not implement multi-session chat history beyond passing optional `session_id` if available.
- Do not expose internal prompts or API keys.
- Do not allow users to edit verified/rejected evidence.
- Do not add authentication.

## 5. Dependencies

- Plan 12 must be completed for `/api/chat/ask` and evidence endpoint.
- Plan 13 must be completed for document list UI and types.
- At least one document should be processed and ready for meaningful manual testing.

## 6. Required Files and Folders

```text
frontend/src/api/chat.ts
- Contains askQuestion function for `/api/chat/ask`.

frontend/src/api/agentRuns.ts
- Contains getAgentRunEvidence and later logs helpers.

frontend/src/types/chat.ts
- Contains chat request/response, citation, and evidence types.

frontend/src/pages/ChatPage.tsx
- Contains document selector, question form, answer display, and evidence trigger.

frontend/src/pages/EvidenceViewerPage.tsx
- Full page or routed view for evidence by agent_run_id.

frontend/src/components/ChatBox.tsx
- Reusable question input and submit state.

frontend/src/components/AnswerPanel.tsx
- Displays final answer, confidence, and citations.

frontend/src/components/EvidencePanel.tsx
- Displays verified and rejected chunks.

frontend/src/components/DocumentSelector.tsx
- Selects one or more ready documents.

frontend/src/App.tsx
- Add route/navigation for Chat and Evidence.

frontend/src/pages/ChatPage.test.tsx
- UI behavior tests if test runner exists.

frontend/src/api/chat.test.ts
- API client tests if test runner exists.
```

## 7. Data Model / Schema Changes

No backend database schema changes in this plan.

Frontend chat request:

```ts
export type AskQuestionRequest = {
  session_id?: string | null;
  question: string;
  document_ids: string[];
};
```

Frontend chat response:

```ts
export type AskQuestionResponse = {
  answer: string;
  confidence: number | null;
  citations: Array<{
    file_name: string;
    quote: string;
  }>;
  agent_run_id: string;
};
```

Evidence response:

```ts
export type AgentRunEvidence = {
  verified_chunks: Array<{
    chunk_id?: string;
    document_id?: string;
    file_name: string;
    quote: string;
    page_number?: number | null;
    verification_reason?: string;
    supports_simple_reasoning?: boolean;
  }>;
  rejected_chunks: Array<{
    chunk_id?: string;
    document_id?: string;
    file_name: string;
    quote: string;
    rejection_reason: string;
  }>;
};
```

## 8. API Design

No new backend APIs in this plan.

Frontend calls existing APIs:

```text
POST /api/chat/ask
Request:
{
  "session_id": "uuid or null",
  "question": "string",
  "document_ids": ["uuid"]
}
Response:
{
  "answer": "string",
  "confidence": 0.82,
  "citations": [],
  "agent_run_id": "uuid"
}
```

```text
GET /api/agent-runs/{agent_run_id}/evidence
Response:
{
  "verified_chunks": [],
  "rejected_chunks": []
}
```

Frontend validation:

```text
Question must be non-empty.
At least one ready document must be selected.
Only documents with status ready can be selected for chat.
```

## 9. Implementation Steps

1. Create `frontend/src/types/chat.ts`.
2. Create `frontend/src/api/chat.ts` with `askQuestion(request)`.
3. Create `frontend/src/api/agentRuns.ts` with `getAgentRunEvidence(agentRunId)`.
4. Create `DocumentSelector.tsx` using document list data and filtering to `status === "ready"`.
5. Support multi-select if the backend accepts multiple document IDs.
6. Create `ChatBox.tsx` with textarea/input, submit button, disabled loading state, and validation message.
7. Create `AnswerPanel.tsx` showing final answer, confidence, and citations.
8. Citations must show file name and quote; do not show chunk IDs in normal answer UI.
9. Create `EvidencePanel.tsx` with separate sections for verified and rejected chunks.
10. Verified evidence should show file name, quote, page number if present, verification reason, and simple reasoning flag.
11. Rejected evidence should show file name, quote, and rejection reason.
12. Create `ChatPage.tsx` combining document selector, chat box, answer panel, and evidence panel trigger.
13. Store the last `agent_run_id` after an answer is returned.
14. Load evidence only after a successful answer or when the user opens the evidence panel.
15. Create `EvidenceViewerPage.tsx` for direct URL access if routing supports `agent_run_id`.
16. Add route/navigation to Chat in `App.tsx`.
17. Add error handling for backend errors, no ready documents, empty question, and evidence load failure.
18. Add frontend tests if the project has a test runner.
19. Run `npm run build`.

## 10. Configuration and Environment Variables

```text
VITE_API_BASE_URL
- Purpose: Base URL for FastAPI backend.
- Required: Yes.
- Example: http://localhost:8000
- Scope: Frontend-safe.
```

Do not add private provider keys to frontend environment variables.

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
Start backend and frontend.
Open Chat page.
Select a ready document.
Ask: Tôi có thể làm việc chính thức vào tháng mấy?
Confirm answer appears.
Confirm confidence appears.
Confirm citations appear as file name plus quote.
Open evidence viewer.
Confirm verified and rejected chunks are visible.
```

Negative manual tests:

```text
Submit empty question and confirm validation error.
Try chat with no selected document and confirm validation error.
Simulate backend failure and confirm error display.
```

## 12. Acceptance Criteria

- Chat page exists and is reachable from navigation.
- User can select one or more ready documents.
- User can submit a non-empty question.
- Answer, confidence, and citations are displayed.
- Citation format shows file name and quoted text.
- Evidence viewer displays verified and rejected chunks.
- Normal chat UI does not expose internal chunk IDs unless the evidence/debug view intentionally includes them.
- Frontend build passes.
- No agent logs debug UI is implemented in this plan.

## 13. Failure Handling

- No ready documents shows a clear empty state.
- Empty question blocks submission.
- Backend chat failure shows a safe error message.
- Evidence load failure does not erase the answer.
- Missing citations displays an explicit "no citations returned" state, but this should be treated as a backend issue in testing.
- Long answers and quotes must wrap without overflowing containers.

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

The report must include whether manual chat and evidence viewer tests were performed.

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

- Confirm only ready documents are selectable.
- Confirm citations are visible and readable.
- Confirm evidence viewer separates verified and rejected chunks.
- Confirm UI stays usable at mobile and desktop widths.
