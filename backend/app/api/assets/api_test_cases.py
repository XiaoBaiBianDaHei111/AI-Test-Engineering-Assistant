"""APITestCase CRUD endpoints (Phase 9)."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas import ApiTestCaseCreate, ApiTestCaseRead, ApiTestCaseUpdate
from app.services.assets import api_test_case_service, project_service

router = APIRouter()


@router.get("/projects/{project_id}/api-test-cases", response_model=list[ApiTestCaseRead])
def list_api_test_cases(project_id: int, db: Session = Depends(get_db)):
    if project_service.get_project(db, project_id) is None:
        raise NotFoundError("Project not found", {"id": project_id})
    return api_test_case_service.list_api_test_cases(db, project_id)


@router.post(
    "/projects/{project_id}/api-test-cases",
    response_model=ApiTestCaseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_api_test_case(project_id: int, payload: ApiTestCaseCreate, db: Session = Depends(get_db)):
    return api_test_case_service.create_api_test_case(db, project_id, payload)


@router.get("/api-test-cases/{api_case_id}", response_model=ApiTestCaseRead)
def get_api_test_case(api_case_id: int, db: Session = Depends(get_db)):
    return api_test_case_service.get_api_test_case(db, api_case_id)


@router.patch("/api-test-cases/{api_case_id}", response_model=ApiTestCaseRead)
def update_api_test_case(api_case_id: int, payload: ApiTestCaseUpdate, db: Session = Depends(get_db)):
    return api_test_case_service.update_api_test_case(db, api_case_id, payload)


@router.delete("/api-test-cases/{api_case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_test_case(api_case_id: int, db: Session = Depends(get_db)):
    api_test_case_service.delete_api_test_case(db, api_case_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
