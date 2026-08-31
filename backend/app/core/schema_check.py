"""Startup schema-compatibility check (P011 hotfix, P1-2 root fix).

``create_all`` only creates NEW tables — it never ALTERs existing ones. So a
development DB created before a later Phase (which added columns) silently misses
those columns and fails at runtime (e.g. ``POST /runs`` 500 on the missing
``test_run_cases.kind``). This check inspects the DB after ``create_all`` and
turns that "runtime 500" into a clear startup error with a migration pointer.

Fresh databases (all tables + columns created by ``create_all``) pass with zero
impact; ``SKIP_SCHEMA_CHECK=1`` is the escape hatch.
"""

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

# Tables added incrementally across Phases (must all exist).
REQUIRED_TABLES: tuple[str, ...] = (
    "projects",
    "requirements",
    "test_points",
    "test_cases",
    "test_case_steps",
    "ai_audit_logs",
    "generation_runs",
    "test_case_reviews",
    "test_runs",
    "test_run_cases",
    "test_step_results",
    "evidence",
    "trace_parses",
    "failure_analyses",
    "test_reports",
    "quality_summaries",
    "api_test_cases",
)

# Columns added to EXISTING tables in later Phases (the ALTER-less gap).
#
# ⚠️ RULE (P014 B-2 hotfix): ANY model change that adds a table/column MUST be
# synced here — otherwise an existing DB silently misses the column and fails at
# RUNTIME with a 500 (``create_all`` never ALTERs).
REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "test_run_cases": ("kind", "api_case_id"),  # Phase 9
    "ai_audit_logs": ("failure_excerpt",),       # P014 B-2
}


def check_schema(engine: Engine) -> list[str]:
    """Return a list of missing tables/columns (empty = compatible)."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing: list[str] = []

    for table in REQUIRED_TABLES:
        if table not in existing_tables:
            missing.append(f"table {table}")

    for table, columns in REQUIRED_COLUMNS.items():
        if table not in existing_tables:
            continue
        existing_columns = {c["name"] for c in inspector.get_columns(table)}
        for column in columns:
            if column not in existing_columns:
                missing.append(f"column {table}.{column}")

    return missing


def build_guidance(missing: list[str]) -> str:
    problems = ", ".join(missing)
    return (
        "数据库 schema 过期，缺少："
        + problems
        + "。请重建数据库（删旧库后重新启动，create_all 自动建表）："
        + "删旧库（*.db / docker compose down -v）后重新启动（create_all）并 seed；"
        + "或设置 SKIP_SCHEMA_CHECK=1 跳过（仅临时，不推荐）。"
    )
