"""Project endpoints.

Path layout follows P000 section 13:
  GET/POST        /projects
  GET/PATCH/DELETE /projects/{project_id}
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.assets import project_service

router = APIRouter(prefix="/projects")


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list:
    return project_service.list_projects(db)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    return project_service.create_project(db, payload)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = project_service.get_project(db, project_id)
    if project is None:
        raise NotFoundError("Project not found", {"id": project_id})
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = project_service.get_project(db, project_id)
    if project is None:
        raise NotFoundError("Project not found", {"id": project_id})
    return project_service.update_project(db, project, payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = project_service.get_project(db, project_id)
    if project is None:
        raise NotFoundError("Project not found", {"id": project_id})
    project_service.delete_project(db, project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
