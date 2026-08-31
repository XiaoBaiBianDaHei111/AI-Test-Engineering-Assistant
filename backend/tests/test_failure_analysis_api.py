"""Failure analysis API tests (P7-008, AC-7-05/06/08)."""

from app.services.assets.test_run_service import create_run

CONFIG = {"base_url": "http://localhost:8001", "qa_mode": "none", "browser": "chromium", "headless": True}
LOCATOR_ERROR = "Timeout 15000ms exceeded.\nwaiting for get_by_test_id(\"login-btn\")"


def _failed_run_case(db_session, sample_project, client):
    case = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "登录", "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run_case = run.run_cases[0]
    run_case.status = "failed"
    run_case.error = LOCATOR_ERROR
    db_session.commit()
    return run, run_case


def test_get_404_when_no_analysis(db_session, sample_project, client):
    _, run_case = _failed_run_case(db_session, sample_project, client)
    assert client.get(f"/api/failure-analysis/{run_case.id}").status_code == 404


def test_post_retry_returns_rule_analysis(db_session, sample_project, client):
    _, run_case = _failed_run_case(db_session, sample_project, client)
    resp = client.post("/api/failure-analysis", json={"run_case_id": run_case.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "BROKEN_LOCATOR"
    assert body["decision_source"] == "rule"
    assert body["needs_human"] is False


def test_confirm_flow_and_409(db_session, sample_project, client):
    _, run_case = _failed_run_case(db_session, sample_project, client)
    analysis = client.post("/api/failure-analysis", json={"run_case_id": run_case.id}).json()
    confirmed = client.post(f"/api/failure-analysis/{analysis['id']}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    again = client.post(f"/api/failure-analysis/{analysis['id']}/confirm")
    assert again.status_code == 409


def test_run_case_detail_nests_failure_analysis(db_session, sample_project, client):
    run, run_case = _failed_run_case(db_session, sample_project, client)
    client.post("/api/failure-analysis", json={"run_case_id": run_case.id})
    detail = client.get(f"/api/runs/{run.id}/cases/{run_case.id}").json()
    assert detail["failure_analysis"]["category"] == "BROKEN_LOCATOR"


def test_run_case_detail_nested_null_when_none(db_session, sample_project, client):
    run, run_case = _failed_run_case(db_session, sample_project, client)
    detail = client.get(f"/api/runs/{run.id}/cases/{run_case.id}").json()
    assert detail["failure_analysis"] is None
