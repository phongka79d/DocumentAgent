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

commit;

