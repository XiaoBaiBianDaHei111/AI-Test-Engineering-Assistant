"""Test-case generation endpoints (POST generate + GET generation runs)."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.schemas import (
    GenerateTestCasesRequest,
    GenerateTestCasesResponse,
    GenerationRunRead,
)
from app.services.ai.agents.test_case_generator import generate_batch
from app.services.assets.generation_run_service import (
    create_run,
    get_project_or_404,
    get_run_or_404,
    list_runs,
    validate_test_points_for_generation,
)

router = APIRouter()


@router.post("/generate-test-cases", response_model=GenerateTestCasesResponse)
def generate_test_cases(
    payload: GenerateTestCasesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    get_project_or_404(db, payload.project_id)
    test_points = validate_test_points_for_generation(
        db, payload.project_id, payload.test_point_ids
    )
    run = create_run(db, payload.project_id, len(test_points))
    background_tasks.add_task(
        generate_batch, SessionLocal, run.id, [tp.id for tp in test_points]
    )
    return {"run_id": run.id, "status": "started", "total": len(test_points)}


@router.get("/generation-runs/{run_id}", response_model=GenerationRunRead)
def get_generation_run(run_id: int, db: Session = Depends(get_db)):
    return get_run_or_404(db, run_id)


@router.get("/generation-runs", response_model=list[GenerationRunRead])
def list_generation_runs(
    project_id: int = Query(...),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return list_runs(db, project_id, limit=limit)
