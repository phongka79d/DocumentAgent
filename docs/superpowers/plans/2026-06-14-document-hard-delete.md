# Document Hard Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add confirmed permanent document deletion across Supabase Storage, Qdrant, relational data, dependent agent/chat history, plus persistent success/failure deletion logs in the existing Logs UI.

**Architecture:** The backend preflights ownership, removes Qdrant points and Storage objects idempotently, then calls one PostgreSQL RPC that deletes relational dependencies and inserts the success audit row atomically. Failures after ownership preflight are written as independent safe audit rows. The frontend removes a document card only after backend success and loads deletion audit history independently from agent-run logs.

**Tech Stack:** FastAPI, Pydantic, Supabase/PostgreSQL RPC, Qdrant Python client, pytest, React 19, TypeScript, Axios, Vite, CSS.

---

## File Structure

- Create `backend/app/db/migrations/002_document_hard_delete.sql`: audit table, indexes, and transactional cascade RPC.
- Create `backend/app/schemas/deletion_logs.py`: public audit-list contracts and deletion count model.
- Create `backend/app/services/deletion_log_service.py`: safe audit insertion/list mapping.
- Create `backend/app/api/deletion_logs.py`: paginated, filterable audit endpoint.
- Create `backend/tests/test_document_deletion.py`: deletion orchestration and route tests.
- Create `backend/tests/test_deletion_logs_api.py`: audit service/API tests.
- Modify `backend/app/schemas/documents.py`: hard-delete response contract.
- Modify `backend/app/services/qdrant_service.py`: filtered point deletion.
- Modify `backend/app/services/supabase_service.py`: Storage removal, RPC call, failed-audit insert, audit listing.
- Modify `backend/app/services/document_service.py`: cross-provider deletion coordinator.
- Modify `backend/app/api/documents.py`: `DELETE` route and safe error mapping.
- Modify `backend/app/main.py`: register deletion-log router.
- Modify existing backend tests for provider adapters and migration contract.
- Create `frontend/src/types/deletionLogs.ts`: audit response types.
- Create `frontend/src/api/deletionLogs.ts`: list API and safe errors.
- Create `frontend/src/components/DeleteDocumentDialog.tsx`: accessible confirmation.
- Create `frontend/src/components/DeletionLogsPanel.tsx`: filters, pagination, expandable rows.
- Modify `frontend/src/types/documents.ts`, `frontend/src/api/documents.ts`: delete response/client.
- Modify `frontend/src/components/DocumentCard.tsx`: delete action and dialog.
- Modify `frontend/src/pages/DocumentListPage.tsx`: deletion state and stale-refresh protection.
- Modify `frontend/src/pages/AgentLogsPage.tsx`: mount independent deletion-log panel.
- Modify `frontend/src/styles.css`: destructive controls, dialog, audit list, responsive rules.

### Task 1: Add the Transactional Deletion Schema

**Files:**
- Create: `backend/app/db/migrations/002_document_hard_delete.sql`
- Test: `backend/tests/test_document_delete_migration.py`

- [ ] **Step 1: Write the failing migration contract tests**

```python
from pathlib import Path


SQL = Path("app/db/migrations/002_document_hard_delete.sql").read_text(
    encoding="utf-8"
).lower()


def test_migration_creates_independent_deletion_logs_table():
    assert "create table if not exists deletion_logs" in SQL
    assert "status text not null" in SQL
    assert "check (status in ('success', 'failed'))" in SQL
    assert "references documents" not in SQL.split(
        "create table if not exists deletion_logs", 1
    )[1].split(");", 1)[0]


def test_rpc_deletes_shared_runs_and_inserts_success_audit_atomically():
    assert "create or replace function delete_owned_document_cascade" in SQL
    assert "selected_document_ids @> jsonb_build_array" in SQL
    assert "delete from agent_runs" in SQL
    assert "delete from documents" in SQL
    assert "insert into deletion_logs" in SQL
    assert "'success'" in SQL
```

