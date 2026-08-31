"""Project CRUD API tests (normal flow, validation, duplicates, 404s, cascade)."""


def _create_project(client, name="Project A", description="desc"):
    return client.post("/api/projects", json={"name": name, "description": description})


def test_list_projects_empty(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.json() == []


def test_create_project(client):
    response = _create_project(client)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "Project A"
    assert body["description"] == "desc"
    assert "created_at" in body and "updated_at" in body


def test_create_project_strips_name(client):
    response = client.post("/api/projects", json={"name": "  Trimmed  "})
    assert response.status_code == 201
    assert response.json()["name"] == "Trimmed"


def test_create_project_blank_name(client):
    response = client.post("/api/projects", json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_create_project_missing_name(client):
    response = client.post("/api/projects", json={})
    assert response.status_code == 422


def test_create_project_duplicate_name(client):
    assert _create_project(client, name="Dup").status_code == 201
    response = _create_project(client, name="Dup")
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_get_project(client):
    created = _create_project(client).json()
    response = client.get(f"/api/projects/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Project A"


def test_get_project_not_found(client):
    response = client.get("/api/projects/999")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_update_project(client):
    created = _create_project(client).json()
    response = client.patch(
        f"/api/projects/{created['id']}",
        json={"name": "Renamed", "description": "new desc"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    assert response.json()["description"] == "new desc"


def test_update_project_partial(client):
    created = _create_project(client).json()
    response = client.patch(f"/api/projects/{created['id']}", json={"description": "only desc"})
    assert response.status_code == 200
    assert response.json()["name"] == "Project A"
    assert response.json()["description"] == "only desc"


def test_update_project_not_found(client):
    response = client.patch("/api/projects/999", json={"name": "X"})
    assert response.status_code == 404


def test_update_project_duplicate_name(client):
    _create_project(client, name="A")
    b = _create_project(client, name="B").json()
    response = client.patch(f"/api/projects/{b['id']}", json={"name": "A"})
    assert response.status_code == 409


def test_delete_project(client):
    created = _create_project(client).json()
    response = client.delete(f"/api/projects/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/projects/{created['id']}").status_code == 404


def test_delete_project_not_found(client):
    assert client.delete("/api/projects/999").status_code == 404


def test_delete_project_cascades_children(client):
    """Deleting a project removes its requirements and test cases."""
    project = _create_project(client).json()
    req = client.post(
        f"/api/projects/{project['id']}/requirements",
        json={"title": "Req 1"},
    ).json()
    case = client.post(
        f"/api/projects/{project['id']}/test-cases",
        json={"title": "Case 1", "steps": [{"step_number": 1, "action": "do"}]},
    ).json()

    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/requirements/{req['id']}").status_code == 404
    assert client.get(f"/api/test-cases/{case['id']}").status_code == 404
