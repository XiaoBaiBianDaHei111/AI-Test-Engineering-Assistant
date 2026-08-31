"""e2e API flow (Phase 10): demo mock API -> generate -> execute -> report -> quality summary.

Requires a running backend (serving the demo API) at E2E_BASE_URL; excluded by
default (``-m "not e2e"``).
"""

import time

import pytest

pytestmark = pytest.mark.e2e


def test_e2e_api_generate_execute_report(e2e_api, e2e_base_url):
    # 1. project
    project = e2e_api.post("/projects", json={"name": "e2e-api", "description": "e2e"}).json()

    # 2. generate API cases from a description
    generated = e2e_api.post("/ai/generate-api-test-cases", json={
        "project_id": project["id"],
        "description": "登录接口 POST /api/demo-api/login，成功返回 token",
    })
    assert generated.status_code == 200
    api_ids = [c["id"] for c in generated.json()["api_test_cases"]]
    assert len(api_ids) >= 3

    # 3. run against the live demo API (e2e_base_url is the raw string URL;
    #    ApiRunner joins base_url + relative url, so it must not be httpx.URL).
    run_id = e2e_api.post("/runs", json={
        "project_id": project["id"], "test_case_ids": [], "api_case_ids": api_ids,
        "config": {"base_url": e2e_base_url, "qa_mode": "none",
                   "browser": "chromium", "headless": True},
    }).json()["run_id"]

    run = None
    for _ in range(60):
        run = e2e_api.get(f"/runs/{run_id}").json()
        if run["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.5)
    assert run["status"] == "completed"
    assert all(c["kind"] == "api" for c in run["cases"])

    # 4. report auto-generated + quality summary
    report = e2e_api.get(f"/reports/{run_id}").json()
    assert report["summary"]["total"] == len(api_ids)
    summary = e2e_api.post(f"/quality-summary/{report['id']}").json()
    assert summary["recommendation"] == "GO"
