"""Runs API tests (P5-009). Real mode (P013): execution stubbed via test-local doubles."""

import time

from tests._stubs import stub_execution


def _approved_case(client, project_id, title="登录成功"):
    case = client.post(
        f"/api/projects/{project_id}/test-cases",
        json={"title": title, "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    return case


def _create_run(client, project_id, case_ids, **config_overrides):
    config = {"base_url": "http://localhost:8001", "qa_mode": "none", "browser": "chromium", "headless": True}
    config.update(config_overrides)
    return client.post(
        "/api/runs", json={"project_id": project_id, "test_case_ids": case_ids, "config": config}
    )


def test_create_run_api_rejects_non_approved(sample_project, client):
    draft = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "draft", "steps": [{"step_number": 1, "action": "a", "expected_result": "b"}]},
    ).json()
    response = _create_run(client, sample_project["id"], [draft["id"]])
    assert response.status_code == 409
    assert response.json()["code"] == "CASE_NOT_APPROVED"


def test_create_run_api_empty_selection(sample_project, client):
    response = _create_run(client, sample_project["id"], [])
    assert response.status_code == 422


def test_create_run_api_project_not_found(client):
    response = _create_run(client, 999, [1])
    assert response.status_code == 404


def test_runs_full_flow(monkeypatch, session_factory, sample_project, client):
    monkeypatch.setattr("app.api.runs.SessionLocal", session_factory)
    stub_execution(monkeypatch)
    case = _approved_case(client, sample_project["id"])
    response = _create_run(client, sample_project["id"], [case["id"]])
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    run = None
    for _ in range(50):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)

    assert run["status"] == "completed"
    assert run["passed_count"] == 1
    run_case = run["cases"][0]
    assert run_case["status"] == "passed"

    # case detail with steps
    detail = client.get(f"/api/runs/{run_id}/cases/{run_case['id']}").json()
    assert detail["status"] == "passed"
    assert len(detail["step_results"]) >= 3


def test_list_runs_exposes_counts_and_cases(monkeypatch, session_factory, sample_project, client):
    """List endpoint must compute per-run counts and expose nested cases so the
    frontend table (passed/failed + expand-to-cases) renders correctly."""
    monkeypatch.setattr("app.api.runs.SessionLocal", session_factory)
    stub_execution(monkeypatch)
    case = _approved_case(client, sample_project["id"])
    run_id = _create_run(client, sample_project["id"], [case["id"]]).json()["run_id"]

    for _ in range(50):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)

    runs = client.get("/api/runs", params={"project_id": sample_project["id"]}).json()
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["total_count"] == 1
    assert runs[0]["passed_count"] == 1
    assert runs[0]["failed_count"] == 0
    assert runs[0]["cases"][0]["status"] == "passed"


def test_script_get_and_put(monkeypatch, session_factory, sample_project, client):
    monkeypatch.setattr("app.api.runs.SessionLocal", session_factory)
    stub_execution(monkeypatch)
    case = _approved_case(client, sample_project["id"])
    run_id = _create_run(client, sample_project["id"], [case["id"]]).json()["run_id"]

    # poll to completion
    run = None
    for _ in range(50):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)
    run_case_id = run["cases"][0]["id"]

    # GET script
    script = client.get(f"/api/runs/{run_id}/cases/{run_case_id}/script")
    assert script.status_code == 200
    assert "STEPS = [" in script.text

    # PUT script (overwrite)
    new_script = script.text.replace("登录成功", "改名登录成功")
    put = client.put(f"/api/runs/{run_id}/cases/{run_case_id}/script", content=new_script)
    assert put.status_code == 200

    # GET again reflects the edit
    assert "改名登录成功" in client.get(f"/api/runs/{run_id}/cases/{run_case_id}/script").text


def test_cancel_run_api(monkeypatch, session_factory, sample_project, client):
    monkeypatch.setattr("app.api.runs.SessionLocal", session_factory)
    stub_execution(monkeypatch)
    case = _approved_case(client, sample_project["id"])
    run_id = _create_run(client, sample_project["id"], [case["id"]]).json()["run_id"]
    # Cancel is a no-op / still valid whether or not the (synchronous) background
    # task has already completed the run.
    response = client.post(f"/api/runs/{run_id}/cancel")
    assert response.status_code == 200
    assert "status" in response.json()
