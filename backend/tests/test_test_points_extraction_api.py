"""Test-point extraction API tests (P2-008/009; P013 real mode)."""

import pytest


def _extract(client, requirement_id):
    return client.post("/api/ai/extract-test-points", json={"requirement_id": requirement_id})


@pytest.mark.real
def test_extract_success(require_llm_key, confirmed_requirement, client):
    response = _extract(client, confirmed_requirement["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert len(body["test_points"]) >= 1
    for tp in body["test_points"]:
        assert tp["requirement_id"] == confirmed_requirement["id"]
        assert tp["technique"] in {
            "equivalence", "boundary", "state_transition", "exception", "error_guessing"
        }
        assert tp["status"] == "extracted"


def test_extract_unconfirmed_requirement_rejected(sample_project, client):
    req = client.post(
        f"/api/projects/{sample_project['id']}/requirements", json={"title": "未确认"}
    ).json()
    assert req["status"] == "parsed"
    response = _extract(client, req["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_extract_requirement_not_found(client):
    assert _extract(client, 999).status_code == 404


@pytest.mark.real
def test_extract_rerun_skips_existing(require_llm_key, confirmed_requirement, client):
    first = _extract(client, confirmed_requirement["id"]).json()
    assert len(first["test_points"]) >= 1
    second = _extract(client, confirmed_requirement["id"])
    assert second.status_code == 200
    body = second.json()
    assert body["status"] in ("success", "partial")


@pytest.mark.real
def test_extract_creates_audit_record(require_llm_key, confirmed_requirement, client):
    _extract(client, confirmed_requirement["id"])
    logs = client.get("/api/ai/audit", params={"agent": "test_point_extractor"}).json()
    assert len(logs) >= 1
    assert logs[0]["agent_name"] == "test_point_extractor"
