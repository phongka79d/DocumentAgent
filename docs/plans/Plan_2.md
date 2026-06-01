# Plan 2 - Database Schema and Supabase Setup

## 1. Goal

Create the Supabase PostgreSQL schema, document the Supabase Storage bucket assumptions, and add a backend-only Supabase service client that can verify database and storage connectivity.

The goal is testable when the SQL migration creates all required tables and the backend can connect to Supabase using `SUPABASE_SERVICE_ROLE_KEY` without exposing it to the frontend.

## 2. Why This Plan Exists

Document upload, chunk persistence, GraphRAG, chat history, and agent logs all depend on a stable database schema. This plan creates those durable tables before any feature writes data to them.

## 3. Scope

- Create Supabase schema SQL for all MVP tables.
- Create indexes needed by document ownership, document lookup, chunk lookup, graph lookup, chat sessions, and agent logs.
- Add backend Supabase service client initialization.
- Add a connection test helper for database and storage access.
- Document the `documents` storage bucket assumption.
- Add development commands for applying the schema manually in Supabase SQL editor or CLI.
- Preserve the no-auth MVP decision by using `SINGLE_USER_ID`.

## 4. Out of Scope

- Do not implement document upload endpoints.
- Do not upload files to storage yet.
- Do not parse or chunk documents.
- Do not generate embeddings.
- Do not connect to Qdrant.
- Do not implement frontend pages.
- Do not add user auth policies, JWT verification, or multi-user account tables.

## 5. Dependencies

- Plan 1 must be completed.
- Requires a Supabase project with PostgreSQL and Storage enabled.

## 6. Required Files and Folders

```text
backend/app/services/__init__.py
- Marks the services package.

backend/app/services/supabase_service.py
- Creates the backend-only Supabase client and helper functions for connection checks.

backend/app/db/__init__.py
- Marks the database package.

backend/app/db/migrations/001_initial_schema.sql
- Contains all required table creation SQL and indexes.

backend/app/api/health.py
- Extend only if adding an optional Supabase connectivity check; keep the existing basic health check working without Supabase.

backend/tests/test_supabase_service.py
- Unit tests for config validation and service helper behavior using mocks.

backend/requirements.txt
- Add Supabase client dependencies.

backend/.env.example
- Add Supabase backend-only variables.
```

## 7. Data Model / Schema Changes

Create `backend/app/db/migrations/001_initial_schema.sql` with these tables.

```sql
create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  file_name text not null,
  file_type text not null,
  storage_path text not null,
  status text not null default 'uploaded',
  chunk_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  error_message text
);
```

Allowed document statuses:

```text
uploaded
processing
ready
failed
```

```sql
create table if not exists document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  user_id text not null,
  chunk_index integer not null,
  content text not null,
  page_number integer,
  section_title text,
  token_count integer not null default 0,
  qdrant_point_id text,
  created_at timestamptz not null default now()
);
```

```sql
create table if not exists document_entities (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  chunk_id uuid references document_chunks(id) on delete cascade,
  user_id text not null,
  entity_name text not null,
  entity_type text not null,
  description text,
  created_at timestamptz not null default now()
);
```

```sql
create table if not exists document_relationships (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  source_type text not null,
  source_id text not null,
  target_type text not null,
  target_id text not null,
  relationship_type text not null,
  weight double precision not null default 1.0,
  description text,
  created_at timestamptz not null default now()
);
```

```sql
create table if not exists chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  title text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

```sql
create table if not exists chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references chat_sessions(id) on delete cascade,
  user_id text not null,
  role text not null,
  content text not null,
  created_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);
