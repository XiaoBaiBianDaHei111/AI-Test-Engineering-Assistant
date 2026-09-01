"""TestRun lifecycle service + batch orchestration (Phase 5) + evidence persistence (Phase 6).

The batch task runs in a background thread with its own session (Phase 3
pattern); per-case failures are isolated and the run always reaches a terminal
state. Evidence is written best-effort (a write failure never blocks the case/run
result). ``driver``/``api_runner`` are injectable for dependency inversion (used
by tests with local stubs, not project mock infrastructure).
"""

import json
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.logging import logger
from app.execution.api_runner import ApiRunner
from app.execution.runner import ScriptExecutor, get_driver
from app.models import (
    APITestCase,
    Evidence,
    Project,
    TestCase,
    TestRun,
    TestRunCase,
    TestStepResult,
    TraceParse,
)
from app.services.ai.agents.script_generator import generate_script
from app.services.ai.providers import get_provider
from app.services.analysis.trace_parser import TraceParseError, parse_trace
from app.services.assets import evidence_service
from app.services.assets.test_case_review_service import assert_cases_executable
from app.services.assets.test_case_service import transition_test_case

# In-memory cancel flags (single-process personal project).
_cancel_requests: set[int] = set()
_cancel_lock = threading.Lock()


def request_cancel(run_id: int) -> None:
    with _cancel_lock:
        _cancel_requests.add(run_id)


def clear_cancel(run_id: int) -> None:
    """Drop the cancel flag once the run reaches a terminal state (R005-A005 SUGGESTION-1)."""
    with _cancel_lock:
        _cancel_requests.discard(run_id)


def is_cancelled(run_id: int) -> bool:
    with _cancel_lock:
        return run_id in _cancel_requests


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def create_run(
    db: Session,
    project_id: int,
    test_case_ids: list[int],
    config: dict,
    api_case_ids: list[int] | None = None,
) -> TestRun:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", {"id": project_id})

    test_case_ids = test_case_ids or []
    api_case_ids = api_case_ids or []
    if not test_case_ids and not api_case_ids:
        raise ValidationFailedError(
            "At least one of test_case_ids / api_case_ids must be provided",
            {"project_id": project_id},
        )
    assert_cases_executable(db, test_case_ids)  # Gate 3 (UI only)

    # Validate API cases: must be active and belong to the project.
    api_cases: list[APITestCase] = []
    for api_case_id in api_case_ids:
        api_case = db.get(APITestCase, api_case_id)
        if api_case is None:
            raise NotFoundError("API test case not found", {"id": api_case_id})
        if api_case.status != "active":
            raise ValidationFailedError(
                "Only active API test cases can be executed",
                {"api_case_id": api_case_id, "status": api_case.status},
            )
        if api_case.project_id != project_id:
            raise ValidationFailedError(
                "API test case does not belong to the project",
                {"api_case_id": api_case_id, "project_id": project_id},
            )
        api_cases.append(api_case)

    run = TestRun(
        project_id=project_id,
        name=f"Run-{datetime.now():%Y%m%d-%H%M%S}",
        config=config,
    )
    db.add(run)
    db.flush()
    for test_case_id in test_case_ids:
        test_case = db.get(TestCase, test_case_id)
        run_case = TestRunCase(
            run_id=run.id,
            test_case_id=test_case_id,
            kind="ui",
            case_label=f"{test_case.case_id} {test_case.title}",
        )
        db.add(run_case)
    for api_case in api_cases:
        run_case = TestRunCase(
            run_id=run.id,
            test_case_id=None,
            kind="api",
            api_case_id=api_case.id,
            case_label=api_case.name,
        )
        db.add(run_case)
    db.commit()
    db.refresh(run)
    return run


def get_run_or_404(db: Session, run_id: int) -> TestRun:
    run = db.scalar(
        select(TestRun)
        .options(selectinload(TestRun.run_cases))
        .where(TestRun.id == run_id)
    )
    if run is None:
        raise NotFoundError("Test run not found", {"id": run_id})
    return run