- [ ] **Step 2: Run tests and confirm the missing migration failure**

Run: `cd backend; pytest tests/test_document_delete_migration.py -v`

Expected: FAIL because `002_document_hard_delete.sql` does not exist.

- [ ] **Step 3: Create the migration**

Implement:

```sql
create table if not exists deletion_logs (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  document_id uuid not null,
  file_name text,
  status text not null check (status in ('success', 'failed')),
  failure_stage text,
  error_message text,
  deleted_storage_file boolean not null default false,
  deleted_qdrant_points boolean not null default false,
  deleted_chunks integer not null default 0,
  deleted_entities integer not null default 0,
  deleted_relationships integer not null default 0,
  deleted_agent_runs integer not null default 0,
  deleted_agent_steps integer not null default 0,
  deleted_chat_messages integer not null default 0,
  deleted_chat_sessions integer not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_deletion_logs_user_created_at
  on deletion_logs(user_id, created_at desc);
create index if not exists idx_deletion_logs_user_status
  on deletion_logs(user_id, status);
```

Add `delete_owned_document_cascade(p_document_id uuid, p_user_id text)` as a
`security definer` PL/pgSQL function with an explicit empty `search_path`. It
must:

1. Lock the owned document and return no rows if absent.
2. Capture counts for chunks, entities, relationships, affected runs, their
   steps, related messages, and candidate sessions.
3. Collect affected runs using
   `selected_document_ids @> jsonb_build_array(p_document_id::text)`.
4. Delete assistant messages by `metadata->>'agent_run_id'`.
5. Delete user messages by
   `(metadata->'document_ids') @> jsonb_build_array(p_document_id::text)`.
6. Delete affected runs, relationships, and the document.
7. Delete candidate sessions only when no messages or runs remain.
8. Insert the `success` row into `deletion_logs` in the same transaction.
9. Return the audit row fields and relational deletion counts. The service adds
   `deleted=true` to the public response. Because the RPC runs only after both
   external deletions succeed, its success audit stores both external booleans
   as true.

Use temporary arrays declared in PL/pgSQL rather than a temporary table:

```sql
v_run_ids uuid[] := '{}';
v_session_ids uuid[] := '{}';
```

Revoke public execution and grant only the service role:

```sql
revoke all on function delete_owned_document_cascade(uuid, text) from public;
grant execute on function delete_owned_document_cascade(uuid, text) to service_role;
```

- [ ] **Step 4: Run the migration contract tests**

Run: `cd backend; pytest tests/test_document_delete_migration.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/db/migrations/002_document_hard_delete.sql backend/tests/test_document_delete_migration.py
git commit -m "feat: add transactional document deletion migration"
```

### Task 2: Add Supabase and Qdrant Deletion Adapters

**Files:**
- Modify: `backend/app/services/supabase_service.py`
- Modify: `backend/app/services/qdrant_service.py`
- Modify: `backend/tests/test_supabase_service.py`
- Modify: `backend/tests/test_qdrant_service.py`

- [ ] **Step 1: Write failing adapter tests**

Add tests asserting:

```python
def test_delete_document_vectors_filters_user_and_document(monkeypatch):
    client = Mock()
    settings = _settings()
    settings.single_user_id = "single_user"
    monkeypatch.setattr(qdrant_service, "get_settings", lambda: settings)
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    qdrant_service.delete_document_vectors("document-id")

    selector = client.delete.call_args.kwargs["points_selector"]
    assert [(item.key, item.match.value) for item in selector.filter.must] == [
        ("user_id", "single_user"),
        ("document_id", "document-id"),
    ]


def test_remove_document_file_uses_exact_storage_path(monkeypatch):
    bucket = SimpleNamespace(remove=Mock(return_value=[]))
    client = SimpleNamespace(storage=SimpleNamespace(from_=Mock(return_value=bucket)))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())

    supabase_service.remove_document_file("documents/single_user/id/file.txt")

    bucket.remove.assert_called_once_with(["documents/single_user/id/file.txt"])
```

