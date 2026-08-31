"""Requirement endpoints.

Path layout follows P000 section 13:
  GET/POST        /projects/{project_id}/requirements
  GET/PATCH/DELETE /requirements/{requirement_id}
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas import RequirementCreate, RequirementRead, RequirementUpdate
from app.services.assets import project_service, requirement_service

router = APIRouter()


@router.get(
    "/projects/{project_id}/requirements", response_model=list[RequirementRead]
)
def list_requirements(project_id: int, db: Session = Depends(get_db)) -> list:
    if project_service.get_project(db, project_id) is None:
        raise NotFoundError("Project not found", {"id": project_id})
    return requirement_service.list_requirements(db, project_id)


@router.post(
    "/projects/{project_id}/requirements",
    response_model=RequirementRead,
    status_code=status.HTTP_201_CREATED,
)
def create_requirement(
    project_id: int, payload: RequirementCreate, db: Session = Depends(get_db)
):
    if project_service.get_project(db, project_id) is None:
        raise NotFoundError("Project not found", {"id": project_id})
    return requirement_service.create_requirement(db, project_id, payload)


@router.get("/requirements/{requirement_id}", response_model=RequirementRead)
def get_requirement(requirement_id: int, db: Session = Depends(get_db)):
    requirement = requirement_service.get_requirement(db, requirement_id)
    if requirement is None:
        raise NotFoundError("Requirement not found", {"id": requirement_id})
    return requirement


@router.patch("/requirements/{requirement_id}", response_model=RequirementRead)
def update_requirement(
    requirement_id: int, payload: RequirementUpdate, db: Session = Depends(get_db)
):
    requirement = requirement_service.get_requirement(db, requirement_id)
    if requirement is None:
        raise NotFoundError("Requirement not found", {"id": requirement_id})
    return requirement_service.update_requirement(db, requirement, payload)


@router.delete("/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requirement(requirement_id: int, db: Session = Depends(get_db)):
    requirement = requirement_service.get_requirement(db, requirement_id)
    if requirement is None:
        raise NotFoundError("Requirement not found", {"id": requirement_id})
    requirement_service.delete_requirement(db, requirement)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
