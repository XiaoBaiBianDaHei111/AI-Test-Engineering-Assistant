"""Coverage view + Gate 3 executable list API tests (P4-004/007)."""


def _create_case(client, project_id, **overrides):
    payload = {
        "title": "用例",
        "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}],
    }
    payload.update(overrides)
    return client.post(f"/api/projects/{project_id}/test-cases", json=payload).json()


def test_uncovered_test_points_api(sample_project, client):
    req = client.post(
        f"/api/projects/{sample_project['id']}/requirements", json={"title": "需求"}
    ).json()
    tp1 = client.post(
        f"/api/requirements/{req['id']}/test-points",
        json={"title": "未覆盖", "technique": "equivalence"},
    ).json()
    tp2 = client.post(
        f"/api/requirements/{req['id']}/test-points",
        json={"title": "已覆盖", "technique": "boundary"},
    ).json()
    _create_case(client, sample_project["id"], title="覆盖用例", test_point_id=tp2["id"])

    response = client.get(f"/api/projects/{sample_project['id']}/coverage/uncovered-test-points")
    assert response.status_code == 200
    uncovered = response.json()
    ids = {u["id"] for u in uncovered}
    assert tp1["id"] in ids
    assert tp2["id"] not in ids
    assert all(u["requirement_title"] == "需求" for u in uncovered)


def test_uncovered_excludes_archived_cases(sample_project, client):
    """R004-P004 SUGGESTION-1: archived cases do not count as coverage."""
    req = client.post(
        f"/api/projects/{sample_project['id']}/requirements", json={"title": "需求"}
    ).json()
    tp = client.post(
        f"/api/requirements/{req['id']}/test-points",
        json={"title": "点", "technique": "equivalence"},
    ).json()
    case = _create_case(client, sample_project["id"], title="归档用例", test_point_id=tp["id"])
    client.patch(f"/api/test-cases/{case['id']}", json={"status": "archived"})

    uncovered = client.get(
        f"/api/projects/{sample_project['id']}/coverage/uncovered-test-points"
    ).json()
    assert tp["id"] in {u["id"] for u in uncovered}


def test_executable_api(sample_project, client):
    case = _create_case(client, sample_project["id"], title="待执行")
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    _create_case(client, sample_project["id"], title="未评审")  # stays draft

    response = client.get(f"/api/projects/{sample_project['id']}/test-cases/executable")
    assert response.status_code == 200
    assert [c["title"] for c in response.json()] == ["待执行"]


def test_coverage_project_not_found(client):
    assert client.get("/api/projects/999/coverage/uncovered-test-points").status_code == 404
    assert client.get("/api/projects/999/test-cases/executable").status_code == 404
