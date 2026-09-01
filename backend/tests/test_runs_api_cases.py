"""runs API extension tests (P9-008, AC-9-05)."""

import time

import httpx

from app.execution.api_runner import ApiRunner


def _approved_case(client, project_id, title="登录成功"):
    case = client.post(
        f"/api/projects/{project_id}/test-cases",
        json={"title": title, "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    return case


def _api_case(client, project_id, status="active"):
    return client.post(
        f"/api/projects/{project_id}/api-test-cases",
        json={
            "name": "登录成功", "method": "POST", "url": "/api/demo-api/login",
            "body": {"username": "testuser", "password": "Test@1234"},
            "assertions": [{"type": "status", "expected": 200}],
            "status": status,
        },
    ).json()


def _api_handler(request):
    return httpx.Response(200, json={"token": "demo-token"})


def _patch_api_runner(monkeypatch, session_factory):
    monkeypatch.setattr("app.api.runs.SessionLocal", session_factory)
    monkeypatch.setattr(
        "app.services.assets.test_run_service.ApiRunner",
        lambda: ApiRunner(transport=httpx.MockTransport(_api_handler)),
    )


def test_mixed_run_creates_ui_and_api_cases(monkeypatch, session_factory, sample_project, client):
    _patch_api_runner(monkeypatch, session_factory)
    ui = _approved_case(client, sample_project["id"])
    api = _api_case(client, sample_project["id"])

    resp = client.post("/api/runs", json={
        "project_id": sample_project["id"],
        "test_case_ids": [ui["id"]],
        "api_case_ids": [api["id"]],
        "config": {"base_url": "http://localhost:8001", "qa_mode": "none",
                   "browser": "chromium", "headless": True},
    })
    assert resp.status_code == 200
    assert resp.json()["total"] == 2
    run_id = resp.json()["run_id"]

    for _ in range(50):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)

    kinds = sorted(c["kind"] for c in run["cases"])
    assert kinds == ["api", "ui"]


def test_empty_ids_422(sample_project, client):
    resp = client.post("/api/runs", json={
        "project_id": sample_project["id"], "test_case_ids": [], "api_case_ids": [],
        "config": {"base_url": "http://localhost:8001", "qa_mode": "none",
                   "browser": "chromium", "headless": True},
    })
    assert resp.status_code == 422


def test_archived_api_422(sample_project, client):
    api = _api_case(client, sample_project["id"], status="archived")
    resp = client.post("/api/runs", json={
        "project_id": sample_project["id"], "test_case_ids": [], "api_case_ids": [api["id"]],
        "config": {"base_url": "http://localhost:8001", "qa_mode": "none",
                   "browser": "chromium", "headless": True},
    })
    assert resp.status_code == 422


def test_non_approved_ui_409(sample_project, client):
    draft = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "draft", "steps": [{"step_number": 1, "action": "a", "expected_result": "b"}]},
    ).json()
    resp = client.post("/api/runs", json={
        "project_id": sample_project["id"], "test_case_ids": [draft["id"]], "api_case_ids": [],
        "config": {"base_url": "http://localhost:8001", "qa_mode": "none",
                   "browser": "chromium", "headless": True},
    })
    assert resp.status_code == 409
    assert resp.json()["code"] == "CASE_NOT_APPROVED"
