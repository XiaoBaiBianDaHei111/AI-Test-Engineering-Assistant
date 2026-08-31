"""PATCH status bypass regression tests (P5-001, R004-A004 MINOR-001)."""


def _create_case(client, project_id, **overrides):
    payload = {"title": "用例", "steps": [{"step_number": 1, "action": "a", "expected_result": "b"}]}
    payload.update(overrides)
    return client.post(f"/api/projects/{project_id}/test-cases", json=payload).json()


def test_patch_status_approved_rejected(sample_project, client):
    case = _create_case(client, sample_project["id"])
    response = client.patch(f"/api/test-cases/{case['id']}", json={"status": "approved"})
    assert response.status_code == 422


def test_patch_status_pending_review_rejected(sample_project, client):
    case = _create_case(client, sample_project["id"])
    response = client.patch(f"/api/test-cases/{case['id']}", json={"status": "pending_review"})
    assert response.status_code == 422


def test_patch_status_needs_work_rejected(sample_project, client):
    case = _create_case(client, sample_project["id"])
    response = client.patch(f"/api/test-cases/{case['id']}", json={"status": "needs_work"})
    assert response.status_code == 422


def test_patch_status_archived_allowed(sample_project, client):
    case = _create_case(client, sample_project["id"])
    response = client.patch(f"/api/test-cases/{case['id']}", json={"status": "archived"})
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_patch_status_draft_noop_allowed(sample_project, client):
    case = _create_case(client, sample_project["id"])
    response = client.patch(f"/api/test-cases/{case['id']}", json={"status": "draft"})
    assert response.status_code == 200
    assert response.json()["status"] == "draft"
