# Answer Agent Run ID Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show each answer's agent run UUID beside the Answer heading as a direct link to its persisted agent steps.

**Architecture:** Reuse the existing `agent_run_id` returned by the chat API. Pass it from `ChatPage` into `AnswerPanel`, render an encoded React Router link, and add responsive styles without changing backend contracts.

**Tech Stack:** React 19, TypeScript, React Router, CSS, Vite

---

### Task 1: Render the agent run identifier

**Files:**
- Modify: `frontend/src/components/AnswerPanel.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: Extend the AnswerPanel contract**

Add `agentRunId: string` to `AnswerPanelProps`, import `Link` from
`react-router-dom`, normalize the ID, and build:

```tsx
const normalizedAgentRunId = agentRunId.trim();
const agentLogsPath = normalizedAgentRunId
  ? `/agent-logs/${encodeURIComponent(normalizedAgentRunId)}`
  : null;
```

- [ ] **Step 2: Render the linked identifier**

Group the heading and run identifier:

```tsx
<div className="answer-panel__title-group">
  <h2 id={titleId}>Answer</h2>
  {agentLogsPath ? (
    <Link className="answer-panel__run-link" to={agentLogsPath}>
      <span className="answer-panel__run-label">Agent run:</span>{" "}
      <span className="answer-panel__run-id">{normalizedAgentRunId}</span>
    </Link>
  ) : null}
</div>
```

- [ ] **Step 3: Pass the API response ID**

Update `ChatPage`:

```tsx
<AnswerPanel
  agentRunId={latestResponse.agent_run_id}
  answer={latestResponse.answer}
  citations={latestResponse.citations}
  confidence={latestResponse.confidence}
/>
```

### Task 2: Add responsive styling

**Files:**
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Style the title group and link**

Add styles that keep the heading and identifier together while allowing the UUID
to wrap:

```css
.answer-panel__title-group {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.45rem 0.75rem;
}

.answer-panel__run-link {
  min-width: 0;
  color: #315f9f;
  font-size: 0.82rem;
  line-height: 1.35;
  text-decoration-thickness: 0.08em;
  text-underline-offset: 0.16em;
}

.answer-panel__run-label {
  font-weight: 800;
}

.answer-panel__run-id {
  overflow-wrap: anywhere;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
```

- [ ] **Step 2: Preserve narrow-screen layout**

In the existing mobile media query, ensure `.answer-panel__title-group` and the
confidence badge align to the first column without page-level overflow.

### Task 3: Validate

**Files:**
- Verify: `frontend/src/components/AnswerPanel.tsx`
- Verify: `frontend/src/pages/ChatPage.tsx`
- Verify: `frontend/src/styles.css`

- [ ] **Step 1: Run production build**

Run:

```powershell
cd frontend
npm run build
```

Expected: TypeScript and Vite complete with exit code 0.

- [ ] **Step 2: Browser verification**

Open `http://localhost:5173/chat`, submit a question using a ready document, and
confirm:

- `Agent run: <UUID>` appears beside `Answer`.
- The UUID matches the chat response.
- Clicking it opens `/agent-logs/<UUID>`.
- Desktop and narrow layouts do not overflow.

- [ ] **Step 3: Review diff**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors and only intended implementation files plus this
plan are changed.
