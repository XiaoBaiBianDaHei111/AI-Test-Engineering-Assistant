"""Review service + coverage + Gate 3 tests (P4-003/004)."""

import pytest

from app.core.exceptions import AppError, ConflictError, InvalidTransitionError, ValidationFailedError
from app.services.assets import test_case_review_service as review_service


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


def test_submit_for_review(sample_project, client, db_session):
    case = _create_case(client, sample_project["id"])
    result = review_service.submit_for_review(db_session, case["id"])
    assert result.status == "pending_review"


def test_submit_empty_case_rejected(sample_project, client, db_session):
    case = _create_case(client, sample_project["id"], steps=[])
    with pytest.raises(ValidationFailedError):
        review_service.submit_for_review(db_session, case["id"])


def test_submit_non_draft_rejected(sample_project, client, db_session):
    case = _create_case(client, sample_project["id"])
    review_service.submit_for_review(db_session, case["id"])
    with pytest.raises(ConflictError):
        review_service.submit_for_review(db_session, case["id"])


def test_human_review_approve(sample_project, client, db_session):
    case = _create_case(client, sample_project["id"])
    review_service.submit_for_review(db_session, case["id"])
    result = review_service.human_review(
        db_session, case["id"], "approved", issues=["ok"], suggestions=["good"]
    )
    assert result.status == "approved"
    reviews = review_service.list_reviews(db_session, case["id"])
    assert len(reviews) == 1
    assert reviews[0].reviewer_type == "human"
    assert reviews[0].verdict == "approved"
    assert reviews[0].issues == ["ok"]


def test_human_review_needs_work(sample_project, client, db_session):
    case = _create_case(client, sample_project["id"])
    review_service.submit_for_review(db_session, case["id"])
    result = review_service.human_review(db_session, case["id"], "needs_work")
    assert result.status == "needs_work"


def test_human_review_non_pending_rejected(sample_project, client, db_session):
    case = _create_case(client, sample_project["id"])
    with pytest.raises(ConflictError):
        review_service.human_review(db_session, case["id"], "approved")


def test_resubmit_for_review(sample_project, client, db_session):
    case = _create_case(client, sample_project["id"])
    review_service.submit_for_review(db_session, case["id"])
    review_service.human_review(db_session, case["id"], "needs_work")
    result = review_service.resubmit_for_review(db_session, case["id"])
    assert result.status == "pending_review"


def test_edit_approved_case_resets_to_needs_work(sample_project, client, db_session):
    """R004-P004 MINOR-001: editing an approved case invalidates its review."""
    case = _create_case(client, sample_project["id"])
    review_service.submit_for_review(db_session, case["id"])
    review_service.human_review(db_session, case["id"], "approved")
    # content edit via PATCH (no explicit status) resets approved -> needs_work
    response = client.patch(f"/api/test-cases/{case['id']}", json={"title": "改名"})
    assert response.status_code == 200
    assert response.json()["status"] == "needs_work"


def test_uncovered_and_covered_test_points(sample_project, client, db_session):
    req = client.post(
        f"/api/projects/{sample_project['id']}/requirements", json={"title": "需求"}
    ).json()
    tp1 = client.post(
        f"/api/requirements/{req['id']}/test-points", json={"title": "未覆盖点", "technique": "equivalence"}
    ).json()
    tp2 = client.post(
        f"/api/requirements/{req['id']}/test-points", json={"title": "已覆盖点", "technique": "boundary"}
    ).json()
    # cover tp2 with a test case
    _create_case(client, sample_project["id"], title="覆盖用例", test_point_id=tp2["id"])

    uncovered = review_service.uncovered_test_points(db_session, sample_project["id"])
    uncovered_ids = {u["id"] for u in uncovered}
    assert tp1["id"] in uncovered_ids
    assert tp2["id"] not in uncovered_ids


def test_executable_cases_only_approved(sample_project, client, db_session):
    case = _create_case(client, sample_project["id"], title="待执行")
    review_service.submit_for_review(db_session, case["id"])
    review_service.human_review(db_session, case["id"], "approved")
    _create_case(client, sample_project["id"], title="未评审")  # stays draft

    executable = review_service.executable_cases(db_session, sample_project["id"])
    assert [c.title for c in executable] == ["待执行"]


def test_assert_cases_executable(sample_project, client, db_session):
    case = _create_case(client, sample_project["id"], title="draft 用例")
    with pytest.raises(AppError) as exc:
        review_service.assert_cases_executable(db_session, [case["id"]])
    assert exc.value.code == "CASE_NOT_APPROVED"
    # approve it, then the assertion passes
    review_service.submit_for_review(db_session, case["id"])
    review_service.human_review(db_session, case["id"], "approved")
    review_service.assert_cases_executable(db_session, [case["id"]])
