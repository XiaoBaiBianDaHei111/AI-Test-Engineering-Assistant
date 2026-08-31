"""Startup schema-compatibility check tests (P011 hotfix, P1-2)."""

from sqlalchemy import text

from app.core.schema_check import build_guidance, check_schema


def test_check_schema_fresh_db_passes(db_engine):
    assert check_schema(db_engine) == []


def test_check_schema_detects_missing_column(db_engine):
    # Simulate a pre-Phase-9 DB that lacks test_run_cases.kind (the ALTER-less gap).
    with db_engine.connect() as conn:
        conn.execute(text("ALTER TABLE test_run_cases DROP COLUMN kind"))
        conn.commit()
    missing = check_schema(db_engine)
    assert "column test_run_cases.kind" in missing


def test_check_schema_detects_missing_failure_excerpt(db_engine):
    # P014 B-2 hotfix: a pre-hotfix DB lacks ai_audit_logs.failure_excerpt.
    with db_engine.connect() as conn:
        conn.execute(text("ALTER TABLE ai_audit_logs DROP COLUMN failure_excerpt"))
        conn.commit()
    missing = check_schema(db_engine)
    assert "column ai_audit_logs.failure_excerpt" in missing


def test_guidance_mentions_rebuild():
    guidance = build_guidance(["column test_run_cases.kind"])
    assert "test_run_cases.kind" in guidance
    assert "重建数据库" in guidance
