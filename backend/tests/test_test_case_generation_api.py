"""Test-case generation API tests (P3-007). Real mode (P013)."""

import time

import pytest


class _FailingProvider:
    def chat(self, *args, **kwargs):
        raise RuntimeError("no LLM in unit gate")


def _confirmed_requirement_and_points(client, project_id, count):
    req = client.post(
        f"/api/projects/{project_id}/requirements", json={"title": "需求"}
    ).json()
    client.patch(f"/api/requirements/{req['id']}", json={"status": "confirmed"})
    ids = []
    for i in range(count):
        tp = client.post(
            f"/api/requirements/{req['id']}/test-points",
            json={"title": f"测试点{i}", "technique": "equivalence"},
        ).json()
        client.patch(f"/api/test-points/{tp['id']}", json={"status": "confirmed"})
        ids.append(tp["id"])
    return req, ids


def test_generate_empty_selection(sample_project, client):
    response = client.post(
        "/api/ai/generate-test-cases",
        json={"project_id": sample_project["id"], "test_point_ids": []},
    )
    assert response.status_code == 422


def test_generate_project_not_found(client):
    response = client.post(
        "/api/ai/generate-test-cases",
        json={"project_id": 999, "test_point_ids": [1]},
    )
    assert response.status_code == 404


def test_generate_test_point_not_found(sample_project, client):
    response = client.post(
        "/api/ai/generate-test-cases",
        json={"project_id": sample_project["id"], "test_point_ids": [999]},
    )
    assert response.status_code == 404


def test_generate_unconfirmed_test_point_rejected(sample_project, client):
    # confirmed requirement + an UNconfirmed (extracted) test point
    req = client.post(
        f"/api/projects/{sample_project['id']}/requirements", json={"title": "需求"}
    ).json()
    client.patch(f"/api/requirements/{req['id']}", json={"status": "confirmed"})
    tp = client.post(
        f"/api/requirements/{req['id']}/test-points",
        json={"title": "未确认测试点", "technique": "equivalence"},
    ).json()
    assert tp["status"] == "extracted"
    response = client.post(
        "/api/ai/generate-test-cases",
        json={"project_id": sample_project["id"], "test_point_ids": [tp["id"]]},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "TEST_POINT_NOT_CONFIRMED"


def test_generate_unconfirmed_requirement_rejected(sample_project, client):
    # UNconfirmed requirement + a confirmed test point (R003-P003 MINOR-001)
    req = client.post(
        f"/api/projects/{sample_project['id']}/requirements", json={"title": "需求"}
    ).json()
    assert req["status"] == "parsed"
    tp = client.post(
        f"/api/requirements/{req['id']}/test-points",
        json={"title": "测试点", "technique": "equivalence"},
    ).json()
    client.patch(f"/api/test-points/{tp['id']}", json={"status": "confirmed"})
    response = client.post(
        "/api/ai/generate-test-cases",
        json={"project_id": sample_project["id"], "test_point_ids": [tp["id"]]},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "REQUIREMENT_NOT_CONFIRMED"


@pytest.mark.real
def test_generate_full_flow(require_llm_key, monkeypatch, session_factory, sample_project, client):
    monkeypatch.setattr("app.api.ai.test_case_generation.SessionLocal", session_factory)
    _, ids = _confirmed_requirement_and_points(client, sample_project["id"], 2)

    response = client.post(
        "/api/ai/generate-test-cases",
        json={"project_id": sample_project["id"], "test_point_ids": ids},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "started"
    assert body["total"] == 2
    run_id = body["run_id"]

    run = None
    for _ in range(50):
        run = client.get(f"/api/ai/generation-runs/{run_id}").json()
        if run["status"] in ("completed", "partial", "failed"):
            break
        time.sleep(0.05)

    assert run["status"] == "completed"
    assert run["processed_items"] == 2
    assert run["created_count"] >= 2  # at least one case per test point

    cases = client.get(f"/api/projects/{sample_project['id']}/test-cases").json()
    assert len(cases) >= 2
    for case in cases:
        assert case["source"] == "ai"
        assert case["status"] == "draft"
        assert case["test_point_id"] in ids


def test_generate_runs_history(monkeypatch, session_factory, sample_project, client):
    monkeypatch.setattr("app.api.ai.test_case_generation.SessionLocal", session_factory)
    # Keep the history check offline: generation fails fast without an LLM.
    monkeypatch.setattr(
        "app.services.ai.agents.test_case_generator.get_provider", lambda: _FailingProvider()
    )
    _, ids = _confirmed_requirement_and_points(client, sample_project["id"], 1)
    client.post(
        "/api/ai/generate-test-cases",
        json={"project_id": sample_project["id"], "test_point_ids": ids},
    )
    history = client.get(
        "/api/ai/generation-runs", params={"project_id": sample_project["id"]}
    ).json()
    assert len(history) >= 1
    assert history[0]["status"] in ("pending", "running", "completed", "partial", "failed")
