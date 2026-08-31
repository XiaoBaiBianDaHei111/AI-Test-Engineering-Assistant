"""GenerationRun lifecycle service (create / query / progress / finish)."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, InvalidTransitionError, NotFoundError, ValidationFailedError
from app.models import GenerationRun, Project, Requirement, TestPoint

# pending -> running -> completed / partial / failed
_RUN_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "failed"},
    "running": {"completed", "partial", "failed"},
    "completed": set(),
    "partial": set(),
    "failed": set(),
}

_TERMINAL = {"completed", "partial", "failed"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_run(db: Session, project_id: int, total_items: int) -> GenerationRun:
    run = GenerationRun(project_id=project_id, total_items=total_items)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_run(db: Session, run_id: int) -> GenerationRun | None:
    return db.get(GenerationRun, run_id)


def get_run_or_404(db: Session, run_id: int) -> GenerationRun:
    run = db.get(GenerationRun, run_id)
    if run is None:
        raise NotFoundError("Generation run not found", {"id": run_id})
    return run


def list_runs(db: Session, project_id: int, limit: int = 20) -> list[GenerationRun]:
    return list(
        db.scalars(
            select(GenerationRun)
            .where(GenerationRun.project_id == project_id)
            .order_by(GenerationRun.created_at.desc(), GenerationRun.id.desc())
            .limit(limit)
        )
    )


def _validate_transition(current: str, new: str) -> None:
    if current == new:
        return
    if new not in _RUN_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError(
            "Invalid generation run status transition", {"from": current, "to": new}
        )


def mark_running(db: Session, run: GenerationRun) -> GenerationRun:
    _validate_transition(run.status, "running")
    run.status = "running"
    run.started_at = _utcnow()
    db.commit()
    db.refresh(run)
    return run


def update_progress(
    db: Session,
    run: GenerationRun,
    *,
    processed_items: int | None = None,
    created_count: int | None = None,
    warnings: list | None = None,
    failed_items: list | None = None,
) -> GenerationRun:
    if processed_items is not None:
        run.processed_items = processed_items
    if created_count is not None:
        run.created_count = created_count
    if warnings is not None:
        run.warnings = warnings
    if failed_items is not None:
        run.failed_items = failed_items
    db.commit()
    db.refresh(run)
    return run


def finish_run(db: Session, run: GenerationRun, status: str) -> GenerationRun:
    if status not in _TERMINAL:
        raise InvalidTransitionError(
            "Invalid generation run terminal status", {"status": status}
        )
    _validate_transition(run.status, status)
    run.status = status
    run.ended_at = _utcnow()
    db.commit()
    db.refresh(run)
    return run


def get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", {"id": project_id})
    return project


def validate_test_points_for_generation(
    db: Session, project_id: int, test_point_ids: list[int]
) -> list[TestPoint]:
    """Validate the selected test points and return them (deduped, ordered).

    Rules (P003 §6.3 + R003-P003 MINOR-001):
      * not found -> 404;
      * belongs to another project -> 422;
      * test point not confirmed -> 409 ``TEST_POINT_NOT_CONFIRMED``;
      * its requirement not confirmed -> 409 ``REQUIREMENT_NOT_CONFIRMED``.
    """
    result: list[TestPoint] = []
    seen: set[int] = set()
    for tp_id in test_point_ids:
        if tp_id in seen:
            continue
        seen.add(tp_id)

        test_point = db.get(TestPoint, tp_id)
        if test_point is None:
            raise NotFoundError("Test point not found", {"test_point_id": tp_id})

        requirement = db.get(Requirement, test_point.requirement_id)
        if requirement is None or requirement.project_id != project_id:
            raise ValidationFailedError(
                "Test point does not belong to the project",
                {"test_point_id": tp_id, "project_id": project_id},
            )
        if test_point.status != "confirmed":
            raise AppError(
                409,
                "TEST_POINT_NOT_CONFIRMED",
                "Test point must be confirmed before generating test cases",
                {"test_point_id": tp_id, "status": test_point.status},
            )
        if requirement.status != "confirmed":
            raise AppError(
                409,
                "REQUIREMENT_NOT_CONFIRMED",
                "The test point's requirement must be confirmed (Gate 1)",
                {"requirement_id": requirement.id, "status": requirement.status},
            )
        result.append(test_point)
    return result
