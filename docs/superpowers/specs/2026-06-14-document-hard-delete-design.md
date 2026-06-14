# Document Hard Delete Design

## Goal

Add a confirmed, permanent document deletion workflow that removes the document
from the visible frontend and from every persisted system that contains the
document or data derived from it.

Deleting one document must remove every agent run that selected that document,
even when the run selected additional documents. Agent runs are immutable
historical units and must not survive with incomplete source provenance.

## Scope

The deletion workflow removes:

- the original file from Supabase Storage;
- all Qdrant points whose payload belongs to the document and configured user;
- the Supabase `documents` row;
- related `document_chunks`, `document_entities`, and
  `document_relationships`;
- every `agent_run` whose `selected_document_ids` contains the document ID;
- all `agent_steps` belonging to those runs;
- assistant chat messages whose metadata references an affected run;
- user chat messages whose metadata selected the deleted document;
- chat sessions that have no remaining messages and no remaining agent runs.

Each deletion attempt also creates an independent audit record that survives
the deleted document, agent runs, and chat data. Both successful and failed
attempts are retained and displayed in the Logs UI.

The workflow is single-user, read/write through the backend only, and does not
add bulk deletion, undo, trash retention, restore, or background jobs.

## Deletion Semantics

### Affected Runs

An agent run is affected when its JSON `selected_document_ids` array contains
the deleted document ID.

If a run selected both `t1` and `t2`, deleting `t1` deletes the complete run and
all its steps immediately. The run is not retained for `t2`.

### Related Chat Data

For affected runs:

- delete assistant messages whose metadata `agent_run_id` matches an affected
  run ID;
- delete user messages whose metadata `document_ids` contains the deleted
  document ID.

After those messages and runs are deleted, delete an owned chat session only
when it has neither remaining messages nor remaining agent runs.

### Database Cascades

Deleting `agent_runs` relies on the existing foreign key cascade to delete
`agent_steps`.

Deleting the `documents` row relies on existing cascades for chunks and
entities. Relationship rows are deleted explicitly as part of the relational
cleanup so behavior does not depend on unverified production migration state.

## Architecture

### API

Add:

```text
DELETE /api/documents/{document_id}
```

Success returns a typed summary:

```json
{
  "document_id": "uuid",
  "deleted": true,
  "deleted_agent_runs": 2,
  "deleted_chat_messages": 4,
  "deleted_chat_sessions": 1,
  "deleted_qdrant_points": true,
  "deleted_storage_file": true
}
```

Errors:

- `404` when the document is missing or not owned by the configured user;
- `500` with a safe public message for Storage, Qdrant, or Supabase cleanup
  failures.

No provider details, environment values, stack traces, bucket names, or keys
are returned to the frontend.

### Backend Service

`document_service.delete_document(document_id)` coordinates deletion:

1. Load and ownership-check the document row.
2. Read its storage path and identify affected run/session/message IDs.
3. Delete Qdrant points by payload filter using both `user_id` and
   `document_id`.
4. Delete the original Supabase Storage object.
5. Execute relational cleanup through one Supabase database RPC transaction.
6. Return the deletion summary.

External deletion happens before relational cleanup. This avoids deleting the
only database metadata needed to locate Storage and Qdrant objects. If the
database cleanup then fails, the endpoint returns an error and a retry safely
continues because missing Qdrant points and a missing Storage object are treated
as already deleted.

The database RPC must be transactional and ownership-scoped. It identifies
affected data again inside the transaction, deletes messages/runs/graph data,
deletes the document, removes newly empty sessions, and returns counts.

### Supabase RPC

Add a migration defining this function:

```text
delete_owned_document_cascade(p_document_id uuid, p_user_id text)
```

The function:

- locks or verifies the owned document;
- collects affected run IDs and session IDs;
- deletes assistant messages referencing affected run IDs;
- deletes user messages whose `document_ids` contains the document;
- deletes affected runs;
- explicitly deletes relationship rows;
- deletes the document and relies on foreign-key cascades where defined;
- deletes affected sessions only when no messages or runs remain;
- returns deletion counts.

The backend service role is the only caller. The frontend never calls Supabase
directly.

### Deletion Audit Logs

Add a `deletion_logs` table independent of `documents` and `agent_runs`. It
must not have cascading foreign keys to records removed by deletion.

Each attempt records:

- a generated log ID;
- configured user ID;
- requested document ID;
- filename captured before deletion;
- `success` or `failed` status;
- timestamp;
- failure stage and a safe error message for failed attempts;
- deletion results or counts for Storage, Qdrant, chunks, entities,
  relationships, agent runs, agent steps, chat messages, and chat sessions.

The log never stores document content, chunk content, secrets, provider error
payloads, stack traces, bucket configuration, or credentials.

The service persists a success record only after all deletion stages complete.
When a stage fails, it persists a failed record containing completed-stage
results and the safe failure stage. A failed audit write must not replace the
original deletion error. If deletion succeeds but the required success audit
record cannot be persisted, the endpoint returns a safe `500`.

Add:

```text
GET /api/deletion-logs
```

The endpoint is ownership-scoped, returns newest records first, and supports
bounded pagination plus an optional `success` or `failed` status filter. It
returns typed public fields only.

### Qdrant

Add a focused service function that deletes points using a filter:

```text
user_id == configured single user
document_id == requested document
```