```

```sql
create table if not exists agent_runs (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references chat_sessions(id) on delete set null,
  user_id text not null,
  question text not null,
  selected_document_ids jsonb not null default '[]'::jsonb,
  status text not null default 'running',
  final_answer text,
  confidence double precision,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  error_message text
);
```

```sql
create table if not exists agent_steps (
  id uuid primary key default gen_random_uuid(),
  agent_run_id uuid not null references agent_runs(id) on delete cascade,
  step_name text not null,
  agent_name text not null,
  input jsonb not null default '{}'::jsonb,
  output jsonb not null default '{}'::jsonb,
  status text not null,
  created_at timestamptz not null default now(),
  error_message text
);
```

Required indexes:

```sql
create index if not exists idx_documents_user_id on documents(user_id);
create index if not exists idx_documents_status on documents(status);
create index if not exists idx_document_chunks_document_id on document_chunks(document_id);
create index if not exists idx_document_chunks_user_id on document_chunks(user_id);
create unique index if not exists idx_document_chunks_document_chunk_index on document_chunks(document_id, chunk_index);
create index if not exists idx_document_entities_document_id on document_entities(document_id);
create index if not exists idx_document_entities_user_name on document_entities(user_id, entity_name);
create index if not exists idx_document_relationships_document_id on document_relationships(document_id);
create index if not exists idx_document_relationships_source on document_relationships(source_type, source_id);
create index if not exists idx_document_relationships_target on document_relationships(target_type, target_id);
create index if not exists idx_chat_sessions_user_id on chat_sessions(user_id);
create index if not exists idx_chat_messages_session_id on chat_messages(session_id);
create index if not exists idx_agent_runs_user_id on agent_runs(user_id);
create index if not exists idx_agent_steps_agent_run_id on agent_steps(agent_run_id);
```

## 8. API Design

No new public API endpoints in this plan.

Optional internal function only:

```text
Function: check_supabase_connection()
Input: none
Output:
{
  "database": true,
  "storage": true
}
Errors:
- Raises SupabaseConnectionError with a clear message.
```

If health is extended, use a query flag so the basic health check remains independent:

```text
GET /api/health?include_dependencies=true
```

## 9. Implementation Steps

1. Add Supabase dependency to `backend/requirements.txt`.
2. Add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET` to `backend/.env.example`.
3. Extend `Settings` in `backend/app/core/config.py` with the Supabase variables.
4. Create `backend/app/db/migrations/001_initial_schema.sql` with all tables and indexes from this plan.
5. Create `backend/app/services/supabase_service.py`.
6. In `supabase_service.py`, initialize the Supabase client from `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
7. Add `get_supabase_client()` that returns a singleton client.
8. Add `check_supabase_connection()` that performs a lightweight query against `documents` and checks the configured storage bucket.
9. Add a custom `SupabaseConnectionError` so callers receive clear failures.
10. Write tests that mock the Supabase client and verify missing config produces a clear error.
11. Apply the SQL migration in Supabase.
12. Verify the storage bucket named by `SUPABASE_STORAGE_BUCKET` exists; create it manually in Supabase if missing.

## 10. Configuration and Environment Variables

```text
SUPABASE_URL
- Purpose: Supabase project URL.
- Required: Yes for this plan's connection test.
- Example: https://example-project.supabase.co
- Scope: Backend-only.

SUPABASE_SERVICE_ROLE_KEY
- Purpose: Backend service-role key for database and storage operations.
- Required: Yes.
- Example: supabase-service-role-placeholder
- Scope: Backend-only. Never expose to frontend.

SUPABASE_STORAGE_BUCKET
- Purpose: Storage bucket for original uploaded files.
- Required: Yes.
- Example: documents
- Scope: Backend-only.

SINGLE_USER_ID
- Purpose: Fixed owner ID for all MVP rows.
- Required: Yes after Plan 1, default can remain single_user.
- Example: single_user
- Scope: Backend-only.
```

## 11. Required Tests

Unit tests:

```text
cd backend
pytest tests/test_supabase_service.py -v
```

Manual database checks:

```text
Open Supabase SQL editor.
Run backend/app/db/migrations/001_initial_schema.sql.
Confirm all 8 tables exist.
```

Manual storage check:

```text
Confirm a Supabase Storage bucket named documents exists.
Confirm it is not accessed from frontend code.
```

Optional backend check:

```text
cd backend
python -c "from app.services.supabase_service import check_supabase_connection; print(check_supabase_connection())"
```

## 12. Acceptance Criteria

- SQL migration creates `documents`, `document_chunks`, `document_entities`, `document_relationships`, `chat_sessions`, `chat_messages`, `agent_runs`, and `agent_steps`.
- Required indexes exist.
- `SUPABASE_SERVICE_ROLE_KEY` appears only in backend files and examples.
- Supabase service client can be initialized from backend settings.
- Connection test reports database and storage availability.
- No frontend file references Supabase service-role secrets.
- No Auth/JWT schema or logic is added.

## 13. Failure Handling

- Missing `SUPABASE_URL` must produce a clear backend configuration error.
- Missing `SUPABASE_SERVICE_ROLE_KEY` must produce a clear backend configuration error.
- Missing storage bucket must be reported as a setup failure, not silently ignored.
- Supabase query failure must include the operation name in the error message.
- Migration failure must be fixed before later plans proceed.

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

The report must also include whether the SQL migration was applied manually, by CLI, or only added to the repository.

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

- Confirm every table includes `user_id` where required.
- Confirm chunk rows cascade when a document is deleted.
- Confirm agent steps cascade when an agent run is deleted.
- Confirm frontend has no Supabase client initialized with private keys.
