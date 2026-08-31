"""TestCase endpoints.

Path layout follows P000 section 13:
  GET/POST         /projects/{project_id}/test-cases
  GET/PATCH/DELETE /test-cases/{test_case_id}
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas import TestCaseCreate, TestCaseRead, TestCaseUpdate
from app.services.assets import project_service, test_case_service

router = APIRouter()


@router.get("/projects/{project_id}/test-cases", response_model=list[TestCaseRead])
def list_test_cases(project_id: int, db: Session = Depends(get_db)) -> list:
    if project_service.get_project(db, project_id) is None:
        raise NotFoundError("Project not found", {"id": project_id})
    return test_case_service.list_test_cases(db, project_id)


@router.post(
    "/projects/{project_id}/test-cases",
    response_model=TestCaseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_test_case(
    project_id: int, payload: TestCaseCreate, db: Session = Depends(get_db)
):
    return test_case_service.create_test_case(db, project_id, payload)


@router.get("/test-cases/{test_case_id}", response_model=TestCaseRead)
def get_test_case(test_case_id: int, db: Session = Depends(get_db)):
    return test_case_service.get_test_case(db, test_case_id)


@router.patch("/test-cases/{test_case_id}", response_model=TestCaseRead)
def update_test_case(
    test_case_id: int, payload: TestCaseUpdate, db: Session = Depends(get_db)
):
    return test_case_service.update_test_case(db, test_case_id, payload)


@router.delete("/test-cases/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_case(test_case_id: int, db: Session = Depends(get_db)):
    test_case_service.delete_test_case(db, test_case_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
