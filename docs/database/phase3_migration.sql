begin;

alter table documents
  add column if not exists error_code text;

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

create index if not exists idx_document_relations_source_document_id
  on document_relations(source_document_id);
create index if not exists idx_document_relations_target_document_id
  on document_relations(target_document_id);

create index if not exists idx_document_chunks_keyword_fts
  on document_chunks
  using gin (to_tsvector('simple', coalesce(heading, '') || ' ' || content));

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
    select
      websearch_to_tsquery('simple', query_text) as tsquery,
      phraseto_tsquery('simple', query_text) as phrase_tsquery,
      phraseto_tsquery('simple', replace(query_text, '-', ' ')) as hyphen_phrase_tsquery,
      to_tsquery('simple',
        btrim(regexp_replace(
          regexp_replace(replace(query_text, '-', ' '), '[^a-zA-Z0-9 ]', '', 'g'),
          ' +', ' | ', 'g'
        ), ' |')
      ) as or_tsquery
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
    greatest(
      ts_rank_cd(
        to_tsvector('simple', coalesce(dc.heading, '') || ' ' || dc.content),
        keyword_query.tsquery
      ),
      ts_rank_cd(
        to_tsvector('simple', coalesce(dc.heading, '') || ' ' || dc.content),
        keyword_query.or_tsquery
      )
    ) as keyword_score
  from document_chunks dc
  join documents on documents.id = dc.document_id
  cross join keyword_query
  where (
    to_tsvector('simple', coalesce(dc.heading, '') || ' ' || dc.content)
      @@ keyword_query.tsquery
    or to_tsvector('simple', coalesce(dc.heading, '') || ' ' || dc.content)
      @@ keyword_query.phrase_tsquery
    or to_tsvector('simple', coalesce(dc.heading, '') || ' ' || dc.content)
      @@ keyword_query.hyphen_phrase_tsquery
    or to_tsvector('simple', coalesce(dc.heading, '') || ' ' || dc.content)
      @@ keyword_query.or_tsquery
  )
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

commit;
