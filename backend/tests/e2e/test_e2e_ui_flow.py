"""e2e UI flow (Phase 10): real browser (PlaywrightDriver) against the demo SPA.

Covers normal mode (login passes) and selector-change (fails and is rule-classified
BROKEN_LOCATOR). Requires a running backend + installed chromium; excluded by default.
"""

import pytest

pytestmark = pytest.mark.e2e

CONFIG = {"browser": "chromium", "headless": True}


@pytest.fixture()
def approved_case(client, sample_project):
    case = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "登录成功", "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    return case


def _run(db_session, session_factory, sample_project, case, qa_mode):
    from app.execution.runner import PlaywrightDriver
    from app.services.assets.test_run_service import create_run, run_batch

    config = {**CONFIG, "base_url": pytest.importorskip("os").environ.get("E2E_BASE_URL", "http://localhost:8000"), "qa_mode": qa_mode}
    run = create_run(db_session, sample_project["id"], [case["id"]], config)
    run_batch(session_factory, run.id, driver=PlaywrightDriver())
    return run


def test_e2e_ui_normal_passes(db_session, session_factory, sample_project, client, approved_case, e2e_base_url):
    from app.services.assets.test_run_service import get_run_or_404

    run = _run(db_session, session_factory, sample_project, approved_case, "none")
    run = get_run_or_404(db_session, run.id)
    assert run.status == "completed"
    assert run.run_cases[0].status == "passed"


def test_e2e_ui_selector_change_rule_classified(db_session, session_factory, sample_project, client, approved_case, e2e_base_url):
    from sqlalchemy import select

    from app.models import FailureAnalysis
    from app.services.assets.test_run_service import get_run_or_404

    run = _run(db_session, session_factory, sample_project, approved_case, "selector-change")
    run = get_run_or_404(db_session, run.id)
    run_case = run.run_cases[0]
    assert run_case.status == "failed"
    analysis = db_session.scalar(select(FailureAnalysis).where(FailureAnalysis.run_case_id == run_case.id))
    assert analysis is not None
    assert analysis.category == "BROKEN_LOCATOR"
    assert analysis.decision_source == "rule"
