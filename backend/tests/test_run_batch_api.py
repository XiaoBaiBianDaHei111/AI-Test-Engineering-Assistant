"""run_batch API-branch integration tests (P9-006, AC-9-04/06/08/09)."""

import json

import httpx
import pytest
from sqlalchemy import select

from app.execution.api_runner import ApiRunner
from app.models import APITestCase, Evidence, FailureAnalysis, TestRun
from app.services.assets.test_run_service import cancel_run, create_run, rerun_case, run_batch

CONFIG = {"base_url": "http://localhost:8001", "qa_mode": "none", "browser": "chromium", "headless": True}


def _api_handler(request):
    if request.url.path == "/api/demo-api/login":
        body = json.loads(request.content or b"{}")
        if "password" not in body:
            return httpx.Response(400, json={"message": "参数缺失"})
        if body.get("username") != "testuser" or body.get("password") != "Test@1234":
            return httpx.Response(401, json={"message": "用户名或密码错误"})
        return httpx.Response(200, json={"token": "demo-token", "user": {"username": "testuser"}})
    if request.url.path == "/api/demo-api/tasks":
        if "bearer" not in request.headers.get("authorization", "").lower():
            return httpx.Response(401, json={"message": "未授权"})
        return httpx.Response(200, json={"tasks": []})
    return httpx.Response(404, json={"message": "not found"})


def _connect_error_handler(request):
    raise httpx.ConnectError("Connection refused")


def _api_case(db_session, project_id, assertions, url="/api/demo-api/login", body=None):
    api_case = APITestCase(
        project_id=project_id, name="登录", method="POST", url=url,
        body=body or {"username": "testuser", "password": "Test@1234"},
        assertions=assertions, status="active",
    )
    db_session.add(api_case)
    db_session.flush()
    return api_case


def _runner(handler=_api_handler):
    return ApiRunner(transport=httpx.MockTransport(handler))


def _read_run(session_factory, run_id):
    s = session_factory()
    try:
        from sqlalchemy.orm import selectinload
        return s.scalar(select(TestRun).options(selectinload(TestRun.run_cases)).where(TestRun.id == run_id))
    finally:
        s.close()


def test_api_case_passed_with_steps_and_evidence(session_factory, db_session, sample_project):
    api_case = _api_case(db_session, sample_project["id"], [
        {"type": "status", "expected": 200},
        {"type": "json_field", "path": "token", "expected": "non_empty"},
    ])
    run = create_run(db_session, sample_project["id"], [], CONFIG, api_case_ids=[api_case.id])
    run_batch(session_factory, run.id, api_runner=_runner())

    run_case = _read_run(session_factory, run.id).run_cases[0]
    assert run_case.kind == "api"
    assert run_case.status == "passed"

    s = session_factory()
    try:
        from app.services.assets.test_run_service import get_case_detail
        detail = get_case_detail(s, run_case.id)
        # steps: send + 2 assertions
        assert len(detail.step_results) == 3
        ev = s.scalar(select(Evidence).where(Evidence.run_case_id == run_case.id, Evidence.kind == "network"))
        assert ev is not None
    finally:
        s.close()


@pytest.mark.real
def test_api_status_failure_analyzed_by_llm(require_llm_key, session_factory, db_session, sample_project):
    api_case = _api_case(db_session, sample_project["id"], [{"type": "status", "expected": 201}])
    run = create_run(db_session, sample_project["id"], [], CONFIG, api_case_ids=[api_case.id])
    run_batch(session_factory, run.id, api_runner=_runner())

    run_case = _read_run(session_factory, run.id).run_cases[0]
    assert run_case.status == "failed"
    s = session_factory()
    try:
        fa = s.scalar(select(FailureAnalysis).where(FailureAnalysis.run_case_id == run_case.id))
        assert fa is not None
        assert fa.decision_source == "llm"
    finally:
        s.close()


def test_api_connection_error_rule_env_issue(session_factory, db_session, sample_project):
    api_case = _api_case(db_session, sample_project["id"], [{"type": "status", "expected": 200}])
    run = create_run(db_session, sample_project["id"], [], CONFIG, api_case_ids=[api_case.id])
    run_batch(session_factory, run.id, api_runner=_runner(_connect_error_handler))

    run_case = _read_run(session_factory, run.id).run_cases[0]
    assert run_case.status == "failed"
    s = session_factory()
    try:
        fa = s.scalar(select(FailureAnalysis).where(FailureAnalysis.run_case_id == run_case.id))
        assert fa.category == "ENV_ISSUE"
        assert fa.decision_source == "rule"
    finally:
        s.close()


def _noop_analyze(monkeypatch):
    # The API-branch tests below only assert run/case status; the failure-analysis
    # side effect is irrelevant here, so neutralize it to stay offline (P013).
    monkeypatch.setattr(
        "app.services.analysis.failure_analyzer.analyze_failure",
        lambda db, run_case_id, provider=None: None,
    )


def test_api_rerun(monkeypatch, session_factory, db_session, sample_project):
    _noop_analyze(monkeypatch)
    api_case = _api_case(db_session, sample_project["id"], [{"type": "status", "expected": 201}])
    run = create_run(db_session, sample_project["id"], [], CONFIG, api_case_ids=[api_case.id])
    run_batch(session_factory, run.id, api_runner=_runner())
    run_case_id = _read_run(session_factory, run.id).run_cases[0].id

    # rerun with a passing expectation
    api_case.assertions = [{"type": "status", "expected": 200}]
    db_session.commit()
    detail = rerun_case(db_session, run_case_id, api_runner=_runner())
    assert detail.status == "passed"


def test_api_deleted_case_blocked(monkeypatch, session_factory, db_session, sample_project):
    _noop_analyze(monkeypatch)
    api_case = _api_case(db_session, sample_project["id"], [{"type": "status", "expected": 200}])
    run = create_run(db_session, sample_project["id"], [], CONFIG, api_case_ids=[api_case.id])
    db_session.delete(api_case)
    db_session.commit()
    run_batch(session_factory, run.id, api_runner=_runner())
    run_case = _read_run(session_factory, run.id).run_cases[0]
    assert run_case.status == "blocked"


def test_api_cancel(session_factory, db_session, sample_project):
    api_case = _api_case(db_session, sample_project["id"], [{"type": "status", "expected": 200}])
    run = create_run(db_session, sample_project["id"], [], CONFIG, api_case_ids=[api_case.id])
    cancel_run(db_session, run.id)
    run_batch(session_factory, run.id, api_runner=_runner())
    run = _read_run(session_factory, run.id)
    assert run.status == "cancelled"
    assert run.run_cases[0].status == "skipped"
