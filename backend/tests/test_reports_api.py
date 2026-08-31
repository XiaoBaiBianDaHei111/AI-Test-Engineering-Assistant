"""Report API tests (P8-005, AC-8-01/02/04/06)."""

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
    run_id = client.post("/api/runs", json={
        "project_id": sample_project["id"], "test_case_ids": [case["id"]],
        "config": {"base_url": "http://localhost:8001", "qa_mode": "none",
                   "browser": "chromium", "headless": True},
    }).json()["run_id"]
    for _ in range(50):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)
    assert run["status"] == "completed"
    return run_id


def test_report_detail(monkeypatch, session_factory, sample_project, client):
    run_id = _completed_run(client, sample_project, monkeypatch, session_factory)
    detail = client.get(f"/api/reports/{run_id}").json()
    assert detail["summary"]["passed"] == 1
    assert detail["stats"]["overview"]["passed"] == 1
    assert detail["quality_summary"] is None


def test_report_html(monkeypatch, session_factory, sample_project, client):
    run_id = _completed_run(client, sample_project, monkeypatch, session_factory)
    resp = client.get(f"/api/reports/{run_id}/html")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "测试报告" in resp.text


def test_report_export_json_and_markdown(monkeypatch, session_factory, sample_project, client):
    run_id = _completed_run(client, sample_project, monkeypatch, session_factory)
    j = client.get(f"/api/reports/{run_id}/export", params={"format": "json"})
    assert j.status_code == 200 and j.headers["content-type"].startswith("application/json")
    # B-5: semantic download name {run_name}-{report_id}.json
    assert "attachment" in j.headers.get("content-disposition", "")
    assert "Run-" in j.headers.get("content-disposition", "")
    md = client.get(f"/api/reports/{run_id}/export", params={"format": "markdown"})
    assert md.status_code == 200
    assert "测试报告" in md.text
    # B-3: markdown now downloads (Content-Disposition attachment) with a .md name.
    assert "attachment" in md.headers.get("content-disposition", "")
    assert ".md" in md.headers.get("content-disposition", "")


def test_report_list(monkeypatch, session_factory, sample_project, client):
    run_id = _completed_run(client, sample_project, monkeypatch, session_factory)
    reports = client.get("/api/reports", params={"project_id": sample_project["id"]}).json()
    assert any(r["run_id"] == run_id for r in reports)


def test_report_404(client):
    assert client.get("/api/reports/99999").status_code == 404
