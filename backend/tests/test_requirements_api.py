"""Requirement CRUD API tests."""


def _create_requirement(client, project_id, **overrides):
    payload = {"title": "User login", "description": "login flow"}
    payload.update(overrides)
    return client.post(f"/api/projects/{project_id}/requirements", json=payload)


def test_create_requirement_with_defaults(sample_project, client):
    response = _create_requirement(client, sample_project["id"])
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "User login"
    assert body["status"] == "parsed"
    assert body["source"] == "manual"
    assert body["acceptance_criteria"] == []
    assert body["risks"] == []
    assert body["gaps"] == []
    assert body["ambiguities"] == []
    assert body["doc_ref"] is None


def test_create_requirement_full_fields(sample_project, client):
    response = _create_requirement(
        client,
        sample_project["id"],
        acceptance_criteria=["AC1: login succeeds", "AC2: wrong password fails"],
        risks=["password brute force"],
        gaps=["rate limiting not specified"],
        ambiguities=["error message wording"],
        status="confirmed",
        source="ai",
        doc_ref="golden_prd.md",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["acceptance_criteria"] == ["AC1: login succeeds", "AC2: wrong password fails"]
    assert body["risks"] == ["password brute force"]
    assert body["gaps"] == ["rate limiting not specified"]
    assert body["ambiguities"] == ["error message wording"]
    assert body["status"] == "confirmed"
    assert body["source"] == "ai"
    assert body["doc_ref"] == "golden_prd.md"


def test_create_requirement_blank_title(sample_project, client):
    response = _create_requirement(client, sample_project["id"], title="  ")
    assert response.status_code == 422


def test_create_requirement_invalid_status(sample_project, client):
    response = _create_requirement(client, sample_project["id"], status="invalid")
    assert response.status_code == 422


def test_create_requirement_invalid_source(sample_project, client):
    response = _create_requirement(client, sample_project["id"], source="robot")
    assert response.status_code == 422


def test_create_requirement_project_not_found(client):
    response = _create_requirement(client, 999)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_list_requirements_empty(sample_project, client):
    response = client.get(f"/api/projects/{sample_project['id']}/requirements")
    assert response.status_code == 200
    assert response.json() == []


def test_list_requirements_scoped_to_project(sample_project, client):
    _create_requirement(client, sample_project["id"], title="R1")
    _create_requirement(client, sample_project["id"], title="R2")
    # another project with its own requirement
    other = client.post("/api/projects", json={"name": "Other"}).json()
    _create_requirement(client, other["id"], title="R-other")

    response = client.get(f"/api/projects/{sample_project['id']}/requirements")
    titles = {r["title"] for r in response.json()}
    assert titles == {"R1", "R2"}


def test_list_requirements_project_not_found(client):
    assert client.get("/api/projects/999/requirements").status_code == 404


def test_get_requirement(sample_project, client):
    created = _create_requirement(client, sample_project["id"]).json()
    response = client.get(f"/api/requirements/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "User login"


def test_get_requirement_not_found(client):
    assert client.get("/api/requirements/999").status_code == 404


def test_update_requirement_status_transition(sample_project, client):
    created = _create_requirement(client, sample_project["id"]).json()
    response = client.patch(f"/api/requirements/{created['id']}", json={"status": "archived"})
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_update_requirement_illegal_transition(sample_project, client):
    """Gate 1: confirmed -> parsed (backwards) must be rejected (AC-2-05)."""
    created = _create_requirement(client, sample_project["id"]).json()
    confirmed = client.patch(
        f"/api/requirements/{created['id']}", json={"status": "confirmed"}
    ).json()
    assert confirmed["status"] == "confirmed"
    response = client.patch(
        f"/api/requirements/{created['id']}", json={"status": "parsed"}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_TRANSITION"


def test_update_requirement_not_found(client):
    assert client.patch("/api/requirements/999", json={"title": "X"}).status_code == 404


def test_delete_requirement(sample_project, client):
    created = _create_requirement(client, sample_project["id"]).json()
    assert client.delete(f"/api/requirements/{created['id']}").status_code == 204
    assert client.get(f"/api/requirements/{created['id']}").status_code == 404


def test_delete_requirement_not_found(client):
    assert client.delete("/api/requirements/999").status_code == 404
