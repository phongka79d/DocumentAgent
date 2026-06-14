import re
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "app"
    / "db"
    / "migrations"
    / "002_document_hard_delete.sql"
)


def migration_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8").lower()


def deletion_logs_table_sql(sql: str) -> str:
    match = re.search(
        r"create\s+table\s+(?:if\s+not\s+exists\s+)?"
        r"public\.deletion_logs\s*\((.*?)\)\s*;",
        sql,
        re.DOTALL,
    )
    assert match, "deletion_logs table must exist"
    return match.group(1)


def deletion_function_sql(sql: str) -> str:
    match = re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"public\.delete_owned_document_cascade\s*\(\s*"
        r"p_document_id\s+uuid\s*,\s*p_user_id\s+text\s*\)"
        r".*?\$\$;(?:\s|$)",
        sql,
        re.DOTALL,
    )
    assert match, "delete_owned_document_cascade(uuid, text) must exist"
    return match.group(0)


def create_agent_run_function_sql(sql: str) -> str:
    match = re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"public\.create_owned_agent_run\s*\(\s*"
        r"p_session_id\s+uuid\s*,\s*p_user_id\s+text\s*,\s*"
        r"p_question\s+text\s*,\s*p_selected_document_ids\s+text\[\]\s*\)"
        r".*?\$\$;(?:\s|$)",
        sql,
        re.DOTALL,
    )
    assert match, "create_owned_agent_run(uuid, text, text, text[]) must exist"
    return match.group(0)


def insert_user_message_function_sql(sql: str) -> str:
    match = re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"public\.insert_user_chat_message_for_documents\s*\(\s*"
        r"p_session_id\s+uuid\s*,\s*p_user_id\s+text\s*,\s*"
        r"p_content\s+text\s*,\s*p_document_ids\s+text\[\]\s*\)"
        r".*?\$\$;(?:\s|$)",
        sql,
        re.DOTALL,
    )
    assert match, "insert_user_chat_message_for_documents(uuid, text, text, text[]) must exist"
    return match.group(0)


def test_deletion_logs_is_independent_and_constrains_status() -> None:
    table_sql = deletion_logs_table_sql(migration_sql())

    assert re.search(
        r"status\s+text\s+not\s+null\s+check\s*"
        r"\(\s*status\s+in\s*\(\s*'success'\s*,\s*'failed'\s*\)\s*\)",
        table_sql,
    )
    assert "references documents" not in table_sql
    assert "references agent_runs" not in table_sql
    assert "on delete cascade" not in table_sql


def test_migration_allows_temporary_deleting_document_status() -> None:
    sql = migration_sql()

    assert "drop constraint if exists documents_status_check" in sql
    assert "add constraint documents_status_check" in sql
    assert "'deleting'" in sql


def test_deletion_logs_constrains_all_deleted_counts_to_nonnegative() -> None:
    table_sql = deletion_logs_table_sql(migration_sql())

    for column in (
        "deleted_chunks",
        "deleted_entities",
        "deleted_relationships",
        "deleted_agent_runs",
        "deleted_agent_steps",
        "deleted_chat_messages",
        "deleted_chat_sessions",
    ):
        assert re.search(
            rf"{column}\s+integer\s+not\s+null\s+default\s+0\s+"
            rf"check\s*\(\s*{column}\s*>=\s*0\s*\)",
            table_sql,
        ), f"{column} must have a nonnegative CHECK constraint"


def test_deletion_logs_has_required_indexes() -> None:
    sql = migration_sql()

    assert re.search(
        r"create\s+index.*on\s+public\.deletion_logs\s*"
        r"\(\s*user_id\s*,\s*created_at\s+desc\s*\)",
        sql,
        re.DOTALL,
    )
    assert re.search(
        r"create\s+index.*on\s+public\.deletion_logs\s*"
        r"\(\s*user_id\s*,\s*status\s*\)",
        sql,
        re.DOTALL,
    )


def test_delete_function_uses_safe_security_definer_contract() -> None:
    sql = migration_sql()
    function_sql = deletion_function_sql(sql)

    assert "security definer" in function_sql
    assert re.search(r"set\s+search_path\s*=\s*pg_catalog(?:\s|$)", function_sql)
    assert "for update" in function_sql
    assert "pg_advisory_xact_lock" in function_sql
    assert "create or replace function public.delete_owned_document_cascade" in sql
    for role in ("public", "anon", "authenticated"):
        assert re.search(
            rf"revoke\s+execute\s+on\s+function\s+"
            rf"public\.delete_owned_document_cascade\s*\(\s*uuid\s*,\s*text\s*\)"
            rf"\s+from\s+{role}\s*;",
            sql,
        )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+"
        r"public\.delete_owned_document_cascade\s*\(\s*uuid\s*,\s*text\s*\)"
        r"\s+to\s+service_role\s*;",
        sql,
    )


