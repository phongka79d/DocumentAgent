create table documents (
  id uuid primary key default gen_random_uuid(),
  title text,
  file_name text not null,
  mime_type text,
  file_size bigint,
  file_hash text,
  storage_path text not null,
  status text default 'uploaded',
  total_pages int,
  total_chunks int default 0,
  parser_name text,
  parser_version text,
  chunking_strategy text,
  chunking_version text,
  embedding_model text,
  embedding_dimension int,
  qdrant_collection text,
  indexed_at timestamptz,
  error_message text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references documents(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  content_hash text,
  token_count int,
  chunk_type text,
  heading text,
  section_path jsonb,
  page_start int,
  page_end int,
  token_start int,
  token_end int,
  qdrant_point_id text,
  metadata jsonb,
  created_at timestamptz default now()
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  question text not null,
  answer text not null,
  sources jsonb,
  metadata jsonb,
  created_at timestamptz default now()
);

create index idx_documents_status on documents(status);
create index idx_documents_created_at on documents(created_at desc);
create unique index idx_documents_file_hash on documents(file_hash);
create index idx_document_chunks_document_id on document_chunks(document_id);
create unique index idx_document_chunks_doc_index on document_chunks(document_id, chunk_index);
create index idx_document_chunks_qdrant_point_id on document_chunks(qdrant_point_id);
create index idx_messages_created_at on messages(created_at desc);
