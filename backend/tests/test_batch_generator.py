"""Batch generator orchestration tests (P3-005). Real mode (P013)."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import GenerationRun
from app.models import TestCase as _TestCase
from app.services.ai.agents.test_case_generator import generate_batch
from app.services.assets.generation_run_service import create_run


def _create_confirmed_test_points(client, project_id, count, prefix="测试点"):
    req = client.post(
        f"/api/projects/{project_id}/requirements", json={"title": "批量需求"}
    ).json()
    client.patch(f"/api/requirements/{req['id']}", json={"status": "confirmed"})
    ids = []
    for i in range(count):
        tp = client.post(
            f"/api/requirements/{req['id']}/test-points",
            json={"title": f"{prefix}{i}", "technique": "equivalence"},
        ).json()
        client.patch(f"/api/test-points/{tp['id']}", json={"status": "confirmed"})
        ids.append(tp["id"])
    return ids


def _read_run(session_factory, run_id) -> GenerationRun:
    """Read the run through a fresh session (cross-session visibility check)."""
    session = session_factory()
    try:
        return session.get(GenerationRun, run_id)
    finally:
        session.close()


def _read_cases(session_factory, project_id) -> list:
    session = session_factory()
    try:
        return list(
            session.scalars(
                select(_TestCase)
                .options(selectinload(_TestCase.steps))
                .where(_TestCase.project_id == project_id)
            )
        )
    finally:
        session.close()


@pytest.mark.real
def test_generate_batch_completed(require_llm_key, session_factory, db_session, sample_project, client):
    ids = _create_confirmed_test_points(client, sample_project["id"], 2)
    run = create_run(db_session, sample_project["id"], len(ids))
    generate_batch(session_factory, run.id, ids)

    run = _read_run(session_factory, run.id)
    assert run.status == "completed"
    assert run.processed_items == 2
    assert run.created_count >= 2  # at least one case per test point
    cases = _read_cases(session_factory, sample_project["id"])
    for case in cases:
        assert case.source == "ai"
        assert case.status == "draft"
        assert case.requirement_id is not None
        assert case.test_point_id in ids
        assert case.case_id.startswith("TC-")
        assert len(case.steps) >= 3
        assert case.expected_result  # copied from the last step


@pytest.mark.real
def test_generate_batch_covers_each_test_point(require_llm_key, session_factory, db_session, sample_project, client):
    ids = _create_confirmed_test_points(client, sample_project["id"], 3)
    run = create_run(db_session, sample_project["id"], len(ids))
    generate_batch(session_factory, run.id, ids)

    run = _read_run(session_factory, run.id)
    assert run.status == "completed"
    covered = {case.test_point_id for case in _read_cases(session_factory, sample_project["id"])}
    assert set(ids) <= covered  # AC-3-03: every test point has >=1 case