def list_runs(db: Session, project_id: int, limit: int = 20) -> list[TestRun]:
    return list(
        db.scalars(
            select(TestRun)
            .options(selectinload(TestRun.run_cases))
            .where(TestRun.project_id == project_id)
            .order_by(TestRun.created_at.desc(), TestRun.id.desc())
            .limit(limit)
        )
    )


def get_run_case_or_404(db: Session, run_case_id: int) -> TestRunCase:
    run_case = db.get(TestRunCase, run_case_id)
    if run_case is None:
        raise NotFoundError("Run case not found", {"id": run_case_id})
    return run_case


def get_case_detail(db: Session, run_case_id: int) -> TestRunCase:
    run_case = db.scalar(
        select(TestRunCase)
        .options(selectinload(TestRunCase.step_results))
        .where(TestRunCase.id == run_case_id)
    )
    if run_case is None:
        raise NotFoundError("Run case not found", {"id": run_case_id})
    return run_case


def cancel_run(db: Session, run_id: int) -> TestRun:
    run = get_run_or_404(db, run_id)
    request_cancel(run_id)
    for run_case in run.run_cases:
        if run_case.status == "pending":
            run_case.status = "skipped"
    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# Progress / result helpers
# ---------------------------------------------------------------------------

def _mark_running(db: Session, run: TestRun) -> TestRun:
    run.status = "running"
    run.started_at = datetime.utcnow()
    db.commit()
    db.refresh(run)
    return run


def _add_step_result(db: Session, run_case: TestRunCase, step_outcome) -> TestStepResult:
    step_result = TestStepResult(
        run_case_id=run_case.id,
        step_number=step_outcome.step_number,
        description=step_outcome.description,
        status=step_outcome.status,
        message=step_outcome.message,
        duration_ms=step_outcome.duration_ms,
        element_found=step_outcome.element_found,
    )
    db.add(step_result)
    return step_result


def _finish_case(db: Session, run_case: TestRunCase, status: str, *, duration_ms=0, error="", script_path="") -> None:
    run_case.status = status
    run_case.duration_ms = duration_ms
    run_case.error = error
    run_case.script_path = script_path


def _finish_run(db: Session, run: TestRun, status: str) -> TestRun:
    run.status = status
    run.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(run)
    clear_cancel(run.id)  # R005-A005 SUGGESTION-1: terminal state clears the flag
    return run


