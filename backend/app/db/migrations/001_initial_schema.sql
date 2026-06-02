create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  file_name text not null,
  file_type text not null,
  storage_path text not null,
  status text not null default 'uploaded' check (status in ('uploaded', 'processing', 'ready', 'failed')),
  chunk_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  error_message text
);

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

create table if not exists chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  title text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references chat_sessions(id) on delete cascade,
  user_id text not null,
  role text not null,
  content text not null,
  created_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

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