This is preferred over trusting stored `qdrant_point_id` values because it also
removes points created before or outside a successful point-ID metadata update.
An already-empty filter result is success.

### Supabase Storage

Add a focused service function that removes the exact `storage_path` from the
configured bucket. A confirmed missing object is treated as already deleted so
the overall operation is retryable.

## Frontend

### API Client

Add a typed `deleteDocument(documentId)` helper to the existing document API
module. It uses the shared Axios client, encodes the path segment, and returns
the deletion summary.

### Document Card

Add a visible `Delete` button to each document card. Activating it opens an
accessible confirmation dialog containing:

- the filename;
- a permanent-deletion warning;
- explicit notice that the stored file, vectors, chunks/graph data, affected
  agent runs/steps, related chat messages, and newly empty sessions will be
  removed.

Actions:

- `Cancel`;
- `Delete permanently`.

The destructive action is disabled while the request is running. Focus returns
to a sensible control after cancellation or failure.

### List State

On success, remove the document from local list state using the confirmed
backend response. This is not a visual-only deletion: the list changes only
after the backend completes.

On failure, keep the card visible and show a safe card-level or page-level
error. Allow retry. Prevent duplicate delete requests for the same document.

If a refresh happens during deletion, stale responses must not restore a
successfully deleted document.

### Logs UI

Extend the existing Agent Logs page with a separate **Deletion Logs** section.
It loads independently of the agent-run UUID lookup and shows status, filename,
document ID, timestamp, deleted resource counts/results, and failed-stage
details.

Provide `All`, `Successful`, and `Failed` filters. Rows are concise and
expandable. Loading, empty, pagination, and failure states remain isolated from
the Agent Logs lookup state.

## Failure Handling and Retry

The operation spans Qdrant, Storage, and PostgreSQL, so it cannot be one
cross-system transaction.

Required behavior:

- preflight ownership before external deletion;
- safe server logging with document ID and operation stage, never secret values;
- persistent success and failure audit records with safe structured fields;
- idempotent Qdrant and Storage deletion;
- transactional relational cleanup through RPC;
- no frontend removal until complete backend success;
- safe retry after any partial failure;
- concurrent duplicate delete requests must produce one successful final state;
  a later request returns the normal ownership-safe `404` after the row is gone.

If Qdrant deletion succeeds and Storage fails, the database remains intact and
a retry re-runs Qdrant deletion safely.

If both external deletions succeed and relational cleanup fails, the database
row remains for retry and the missing external objects are treated as already
deleted.

## Testing

### Backend

Add focused tests for:

- route success, ownership-safe `404`, UUID validation, and safe `500` errors;
- service operation ordering and returned summary;
- Qdrant filtered delete using both user and document conditions;
- Storage exact-path delete and missing-object idempotency;
- RPC invocation with the configured user;
- affected multi-document runs being deleted in full;
- unrelated runs/messages/sessions remaining;
- assistant and user related-message deletion;
- empty-session deletion and non-empty-session preservation;
- retry behavior after partial external success;
- no external deletion when ownership lookup fails;
- successful and failed audit-record persistence;
- safe failure-stage recording without provider details;
- deletion-log listing, filtering, ownership scope, ordering, and pagination;
- success-audit failure returning a safe `500`;
- failure-audit failure preserving the original deletion error.

Where practical, add a migration/RPC integration test or SQL contract
inspection covering transactional deletion order and JSON containment.

### Frontend

Use existing frontend test infrastructure only if present. Otherwise validate
with the production build and manual browser checks:

- Delete button opens confirmation.
- Cancel makes no request and changes no list state.
- Confirmation text names all destructive consequences.
- Confirm disables duplicate actions and shows progress.
- Success removes the card only after the backend response.
- Failure retains the card and exposes a safe retryable error.
- Keyboard focus and dialog semantics work.
- Layout remains usable at narrow widths.
- Deletion Logs load independently from agent-run lookup.
- Filters, expanded details, pagination, and isolated UI states work.

### End-to-End

Create a disposable test document and, if feasible, a run that uses it.
After confirmed deletion verify:

- document GET/list no longer returns it;
- Storage object is absent;
- Qdrant filtered query/count has no document points;
- document chunks/entities/relationships are absent;
- every run selecting the document and its steps are absent;
- related messages are absent;
- unrelated multi-document data remains;
- empty sessions are removed and non-empty sessions remain;
- a successful deletion audit record remains after dependent data is gone;
- a disposable failed attempt creates a safe failed audit record.

Never use an irreplaceable user document for destructive validation.

## Intentional Exclusions

- soft delete or trash;
- restore/undo;
- bulk selection deletion;
- retention policies;
- partial redaction of multi-document runs;
- direct frontend Supabase or Qdrant calls;
- asynchronous cleanup workers.

## Acceptance Criteria

- A user must explicitly confirm permanent deletion.
- The frontend never removes a card before backend success.
- The original Storage object and all Qdrant points for the document are gone.
- Supabase document-derived rows are gone.
- Every run that selected the document is deleted in full with its steps.
- Related chat messages are deleted.
- Chat sessions are deleted only when they have no remaining messages or runs.
- Unrelated documents, runs, messages, and sessions remain intact.
- Partial failures return safe errors and are retryable.
- Successful and failed attempts remain visible in Deletion Logs.
- Audit records contain only safe metadata and deletion results.
- Automated backend tests and frontend build pass.
