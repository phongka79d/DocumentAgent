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
