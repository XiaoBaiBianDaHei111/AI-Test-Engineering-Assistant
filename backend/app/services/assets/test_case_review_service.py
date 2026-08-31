"""Test-case review service (M1): submit / human review / resubmit / history,
plus coverage view and Gate 3 (executable cases)."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationFailedError
from app.models import Requirement, TestCase, TestCaseReview, TestPoint
from app.services.assets.test_case_service import _get_test_case, transition_test_case


def _require_status(test_case: TestCase, expected: set[str], action: str) -> None:
    if test_case.status not in expected:
        raise ConflictError(
            f"Cannot {action} a test case in '{test_case.status}' status",
            {"test_case_id": test_case.id, "status": test_case.status},
        )


def submit_for_review(db: Session, test_case_id: int) -> TestCase:
    test_case = _get_test_case(db, test_case_id)
    _require_status(test_case, {"draft"}, "submit for review")
    if not test_case.steps:
        raise ValidationFailedError(
            "Cannot submit a test case without steps for review",
            {"test_case_id": test_case_id},
        )
    transition_test_case(db, test_case, "pending_review")
    db.commit()
    db.refresh(test_case)
    return _get_test_case(db, test_case_id)


def human_review(
    db: Session,
    test_case_id: int,
    verdict: str,
    issues: list[str] | None = None,
    suggestions: list[str] | None = None,
) -> TestCase:
    test_case = _get_test_case(db, test_case_id)
    _require_status(test_case, {"pending_review"}, "review")
    transition_test_case(db, test_case, verdict)  # pending_review -> approved/needs_work
    review = TestCaseReview(
        test_case_id=test_case_id,
        reviewer_type="human",
        verdict=verdict,
        scores=None,
        issues=issues or [],
        missing_scenarios=[],
        suggestions=suggestions or [],
    )
    db.add(review)
    db.commit()  # status transition + review record in one transaction
    db.refresh(test_case)
    return _get_test_case(db, test_case_id)


def resubmit_for_review(db: Session, test_case_id: int) -> TestCase:
    test_case = _get_test_case(db, test_case_id)
    _require_status(test_case, {"needs_work"}, "resubmit for review")
    transition_test_case(db, test_case, "pending_review")
    db.commit()
    db.refresh(test_case)
    return _get_test_case(db, test_case_id)


def list_reviews(db: Session, test_case_id: int) -> list[TestCaseReview]:
    # Ensure the case exists (404 otherwise).
    _get_test_case(db, test_case_id)
    return list(
        db.scalars(
            select(TestCaseReview)
            .where(TestCaseReview.test_case_id == test_case_id)
            .order_by(TestCaseReview.created_at.desc(), TestCaseReview.id.desc())
        )
    )


def create_ai_review(
    db: Session,
    test_case_id: int,
    verdict: str,
    scores: dict,
    issues: list[str],
    missing_scenarios: list[str],
    suggestions: list[str],
) -> TestCaseReview:
    # RUI-03a: AI review is an upsert — drop the previous AI review(s) so a repeated
    # AI review does not stack near-identical records. Human reviews are preserved.
    db.execute(
        delete(TestCaseReview).where(
            TestCaseReview.test_case_id == test_case_id,
            TestCaseReview.reviewer_type == "ai",
        )
    )
    review = TestCaseReview(
        test_case_id=test_case_id,
        reviewer_type="ai",
        verdict=verdict,
        scores=scores,
        issues=issues,
        missing_scenarios=missing_scenarios,
        suggestions=suggestions,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def uncovered_test_points(db: Session, project_id: int) -> list[dict]:
    """Test points in the project with no non-archived test case referencing them
    (R004-P004 SUGGESTION-1: archived cases do not count as coverage)."""
    test_points = list(
        db.scalars(
            select(TestPoint)
            .join(Requirement, TestPoint.requirement_id == Requirement.id)
            .where(Requirement.project_id == project_id, TestPoint.status != "archived")
            .order_by(TestPoint.id)
        )
    )
    covered_ids = set(
        db.scalars(
            select(TestCase.test_point_id).where(
                TestCase.project_id == project_id,
                TestCase.test_point_id.is_not(None),
                TestCase.status != "archived",
            )
        )
    )
    requirement_titles = {
        r.id: r.title
        for r in db.scalars(
            select(Requirement).where(Requirement.project_id == project_id)
        )
    }
    return [
        {
            "id": tp.id,
            "requirement_id": tp.requirement_id,
            "requirement_title": requirement_titles.get(tp.requirement_id, ""),
            "title": tp.title,
            "technique": tp.technique,
            "status": tp.status,
        }
        for tp in test_points
        if tp.id not in covered_ids
    ]


def executable_cases(db: Session, project_id: int) -> list[TestCase]:
    """Gate 3: only approved test cases are executable."""
    return list(
        db.scalars(
            select(TestCase)
            .options(selectinload(TestCase.steps))
            .where(TestCase.project_id == project_id, TestCase.status == "approved")
            .order_by(TestCase.case_id, TestCase.id)
        )
    )


def assert_cases_executable(db: Session, case_ids: list[int]) -> None:
    """Raise 409 CASE_NOT_APPROVED if any selected case is not approved."""
    for case_id in case_ids:
        test_case = db.get(TestCase, case_id)
        if test_case is None:
            raise NotFoundError("Test case not found", {"id": case_id})
        if test_case.status != "approved":
            raise AppError(
                409,
                "CASE_NOT_APPROVED",
                "Only approved test cases can be executed",
                {"test_case_id": case_id, "status": test_case.status},
            )
