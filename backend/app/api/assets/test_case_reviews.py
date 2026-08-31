"""TestCase review endpoints (M1) + coverage view + Gate 3 executable list."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas import TestCaseRead, TestCaseReviewCreate, TestCaseReviewRead
from app.services.assets import project_service, test_case_review_service

router = APIRouter()


@router.post("/test-cases/{test_case_id}/submit-review", response_model=TestCaseRead)
def submit_review(test_case_id: int, db: Session = Depends(get_db)):
    return test_case_review_service.submit_for_review(db, test_case_id)


@router.post("/test-cases/{test_case_id}/review", response_model=TestCaseRead)
def review_test_case(
    test_case_id: int, payload: TestCaseReviewCreate, db: Session = Depends(get_db)
):
    return test_case_review_service.human_review(
        db, test_case_id, payload.verdict.value, payload.issues, payload.suggestions
    )


@router.post("/test-cases/{test_case_id}/resubmit-review", response_model=TestCaseRead)
def resubmit_review(test_case_id: int, db: Session = Depends(get_db)):
    return test_case_review_service.resubmit_for_review(db, test_case_id)


@router.get("/test-cases/{test_case_id}/reviews", response_model=list[TestCaseReviewRead])
def list_reviews(test_case_id: int, db: Session = Depends(get_db)):
    return test_case_review_service.list_reviews(db, test_case_id)


@router.get("/projects/{project_id}/coverage/uncovered-test-points")
def uncovered_test_points(project_id: int, db: Session = Depends(get_db)):
    if project_service.get_project(db, project_id) is None:
        raise NotFoundError("Project not found", {"id": project_id})
    return test_case_review_service.uncovered_test_points(db, project_id)


@router.get("/projects/{project_id}/test-cases/executable", response_model=list[TestCaseRead])
def executable_cases(project_id: int, db: Session = Depends(get_db)):
    if project_service.get_project(db, project_id) is None:
        raise NotFoundError("Project not found", {"id": project_id})
    return test_case_review_service.executable_cases(db, project_id)