def test_deletion_logs_is_service_role_only_without_frontend_policies() -> None:
    sql = migration_sql()

    assert "alter table public.deletion_logs enable row level security;" in sql
    for role in ("anon", "authenticated"):
        assert re.search(
            rf"revoke\s+all\s+privileges\s+on\s+table\s+"
            rf"public\.deletion_logs\s+from\s+{role}\s*;",
            sql,
        )
    assert re.search(
        r"grant\s+select\s*,\s*insert\s+on\s+table\s+"
        r"public\.deletion_logs\s+to\s+service_role\s*;",
        sql,
    )
    assert not re.search(
        r"create\s+policy\b.*\bon\s+public\.deletion_logs\b",
        sql,
        re.DOTALL,
    )


def test_delete_function_collects_all_runs_by_json_containment() -> None:
    function_sql = deletion_function_sql(migration_sql())

    assert "selected_document_ids" in function_sql
    assert re.search(
        r"selected_document_ids\s*@>\s*jsonb_build_array\s*\(\s*p_document_id::text\s*\)",
        function_sql,
    )


def test_delete_function_removes_runs_messages_and_document_data() -> None:
    function_sql = deletion_function_sql(migration_sql())

    for statement in (
        "delete from public.chat_messages",
        "delete from public.agent_runs",
        "delete from public.document_relationships",
        "delete from public.documents",
        "delete from public.chat_sessions",
    ):
        assert statement in function_sql

    assert "metadata ->> 'agent_run_id'" in function_sql
    assert "metadata -> 'document_ids'" in function_sql


def test_delete_function_inserts_atomic_success_log() -> None:
    function_sql = deletion_function_sql(migration_sql())

    assert "insert into public.deletion_logs" in function_sql
    assert "'success'" in function_sql
    assert "deleted_storage_file" in function_sql
    assert "deleted_qdrant_points" in function_sql


def test_create_agent_run_function_validates_documents_under_same_lock() -> None:
    sql = migration_sql()
    function_sql = create_agent_run_function_sql(sql)

    assert "security definer" in function_sql
    assert re.search(r"set\s+search_path\s*=\s*pg_catalog(?:\s|$)", function_sql)
    assert "pg_advisory_xact_lock" in function_sql
    assert "p_selected_document_ids" in function_sql
    assert "raise exception 'selected document not found.'" in function_sql
    assert "insert into public.agent_runs" in function_sql

    for role in ("public", "anon", "authenticated"):
        assert re.search(
            rf"revoke\s+execute\s+on\s+function\s+"
            rf"public\.create_owned_agent_run\s*\("
            rf"\s*uuid\s*,\s*text\s*,\s*text\s*,\s*text\[\]\s*\)"
            rf"\s+from\s+{role}\s*;",
            sql,
        )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+"
        r"public\.create_owned_agent_run\s*\("
        r"\s*uuid\s*,\s*text\s*,\s*text\s*,\s*text\[\]\s*\)"
        r"\s+to\s+service_role\s*;",
        sql,
    )


def test_user_chat_message_function_validates_documents_under_same_lock() -> None:
    sql = migration_sql()
    function_sql = insert_user_message_function_sql(sql)

    assert "security definer" in function_sql
    assert re.search(r"set\s+search_path\s*=\s*pg_catalog(?:\s|$)", function_sql)
    assert "pg_advisory_xact_lock" in function_sql
    assert "p_document_ids" in function_sql
    assert "raise exception 'selected document not found.'" in function_sql
    assert "insert into public.chat_messages" in function_sql
    assert "jsonb_build_object('document_ids'" in function_sql

    for role in ("public", "anon", "authenticated"):
        assert re.search(
            rf"revoke\s+execute\s+on\s+function\s+"
            rf"public\.insert_user_chat_message_for_documents\s*\("
            rf"\s*uuid\s*,\s*text\s*,\s*text\s*,\s*text\[\]\s*\)"
            rf"\s+from\s+{role}\s*;",
            sql,
        )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+"
        r"public\.insert_user_chat_message_for_documents\s*\("
        r"\s*uuid\s*,\s*text\s*,\s*text\s*,\s*text\[\]\s*\)"
        r"\s+to\s+service_role\s*;",
        sql,
    )
