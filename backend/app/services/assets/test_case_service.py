"""TestCase / TestCaseStep business logic."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models import Project, Requirement, TestCase, TestCaseStep, TestPoint
from app.schemas import TestCaseCreate, TestCaseUpdate
from app.services.state_machine import TEST_CASE_TRANSITIONS, validate_transition

_CASE_ID_PATTERN = re.compile(r"^TC-\d+$")

# Fields whose modification counts as a "content edit" (triggers re-review reset).
_CONTENT_FIELDS = {
    "title", "priority", "type", "precondition", "test_data",
    "expected_result", "steps", "requirement_id", "test_point_id",
}


def _get_test_case(db: Session, test_case_id: int) -> TestCase:
    test_case = db.scalar(
        select(TestCase)
        .options(selectinload(TestCase.steps))
        .where(TestCase.id == test_case_id)
    )
    if test_case is None:
        raise NotFoundError("Test case not found", {"id": test_case_id})
    return test_case


def list_test_cases(db: Session, project_id: int) -> list[TestCase]:
    return list(
        db.scalars(
            select(TestCase)
            .options(selectinload(TestCase.steps))
            .where(TestCase.project_id == project_id)
            .order_by(TestCase.case_id, TestCase.id)
        )
    )


def get_test_case(db: Session, test_case_id: int) -> TestCase:
    return _get_test_case(db, test_case_id)


def _validate_requirement(db: Session, project_id: int, requirement_id: int | None) -> None:
    """Ensure a referenced requirement exists and belongs to the same project."""
    if requirement_id is None:
        return
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise NotFoundError("Requirement not found", {"requirement_id": requirement_id})
    if requirement.project_id != project_id:
        raise ValidationFailedError(
            "Requirement does not belong to the project",
            {"requirement_id": requirement_id, "project_id": project_id},
        )


def _resolve_test_point(
    db: Session, project_id: int, requirement_id: int | None, test_point_id: int | None
) -> int | None:
    """Validate ``test_point_id`` and keep it consistent with ``requirement_id``.

    Rules (R003 MINOR-002):
      * the test point must exist and belong to the same project (checked via
        the test point's requirement, since TestPoint has no project_id);
      * if both are set, the test point's requirement must equal the requirement;
      * if ``requirement_id`` is None, it is derived from the test point so the
        traceability chain (test case -> test point -> requirement) never breaks.

    Returns the (possibly derived) requirement_id.
    """
    if test_point_id is None:
        return requirement_id
    test_point = db.get(TestPoint, test_point_id)
    if test_point is None:
        raise NotFoundError("Test point not found", {"test_point_id": test_point_id})
    tp_requirement = db.get(Requirement, test_point.requirement_id)
    if tp_requirement is None or tp_requirement.project_id != project_id:
        raise ValidationFailedError(
            "Test point does not belong to the project",
            {"test_point_id": test_point_id, "project_id": project_id},
        )
    if requirement_id is not None and requirement_id != test_point.requirement_id:
        raise ValidationFailedError(
            "Test point belongs to a different requirement",
            {
                "test_point_id": test_point_id,
                "requirement_id": requirement_id,
                "test_point_requirement_id": test_point.requirement_id,
            },
        )
    return test_point.requirement_id


def _generate_case_id(db: Session, project_id: int) -> str:
    """Generate the next project-scoped id, e.g. TC-001, TC-002, ..."""
    max_number = 0
    rows = db.execute(
        select(TestCase.case_id).where(TestCase.project_id == project_id)
    ).all()
    for (case_id,) in rows:
        match = _CASE_ID_PATTERN.fullmatch(case_id)
        if match:
            max_number = max(max_number, int(match.group(0)[3:]))
    return f"TC-{max_number + 1:03d}"


def _ensure_unique_case_id(db: Session, project_id: int, case_id: str) -> None:
    existing = db.scalar(
        select(TestCase.id).where(
            TestCase.project_id == project_id, TestCase.case_id == case_id
        )
    )
    if existing is not None:
        raise ConflictError(
            "case_id already exists in this project", {"case_id": case_id}
        )


def _build_steps(test_case: TestCase, steps: list) -> list[TestCaseStep]:
    return [
        TestCaseStep(
            test_case_id=test_case.id,
            step_number=step.step_number,
            action=step.action,
            expected_result=step.expected_result,
        )
        for step in steps
    ]


def create_test_case(db: Session, project_id: int, data: TestCaseCreate) -> TestCase:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", {"id": project_id})

    _validate_requirement(db, project_id, data.requirement_id)
    requirement_id = _resolve_test_point(db, project_id, data.requirement_id, data.test_point_id)

    if data.case_id:
        if not _CASE_ID_PATTERN.fullmatch(data.case_id):
            raise ValidationFailedError(
                "case_id must match pattern TC-<number>", {"case_id": data.case_id}
            )
        _ensure_unique_case_id(db, project_id, data.case_id)
        case_id = data.case_id
    else:
        case_id = _generate_case_id(db, project_id)

    fields = data.model_dump(mode="json", exclude={"case_id", "steps"})
    fields["requirement_id"] = requirement_id
    test_case = TestCase(project_id=project_id, case_id=case_id, **fields)
    db.add(test_case)
    db.flush()  # assign test_case.id for step foreign keys
    test_case.steps = _build_steps(test_case, data.steps)
    db.commit()
    db.refresh(test_case)
    return _get_test_case(db, test_case.id)


def transition_test_case(db: Session, test_case: TestCase, new_status: str) -> TestCase:
    """Validate and apply a status transition (no commit — caller composes it)."""
    validate_transition("test case", test_case.status, new_status, TEST_CASE_TRANSITIONS)
    test_case.status = new_status
    return test_case


def update_test_case(db: Session, test_case_id: int, data: TestCaseUpdate) -> TestCase:
    test_case = _get_test_case(db, test_case_id)
    fields = data.model_dump(exclude_unset=True, mode="json")

    if "requirement_id" in fields:
        _validate_requirement(db, test_case.project_id, fields["requirement_id"])

    final_requirement_id = fields.get("requirement_id", test_case.requirement_id)
    final_test_point_id = fields.get("test_point_id", test_case.test_point_id)
    if final_test_point_id is not None:
        resolved = _resolve_test_point(
            db, test_case.project_id, final_requirement_id, final_test_point_id
        )
        if final_requirement_id is None:
            fields["requirement_id"] = resolved

    if data.steps is not None:
        # Replace the full step list: delete existing steps first and flush so the
        # unique (test_case_id, step_number) constraint does not fire during insert.
        for old_step in list(test_case.steps):
            db.delete(old_step)
        db.flush()
        test_case.steps = _build_steps(test_case, data.steps)

    # R004-A004 MINOR-001: review/execution statuses must flow through the review
    # endpoints (or execution service), not a raw PATCH. Only administrative
    # statuses (draft / archived) may be set directly via PATCH.
    if "status" in fields and fields["status"] not in {"draft", "archived"}:
        raise ValidationFailedError(
            "status must be changed via the review endpoints (submit/review/resubmit)",
            {"status": fields["status"]},
        )

    # R004-P004 MINOR-001: editing the content of an approved / pending_review
    # case invalidates its review, so it is reset to needs_work for re-review.
    content_changed = bool(set(fields) & _CONTENT_FIELDS)
    if content_changed and test_case.status in {"approved", "pending_review"} and "status" not in fields:
        fields["status"] = "needs_work"

    if "status" in fields:
        validate_transition("test case", test_case.status, fields["status"], TEST_CASE_TRANSITIONS)

    for field, value in fields.items():
        if field == "steps":
            continue
        setattr(test_case, field, value)

    db.commit()
    db.refresh(test_case)
    return _get_test_case(db, test_case.id)


def delete_test_case(db: Session, test_case_id: int) -> None:
    test_case = _get_test_case(db, test_case_id)
    db.delete(test_case)
    db.commit()
