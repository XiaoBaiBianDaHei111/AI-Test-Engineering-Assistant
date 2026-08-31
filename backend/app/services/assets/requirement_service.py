"""Requirement business logic."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Requirement
from app.schemas import RequirementCreate, RequirementUpdate
from app.services.state_machine import REQUIREMENT_TRANSITIONS, validate_transition


def list_requirements(db: Session, project_id: int) -> list[Requirement]:
    return list(
        db.scalars(
            select(Requirement)
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.created_at.desc(), Requirement.id.desc())
        )
    )


def get_requirement(db: Session, requirement_id: int) -> Requirement | None:
    return db.get(Requirement, requirement_id)


def create_requirement(db: Session, project_id: int, data: RequirementCreate) -> Requirement:
    requirement = Requirement(project_id=project_id, **data.model_dump(mode="json"))
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


def update_requirement(
    db: Session, requirement: Requirement, data: RequirementUpdate
) -> Requirement:
    fields = data.model_dump(exclude_unset=True, mode="json")

    if "status" in fields:
        validate_transition(
            "requirement", requirement.status, fields["status"], REQUIREMENT_TRANSITIONS
        )

    for field, value in fields.items():
        setattr(requirement, field, value)
    db.commit()
    db.refresh(requirement)
    return requirement


def delete_requirement(db: Session, requirement: Requirement) -> None:
    db.delete(requirement)
    db.commit()
