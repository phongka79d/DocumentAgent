create table if not exists public.deletion_logs (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  document_id uuid not null,
  file_name text,
  status text not null check (status in ('success', 'failed')),
  failure_stage text,
  error_message text,
  deleted_storage_file boolean not null default false,
  deleted_qdrant_points boolean not null default false,
  deleted_chunks integer not null default 0 check (deleted_chunks >= 0),
  deleted_entities integer not null default 0 check (deleted_entities >= 0),
  deleted_relationships integer not null default 0 check (deleted_relationships >= 0),
  deleted_agent_runs integer not null default 0 check (deleted_agent_runs >= 0),
  deleted_agent_steps integer not null default 0 check (deleted_agent_steps >= 0),
  deleted_chat_messages integer not null default 0 check (deleted_chat_messages >= 0),
  deleted_chat_sessions integer not null default 0 check (deleted_chat_sessions >= 0),
  created_at timestamptz not null default now()
);

create index if not exists idx_deletion_logs_user_created_at
  on public.deletion_logs(user_id, created_at desc);
create index if not exists idx_deletion_logs_user_status
  on public.deletion_logs(user_id, status);

alter table public.deletion_logs enable row level security;
revoke all privileges on table public.deletion_logs from anon;
revoke all privileges on table public.deletion_logs from authenticated;
grant select, insert on table public.deletion_logs to service_role;

create or replace function public.delete_owned_document_cascade(
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
  perform pg_advisory_xact_lock(hashtextextended(p_document_id::text, 0));

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

revoke execute on function public.delete_owned_document_cascade(uuid, text) from public;
revoke execute on function public.delete_owned_document_cascade(uuid, text) from anon;
revoke execute on function public.delete_owned_document_cascade(uuid, text) from authenticated;
grant execute on function public.delete_owned_document_cascade(uuid, text) to service_role;

create or replace function public.lock_owned_document_for_indexing(
  p_document_id uuid,
  p_user_id text
)
returns table (
  id uuid,
  user_id text,
  status text
)
language plpgsql
security definer
set search_path = pg_catalog
as $$
begin
  perform pg_advisory_xact_lock(hashtextextended(p_document_id::text, 0));

  return query
  select d.id, d.user_id, d.status
    from public.documents as d
   where d.id = p_document_id
     and d.user_id = p_user_id
     and d.status = 'ready'
   for update;
end;
$$;

revoke execute on function public.lock_owned_document_for_indexing(uuid, text) from public;
revoke execute on function public.lock_owned_document_for_indexing(uuid, text) from anon;
revoke execute on function public.lock_owned_document_for_indexing(uuid, text) from authenticated;
grant execute on function public.lock_owned_document_for_indexing(uuid, text) to service_role;

create or replace function public.insert_user_chat_message_for_documents(
  p_session_id uuid,
  p_user_id text,
  p_content text,
  p_document_ids text[]
)
returns table (
  id uuid,
  session_id uuid,
  user_id text,
  role text,
  content text,
  created_at timestamptz,
  metadata jsonb
)
language plpgsql
security definer
set search_path = pg_catalog
as $$
declare
  v_document_id text;
  v_owned_document_count integer := 0;
begin
  if p_document_ids is null or cardinality(p_document_ids) = 0 then
    raise exception 'selected document not found.';
  end if;

  for v_document_id in
    select distinct selected_document_id
      from unnest(p_document_ids) as selected_document_id
     order by selected_document_id
  loop
    perform pg_advisory_xact_lock(hashtextextended(v_document_id, 0));
  end loop;

  select count(*)::integer
    into v_owned_document_count
    from public.documents as d
   where d.user_id = p_user_id
     and d.id::text = any(p_document_ids);

  if v_owned_document_count <> cardinality(p_document_ids) then
    raise exception 'selected document not found.';
  end if;

  if not exists (
    select 1
      from public.chat_sessions as cs
     where cs.id = p_session_id
       and cs.user_id = p_user_id
  ) then
    raise exception 'chat session not found.';
  end if;

  return query
  insert into public.chat_messages (
    session_id,
    user_id,
    role,
    content,
    metadata
  )
  values (
    p_session_id,
    p_user_id,
    'user',
    p_content,
    jsonb_build_object('document_ids', p_document_ids)
  )
  returning
    chat_messages.id,
    chat_messages.session_id,
    chat_messages.user_id,
    chat_messages.role,
    chat_messages.content,
    chat_messages.created_at,
    chat_messages.metadata;
end;
$$;

revoke execute on function public.insert_user_chat_message_for_documents(uuid, text, text, text[]) from public;
revoke execute on function public.insert_user_chat_message_for_documents(uuid, text, text, text[]) from anon;
revoke execute on function public.insert_user_chat_message_for_documents(uuid, text, text, text[]) from authenticated;
grant execute on function public.insert_user_chat_message_for_documents(uuid, text, text, text[]) to service_role;

create or replace function public.create_owned_agent_run(
  p_session_id uuid,
  p_user_id text,
  p_question text,
  p_selected_document_ids text[]
)
returns table (
  id uuid,
  session_id uuid,
  user_id text,
  question text,
  selected_document_ids jsonb,
  status text,
  final_answer text,
  confidence double precision,
  created_at timestamptz,
  updated_at timestamptz,
  error_message text
)
language plpgsql
security definer
set search_path = pg_catalog
as $$
declare
  v_document_id text;
  v_owned_document_count integer := 0;
begin
  if p_selected_document_ids is null or cardinality(p_selected_document_ids) = 0 then
    raise exception 'selected document not found.';
  end if;

  for v_document_id in
    select distinct selected_document_id
      from unnest(p_selected_document_ids) as selected_document_id
     order by selected_document_id
  loop
    perform pg_advisory_xact_lock(hashtextextended(v_document_id, 0));
  end loop;

  select count(*)::integer
    into v_owned_document_count
    from public.documents as d
   where d.user_id = p_user_id
     and d.id::text = any(p_selected_document_ids);

  if v_owned_document_count <> cardinality(p_selected_document_ids) then
    raise exception 'selected document not found.';
  end if;

  if p_session_id is not null and not exists (
    select 1
      from public.chat_sessions as cs
     where cs.id = p_session_id
       and cs.user_id = p_user_id
  ) then
    raise exception 'chat session not found.';
  end if;

  return query
  insert into public.agent_runs (
    session_id,
    user_id,
    question,
    selected_document_ids,
    status,
    final_answer,
    confidence,
    error_message
  )
  values (
    p_session_id,
    p_user_id,
    p_question,
    to_jsonb(p_selected_document_ids),
    'running',
    null,
    null,
    null
  )
  returning
    agent_runs.id,
    agent_runs.session_id,
    agent_runs.user_id,
    agent_runs.question,
    agent_runs.selected_document_ids,
    agent_runs.status,
    agent_runs.final_answer,
    agent_runs.confidence,
    agent_runs.created_at,
    agent_runs.updated_at,
    agent_runs.error_message;
end;
$$;

revoke execute on function public.create_owned_agent_run(uuid, text, text, text[]) from public;
revoke execute on function public.create_owned_agent_run(uuid, text, text, text[]) from anon;
revoke execute on function public.create_owned_agent_run(uuid, text, text, text[]) from authenticated;
grant execute on function public.create_owned_agent_run(uuid, text, text, text[]) to service_role;
