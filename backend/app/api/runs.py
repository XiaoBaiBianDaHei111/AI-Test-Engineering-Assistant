"""Execution endpoints (Phase 5): create run / list / detail / cancel / script / rerun."""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.exceptions import NotFoundError
from app.models import FailureAnalysis
from app.schemas import (
    FailureAnalysisRead,
    RunCreateResponse,
    TestRunCaseDetail,
    TestRunCreate,
    TestRunRead,
)
from app.services.assets import test_run_service
from app.services.assets.test_run_service import run_batch

router = APIRouter()


def _run_to_read(run) -> dict:
    return TestRunRead.model_validate(run).model_dump(mode="json")


@router.post("/runs", response_model=RunCreateResponse)
def create_run(
    payload: TestRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    run = test_run_service.create_run(
        db,
        payload.project_id,
        payload.test_case_ids,
        payload.config.model_dump(),
        api_case_ids=payload.api_case_ids,
    )
    background_tasks.add_task(run_batch, SessionLocal, run.id)
    total = len(payload.test_case_ids) + len(payload.api_case_ids)
    return {"run_id": run.id, "status": "started", "total": total}


@router.get("/runs", response_model=list[TestRunRead])
def list_runs(
    project_id: int = Query(...),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return test_run_service.list_runs(db, project_id, limit=limit)


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = test_run_service.get_run_or_404(db, run_id)
    return _run_to_read(run)


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: int, db: Session = Depends(get_db)):
    run = test_run_service.cancel_run(db, run_id)
    return _run_to_read(run)


@router.get("/runs/{run_id}/cases/{run_case_id}", response_model=TestRunCaseDetail)
def get_run_case(run_id: int, run_case_id: int, db: Session = Depends(get_db)):
    run_case = test_run_service.get_case_detail(db, run_case_id)
    if run_case.run_id != run_id:
        raise NotFoundError("Run case not found", {"id": run_case_id})
    data = TestRunCaseDetail.model_validate(run_case).model_dump(mode="json")
    analysis = db.scalar(
        select(FailureAnalysis).where(FailureAnalysis.run_case_id == run_case_id)
    )
    data["failure_analysis"] = (
        FailureAnalysisRead.model_validate(analysis).model_dump(mode="json")
        if analysis else None
    )
    return data


def _script_path(run_case) -> Path:
    if run_case.script_path:
        return Path(run_case.script_path)
    # blocked case with no script yet: derive a server-side path
    return Path(__file__).resolve().parents[2] / "artifacts" / str(run_case.run_id) / "scripts" / f"{run_case.id}.py"


@router.get("/runs/{run_id}/cases/{run_case_id}/script")
def get_script(run_id: int, run_case_id: int, db: Session = Depends(get_db)):
    run_case = test_run_service.get_run_case_or_404(db, run_case_id)
    if run_case.run_id != run_id:
        raise NotFoundError("Run case not found", {"id": run_case_id})
    path = _script_path(run_case)
    if not path.exists():
        raise NotFoundError("Script file not found", {"run_case_id": run_case_id})
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@router.put("/runs/{run_id}/cases/{run_case_id}/script")
def put_script(run_id: int, run_case_id: int, body: str = Body(...), db: Session = Depends(get_db)):
    run_case = test_run_service.get_run_case_or_404(db, run_case_id)
    if run_case.run_id != run_id:
        raise NotFoundError("Run case not found", {"id": run_case_id})
    path = _script_path(run_case)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    if not run_case.script_path:
        run_case.script_path = str(path)
        db.commit()
    return {"run_case_id": run_case_id, "updated": True}


@router.post("/runs/{run_id}/cases/{run_case_id}/rerun", response_model=TestRunCaseDetail)
def rerun_case(run_id: int, run_case_id: int, db: Session = Depends(get_db)):
    run_case = test_run_service.get_run_case_or_404(db, run_case_id)
    if run_case.run_id != run_id:
        raise NotFoundError("Run case not found", {"id": run_case_id})
    return test_run_service.rerun_case(db, run_case_id)
