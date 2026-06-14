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
        r"create\s+table\s+(?:if\s+not\s+exists\s+)?deletion_logs\s*\((.*?)\)\s*;",
        sql,
        re.DOTALL,
    )
    assert match, "deletion_logs table must exist"
    return match.group(1)


def deletion_function_sql(sql: str) -> str:
    match = re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"delete_owned_document_cascade\s*\(\s*"
        r"p_document_id\s+uuid\s*,\s*p_user_id\s+text\s*\)"
        r".*?\$\$;(?:\s|$)",
        sql,
        re.DOTALL,
    )
    assert match, "delete_owned_document_cascade(uuid, text) must exist"
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


def test_deletion_logs_has_required_indexes() -> None:
    sql = migration_sql()

    assert re.search(
        r"create\s+index.*on\s+deletion_logs\s*\(\s*user_id\s*,\s*created_at\s*\)",
        sql,
        re.DOTALL,
    )
    assert re.search(
        r"create\s+index.*on\s+deletion_logs\s*\(\s*user_id\s*,\s*status\s*\)",
        sql,
        re.DOTALL,
    )


def test_delete_function_uses_safe_security_definer_contract() -> None:
    function_sql = deletion_function_sql(migration_sql())

    assert "security definer" in function_sql
    assert re.search(r"set\s+search_path\s*=\s*pg_catalog(?:\s|$)", function_sql)
    assert "for update" in function_sql
    assert "revoke execute on function delete_owned_document_cascade" in migration_sql()
    assert "grant execute on function delete_owned_document_cascade" in migration_sql()
    assert "to service_role" in migration_sql()


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