Also test safe exception mapping, RPC parameters, failed-audit row shape, and
newest-first filtered pagination.

- [ ] **Step 2: Run focused tests and verify failure**

Run:
`cd backend; pytest tests/test_supabase_service.py tests/test_qdrant_service.py -q`

Expected: FAIL because the deletion helpers do not exist.

- [ ] **Step 3: Implement Qdrant filtered deletion**

Import `FilterSelector` and add:

```python
class QdrantDeleteError(RuntimeError):
    """Raised when document vector deletion fails safely."""


def delete_document_vectors(document_id: UUID | str) -> bool:
    settings = get_settings()
    try:
        qdrant_settings = settings.require_qdrant_settings()
        selector = FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=settings.single_user_id),
                    ),
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(document_id)),
                    ),
                ]
            )
        )
        get_qdrant_client().delete(
            collection_name=qdrant_settings["collection"],
            points_selector=selector,
            wait=True,
        )
    except Exception as exc:
        logger.error("Qdrant document vector deletion failed for document_id=%s", document_id)
        raise QdrantDeleteError("Document vector deletion failed.") from exc
    return True
```

- [ ] **Step 4: Implement Supabase helpers**

Add:

```python
def remove_document_file(storage_path: str) -> bool:
    try:
        get_supabase_client().storage.from_(
            _get_configured_storage_bucket()
        ).remove([storage_path])
    except Exception as exc:
        _raise_supabase_query_error("storage document delete", exc)
    return True


def delete_owned_document_cascade(document_id: str, user_id: str) -> dict | None:
    try:
        response = get_supabase_client().rpc(
            "delete_owned_document_cascade",
            {"p_document_id": document_id, "p_user_id": user_id},
        ).execute()
    except Exception as exc:
        _raise_supabase_query_error("document cascade delete", exc)
    rows = _response_rows(response)
    return rows[0] if rows else None


def insert_deletion_log(row: dict[str, Any]) -> dict:
    try:
        response = get_supabase_client().table("deletion_logs").insert(row).execute()
    except Exception as exc:
        _raise_supabase_query_error("deletion log insert", exc)
    return _first_response_row("deletion log insert", response)


def list_deletion_logs(
    user_id: str, *, status: str | None, limit: int, offset: int
) -> list[dict]:
    query = (
        get_supabase_client()
        .table("deletion_logs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if status is not None:
        query = query.eq("status", status)
    try:
        return _response_rows(query.execute())
    except Exception as exc:
        _raise_supabase_query_error("deletion log list", exc)
```

- [ ] **Step 5: Run focused adapter tests**

Run:
`cd backend; pytest tests/test_supabase_service.py tests/test_qdrant_service.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/supabase_service.py backend/app/services/qdrant_service.py backend/tests/test_supabase_service.py backend/tests/test_qdrant_service.py
git commit -m "feat: add document deletion provider adapters"
```

### Task 3: Implement Backend Deletion Orchestration

**Files:**
- Modify: `backend/app/schemas/documents.py`
- Modify: `backend/app/services/document_service.py`
- Modify: `backend/app/api/documents.py`
- Create: `backend/tests/test_document_deletion.py`

- [ ] **Step 1: Write failing service and route tests**

Cover:

```python
def test_delete_document_orders_external_cleanup_before_rpc(monkeypatch):
    calls = []
    monkeypatch.setattr(document_service, "get_settings", _settings)
    monkeypatch.setattr(
        document_service, "get_document_metadata",
        Mock(return_value=_metadata_row()),
    )
    monkeypatch.setattr(
        document_service, "delete_document_vectors",
        Mock(side_effect=lambda _id: calls.append("qdrant") or True),
    )
    monkeypatch.setattr(
        document_service, "remove_document_file",
        Mock(side_effect=lambda _path: calls.append("storage") or True),
    )
    monkeypatch.setattr(
        document_service, "delete_owned_document_cascade",
        Mock(side_effect=lambda _id, _user: calls.append("rpc") or SUCCESS_ROW),
    )

    response = document_service.delete_document(DOCUMENT_ID)

    assert calls == ["qdrant", "storage", "rpc"]
    assert response.deleted is True
```

