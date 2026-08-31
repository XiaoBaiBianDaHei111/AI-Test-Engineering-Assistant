"""Failure context builder tests (P7-003, AC-7-09)."""

import json

from app.core.config import settings
from app.models import TestRunCase, TestStepResult
from app.services.analysis.failure_context import build_failure_context


def _run_case(db_session, error="Timeout waiting for get_by_test_id('login-btn')"):
    run_case = TestRunCase(run_id=1, test_case_id=1, case_label="TC-001 登录", status="failed", error=error)
    db_session.add(run_case)
    db_session.flush()
    db_session.add(TestStepResult(
        run_case_id=run_case.id, step_number=1, description="点击登录",
        status="failed", message=error, element_found=False,
    ))
    db_session.commit()
    return run_case


def test_build_failure_context_fields(db_session):
    run_case = _run_case(db_session)
    context = build_failure_context(db_session, run_case, "def run():\n    pass")
    assert context["error"].startswith("Timeout waiting")
    assert "failed_steps" in context
    assert "script_summary" in context
    assert context["evidence_summary"] == {
        "console_errors": [], "network_non_2xx": [], "screenshot_count": 0,
    }
    assert context["truncated"] is False


def test_build_failure_context_truncates(monkeypatch, db_session):
    monkeypatch.setattr(settings, "failure_context_max_chars", 300)
    run_case = _run_case(db_session)
    context = build_failure_context(db_session, run_case, "x" * 5000)
    assert context["truncated"] is True
    assert len(json.dumps(context, ensure_ascii=False)) < 300 + 500  # bounded


def test_build_failure_context_no_evidence_degrades(db_session):
    run_case = _run_case(db_session, error="blocked: script generation failed")
    context = build_failure_context(db_session, run_case, "")
    assert context["evidence_summary"]["screenshot_count"] == 0
    assert context["script_summary"] == ""
