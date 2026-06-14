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

create or replace function delete_owned_document_cascade(
  p_document_id uuid,
  p_user_id text
)
returns table (
  document_id uuid,
  file_name text,
  deleted boolean,
  deleted_storage_file boolean,
  deleted_qdrant_points boolean,
  deleted_chunks integer,
  deleted_entities integer,
  deleted_relationships integer,
  deleted_agent_runs integer,
  deleted_agent_steps integer,
  deleted_chat_messages integer,
  deleted_chat_sessions integer
)
language plpgsql
security definer
set search_path = pg_catalog
as $$
declare
  v_file_name text;
  v_affected_run_ids uuid[] := array[]::uuid[];
  v_affected_run_id_texts text[] := array[]::text[];
  v_candidate_session_ids uuid[] := array[]::uuid[];
  v_deleted_chunks integer := 0;
  v_deleted_entities integer := 0;
  v_deleted_relationships integer := 0;
  v_deleted_agent_runs integer := 0;
  v_deleted_agent_steps integer := 0;
  v_deleted_chat_messages integer := 0;
  v_deleted_chat_sessions integer := 0;
begin
  select d.file_name
    into v_file_name
    from public.documents as d
   where d.id = p_document_id
     and d.user_id = p_user_id
   for update;

  if not found then
    return;
  end if;

  select coalesce(array_agg(ar.id), array[]::uuid[])
    into v_affected_run_ids
    from public.agent_runs as ar
   where ar.user_id = p_user_id
     and ar.selected_document_ids @> jsonb_build_array(p_document_id::text);

  select coalesce(array_agg(run_id::text), array[]::text[])
    into v_affected_run_id_texts
    from unnest(v_affected_run_ids) as run_id;

  select count(*)::integer
    into v_deleted_chunks
    from public.document_chunks as dc
   where dc.document_id = p_document_id;

  select count(*)::integer
    into v_deleted_entities
    from public.document_entities as de
   where de.document_id = p_document_id;

  select count(*)::integer
    into v_deleted_relationships
    from public.document_relationships as dr
   where dr.document_id = p_document_id;

  select count(*)::integer
    into v_deleted_agent_steps
    from public.agent_steps as ast
   where ast.agent_run_id = any(v_affected_run_ids);

  select coalesce(array_agg(distinct candidate.session_id), array[]::uuid[])
    into v_candidate_session_ids
    from (
      select ar.session_id
        from public.agent_runs as ar
       where ar.id = any(v_affected_run_ids)
         and ar.session_id is not null
      union
      select cm.session_id
        from public.chat_messages as cm
       where cm.user_id = p_user_id
         and (
           (
             cm.role = 'assistant'
             and cm.metadata ->> 'agent_run_id' = any(v_affected_run_id_texts)
           )
           or (
             cm.role = 'user'
             and cm.metadata -> 'document_ids'
               @> jsonb_build_array(p_document_id::text)
           )
         )
    ) as candidate;

  delete from public.chat_messages as cm
   where cm.user_id = p_user_id
     and (
       (
         cm.role = 'assistant'
         and cm.metadata ->> 'agent_run_id' = any(v_affected_run_id_texts)
       )
       or (
         cm.role = 'user'
         and cm.metadata -> 'document_ids'
           @> jsonb_build_array(p_document_id::text)
       )
     );
  get diagnostics v_deleted_chat_messages = row_count;

  delete from public.agent_runs as ar
   where ar.user_id = p_user_id
     and ar.id = any(v_affected_run_ids);
  get diagnostics v_deleted_agent_runs = row_count;

  delete from public.document_relationships as dr
   where dr.document_id = p_document_id;
  get diagnostics v_deleted_relationships = row_count;

  delete from public.documents as d
   where d.id = p_document_id
     and d.user_id = p_user_id;

  delete from public.chat_sessions as cs
   where cs.user_id = p_user_id
     and cs.id = any(v_candidate_session_ids)
     and not exists (
       select 1
         from public.chat_messages as cm
        where cm.session_id = cs.id
     )
     and not exists (
       select 1
         from public.agent_runs as ar
        where ar.session_id = cs.id
     );
  get diagnostics v_deleted_chat_sessions = row_count;

  insert into public.deletion_logs (
    user_id,
    document_id,
    file_name,
    status,
    deleted_storage_file,
    deleted_qdrant_points,
    deleted_chunks,
    deleted_entities,
    deleted_relationships,
    deleted_agent_runs,
    deleted_agent_steps,
    deleted_chat_messages,
    deleted_chat_sessions
  )
  values (
    p_user_id,
    p_document_id,
    v_file_name,
    'success',
    true,
    true,
    v_deleted_chunks,
    v_deleted_entities,
    v_deleted_relationships,
    v_deleted_agent_runs,
    v_deleted_agent_steps,
    v_deleted_chat_messages,
    v_deleted_chat_sessions
  );

  return query
  select
    p_document_id,
    v_file_name,
    true,
    true,
    true,
    v_deleted_chunks,
    v_deleted_entities,
    v_deleted_relationships,
    v_deleted_agent_runs,
    v_deleted_agent_steps,
    v_deleted_chat_messages,
    v_deleted_chat_sessions;
end;
$$;

revoke execute on function delete_owned_document_cascade(uuid, text) from public;
grant execute on function delete_owned_document_cascade(uuid, text) to service_role;