Add tests for ownership-safe 404, Qdrant failure audit, Storage failure audit,
RPC failure audit, failed-audit write preserving the original error, full count
mapping, UUID route validation, safe 500 bodies, retry after either external
system has already deleted its target, and concurrent duplicate requests where
the later request receives the ownership-safe 404.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `cd backend; pytest tests/test_document_deletion.py -v`

Expected: FAIL because contracts and service function do not exist.

- [ ] **Step 3: Add the response contract**

```python
class DocumentDeleteResponse(BaseModel):
    document_id: UUID
    deleted: bool
    deleted_agent_runs: int
    deleted_agent_steps: int
    deleted_chat_messages: int
    deleted_chat_sessions: int
    deleted_chunks: int
    deleted_entities: int
    deleted_relationships: int
    deleted_qdrant_points: bool
    deleted_storage_file: bool
```

- [ ] **Step 4: Implement deletion orchestration**

Add safe errors:

```python
class DocumentDeletionError(DocumentServiceError):
    """Raised when permanent deletion does not fully complete."""


SAFE_DOCUMENT_DELETION_MESSAGE = "Document deletion failed. Please try again."
```

Implement `delete_document(document_id)` with a progress dictionary initialized
to false/zero. Ownership lookup failure raises `DocumentNotFoundError` without
calling external systems. After preflight:

```python
stage = "qdrant"
delete_document_vectors(document_id)
progress["deleted_qdrant_points"] = True

stage = "storage"
remove_document_file(row["storage_path"])
progress["deleted_storage_file"] = True

stage = "database"
deleted = delete_owned_document_cascade(
    str(document_id), settings.single_user_id
)
if deleted is None:
    raise DocumentNotFoundError("Document not found.")
return DocumentDeleteResponse.model_validate({
    "document_id": str(document_id),
    "deleted": True,
    **deleted,
})
```

Wrap dependency failures after preflight. Attempt:

```python
insert_deletion_log({
    "user_id": settings.single_user_id,
    "document_id": str(document_id),
    "file_name": row["file_name"],
    "status": "failed",
    "failure_stage": stage,
    "error_message": SAFE_DOCUMENT_DELETION_MESSAGE,
    **progress,
})
```

Log an audit insertion failure safely, then raise `DocumentDeletionError` from
the original exception. Do not include provider details in the public error or
audit row.

- [ ] **Step 5: Add the DELETE route**

```python
@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    status_code=status.HTTP_200_OK,
)
def delete_document(document_id: UUID) -> DocumentDeleteResponse:
    try:
        return document_service.delete_document(document_id)
    except document_service.DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except document_service.DocumentDeletionError as exc:
        raise HTTPException(
            status_code=500,
            detail=document_service.SAFE_DOCUMENT_DELETION_MESSAGE,
        ) from exc
```

- [ ] **Step 6: Run deletion tests**

Run:
`cd backend; pytest tests/test_document_deletion.py tests/test_document_api.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/schemas/documents.py backend/app/services/document_service.py backend/app/api/documents.py backend/tests/test_document_deletion.py
git commit -m "feat: add permanent document deletion endpoint"
```

### Task 4: Add the Deletion Logs Backend API

**Files:**
- Create: `backend/app/schemas/deletion_logs.py`
- Create: `backend/app/services/deletion_log_service.py`
- Create: `backend/app/api/deletion_logs.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_deletion_logs_api.py`

- [ ] **Step 1: Write failing schema, service, and API tests**

