"""TestPoint CRUD / state machine / cascade / test-case-consistency tests (P2-005/009)."""


def _create_test_point(client, requirement_id, **overrides):
    payload = {"title": "边界值测试", "technique": "boundary"}
    payload.update(overrides)
    return client.post(f"/api/requirements/{requirement_id}/test-points", json=payload)


def _create_requirement(client, project_id, title="Req"):
    return client.post(f"/api/projects/{project_id}/requirements", json={"title": title}).json()


def test_create_test_point(sample_project, client):
    req = _create_requirement(client, sample_project["id"])
    response = _create_test_point(client, req["id"])
    assert response.status_code == 201
    body = response.json()
    assert body["requirement_id"] == req["id"]
    assert body["status"] == "extracted"
    assert body["technique"] == "boundary"


def test_create_test_point_invalid_technique(sample_project, client):
    req = _create_requirement(client, sample_project["id"])
    assert _create_test_point(client, req["id"], technique="invalid").status_code == 422


def test_create_test_point_blank_title(sample_project, client):
    req = _create_requirement(client, sample_project["id"])
    assert _create_test_point(client, req["id"], title="   ").status_code == 422


def test_create_test_point_requirement_not_found(client):
    assert _create_test_point(client, 999).status_code == 404


def test_list_test_points(sample_project, client):
    req = _create_requirement(client, sample_project["id"])
    _create_test_point(client, req["id"], title="A")
    _create_test_point(client, req["id"], title="B")
    response = client.get(f"/api/requirements/{req['id']}/test-points")
    assert response.status_code == 200
    assert {tp["title"] for tp in response.json()} == {"A", "B"}


def test_list_test_points_requirement_not_found(client):
    assert client.get("/api/requirements/999/test-points").status_code == 404


def test_get_test_point_not_found(client):
    assert client.get("/api/test-points/999").status_code == 404


def test_update_test_point_status_transition(sample_project, client):
    req = _create_requirement(client, sample_project["id"])
    tp = _create_test_point(client, req["id"]).json()
    # extracted -> confirmed OK
    response = client.patch(f"/api/test-points/{tp['id']}", json={"status": "confirmed"})
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_update_test_point_illegal_transition(sample_project, client):
    req = _create_requirement(client, sample_project["id"])
    tp = _create_test_point(client, req["id"]).json()
    # confirmed -> extracted is illegal (need to confirm first)
    client.patch(f"/api/test-points/{tp['id']}", json={"status": "confirmed"})
    response = client.patch(f"/api/test-points/{tp['id']}", json={"status": "extracted"})
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_TRANSITION"


def test_delete_test_point(sample_project, client):
    req = _create_requirement(client, sample_project["id"])
    tp = _create_test_point(client, req["id"]).json()
    assert client.delete(f"/api/test-points/{tp['id']}").status_code == 204
    assert client.get(f"/api/test-points/{tp['id']}").status_code == 404


def test_delete_requirement_cascades_test_points(sample_project, client):
    req = _create_requirement(client, sample_project["id"])
    tp = _create_test_point(client, req["id"]).json()
    assert client.delete(f"/api/requirements/{req['id']}").status_code == 204
    assert client.get(f"/api/test-points/{tp['id']}").status_code == 404


# --- TestCase <-> TestPoint consistency (R003 MINOR-002) -----------------

def test_create_test_case_derives_requirement_from_test_point(sample_project, client):
    req = _create_requirement(client, sample_project["id"])
    tp = _create_test_point(client, req["id"]).json()
    response = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "Case", "test_point_id": tp["id"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["test_point_id"] == tp["id"]
    assert body["requirement_id"] == req["id"]  # derived


def test_create_test_case_test_point_wrong_project(sample_project, client):
    other = client.post("/api/projects", json={"name": "Other"}).json()
    other_req = _create_requirement(client, other["id"])
    other_tp = _create_test_point(client, other_req["id"]).json()
    response = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "Case", "test_point_id": other_tp["id"]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_create_test_case_inconsistent_requirement_and_test_point(sample_project, client):
    req1 = _create_requirement(client, sample_project["id"], title="Req1")
    req2 = _create_requirement(client, sample_project["id"], title="Req2")
    tp1 = _create_test_point(client, req1["id"]).json()
    response = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "Case", "requirement_id": req2["id"], "test_point_id": tp1["id"]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_create_test_case_test_point_not_found(sample_project, client):
    response = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "Case", "test_point_id": 999},
    )
    assert response.status_code == 404


def test_delete_test_point_sets_test_case_test_point_null(sample_project, client):
    req = _create_requirement(client, sample_project["id"])
    tp = _create_test_point(client, req["id"]).json()
    case = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "Case", "test_point_id": tp["id"]},
    ).json()
    assert case["test_point_id"] == tp["id"]
    assert client.delete(f"/api/test-points/{tp['id']}").status_code == 204
    fetched = client.get(f"/api/test-cases/{case['id']}").json()
    assert fetched["test_point_id"] is None
    assert fetched["requirement_id"] == req["id"]  # requirement survives
