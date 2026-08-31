"""Quality summary API tests (P8-005 M2, AC-8-05/09)."""

import time

from tests._stubs import stub_execution


def _stub_summarize(db, stats, provider=None):
    # The quality-summary recommendation/score are rule-derived; the LLM only
    # supplies reasoning/risk_factors. Stub it so this API test stays offline.
    return {"overall_score": 90, "recommendation": "GO", "risk_factors": ["stub"], "reasoning": "stub reasoning"}


def _approved_case(client, project_id, title="登录成功"):
    case = client.post(
        f"/api/projects/{project_id}/test-cases",
        json={"title": title, "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    return case


def _completed_report(client, sample_project, monkeypatch, session_factory):
    monkeypatch.setattr("app.api.runs.SessionLocal", session_factory)
    stub_execution(monkeypatch)
    monkeypatch.setattr("app.services.assets.test_report_service.analyze_with_llm", _stub_summarize)
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
    report = client.get(f"/api/reports/{run_id}").json()
    return report


def test_quality_summary_go(monkeypatch, session_factory, sample_project, client):
    report = _completed_report(client, sample_project, monkeypatch, session_factory)
    resp = client.post(f"/api/quality-summary/{report['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendation"] == "GO"
    assert body["overall_score"] == 100
    assert body["reasoning"]


def test_quality_summary_nested_in_report(monkeypatch, session_factory, sample_project, client):
    report = _completed_report(client, sample_project, monkeypatch, session_factory)
    client.post(f"/api/quality-summary/{report['id']}")
    detail = client.get(f"/api/reports/{report['run_id']}").json()
    assert detail["quality_summary"]["recommendation"] == "GO"


def test_quality_summary_404(client):
    assert client.post("/api/quality-summary/99999").status_code == 404