Test `GET /api/deletion-logs?status=failed&limit=20&offset=0`, validation for
invalid status/limit/offset, user scoping, newest-first passthrough, safe 500,
and the exact public response shape.

```python
assert response.json() == {
    "logs": [{
        "id": str(LOG_ID),
        "document_id": str(DOCUMENT_ID),
        "file_name": "contract.pdf",
        "status": "failed",
        "failure_stage": "storage",
        "error_message": "Document deletion failed. Please try again.",
        "deleted_storage_file": False,
        "deleted_qdrant_points": True,
        "deleted_chunks": 0,
        "deleted_entities": 0,
        "deleted_relationships": 0,
        "deleted_agent_runs": 0,
        "deleted_agent_steps": 0,
        "deleted_chat_messages": 0,
        "deleted_chat_sessions": 0,
        "created_at": "2026-06-14T10:00:00Z",
    }],
    "limit": 20,
    "offset": 0,
    "has_more": False,
}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd backend; pytest tests/test_deletion_logs_api.py -v`

Expected: FAIL because the deletion-log API modules do not exist.

- [ ] **Step 3: Add typed schemas**

Define `DeletionLogStatus = Literal["success", "failed"]`,
`DeletionLogResponse`, and:

```python
class DeletionLogListResponse(BaseModel):
    logs: list[DeletionLogResponse]
    limit: int
    offset: int
    has_more: bool
```

- [ ] **Step 4: Implement service pagination**

Fetch `limit + 1` rows to derive `has_more`, expose only `limit`, and map rows
through Pydantic. Wrap Supabase failures in:

```python
class DeletionLogServiceError(RuntimeError):
    public_message = "Deletion logs are temporarily unavailable."
```

- [ ] **Step 5: Add and register the route**

```python
@router.get("", response_model=DeletionLogListResponse)
def list_deletion_logs(
    status: Literal["success", "failed"] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DeletionLogListResponse:
    try:
        return deletion_log_service.list_deletion_logs(
            status=status, limit=limit, offset=offset
        )
    except deletion_log_service.DeletionLogServiceError as exc:
        raise HTTPException(status_code=500, detail=exc.public_message) from exc
```

Register at `/api/deletion-logs` in `create_app()`.

- [ ] **Step 6: Run API tests**

Run:
`cd backend; pytest tests/test_deletion_logs_api.py tests/test_document_deletion.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/schemas/deletion_logs.py backend/app/services/deletion_log_service.py backend/app/api/deletion_logs.py backend/app/main.py backend/tests/test_deletion_logs_api.py
git commit -m "feat: expose persistent deletion audit logs"
```

### Task 5: Add the Frontend Delete API and Confirmation Dialog

