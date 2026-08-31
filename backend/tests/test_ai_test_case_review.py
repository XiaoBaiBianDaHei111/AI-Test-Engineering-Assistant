"""AI test-case review tests (M2, P4-005/006/007; P013 real mode)."""

import pytest


def _create_case(client, project_id, **overrides):
    payload = {
        "title": "登录成功",
        "steps": [
            {"step_number": 1, "action": "打开登录页", "expected_result": "显示表单"},
            {"step_number": 2, "action": "提交登录", "expected_result": "跳转列表"},
        ],
    }
    payload.update(overrides)
    return client.post(f"/api/projects/{project_id}/test-cases", json=payload).json()


def _review(client, case_ids):
    return client.post("/api/ai/review-test-cases", json={"test_case_ids": case_ids})


@pytest.mark.real
def test_ai_review_endpoint_creates_record(require_llm_key, sample_project, client):
    case = _create_case(client, sample_project["id"])
    response = _review(client, [case["id"]])
    assert response.status_code == 200
    body = response.json()
    assert body["reviewed"] == 1
    assert body["failed"] == []

    reviews = client.get(f"/api/test-cases/{case['id']}/reviews").json()
    assert len(reviews) == 1
    review = reviews[0]
    assert review["reviewer_type"] == "ai"
    assert review["verdict"] in ("approved", "needs_work")
    assert set(review["scores"]) == {"completeness", "accuracy", "executability"}


def test_ai_review_archived_skipped(sample_project, client):
    case = _create_case(client, sample_project["id"])
    client.patch(f"/api/test-cases/{case['id']}", json={"status": "archived"})
    response = _review(client, [case["id"]])
    assert response.status_code == 200
    assert response.json()["reviewed"] == 0
    assert len(response.json()["warnings"]) == 1


def test_ai_review_not_found(sample_project, client):
    response = _review(client, [999])
    assert response.status_code == 200
    assert response.json()["failed"][0]["error_code"] == "NOT_FOUND"


def test_ai_review_batch_limit(client):
    response = _review(client, list(range(1, 52)))  # 51 > 50 limit
    assert response.status_code == 422


def test_create_ai_review_upserts(db_session, sample_project, client):
    # RUI-03a: a second AI review replaces the first (no stacking); human history
    # is preserved.
    from sqlalchemy import select

    from app.models import TestCaseReview
    from app.services.assets.test_case_review_service import create_ai_review

    case = _create_case(client, sample_project["id"])
    db_session.add(TestCaseReview(
        test_case_id=case["id"], reviewer_type="human", verdict="needs_work",
        scores=None, issues=["人工退回"], missing_scenarios=[], suggestions=[],
    ))
    db_session.commit()

    create_ai_review(db_session, case["id"], "approved",
                     {"completeness": 5, "accuracy": 5, "executability": 5}, ["旧问题"], [], [])
    create_ai_review(db_session, case["id"], "needs_work",
                     {"completeness": 2, "accuracy": 5, "executability": 5}, ["新问题"], [], [])

    ai = list(db_session.scalars(select(TestCaseReview).where(
        TestCaseReview.test_case_id == case["id"], TestCaseReview.reviewer_type == "ai")))
    human = list(db_session.scalars(select(TestCaseReview).where(
        TestCaseReview.test_case_id == case["id"], TestCaseReview.reviewer_type == "human")))
    assert len(ai) == 1
    assert ai[0].issues == ["新问题"]
    assert len(human) == 1
    assert human[0].issues == ["人工退回"]
