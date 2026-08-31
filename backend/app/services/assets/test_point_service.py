"""TestPoint business logic (CRUD + status transitions)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import Requirement, TestPoint
from app.schemas import TestPointCreate, TestPointUpdate
from app.services.state_machine import TEST_POINT_TRANSITIONS, validate_transition


def list_test_points(db: Session, requirement_id: int) -> list[TestPoint]:
    return list(
        db.scalars(
            select(TestPoint)
            .where(TestPoint.requirement_id == requirement_id)
            .order_by(TestPoint.created_at, TestPoint.id)
        )
    )


def get_test_point(db: Session, test_point_id: int) -> TestPoint | None:
    return db.get(TestPoint, test_point_id)


def get_test_point_or_404(db: Session, test_point_id: int) -> TestPoint:
    test_point = db.get(TestPoint, test_point_id)
    if test_point is None:
        raise NotFoundError("Test point not found", {"id": test_point_id})
    return test_point


def create_test_point(db: Session, requirement_id: int, data: TestPointCreate) -> TestPoint:
    test_point = TestPoint(requirement_id=requirement_id, **data.model_dump(mode="json"))
    db.add(test_point)
    db.commit()
    db.refresh(test_point)
    return test_point


def update_test_point(db: Session, test_point: TestPoint, data: TestPointUpdate) -> TestPoint:
    fields = data.model_dump(exclude_unset=True, mode="json")

    if "status" in fields:
        validate_transition(
            "test point", test_point.status, fields["status"], TEST_POINT_TRANSITIONS
        )

    for field, value in fields.items():
        setattr(test_point, field, value)
    db.commit()
    db.refresh(test_point)
    return test_point


def delete_test_point(db: Session, test_point: TestPoint) -> None:
    db.delete(test_point)
    db.commit()


def get_requirement_or_404(db: Session, requirement_id: int) -> Requirement:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise NotFoundError("Requirement not found", {"id": requirement_id})
    return requirement