**Files:**
- Modify: `frontend/src/types/documents.ts`
- Modify: `frontend/src/api/documents.ts`
- Create: `frontend/src/components/DeleteDocumentDialog.tsx`
- Modify: `frontend/src/components/DocumentCard.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add frontend deletion contracts**

```typescript
export type DocumentDeleteResponse = {
  document_id: string;
  deleted: true;
  deleted_agent_runs: number;
  deleted_agent_steps: number;
  deleted_chat_messages: number;
  deleted_chat_sessions: number;
  deleted_chunks: number;
  deleted_entities: number;
  deleted_relationships: number;
  deleted_qdrant_points: boolean;
  deleted_storage_file: boolean;
};
```

Add:

```typescript
export function deleteDocument(
  documentId: string,
): Promise<DocumentDeleteResponse> {
  return apiClient
    .delete<DocumentDeleteResponse>(
      `/api/documents/${encodeURIComponent(documentId)}`,
    )
    .then((response) => response.data);
}
```

- [ ] **Step 2: Create the accessible dialog**

Implement a native `<dialog>` opened with `showModal()` and closed with
`close()`. Accept:

```typescript
type DeleteDocumentDialogProps = {
  document: DocumentListItem;
  isDeleting: boolean;
  errorMessage: string | null;
  onConfirm: () => Promise<void>;
  onClose: () => void;
};
```

The visible warning must name file, vectors, chunks/graph data, affected agent
runs/steps, related chat messages, and newly empty sessions. Disable both
duplicate destructive submission and backdrop dismissal while deleting. Invoke
the promise as `void onConfirm().catch(() => undefined)` so a handled page-level
failure keeps the dialog open without creating an unhandled rejection.

- [ ] **Step 3: Wire the card action**

Extend `DocumentCardProps`:

```typescript
type DocumentCardProps = {
  document: DocumentListItem;
  isDeleting: boolean;
  deleteError: string | null;
  onDelete: (document: DocumentListItem) => Promise<void>;
};
```

Add a visible `Delete` button and keep the dialog mounted only while selected.
The card must not remove itself; it delegates successful list mutation to the
page.

- [ ] **Step 4: Add focused styles**

Add `.document-card__delete`, `.delete-document-dialog`, warning/error/action
classes, visible focus styles, disabled states, and narrow-screen stacking.
Use the existing color variables and typography.

- [ ] **Step 5: Run the frontend build**

Run: `cd frontend; npm run build`

Expected: TypeScript and Vite build succeed.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/types/documents.ts frontend/src/api/documents.ts frontend/src/components/DeleteDocumentDialog.tsx frontend/src/components/DocumentCard.tsx frontend/src/styles.css
git commit -m "feat: add confirmed document delete control"
```

### Task 6: Make Document List Deletion Race-Safe

**Files:**
- Modify: `frontend/src/pages/DocumentListPage.tsx`

- [ ] **Step 1: Add deletion state**

```typescript
const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);
const [deleteErrors, setDeleteErrors] = useState<Record<string, string>>({});
const deletedDocumentIdsRef = useRef(new Set<string>());
```

- [ ] **Step 2: Filter stale list responses**

For both initial load and refresh:

```typescript
setDocuments(
  response.documents.filter(
    (document) => !deletedDocumentIdsRef.current.has(document.id),
  ),
);
```

- [ ] **Step 3: Implement confirmed deletion**

```typescript
async function handleDelete(document: DocumentListItem) {
  if (deletingDocumentId !== null) return;
  setDeletingDocumentId(document.id);
  setDeleteErrors((current) => ({ ...current, [document.id]: "" }));
  try {
    const response = await deleteDocument(document.id);
    if (!response.deleted || response.document_id !== document.id) {
      throw new Error("Unexpected document deletion response.");
    }
    deletedDocumentIdsRef.current.add(document.id);
    setDocuments((current) => current.filter((item) => item.id !== document.id));
  } catch (error) {
    setDeleteErrors((current) => ({
      ...current,
      [document.id]: getDocumentApiErrorMessage(error),
    }));
    throw error;
  } finally {
    setDeletingDocumentId(null);
  }
}
```

Pass per-card state and handler into `DocumentCard`.

- [ ] **Step 4: Build and manually inspect list behavior**

Run: `cd frontend; npm run build`

Expected: PASS. With backend running, verify cancel makes no request, failure
keeps the card, success removes it after response, and refresh cannot restore
the deleted ID.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/pages/DocumentListPage.tsx
git commit -m "feat: synchronize document list after deletion"
```

### Task 7: Add Deletion Logs to the Existing Logs UI

**Files:**
- Create: `frontend/src/types/deletionLogs.ts`
- Create: `frontend/src/api/deletionLogs.ts`
- Create: `frontend/src/components/DeletionLogsPanel.tsx`
- Modify: `frontend/src/pages/AgentLogsPage.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add typed API contracts**

