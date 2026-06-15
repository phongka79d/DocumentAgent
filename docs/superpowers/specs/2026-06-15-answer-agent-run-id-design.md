# Answer Agent Run ID Design

## Goal

Display the current answer's `agent_run_id` beside the Answer heading so the
user can provide the identifier for debugging and open all persisted agent
steps directly.

## UI Behavior

- The Answer header shows `Agent run: <UUID>` beside the `Answer` heading.
- The UUID links to `/agent-logs/<encoded-agent-run-id>`.
- The existing confidence badge remains aligned on the right.
- The identifier wraps without causing horizontal page overflow on narrow
  screens.
- The existing `Inspect agent logs` action remains available in the evidence
  section.

## Component Changes

- `ChatPage` passes `latestResponse.agent_run_id` to `AnswerPanel`.
- `AnswerPanel` adds a required `agentRunId` prop and renders the identifier as
  a React Router link.
- `styles.css` adds focused styles for the heading/identifier group and mobile
  wrapping.

## Data Flow

The backend response contract already includes `agent_run_id`. No backend,
schema, API-client, persistence, or agent behavior changes are required.

## Validation

- Run `npm run build` from `frontend/`.
- Verify in the browser that a completed answer displays the same UUID returned
  by the chat API.
- Verify the UUID link opens the matching Agent Logs route.
- Verify the Answer header remains usable at desktop and narrow viewport widths.

## Scope

This change only exposes the existing run identifier in the answer UI. It does
not fetch agent steps inside the Answer panel, change agent logging, or add a
new backend endpoint.
