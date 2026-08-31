"""APITestCase CRUD + generation endpoint tests (P9-008, AC-9-07). Real mode (P013)."""

import pytest


def _payload(**overrides):
    data = {
        "name": "登录成功",
        "method": "POST",
        "url": "/api/demo-api/login",
        "headers": {},
        "body": {"username": "testuser", "password": "Test@1234"},
        "assertions": [{"type": "status", "expected": 200}],
    }
    data.update(overrides)
    return data


def test_create_and_list(sample_project, client):
    created = client.post(f"/api/projects/{sample_project['id']}/api-test-cases", json=_payload())
    assert created.status_code == 201
    assert created.json()["status"] == "active"
    listed = client.get(f"/api/projects/{sample_project['id']}/api-test-cases").json()
    assert any(c["id"] == created.json()["id"] for c in listed)


def test_update_and_archive(sample_project, client):
    created = client.post(f"/api/projects/{sample_project['id']}/api-test-cases", json=_payload()).json()
    patched = client.patch(f"/api/api-test-cases/{created['id']}", json={"name": "改名"})
    assert patched.status_code == 200 and patched.json()["name"] == "改名"
    archived = client.patch(f"/api/api-test-cases/{created['id']}", json={"status": "archived"})
    assert archived.json()["status"] == "archived"


def test_delete(sample_project, client):
    created = client.post(f"/api/projects/{sample_project['id']}/api-test-cases", json=_payload()).json()
    assert client.delete(f"/api/api-test-cases/{created['id']}").status_code == 204
    assert client.get(f"/api/api-test-cases/{created['id']}").status_code == 404


@pytest.mark.real
def test_generate_endpoint(require_llm_key, sample_project, client):
    # Use a specific description: the bare "登录接口" prompt makes DeepSeek emit a
    # very long (and sometimes truncated) response — a documented non-determinism.
    r = client.post("/api/ai/generate-api-test-cases", json={
        "project_id": sample_project["id"], "description": "登录接口 POST /api/demo-api/login，成功返回 token",
    })
    assert r.status_code == 200
    cases = r.json()["api_test_cases"]
    assert len(cases) >= 1
    for case in cases:
        assert case["name"]
        assert case["url"]
        assert case["assertions"]


def test_invalid_assertion_422(sample_project, client):
    r = client.post(f"/api/projects/{sample_project['id']}/api-test-cases", json=_payload(assertions=[]))
    assert r.status_code == 422


def test_invalid_response_time_name_422(sample_project, client):
    # B-4: response_time `name` is restricted to less_than / greater_than.
    payload = _payload(assertions=[{"type": "response_time", "expected_ms": 3000, "name": "greater"}])
    r = client.post(f"/api/projects/{sample_project['id']}/api-test-cases", json=payload)
    assert r.status_code == 422


def test_create_from_generated_dedup(db_session, sample_project):
    # B-1: duplicate (method, url, name) within a batch and against existing cases
    # are skipped with a warning.
    from app.services.assets import api_test_case_service

    items = [
        {"name": "登录成功", "method": "POST", "url": "/api/demo-api/login",
         "headers": {}, "body": {}, "assertions": [{"type": "status", "expected": 200}]},
        {"name": "登录成功", "method": "POST", "url": "/api/demo-api/login",
         "headers": {}, "body": {}, "assertions": [{"type": "status", "expected": 200}]},
        {"name": "登录失败", "method": "POST", "url": "/api/demo-api/login",
         "headers": {}, "body": {}, "assertions": [{"type": "status", "expected": 401}]},
    ]
    created, warnings = api_test_case_service.create_from_generated(
        db_session, sample_project["id"], None, items
    )
    assert len(created) == 2
    assert any("重复" in w for w in warnings)

    # Re-generating the same description yields no new rows (existing dedup).
    created2, warnings2 = api_test_case_service.create_from_generated(
        db_session, sample_project["id"], None, items
    )
    assert len(created2) == 0
    assert any("重复" in w for w in warnings2)
