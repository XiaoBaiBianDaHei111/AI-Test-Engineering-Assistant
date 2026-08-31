"""run_batch orchestration tests (P5/P6/P7/P8 + cancel cleanup). Real mode (P013).

MINOR-002: the driver is a test-local stub (not project mock infrastructure) and
``generate_script`` is monkeypatched so no real LLM / browser is exercised. All
failing cases use a locator-marker error so ``_maybe_analyze`` resolves via the
deterministic rule layer (zero LLM calls).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models import Evidence, FailureAnalysis, TestCase as _TestCase, TestReport, TestRun, TraceParse
from app.services.assets import evidence_service, test_run_service
from app.services.assets.test_run_service import (
    cancel_run,
    create_run,
    is_cancelled,
    rerun_case,
    run_batch,
)
from tests._stubs import StubDriver, make_script_generator, success_script

CONFIG = {"base_url": "http://localhost:8001", "qa_mode": "none", "browser": "chromium", "headless": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _approved_case(client, project_id, title="登录成功"):
    case = client.post(
        f"/api/projects/{project_id}/test-cases",
        json={"title": title, "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    return case


def _read_run(session_factory, run_id) -> TestRun:
    s = session_factory()
    try:
        return s.scalar(
            select(TestRun).options(selectinload(TestRun.run_cases)).where(TestRun.id == run_id)
        )
    finally:
        s.close()


def _read_case_status(session_factory, test_case_id) -> str:
    s = session_factory()
    try:
        return s.get(_TestCase, test_case_id).status
    finally:
        s.close()


def _analysis(session_factory, run_case_id):
    s = session_factory()
    try:
        return s.scalar(select(FailureAnalysis).where(FailureAnalysis.run_case_id == run_case_id))
    finally:
        s.close()


def _evidence_rows(session_factory, run_id=None, run_case_id=None) -> list[Evidence]:
    s = session_factory()
    try:
        q = select(Evidence)
        if run_case_id is not None:
            q = q.where(Evidence.run_case_id == run_case_id)
        elif run_id is not None:
            q = q.where(Evidence.run_id == run_id)
        return list(s.scalars(q.order_by(Evidence.kind, Evidence.id)))
    finally:
        s.close()


def _case_detail(session_factory, run_case_id):
    s = session_factory()
    try:
        return test_run_service.get_case_detail(s, run_case_id)
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Status closure / cancel / rerun
# ---------------------------------------------------------------------------

def test_run_batch_completed_and_passed_to_executed(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())

    run = _read_run(session_factory, run.id)
    assert run.status == "completed"
    assert run.run_cases[0].status == "passed"
    assert _read_case_status(session_factory, case["id"]) == "executed"


def test_run_batch_failed_keeps_approved(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver(fail_step=2))

    run = _read_run(session_factory, run.id)
    assert run.status == "failed"
    run_case = run.run_cases[0]
    assert run_case.status == "failed"
    assert "get_by_test_id" in run_case.error
    assert _read_case_status(session_factory, case["id"]) == "approved"  # stays approved


def test_run_batch_blocked_does_not_interrupt(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr(
        "app.services.assets.test_run_service.generate_script",
        make_script_generator(fail_title="用例一"),
    )
    case1 = _approved_case(client, sample_project["id"], title="用例一")
    case2 = _approved_case(client, sample_project["id"], title="用例二")
    run = create_run(db_session, sample_project["id"], [case1["id"], case2["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())

    run = _read_run(session_factory, run.id)
    statuses = {c.case_label: c.status for c in run.run_cases}
    assert any(s == "blocked" for s in statuses.values())  # 用例一 blocked
    assert any(s == "passed" for s in statuses.values())   # 用例二 passed
    assert run.status == "failed"  # not all passed


def test_run_batch_deterministic_failure(monkeypatch, session_factory, db_session, sample_project, client):
    """AC-5-03: repeated failing executions yield identical step results and stay approved."""
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    sequences = []
    for _ in range(2):
        run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
        run_batch(session_factory, run.id, driver=StubDriver(fail_step=2))
        run = _read_run(session_factory, run.id)
        assert run.status == "failed"
        assert run.run_cases[0].status == "failed"
        detail = _case_detail(session_factory, run.run_cases[0].id)
        sequences.append([(s.step_number, s.status) for s in detail.step_results])
        assert _read_case_status(session_factory, case["id"]) == "approved"  # re-selectable

    assert sequences[0] == sequences[1]
    assert sequences[0][-1][1] == "failed"  # identical failing step at the tail


def test_run_batch_cancel(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    cancel_run(db_session, run.id)  # mark skipped + set flag
    run_batch(session_factory, run.id, driver=StubDriver())

    run = _read_run(session_factory, run.id)
    assert run.status == "cancelled"
    assert run.run_cases[0].status == "skipped"


def test_rerun_reuses_edited_script(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver(fail_step=2))
    run_case_id = _read_run(session_factory, run.id).run_cases[0].id

    # rerun with a passing driver (same script file is reused)
    rerun_case(db_session, run_case_id, driver=StubDriver())
    detail = _case_detail(session_factory, run_case_id)
    assert detail.status == "passed"


def test_rerun_non_failed_rejected(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())  # passed
    run_case_id = _read_run(session_factory, run.id).run_cases[0].id
    with pytest.raises(AppError) as exc:
        rerun_case(db_session, run_case_id, driver=StubDriver())
    assert exc.value.code == "CONFLICT"


# ---------------------------------------------------------------------------
# Auto-trigger failure analysis (rule layer, zero LLM)
# ---------------------------------------------------------------------------

def test_failed_case_auto_analyzed_by_rule(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver(fail_step=1))

    run_case = _read_run(session_factory, run.id).run_cases[0]
    assert run_case.status == "failed"
    analysis = _analysis(session_factory, run_case.id)
    assert analysis is not None
    assert analysis.category == "BROKEN_LOCATOR"
    assert analysis.decision_source == "rule"


def test_analysis_failure_does_not_block_run(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)

    def boom(*args, **kwargs):
        raise RuntimeError("analysis exploded")

    monkeypatch.setattr("app.services.analysis.failure_analyzer.analyze_failure", boom)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver(fail_step=1))

    run = _read_run(session_factory, run.id)
    assert run.status == "failed"  # run still reaches a terminal state
    run_case = run.run_cases[0]
    assert run_case.status == "failed"
    assert _analysis(session_factory, run_case.id) is None  # no row written


def test_passed_case_has_no_analysis(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())

    run_case = _read_run(session_factory, run.id).run_cases[0]
    assert run_case.status == "passed"
    assert _analysis(session_factory, run_case.id) is None


# ---------------------------------------------------------------------------
# Evidence persistence
# ---------------------------------------------------------------------------

def test_run_batch_writes_evidence_rows(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())

    run = _read_run(session_factory, run.id)
    assert run.status == "completed"
    run_case = run.run_cases[0]
    rows = _evidence_rows(session_factory, run_case_id=run_case.id)
    kinds = sorted(r.kind for r in rows)
    assert kinds.count("screenshot") == 5
    assert "console" in kinds
    assert "network" in kinds
    assert "trace" in kinds
    assert len(rows) == 8


def test_failed_case_has_screenshot_and_trace(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver(fail_step=2))

    run = _read_run(session_factory, run.id)
    run_case = run.run_cases[0]
    assert run_case.status == "failed"
    rows = _evidence_rows(session_factory, run_case_id=run_case.id)
    screenshots = [r for r in rows if r.kind == "screenshot"]
    assert len(screenshots) >= 1  # AC-6-01
    assert any(r.kind == "trace" for r in rows)
    assert any(r.kind == "console" for r in rows)
    assert any(r.kind == "network" for r in rows)
    for r in rows:
        assert evidence_service.resolve_content_path(r).is_file()


def test_evidence_ids_populated(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())

    run_case = _read_run(session_factory, run.id).run_cases[0]
    rows = _evidence_rows(session_factory, run_case_id=run_case.id)
    assert len(run_case.evidence_ids) == len(rows)
    assert set(run_case.evidence_ids) == {r.id for r in rows}


def test_screenshot_ref_on_failed_step(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver(fail_step=2))

    run_case = _read_run(session_factory, run.id).run_cases[0]
    detail = _case_detail(session_factory, run_case.id)
    failed = [s for s in detail.step_results if s.status == "failed"]
    assert len(failed) == 1
    ref = failed[0].screenshot_ref
    assert ref is not None
    assert str(ref).isdigit()
    s = session_factory()
    try:
        ev = s.get(Evidence, int(ref))
        assert ev.kind == "screenshot"
        assert ev.run_case_id == run_case.id
    finally:
        s.close()


def test_run_level_log_exists(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())

    logs = [r for r in _evidence_rows(session_factory, run_id=run.id) if r.kind == "log"]
    assert len(logs) == 1
    assert logs[0].run_case_id is None
    assert logs[0].file_path.endswith(f"logs/run_{run.id}.log")


def test_trace_parse_auto_ingested(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())

    run_case = _read_run(session_factory, run.id).run_cases[0]
    traces = [r for r in _evidence_rows(session_factory, run_case_id=run_case.id) if r.kind == "trace"]
    assert len(traces) == 1
    s = session_factory()
    try:
        tp = s.scalar(select(TraceParse).where(TraceParse.evidence_id == traces[0].id))
        assert tp is not None
        assert len(tp.actions) >= 1
        assert len(tp.network) >= 1
        assert len(tp.console) >= 1
    finally:
        s.close()


def test_evidence_write_failure_does_not_block(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(evidence_service, "save_evidence", boom)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())

    run = _read_run(session_factory, run.id)
    assert run.status == "completed"
    assert run.run_cases[0].status == "passed"


# ---------------------------------------------------------------------------
# Auto-report generation (deterministic, no LLM)
# ---------------------------------------------------------------------------

def _report(session_factory, run_id):
    s = session_factory()
    try:
        return s.scalar(select(TestReport).where(TestReport.run_id == run_id))
    finally:
        s.close()


def test_completed_run_auto_generates_report(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())
    report = _report(session_factory, run.id)
    assert report is not None
    assert report.summary["passed"] == 1


def test_failed_run_auto_generates_report(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver(fail_step=1))
    report = _report(session_factory, run.id)
    assert report is not None
    assert report.summary["failed"] == 1


def test_report_generation_failure_does_not_block_run(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)

    def boom(*args, **kwargs):
        raise RuntimeError("report exploded")

    monkeypatch.setattr("app.services.assets.test_report_service.generate_report", boom)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())

    s = session_factory()
    try:
        refreshed = s.get(type(run), run.id)
        assert refreshed.status == "completed"
        assert _report(session_factory, run.id) is None  # no row written
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Cancel-flag cleanup
# ---------------------------------------------------------------------------

def test_cancel_flag_cleared_on_terminal(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    cancel_run(db_session, run.id)
    assert is_cancelled(run.id) is True
    run_batch(session_factory, run.id, driver=StubDriver())
    assert is_cancelled(run.id) is False  # terminal state cleared the flag


def test_normal_completion_leaves_flag_clear(monkeypatch, session_factory, db_session, sample_project, client):
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_batch(session_factory, run.id, driver=StubDriver())
    assert is_cancelled(run.id) is False
