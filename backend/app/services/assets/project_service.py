"""Project business logic."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models import Project
from app.schemas import ProjectCreate, ProjectUpdate


def list_projects(db: Session) -> list[Project]:
    return list(
        db.scalars(
            select(Project).order_by(Project.created_at.desc(), Project.id.desc())
        )
    )


def get_project(db: Session, project_id: int) -> Project | None:
    return db.get(Project, project_id)


def create_project(db: Session, data: ProjectCreate) -> Project:
    existing = db.scalar(select(Project).where(Project.name == data.name))
    if existing is not None:
        raise ConflictError("Project name already exists", {"name": data.name})
    project = Project(name=data.name, description=data.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: Project, data: ProjectUpdate) -> Project:
    if data.name is not None and data.name != project.name:
        existing = db.scalar(select(Project).where(Project.name == data.name))
        if existing is not None:
            raise ConflictError("Project name already exists", {"name": data.name})
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> None:
    db.delete(project)
    db.commit()
