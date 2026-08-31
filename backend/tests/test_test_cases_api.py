"""TestCase / TestCaseStep CRUD API tests."""


def _create_test_case(client, project_id, **overrides):
    payload = {
        "title": "Login with valid credentials",
        "steps": [
            {"step_number": 1, "action": "open login page", "expected_result": "page shown"},
            {"step_number": 2, "action": "enter credentials", "expected_result": "fields filled"},
            {"step_number": 3, "action": "submit", "expected_result": "dashboard shown"},
        ],
    }
    payload.update(overrides)
    return client.post(f"/api/projects/{project_id}/test-cases", json=payload)


def test_create_test_case_with_steps(sample_project, client):
    response = _create_test_case(client, sample_project["id"])
    assert response.status_code == 201
    body = response.json()
    assert body["case_id"] == "TC-001"
    assert body["status"] == "draft"
    assert body["priority"] == "P2"
    assert body["type"] == "functional"
    assert body["source"] == "manual"
    assert [s["step_number"] for s in body["steps"]] == [1, 2, 3]
    assert body["steps"][0]["action"] == "open login page"


def test_create_test_case_auto_increments_case_id(sample_project, client):
    assert _create_test_case(client, sample_project["id"]).json()["case_id"] == "TC-001"
    assert _create_test_case(client, sample_project["id"], title="Second").json()["case_id"] == "TC-002"


def test_create_test_case_explicit_case_id(sample_project, client):
    response = _create_test_case(client, sample_project["id"], case_id="TC-042", title="T")
    assert response.status_code == 201
    assert response.json()["case_id"] == "TC-042"


def test_create_test_case_duplicate_case_id(sample_project, client):
    _create_test_case(client, sample_project["id"], case_id="TC-100", title="A")
    response = _create_test_case(client, sample_project["id"], case_id="TC-100", title="B")
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_create_test_case_invalid_case_id_format(sample_project, client):
    response = _create_test_case(client, sample_project["id"], case_id="FOO-1")
    assert response.status_code == 422


def test_create_test_case_blank_title(sample_project, client):
    response = _create_test_case(client, sample_project["id"], title="   ")
    assert response.status_code == 422


def test_create_test_case_invalid_priority(sample_project, client):
    response = _create_test_case(client, sample_project["id"], priority="P9")
    assert response.status_code == 422


def test_create_test_case_invalid_status(sample_project, client):
    response = _create_test_case(client, sample_project["id"], status="nope")
    assert response.status_code == 422


def test_create_test_case_duplicate_step_numbers(sample_project, client):
    response = _create_test_case(
        client,
        sample_project["id"],
        steps=[
            {"step_number": 1, "action": "a"},
            {"step_number": 1, "action": "b"},
        ],
    )
    assert response.status_code == 422


def test_create_test_case_empty_steps_allowed(sample_project, client):
    response = _create_test_case(client, sample_project["id"], steps=[])
    assert response.status_code == 201
    assert response.json()["steps"] == []


def test_create_test_case_project_not_found(client):
    response = _create_test_case(client, 999)
    assert response.status_code == 404


def test_create_test_case_requirement_wrong_project(sample_project, client):
    other = client.post("/api/projects", json={"name": "Other"}).json()
    other_req = client.post(
        f"/api/projects/{other['id']}/requirements", json={"title": "foreign"}
    ).json()
    response = _create_test_case(
        client, sample_project["id"], requirement_id=other_req["id"]
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_create_test_case_requirement_not_found(sample_project, client):
    response = _create_test_case(client, sample_project["id"], requirement_id=999)
    assert response.status_code == 404


def test_list_test_cases_scoped_to_project(sample_project, client):
    _create_test_case(client, sample_project["id"], title="A")
    _create_test_case(client, sample_project["id"], title="B")
    other = client.post("/api/projects", json={"name": "Other"}).json()
    _create_test_case(client, other["id"], title="C")

    response = client.get(f"/api/projects/{sample_project['id']}/test-cases")
    titles = {t["title"] for t in response.json()}
    assert titles == {"A", "B"}


def test_get_test_case_not_found(client):
    assert client.get("/api/test-cases/999").status_code == 404


def test_update_test_case_title_and_steps(sample_project, client):
    created = _create_test_case(client, sample_project["id"]).json()
    response = client.patch(
        f"/api/test-cases/{created['id']}",
        json={
            "title": "Renamed",
            "steps": [{"step_number": 1, "action": "only one step"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Renamed"
    assert body["status"] == "draft"
    assert len(body["steps"]) == 1
    assert body["steps"][0]["action"] == "only one step"


def test_update_test_case_preserves_steps_when_omitted(sample_project, client):
    created = _create_test_case(client, sample_project["id"]).json()
    response = client.patch(f"/api/test-cases/{created['id']}", json={"priority": "P0"})
    assert response.status_code == 200
    assert response.json()["priority"] == "P0"
    assert len(response.json()["steps"]) == 3


def test_update_test_case_not_found(client):
    assert client.patch("/api/test-cases/999", json={"title": "X"}).status_code == 404


def test_delete_test_case(sample_project, client):
    created = _create_test_case(client, sample_project["id"]).json()
    assert client.delete(f"/api/test-cases/{created['id']}").status_code == 204
    assert client.get(f"/api/test-cases/{created['id']}").status_code == 404


def test_delete_test_case_not_found(client):
    assert client.delete("/api/test-cases/999").status_code == 404


def test_delete_requirement_unlinks_test_case(sample_project, client):
    """Deleting a requirement SET NULL on dependent test cases (they survive)."""
    req = client.post(
        f"/api/projects/{sample_project['id']}/requirements", json={"title": "Req"}
    ).json()
    case = _create_test_case(
        client, sample_project["id"], requirement_id=req["id"]
    ).json()
    assert case["requirement_id"] == req["id"]

    assert client.delete(f"/api/requirements/{req['id']}").status_code == 204

    fetched = client.get(f"/api/test-cases/{case['id']}").json()
    assert fetched["requirement_id"] is None


def test_full_crud_flow(sample_project, client):
    """The exact AC-2 sequence: create project -> requirement -> test case ->
    list -> update -> delete, with data persisted in the DB."""
    project = sample_project
    # 录入需求
    req = client.post(
        f"/api/projects/{project['id']}/requirements",
        json={"title": "User login", "acceptance_criteria": ["AC1"]},
    ).json()
    # 录入用例（含步骤）
    case = client.post(
        f"/api/projects/{project['id']}/test-cases",
        json={
            "title": "Login success",
            "requirement_id": req["id"],
            "steps": [{"step_number": 1, "action": "submit valid login"}],
        },
    ).json()
    assert case["case_id"] == "TC-001"

    # 查询列表
    assert len(client.get(f"/api/projects/{project['id']}/requirements").json()) == 1
    cases = client.get(f"/api/projects/{project['id']}/test-cases").json()
    assert len(cases) == 1 and cases[0]["steps"]

    # 修改（内容编辑：review 状态经评审端点流转，PATCH 仅允许 draft/archived）
    updated = client.patch(
        f"/api/test-cases/{case['id']}", json={"title": "Login success (renamed)"}
    ).json()
    assert updated["title"] == "Login success (renamed)"

    # 删除
    assert client.delete(f"/api/test-cases/{case['id']}").status_code == 204
    assert client.delete(f"/api/requirements/{req['id']}").status_code == 204
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