def save_script(run_id: int, run_case_id: int, script_text: str) -> str:
    directory = Path(settings.artifacts_dir) / str(run_id) / settings.run_script_subdir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run_case_id}.py"
    path.write_text(script_text, encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# Evidence persistence (Phase 6) — best-effort, never blocks the case/run result
# ---------------------------------------------------------------------------

def _ingest_trace_parse(db: Session, evidence: Evidence, trace_bytes: bytes) -> None:
    """Parse trace evidence into a TraceParse row (M2); failure records meta only."""
    try:
        parsed = parse_trace(trace_bytes)
    except TraceParseError as exc:
        logger.warning("trace parse failed for evidence %s: %s", evidence.id, exc)
        evidence.meta = {**(evidence.meta or {}), "trace_parse_error": str(exc)}
        return
    db.add(TraceParse(
        evidence_id=evidence.id,
        actions=parsed["actions"],
        network=parsed["network"],
        console=parsed["console"],
        snapshots=parsed["snapshots"],
    ))
    if parsed.get("truncated"):
        evidence.meta = {**(evidence.meta or {}), "truncated": True}


def _persist_case_evidence(
    db: Session, run: TestRun, run_case: TestRunCase, outcome, step_results: list[TestStepResult]
) -> None:
    """Write the outcome's evidence (screenshots/console/network/trace) + link screenshot_ref.

    Wrapped in a single try/except so an evidence write failure never blocks the
    case/run result (D4). Screenshots link to failed step results via
    ``screenshot_ref`` (R006-P006 SUGGESTION-3: str(Evidence.id)).
    """
    try:
        evidence_ids = list(run_case.evidence_ids or [])
        screenshot_ids: dict[int, str] = {}

        for shot in outcome.evidence.screenshots:
            ev = evidence_service.save_evidence(
                db, run.id, run_case.id, "screenshot",
                f"{run_case.id}_{shot.step_number}.png", shot.bytes,
                meta={"step_number": shot.step_number, "description": shot.description},
            )
            evidence_ids.append(ev.id)
            screenshot_ids[shot.step_number] = str(ev.id)

        console_data = [asdict(c) for c in outcome.evidence.console]
        ev = evidence_service.save_evidence(
            db, run.id, run_case.id, "console", f"{run_case.id}.json",
            json.dumps(console_data, ensure_ascii=False).encode("utf-8"),
        )
        evidence_ids.append(ev.id)

        network_data = [asdict(n) for n in outcome.evidence.network]
        ev = evidence_service.save_evidence(
            db, run.id, run_case.id, "network", f"{run_case.id}.json",
            json.dumps(network_data, ensure_ascii=False).encode("utf-8"),
        )
        evidence_ids.append(ev.id)

        trace_ev = evidence_service.save_evidence(
            db, run.id, run_case.id, "trace", f"{run_case.id}.zip", outcome.evidence.trace_bytes,
        )
        evidence_ids.append(trace_ev.id)
        _ingest_trace_parse(db, trace_ev, outcome.evidence.trace_bytes)

        # Link each step's screenshot (R006-P006 SUGGESTION-3: str(Evidence.id)).
        for step_result in step_results:
            if step_result.step_number in screenshot_ids:
                step_result.screenshot_ref = screenshot_ids[step_result.step_number]

        run_case.evidence_ids = evidence_ids
        db.commit()
    except Exception as exc:  # noqa: BLE001 - evidence is additive, never fatal
        logger.warning("evidence write failed for run_case %s: %s", run_case.id, exc)
        db.rollback()


def _write_run_log(db: Session, run: TestRun) -> None:
    """Write a run-level execution log (Evidence kind=log, run_case_id=None)."""
    try:
        lines = [
            f"run {run.id} status={run.status}",
            f"started_at={run.started_at}",
            f"ended_at={run.ended_at}",
        ]
        for run_case in list(run.run_cases):
            lines.append(
                f"case {run_case.id} [{run_case.case_label}] -> {run_case.status} ({run_case.duration_ms}ms)"
            )
        evidence_service.save_evidence(
            db, run.id, None, "log", f"run_{run.id}.log",
            ("\n".join(lines) + "\n").encode("utf-8"),
            meta={"run_status": run.status},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("run log write failed for run %s: %s", run.id, exc)


def _clear_case_evidence(db: Session, run_case_id: int) -> None:
    """Delete a run case's evidence + trace parses (rerun replaces them)."""
    evidence_ids = db.scalars(select(Evidence.id).where(Evidence.run_case_id == run_case_id)).all()
    if evidence_ids:
        db.execute(delete(TraceParse).where(TraceParse.evidence_id.in_(evidence_ids)))
        db.execute(delete(Evidence).where(Evidence.id.in_(evidence_ids)))
        db.flush()


def _maybe_analyze(db: Session, run_case: TestRunCase) -> None:
    """Auto-trigger failure analysis for failed/blocked cases (isolated, D5).

    A failure here must never affect the run/case result (D2); the analysis is an
    additive value and the frontend offers a retry on 404.
    """
    if run_case.status not in {"failed", "blocked"}:
        return
    try:
        from app.services.analysis.failure_analyzer import analyze_failure

        analyze_failure(db, run_case.id)
    except Exception as exc:  # noqa: BLE001 - analysis is additive, never fatal
        logger.warning("failure analysis failed for run_case %s: %s", run_case.id, exc)


def _maybe_generate_report(db: Session, run: TestRun) -> None:
    """Auto-generate the report when a run reaches completed/failed (isolated, D5).

    Report generation is deterministic (no LLM) and must never block the run.
    """
    if run.status not in {"completed", "failed"}:
        return
    try:
        from app.services.assets.test_report_service import generate_report

        generate_report(db, run.id)
    except Exception as exc:  # noqa: BLE001 - report is additive, never fatal
        logger.warning("report generation failed for run %s: %s", run.id, exc)


# ---------------------------------------------------------------------------
# Batch orchestration (background task)
# ---------------------------------------------------------------------------

def run_batch(
    session_factory,
    run_id: int,
    driver: ScriptExecutor | None = None,
    api_runner: ApiRunner | None = None,
) -> None:
    db = session_factory()
    run = None
    try:
        run = get_run_or_404(db, run_id)
        _run_batch(db, run, driver or get_driver(), api_runner or ApiRunner())
    except Exception:  # noqa: BLE001 - safety net, run must reach terminal state
        logger.exception("run_batch crashed for run %s", run_id)
        if run is not None:
            try:
                db.rollback()
                run = get_run_or_404(db, run_id)
                if run.status not in {"completed", "failed", "cancelled"}:
                    _finish_run(db, run, "failed")
            except Exception:  # noqa: BLE001
                logger.exception("failed to mark run %s failed", run_id)
    finally:
        clear_cancel(run_id)  # safety net: flag must not outlive the run
        db.close()


def _run_batch(db: Session, run: TestRun, driver: ScriptExecutor, api_runner: ApiRunner) -> None:
    run = _mark_running(db, run)
    provider = get_provider()
    run_cases = list(run.run_cases)

    for run_case in run_cases:
        if is_cancelled(run.id):
            break
        if run_case.kind == "api":
            _process_api_case(db, run, run_case, api_runner)
        else:
            _process_case(db, run, run_case, driver, provider)

    if is_cancelled(run.id):
        final = _finish_run(db, run, "cancelled")
    elif any(c.status in {"failed", "blocked"} for c in run_cases):
        final = _finish_run(db, run, "failed")
    else:
        final = _finish_run(db, run, "completed")
    _write_run_log(db, final)
    _maybe_generate_report(db, final)


def _process_api_case(db: Session, run: TestRun, run_case: TestRunCase, api_runner: ApiRunner) -> None:
    api_case = db.get(APITestCase, run_case.api_case_id) if run_case.api_case_id else None
    if api_case is None:
        _finish_case(db, run_case, "blocked", error="接口用例已删除")
        db.commit()
        _maybe_analyze(db, run_case)
        return

    run_case.status = "running"
    db.commit()

    base_url = run.config.get("base_url", "http://localhost:8001")
    outcome = api_runner.execute(api_case, base_url)
    for step_outcome in outcome.steps:
        _add_step_result(db, run_case, step_outcome)

    status = "passed" if outcome.status == "passed" else "failed"
    _finish_case(db, run_case, status, duration_ms=outcome.duration_ms, error=outcome.error)
    db.commit()
    _persist_api_evidence(db, run, run_case, outcome)

    # D5: no executed closure for API cases (executed is UI-only semantics).
    if status != "passed":
        _maybe_analyze(db, run_case)


def _persist_api_evidence(db: Session, run: TestRun, run_case: TestRunCase, outcome) -> None:
    """Persist the API network evidence (with truncated response body, D3)."""
    try:
        network_data = [asdict(n) for n in outcome.evidence.network]
        evidence = evidence_service.save_evidence(
            db, run.id, run_case.id, "network", f"{run_case.id}.json",
            json.dumps(network_data, ensure_ascii=False).encode("utf-8"),
            meta={"body_truncated": any(n.body_truncated for n in outcome.evidence.network)},
        )
        run_case.evidence_ids = list(run_case.evidence_ids or []) + [evidence.id]
        db.commit()
    except Exception as exc:  # noqa: BLE001 - evidence is additive, never fatal
        logger.warning("API evidence write failed for run_case %s: %s", run_case.id, exc)
        db.rollback()


def _process_case(db: Session, run: TestRun, run_case: TestRunCase, driver: ScriptExecutor, provider) -> None:
    test_case = db.get(TestCase, run_case.test_case_id)
    if test_case is None:
        _finish_case(db, run_case, "blocked", error="测试用例已删除")
        db.commit()
        _maybe_analyze(db, run_case)
        return

    run_case.status = "running"
    db.commit()

    # 1. generate + assemble + static-validate (repair <=2)
    result = generate_script(db, test_case, run.config, provider)
    if result["status"] == "failed":
        _finish_case(db, run_case, "blocked", error=f"脚本生成失败：{result['error_code']}")
        db.commit()
        _maybe_analyze(db, run_case)
        return

    script_text = result["script_text"]
    script_path = save_script(run.id, run_case.id, script_text)

    # 2. execute step-by-step + persist evidence (best-effort)
    outcome = driver.execute(script_text, run.config)
    step_results = [_add_step_result(db, run_case, step_outcome) for step_outcome in outcome.steps]

    status = "passed" if outcome.status == "passed" else "failed"
    _finish_case(db, run_case, status, duration_ms=outcome.duration_ms, error=outcome.error, script_path=script_path)
    db.commit()
    _persist_case_evidence(db, run, run_case, outcome, step_results)

    # 3. status closure: passed -> executed (R004-A004 SUGGESTION-3)
    if status == "passed":
        transition_test_case(db, test_case, "executed")
        db.commit()
    else:
        _maybe_analyze(db, run_case)


# ---------------------------------------------------------------------------
# Single-case rerun (synchronous; reuses the existing script, no re-generation)
# ---------------------------------------------------------------------------

def assert_rerunnable(run_case: TestRunCase) -> None:
    if run_case.status not in {"failed", "blocked"}:
        raise ConflictError(
            "Only failed/blocked run cases can be rerun",
            {"run_case_id": run_case.id, "status": run_case.status},
        )


def rerun_case(
    db: Session,
    run_case_id: int,
    driver: ScriptExecutor | None = None,
    api_runner: ApiRunner | None = None,
) -> TestRunCase:
    run_case = get_run_case_or_404(db, run_case_id)
    assert_rerunnable(run_case)
    run = get_run_or_404(db, run_case.run_id)

    for step in list(run_case.step_results):
        db.delete(step)
    _clear_case_evidence(db, run_case_id)  # rerun replaces old evidence
    run_case.evidence_ids = []
    db.flush()

    if run_case.kind == "api":
        # R009 SUGGESTION-1: API rerun re-reads the latest APITestCase (no script).
        api_case = db.get(APITestCase, run_case.api_case_id) if run_case.api_case_id else None
        if api_case is None:
            _finish_case(db, run_case, "blocked", error="接口用例已删除")
            db.commit()
            return get_case_detail(db, run_case_id)
        base_url = run.config.get("base_url", "http://localhost:8001")
        outcome = (api_runner or ApiRunner()).execute(api_case, base_url)
    else:
        script_path = run_case.script_path
        if not script_path or not Path(script_path).exists():
            raise ConflictError("Script file not found for rerun", {"run_case_id": run_case_id})
        script_text = Path(script_path).read_text(encoding="utf-8")
        outcome = (driver or get_driver()).execute(script_text, run.config)

    step_results = [_add_step_result(db, run_case, step_outcome) for step_outcome in outcome.steps]

    status = "passed" if outcome.status == "passed" else "failed"
    _finish_case(db, run_case, status, duration_ms=outcome.duration_ms, error=outcome.error)
    db.commit()
    if run_case.kind == "api":
        _persist_api_evidence(db, run, run_case, outcome)
    else:
        _persist_case_evidence(db, run, run_case, outcome, step_results)
    return get_case_detail(db, run_case_id)
