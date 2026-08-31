"""Failure analysis orchestrator tests (P7-005, AC-7-02/03/07/08). Real mode (P013)."""

import pytest

from app.core.exceptions import AppError
from app.models import FailureAnalysis
from app.services.analysis.failure_analyzer import (
    analyze_failure,
    confirm_analysis,
    get_analysis,
)
from app.services.assets.test_run_service import create_run

CONFIG = {"base_url": "http://localhost:8001", "qa_mode": "none", "browser": "chromium", "headless": True}
LOCATOR_ERROR = "Timeout 15000ms exceeded.\nwaiting for get_by_test_id(\"login-btn\")"
ASSERTION_ERROR = "Error: expect(received).toBe(expected)\n\nexpected: '首页'\nreceived: '登录'"
FAILURE_CATEGORIES = {"BROKEN_LOCATOR", "REAL_BUG", "FLAKY", "ENV_ISSUE"}


def _failed_run_case(db_session, sample_project, client, error=LOCATOR_ERROR):
    case = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "登录", "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_case = run.run_cases[0]
    run_case.status = "failed"
    run_case.error = error
    db_session.commit()
    return run_case


def test_rule_hit_locator(db_session, sample_project, client):
    # Rule layer resolves a locator timeout with zero LLM calls.
    run_case = _failed_run_case(db_session, sample_project, client)
    analysis = analyze_failure(db_session, run_case.id)
    assert analysis.category == "BROKEN_LOCATOR"
    assert analysis.decision_source == "rule"
    assert analysis.needs_human is False


@pytest.mark.real
def test_llm_path(require_llm_key, db_session, sample_project, client):
    run_case = _failed_run_case(db_session, sample_project, client, error=ASSERTION_ERROR)
    analysis = analyze_failure(db_session, run_case.id)
    assert analysis.category in FAILURE_CATEGORIES
    assert analysis.decision_source == "llm"


@pytest.mark.real
def test_upsert_overwrites(require_llm_key, db_session, sample_project, client):
    run_case = _failed_run_case(db_session, sample_project, client)
    first = analyze_failure(db_session, run_case.id)  # rule hit
    assert first.category == "BROKEN_LOCATOR"
    # re-analyze with a different error (LLM path)
    run_case.error = ASSERTION_ERROR
    db_session.commit()
    second = analyze_failure(db_session, run_case.id)
    assert second.decision_source == "llm"
    assert second.category in FAILURE_CATEGORIES
    assert db_session.query(FailureAnalysis).count() == 1  # single row (D6)


def test_confirm_transition(db_session, sample_project, client):
    run_case = _failed_run_case(db_session, sample_project, client)
    analysis = analyze_failure(db_session, run_case.id)  # rule hit
    confirmed = confirm_analysis(db_session, analysis.id)
    assert confirmed.status == "confirmed"


def test_confirm_already_confirmed_409(db_session, sample_project, client):
    run_case = _failed_run_case(db_session, sample_project, client)
    analysis = analyze_failure(db_session, run_case.id)  # rule hit
    confirm_analysis(db_session, analysis.id)
    with pytest.raises(AppError) as exc:
        confirm_analysis(db_session, analysis.id)
    assert exc.value.code == "INVALID_TRANSITION"


def test_analyze_non_failed_422(db_session, sample_project, client):
    case = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "登录", "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_case = run.run_cases[0]  # status pending
    with pytest.raises(AppError) as exc:
        analyze_failure(db_session, run_case.id)
    assert exc.value.status_code == 422
    assert get_analysis(db_session, run_case.id) is None
