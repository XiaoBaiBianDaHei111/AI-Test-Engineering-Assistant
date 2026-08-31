"""Batch test-case generation orchestrator (run-driven, background task)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import TestCase, TestCaseStep, TestPoint
from app.services.ai.agents.test_case_writer import generate_for_test_point
from app.services.ai.providers import get_provider
from app.services.assets.generation_run_service import (
    finish_run,
    get_run_or_404,
    mark_running,
    update_progress,
)
from app.services.assets.test_case_service import _generate_case_id


def check_priority_distribution(
    techniques: set[str], priorities: set[str]
) -> list[str]:
    """AC-3-04 post-check: main-flow scenarios need at least one case <= P1."""
    warnings: list[str] = []
    main_techniques = {"equivalence", "state_transition"}
    if main_techniques & techniques and not {"P0", "P1"} & priorities:
        warnings.append(
            "主流程场景（equivalence/state_transition）缺少 priority ≤ P1 的用例"
        )
    return warnings


def _insert_case(db: Session, run, item: dict, test_point: TestPoint) -> None:
    steps = item["steps"]
    case = TestCase(
        project_id=run.project_id,
        requirement_id=test_point.requirement_id,
        test_point_id=test_point.id,
        case_id=_generate_case_id(db, run.project_id),
        title=item["title"],
        priority=item["priority"],
        type=item["type"],
        precondition=item["precondition"],
        test_data=item["test_data"],
        # R003-P003 Suggestion 1: copy the final step's expected_result up.
        expected_result=steps[-1]["expected_result"],
        status="draft",
        source="ai",
    )
    db.add(case)
    db.flush()  # assign case.id for step FKs + make case_id visible for the next
    for index, step in enumerate(steps, start=1):
        db.add(
            TestCaseStep(
                test_case_id=case.id,
                step_number=index,
                action=step["action"],
                expected_result=step["expected_result"],
            )
        )


def generate_batch(session_factory, run_id: int, test_point_ids: list[int]) -> None:
    """Run the whole batch. Always leaves the run in a terminal state.

    R003-P003 MINOR-002: any unexpected exception is caught, the run is marked
    ``failed`` (with an error entry) rather than being left ``running``.
    """
    db = session_factory()
    run = None
    try:
        run = get_run_or_404(db, run_id)
        _run_batch(db, run, test_point_ids)
    except Exception as exc:  # noqa: BLE001 - background-task safety net
        logger.exception("generate_batch crashed for run %s", run_id)
        if run is not None:
            try:
                db.rollback()
                current = list(run.failed_items or [])
                current.append({"reason": f"unexpected error: {exc}", "error_code": "INTERNAL"})
                run = get_run_or_404(db, run_id)
                update_progress(db, run, failed_items=current)
                if run.status not in {"completed", "partial", "failed"}:
                    finish_run(db, run, "failed")
            except Exception:  # noqa: BLE001
                logger.exception("failed to mark run %s failed", run_id)
    finally:
        db.close()


def _run_batch(db: Session, run, test_point_ids: list[int]) -> None:
    run = mark_running(db, run)

    test_points: list[TestPoint] = []
    for tp_id in test_point_ids:
        tp = db.get(TestPoint, tp_id)
        if tp is not None:
            test_points.append(tp)

    provider = get_provider()
    existing_titles = {
        tc.title.strip().lower()
        for tc in db.scalars(
            select(TestCase).where(TestCase.project_id == run.project_id)
        )
    }

    warnings: list[str] = []
    failed_items: list[dict] = []
    created_count = 0
    processed = 0
    techniques: set[str] = set()
    priorities: set[str] = set()

    for tp in test_points:
        techniques.add(tp.technique)
        try:
            result = generate_for_test_point(db, tp, provider)
            warnings.extend(result["warnings"])
            for item in result["items"]:
                key = item["title"].strip().lower()
                if key in existing_titles:
                    warnings.append(f"与已有用例重复，已跳过：{item['title']}")
                    continue
                existing_titles.add(key)
                _insert_case(db, run, item, tp)
                created_count += 1
                priorities.add(item["priority"])
        except Exception as exc:  # noqa: BLE001 - one point failure must not abort the batch
            code = getattr(exc, "code", None) or "INTERNAL"
            message = getattr(exc, "message", None) or str(exc)
            failed_items.append(
                {"test_point_id": tp.id, "reason": message, "error_code": code}
            )

        processed += 1
        update_progress(
            db, run, processed_items=processed, created_count=created_count,
            warnings=warnings, failed_items=failed_items,
        )

    # AC-3-04 priority-distribution post-check (warning only, not a hard failure).
    warnings.extend(check_priority_distribution(techniques, priorities))
    update_progress(db, run, warnings=warnings)

    if created_count == 0 and failed_items:
        status = "failed"
    elif failed_items:
        status = "partial"
    else:
        status = "completed"
    finish_run(db, run, status)