```typescript
export type DeletionLogStatus = "success" | "failed";
export type DeletionLog = {
  id: string;
  document_id: string;
  file_name: string | null;
  status: DeletionLogStatus;
  failure_stage: string | null;
  error_message: string | null;
  deleted_storage_file: boolean;
  deleted_qdrant_points: boolean;
  deleted_chunks: number;
  deleted_entities: number;
  deleted_relationships: number;
  deleted_agent_runs: number;
  deleted_agent_steps: number;
  deleted_chat_messages: number;
  deleted_chat_sessions: number;
  created_at: string;
};
export type DeletionLogListResponse = {
  logs: DeletionLog[];
  limit: number;
  offset: number;
  has_more: boolean;
};
```

Implement `listDeletionLogs({status, limit, offset})`, omitting `status` for
All and reusing the safe Axios-error pattern.

- [ ] **Step 2: Build the independent panel**

`DeletionLogsPanel` owns its own:

```typescript
type Filter = "all" | DeletionLogStatus;
const PAGE_SIZE = 20;
```

On filter change reset offset to zero. Render All/Successful/Failed buttons,
loading/error/empty states, `<details>` rows, and Previous/Next controls.
Display timestamp, filename fallback, document ID, status, failure stage/error,
booleans, and all count fields.

- [ ] **Step 3: Mount below agent logs**

Append `<DeletionLogsPanel />` after the existing agent-log state/viewer blocks.
Do not share `loadState`, request IDs, errors, or route params with agent logs.

- [ ] **Step 4: Add responsive and accessible styling**

Add status chips, filter group, audit cards, count grid, pagination, focus
states, and narrow-width single-column layout.

- [ ] **Step 5: Build frontend**

Run: `cd frontend; npm run build`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/types/deletionLogs.ts frontend/src/api/deletionLogs.ts frontend/src/components/DeletionLogsPanel.tsx frontend/src/pages/AgentLogsPage.tsx frontend/src/styles.css
git commit -m "feat: show deletion audit history in logs"
```

### Task 8: Full Verification and Disposable End-to-End Test

**Files:**
- Modify only if verification exposes defects.

- [ ] **Step 1: Run the complete backend suite**

Run: `cd backend; pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run the production frontend build**

Run: `cd frontend; npm run build`

Expected: TypeScript check and Vite build pass.

- [ ] **Step 3: Apply the migration to the configured development Supabase**

Apply `backend/app/db/migrations/002_document_hard_delete.sql` using the
project’s established Supabase SQL workflow. Verify the table and function
exist before destructive testing.

- [ ] **Step 4: Start backend and frontend**

Use free ports if `8000` or `5173` are reserved:

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

```powershell
cd frontend
$env:VITE_API_BASE_URL='http://127.0.0.1:8001'
npm run dev -- --host 127.0.0.1 --port 5174
```

- [ ] **Step 5: Verify with a disposable document only**

Upload a new disposable file, create a chat/agent run selecting it (including a
run that also selects another disposable document when feasible), then delete
the first document through the UI.

Verify:

```text
GET /api/documents no longer includes the deleted ID
GET /api/documents/{id} returns 404
Supabase Storage exact object is absent
Qdrant filter user_id + document_id returns no points
chunks/entities/relationships are absent
every run selecting the document and all its steps are absent
related messages are absent
unrelated data remains
empty sessions are removed; non-empty sessions remain
GET /api/deletion-logs contains the success row
```

Create a controlled disposable failure (for example, temporarily use an invalid
Qdrant collection in a test environment), restore configuration immediately,
and verify a safe failed audit row with `failure_stage="qdrant"` and no provider
details.

- [ ] **Step 6: Inspect the UI**

Verify keyboard operation, dialog focus, cancel behavior, duplicate-submit
prevention, card retention on failure, audit filters, expanded counts,
pagination, and narrow viewport layout.

- [ ] **Step 7: Check final diff and commit verification repairs**

Run:

```powershell
git status --short
git diff --check
```

If verification required fixes:

```powershell
git add backend/app backend/tests frontend/src
git commit -m "fix: complete document deletion verification"
```
