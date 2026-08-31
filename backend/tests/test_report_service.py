"""Report service tests (P8-004, AC-8-05/07/08). Real mode (P013)."""

import json
from pathlib import Path

import pytest

from app.core.exceptions import ValidationFailedError
from app.models import TestReport
from app.services.assets import test_report_service
from app.services.assets.test_run_service import create_run
from app.services.ai.providers import ChatResult

CONFIG = {"base_url": "http://localhost:8001", "qa_mode": "none", "browser": "chromium", "headless": True}


def _approved_case(client, project_id, title="登录成功"):
    case = client.post(
        f"/api/projects/{project_id}/test-cases",
        json={"title": title, "steps": [{"step_number": 1, "action": "打开", "expected_result": "显示"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    return case


def _completed_run(db_session, sample_project, client):
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    run.status = "completed"
    run.run_cases[0].status = "passed"
    db_session.commit()
    return run


def test_generate_report_writes_files(db_session, sample_project, client):
    run = _completed_run(db_session, sample_project, client)
    report = test_report_service.generate_report(db_session, run.id)
    assert report.id is not None
    assert Path(report.html_path).exists()
    assert Path(report.json_path).exists()
    data = json.loads(Path(report.json_path).read_text(encoding="utf-8"))
    assert data["overview"]["passed"] == 1


def test_generate_report_pending_422(db_session, sample_project, client):
    case = _approved_case(client, sample_project["id"])
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    with pytest.raises(ValidationFailedError):
        test_report_service.generate_report(db_session, run.id)


def test_regenerate_overwrites(db_session, sample_project, client):
    run = _completed_run(db_session, sample_project, client)
    test_report_service.generate_report(db_session, run.id)
    test_report_service.generate_report(db_session, run.id)
    assert db_session.query(TestReport).count() == 1


@pytest.mark.real
def test_generate_quality_summary_rule_go(require_llm_key, db_session, sample_project, client):
    run = _completed_run(db_session, sample_project, client)
    report = test_report_service.generate_report(db_session, run.id)
    summary = test_report_service.generate_quality_summary(db_session, report.id)
    assert summary.recommendation == "GO"
    assert summary.overall_score == 100


class _NoGoProvider:
    """Test-local stub: returns a valid summary the rule must override."""

    def chat(self, system, user, json_mode=True, agent=""):
        return ChatResult(
            json.dumps({"quality_summary": [{
                "overall_score": 10, "recommendation": "NO_GO",
                "risk_factors": ["幻觉风险"], "reasoning": "乱说",
            }]}),
            tokens_in=1, tokens_out=1, latency_ms=1,
        )


def test_recommendation_rule_overrides_llm(db_session, sample_project, client):
    run = _completed_run(db_session, sample_project, client)
    report = test_report_service.generate_report(db_session, run.id)
    summary = test_report_service.generate_quality_summary(db_session, report.id, provider=_NoGoProvider())
    assert summary.recommendation == "GO"  # rule overrides LLM's NO_GO
    assert summary.overall_score == 100
