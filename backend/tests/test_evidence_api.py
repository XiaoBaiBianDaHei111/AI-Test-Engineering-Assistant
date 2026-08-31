"""Evidence API tests (P6-007, AC-6-02/6-05)."""

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


def _completed_run(client, sample_project, monkeypatch, session_factory):
    monkeypatch.setattr("app.api.runs.SessionLocal", session_factory)
    stub_execution(monkeypatch)
    case = _approved_case(client, sample_project["id"])
    payload = {
        "project_id": sample_project["id"],
        "test_case_ids": [case["id"]],
        "config": {"base_url": "http://localhost:8001", "qa_mode": "none",
                   "browser": "chromium", "headless": True},
    }
    run_id = client.post("/api/runs", json=payload).json()["run_id"]
    run = None
    for _ in range(50):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)
    assert run["status"] == "completed"
    return run_id, run["cases"][0]["id"]


def test_evidence_list_endpoint(monkeypatch, session_factory, sample_project, client):
    run_id, run_case_id = _completed_run(client, sample_project, monkeypatch, session_factory)
    resp = client.get(f"/api/runs/{run_id}/cases/{run_case_id}/evidence")
    assert resp.status_code == 200
    kinds = sorted(e["kind"] for e in resp.json())
    assert kinds.count("screenshot") == 5
    assert "console" in kinds and "network" in kinds and "trace" in kinds


def test_evidence_content_screenshot(monkeypatch, session_factory, sample_project, client):
    run_id, run_case_id = _completed_run(client, sample_project, monkeypatch, session_factory)
    rows = client.get(f"/api/runs/{run_id}/cases/{run_case_id}/evidence").json()
    shot = next(e for e in rows if e["kind"] == "screenshot")
    content = client.get(f"/api/evidence/{shot['id']}/content")
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("image/png")
    assert len(content.content) > 0


def test_evidence_content_console_json(monkeypatch, session_factory, sample_project, client):
    run_id, run_case_id = _completed_run(client, sample_project, monkeypatch, session_factory)
    rows = client.get(f"/api/runs/{run_id}/cases/{run_case_id}/evidence").json()
    console = next(e for e in rows if e["kind"] == "console")
    content = client.get(f"/api/evidence/{console['id']}/content")
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("application/json")
    assert isinstance(content.json(), list)


def test_evidence_content_trace_zip(monkeypatch, session_factory, sample_project, client):
    run_id, run_case_id = _completed_run(client, sample_project, monkeypatch, session_factory)
    rows = client.get(f"/api/runs/{run_id}/cases/{run_case_id}/evidence").json()
    trace = next(e for e in rows if e["kind"] == "trace")
    content = client.get(f"/api/evidence/{trace['id']}/content")
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("application/zip")


def test_evidence_content_404(client):
    assert client.get("/api/evidence/99999/content").status_code == 404


def test_trace_parse_endpoint(monkeypatch, session_factory, sample_project, client):
    run_id, run_case_id = _completed_run(client, sample_project, monkeypatch, session_factory)
    rows = client.get(f"/api/runs/{run_id}/cases/{run_case_id}/evidence").json()
    trace = next(e for e in rows if e["kind"] == "trace")
    resp = client.get(f"/api/evidence/{trace['id']}/trace-parse")
    assert resp.status_code == 200
    assert len(resp.json()["actions"]) >= 1
    assert len(resp.json()["network"]) >= 1


def test_trace_parse_404_for_non_trace(client, monkeypatch, session_factory, sample_project):
    run_id, run_case_id = _completed_run(client, sample_project, monkeypatch, session_factory)
    rows = client.get(f"/api/runs/{run_id}/cases/{run_case_id}/evidence").json()
    console = next(e for e in rows if e["kind"] == "console")
    assert client.get(f"/api/evidence/{console['id']}/trace-parse").status_code == 404


def test_run_level_evidence_endpoint(monkeypatch, session_factory, sample_project, client):
    run_id, _ = _completed_run(client, sample_project, monkeypatch, session_factory)
    resp = client.get(f"/api/runs/{run_id}/evidence")
    assert resp.status_code == 200
    assert any(e["kind"] == "log" for e in resp.json())
