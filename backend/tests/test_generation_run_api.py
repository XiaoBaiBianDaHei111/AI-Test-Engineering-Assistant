"""GenerationRun lifecycle / state machine / API tests (P3-003)."""

import pytest

from app.core.exceptions import InvalidTransitionError, NotFoundError
from app.services.assets.generation_run_service import (
    create_run,
    finish_run,
    get_run_or_404,
    list_runs,
    mark_running,
    update_progress,
)


def test_run_lifecycle(db_session, sample_project):
    run = create_run(db_session, sample_project["id"], 3)
    assert run.status == "pending"
    assert run.total_items == 3
    run = mark_running(db_session, run)
    assert run.status == "running"
    assert run.started_at is not None
    run = update_progress(db_session, run, processed_items=2, created_count=5)
    assert run.processed_items == 2
    assert run.created_count == 5
    run = finish_run(db_session, run, "completed")
    assert run.status == "completed"
    assert run.ended_at is not None


def test_run_illegal_transition(db_session, sample_project):
    run = create_run(db_session, sample_project["id"], 3)
    with pytest.raises(InvalidTransitionError):
        finish_run(db_session, run, "completed")  # pending -> completed illegal


def test_run_pending_to_failed_allowed(db_session, sample_project):
    # pending -> failed is allowed (crash before running -> exception fallback)
    run = create_run(db_session, sample_project["id"], 3)
    run = finish_run(db_session, run, "failed")
    assert run.status == "failed"


def test_get_run_not_found(db_session):
    with pytest.raises(NotFoundError):
        get_run_or_404(db_session, 999)


def test_list_runs(db_session, sample_project):
    create_run(db_session, sample_project["id"], 1)
    create_run(db_session, sample_project["id"], 2)
    runs = list_runs(db_session, sample_project["id"])
    assert len(runs) == 2


def test_run_api_detail_and_list(sample_project, client):
    assert client.get("/api/ai/generation-runs/999").status_code == 404
    response = client.get(
        "/api/ai/generation-runs", params={"project_id": sample_project["id"]}
    )
    assert response.status_code == 200
    assert response.json() == []
