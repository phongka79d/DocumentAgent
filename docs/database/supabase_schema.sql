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
  error_code text,
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

create table if not exists document_summaries (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  summary_type text not null constraint document_summaries_summary_type_check
    check (summary_type in ('section', 'document')),
  heading text,
  section_path jsonb not null default '[]'::jsonb,
  content text not null,
  source_chunk_ids jsonb not null default '[]'::jsonb,
  model text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists document_relations (
  id uuid primary key default gen_random_uuid(),
  source_document_id uuid not null references documents(id) on delete cascade,
  target_document_id uuid not null references documents(id) on delete cascade,
  relation_type text not null constraint document_relations_relation_type_check
    check (relation_type in ('same_topic', 'supports', 'contradicts', 'references')),
  description text not null,
  evidence_chunk_ids jsonb not null default '[]'::jsonb,
  confidence double precision not null constraint document_relations_confidence_check
    check (confidence >= 0 and confidence <= 1),
  model text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint document_relations_no_self_check
    check (source_document_id <> target_document_id),
  constraint document_relations_canonical_pair_check
    check (source_document_id < target_document_id),
  constraint document_relations_pair_type_unique
    unique (source_document_id, target_document_id, relation_type)
);

create table if not exists workflow_runs (
  id uuid primary key default gen_random_uuid(),
  workflow_type text not null constraint workflow_runs_workflow_type_check
    check (workflow_type in ('ingestion', 'query')),
  entity_id text,
  status text not null default 'running' constraint workflow_runs_status_check
    check (status in ('running', 'completed', 'failed')),
  trace jsonb not null default '[]'::jsonb,
  error_code text,
  error_message text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  duration_ms integer,
  created_at timestamptz not null default now()
);

create index idx_documents_status on documents(status);
create index idx_documents_created_at on documents(created_at desc);
create unique index idx_documents_file_hash on documents(file_hash);
create index idx_document_chunks_document_id on document_chunks(document_id);
create unique index idx_document_chunks_doc_index on document_chunks(document_id, chunk_index);
create index idx_document_chunks_qdrant_point_id on document_chunks(qdrant_point_id);
create index idx_messages_created_at on messages(created_at desc);
create unique index if not exists idx_document_summaries_document_unique
  on document_summaries(document_id)
  where summary_type = 'document';
create unique index if not exists idx_document_summaries_section_unique
  on document_summaries(document_id, section_path)
  where summary_type = 'section';
create index if not exists idx_document_summaries_document_id
  on document_summaries(document_id);
create index if not exists idx_document_summaries_summary_type
  on document_summaries(summary_type);
create index if not exists idx_document_relations_source_document_id
  on document_relations(source_document_id);
create index if not exists idx_document_relations_target_document_id
  on document_relations(target_document_id);
create index if not exists idx_document_chunks_keyword_fts
  on document_chunks
  using gin (to_tsvector('simple', coalesce(heading, '') || ' ' || content));
create index if not exists idx_workflow_runs_created_at
  on workflow_runs(created_at desc);
create index if not exists idx_workflow_runs_workflow_type
  on workflow_runs(workflow_type);
create index if not exists idx_workflow_runs_status
  on workflow_runs(status);

create or replace function search_document_chunks_keyword(
  query_text text,
  result_limit integer default 40,
  document_ids uuid[] default null,
  mime_types text[] default null,
  filter_heading text default null,
  filter_section_path text[] default null,
  filter_page_start integer default null,
  filter_page_end integer default null
)
returns table (
  chunk_id uuid,
  document_id uuid,
  file_name text,
  chunk_index integer,
  content text,
  heading text,
  section_path jsonb,
  page_start integer,
  page_end integer,
  chunk_type text,
  token_count integer,
  keyword_score double precision
)
language sql
stable
as $$
  with keyword_query as (
    select websearch_to_tsquery('simple', query_text) as tsquery
  )
  select
    dc.id as chunk_id,
    dc.document_id,
    documents.file_name,
    dc.chunk_index,
    dc.content,
    dc.heading,
    coalesce(dc.section_path, '[]'::jsonb) as section_path,
    dc.page_start,
    dc.page_end,
    dc.chunk_type,
    dc.token_count,
    ts_rank_cd(
      to_tsvector('simple', coalesce(dc.heading, '') || ' ' || dc.content),
      keyword_query.tsquery
    ) as keyword_score
  from document_chunks dc
  join documents on documents.id = dc.document_id
  cross join keyword_query
  where to_tsvector('simple', coalesce(dc.heading, '') || ' ' || dc.content)
    @@ keyword_query.tsquery
    and (document_ids is null or dc.document_id = any(document_ids))
    and (mime_types is null or documents.mime_type = any(mime_types))
    and (
      filter_heading is null
      or to_tsvector('simple', coalesce(dc.heading, ''))
        @@ plainto_tsquery('simple', filter_heading)
    )
    and (
      filter_section_path is null
      or coalesce(dc.section_path, '[]'::jsonb)
        @> to_jsonb(filter_section_path)
    )
    -- Page overlap semantics: dc.page_start <= page_end and dc.page_end >= page_start.
    and (filter_page_end is null or dc.page_start <= filter_page_end)
    and (filter_page_start is null or dc.page_end >= filter_page_start)
  order by keyword_score desc, document_id asc, chunk_index asc
  limit result_limit;
$$;
