"""TestRun lifecycle + Gate 3 tests (P5-007)."""

import pytest

from app.core.exceptions import AppError, NotFoundError
from app.services.assets import test_run_service
from app.services.assets.test_run_service import cancel_run, create_run, get_run_or_404, list_runs

CONFIG = {"base_url": "http://localhost:8001", "qa_mode": "none", "browser": "chromium", "headless": True}


def _approved_case(client, project_id, title="登录成功"):
    case = client.post(
        f"/api/projects/{project_id}/test-cases",
        json={"title": title, "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    return case


def test_create_run_gate3_rejects_non_approved(sample_project, client, db_session):
    draft = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "draft", "steps": [{"step_number": 1, "action": "a", "expected_result": "b"}]},
    ).json()
    with pytest.raises(AppError) as exc:
        create_run(db_session, sample_project["id"], [draft["id"]], CONFIG)
    assert exc.value.code == "CASE_NOT_APPROVED"


def test_create_run_creates_run_and_cases(sample_project, client, db_session):
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    assert run.status == "pending"
    assert len(run.run_cases) == 1
    assert run.run_cases[0].test_case_id == case["id"]
    assert run.run_cases[0].status == "pending"


def test_create_run_project_not_found(client, db_session):
    with pytest.raises(NotFoundError):
        create_run(db_session, 999, [1], CONFIG)


def test_list_runs(sample_project, client, db_session):
    case = _approved_case(client, sample_project["id"])
    create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    assert len(list_runs(db_session, sample_project["id"])) == 2


def test_cancel_run_marks_pending_skipped(sample_project, client, db_session):
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run = cancel_run(db_session, run.id)
    assert run.run_cases[0].status == "skipped"
    assert test_run_service.is_cancelled(run.id)


def test_get_run_not_found(db_session):
    with pytest.raises(NotFoundError):
        get_run_or_404(db_session, 999)
