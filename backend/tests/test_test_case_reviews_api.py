"""Review API endpoints tests (P4-007)."""


def _create_case(client, project_id, **overrides):
    payload = {
        "title": "登录成功",
        "steps": [{"step_number": 1, "action": "打开登录页", "expected_result": "显示表单"}],
    }
    payload.update(overrides)
    return client.post(f"/api/projects/{project_id}/test-cases", json=payload).json()


def _submit(client, case_id):
    return client.post(f"/api/test-cases/{case_id}/submit-review")


def test_submit_review_api(sample_project, client):
    case = _create_case(client, sample_project["id"])
    response = _submit(client, case["id"])
    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"


def test_submit_empty_case_422(sample_project, client):
    case = _create_case(client, sample_project["id"], steps=[])
    assert _submit(client, case["id"]).status_code == 422


def test_submit_wrong_status_409(sample_project, client):
    case = _create_case(client, sample_project["id"])
    _submit(client, case["id"])
    # already pending_review -> submitting again is a conflict
    assert _submit(client, case["id"]).status_code == 409


def test_review_approve_api(sample_project, client):
    case = _create_case(client, sample_project["id"])
    _submit(client, case["id"])
    response = client.post(
        f"/api/test-cases/{case['id']}/review",
        json={"verdict": "approved", "issues": ["无明显问题"], "suggestions": ["补充边界"]},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_review_needs_work_api(sample_project, client):
    case = _create_case(client, sample_project["id"])
    _submit(client, case["id"])
    response = client.post(
        f"/api/test-cases/{case['id']}/review", json={"verdict": "needs_work"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "needs_work"


def test_review_invalid_verdict_422(sample_project, client):
    case = _create_case(client, sample_project["id"])
    _submit(client, case["id"])
    assert (
        client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "invalid"}).status_code
        == 422
    )


def test_review_non_pending_409(sample_project, client):
    case = _create_case(client, sample_project["id"])  # draft, not pending_review
    response = client.post(
        f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"}
    )
    assert response.status_code == 409


def test_resubmit_api(sample_project, client):
    case = _create_case(client, sample_project["id"])
    _submit(client, case["id"])
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "needs_work"})
    response = client.post(f"/api/test-cases/{case['id']}/resubmit-review")
    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"


def test_reviews_history_api(sample_project, client):
    case = _create_case(client, sample_project["id"])
    _submit(client, case["id"])
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    response = client.get(f"/api/test-cases/{case['id']}/reviews")
    assert response.status_code == 200
    reviews = response.json()
    assert len(reviews) == 1
    assert reviews[0]["reviewer_type"] == "human"
    assert reviews[0]["verdict"] == "approved"


def test_review_not_found_404(client):
    assert _submit(client, 999).status_code == 404
    assert client.get("/api/test-cases/999/reviews").status_code == 404
