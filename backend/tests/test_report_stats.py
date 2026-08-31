"""Report statistics aggregation tests (P8-002, AC-8-01/08)."""

from app.models import FailureAnalysis
from app.services.analysis.report_stats import build_report_stats
from app.services.assets import evidence_service
from app.services.assets.test_run_service import create_run

CONFIG = {"base_url": "http://localhost:8001", "qa_mode": "none", "browser": "chromium", "headless": True}


def _scenario(db_session, sample_project, client):
    cases = []
    for i, prio in enumerate(["P0", "P1", "P2"]):
        c = client.post(
            f"/api/projects/{sample_project['id']}/test-cases",
            json={"title": f"case{i}", "priority": prio,
                  "steps": [{"step_number": 1, "action": "a", "expected_result": "b"}]},
        ).json()
        client.post(f"/api/test-cases/{c['id']}/submit-review")
        client.post(f"/api/test-cases/{c['id']}/review", json={"verdict": "approved"})
        cases.append(c)
    run = create_run(db_session, sample_project["id"], [c["id"] for c in cases], CONFIG)
    rc0, rc1, rc2 = run.run_cases
    rc0.status = "passed"
    rc1.status = "failed"
    rc1.error = "boom"
    rc2.status = "blocked"
    db_session.add(FailureAnalysis(
        run_case_id=rc1.id, category="REAL_BUG", confidence=0.9,
        reason="r", suggested_fix="f", decision_source="llm",
        needs_human=False, status="classified",
    ))
    db_session.commit()
    evidence_service.save_evidence(db_session, run.id, rc1.id, "screenshot", f"{rc1.id}_1.png", b"png", meta={"step_number": 1})
    return run


def test_overview_and_pass_rate(db_session, sample_project, client):
    run = _scenario(db_session, sample_project, client)
    stats = build_report_stats(db_session, run.id)
    overview = stats["overview"]
    assert overview["total"] == 3
    assert overview["passed"] == 1
    assert overview["failed"] == 1
    assert overview["blocked"] == 1
    assert overview["pass_rate"] == 0.5  # 1 / (1 + 1)


def test_priority_distribution(db_session, sample_project, client):
    run = _scenario(db_session, sample_project, client)
    stats = build_report_stats(db_session, run.id)
    priority = stats["priority"]
    assert priority["P0"]["total"] == 1 and priority["P0"]["passed"] == 1
    assert priority["P1"]["total"] == 1 and priority["P1"]["failed"] == 1
    assert priority["P2"]["total"] == 1  # blocked -> neither passed nor failed
    assert priority["P2"]["pass_rate"] == 0.0


def test_failure_categories_and_case_detail(db_session, sample_project, client):
    run = _scenario(db_session, sample_project, client)
    stats = build_report_stats(db_session, run.id)
    assert stats["failure_categories"]["REAL_BUG"] == 1
    failed_case = next(c for c in stats["cases"] if c["status"] == "failed")
    assert failed_case["failure_analysis"]["category"] == "REAL_BUG"
    assert failed_case["evidence"]["screenshots"]  # screenshot referenced


def test_deleted_case_priority_unknown(db_session, sample_project, client):
    run = _scenario(db_session, sample_project, client)
    # simulate a deleted test case: null out test_case_id
    run.run_cases[0].test_case_id = None
    db_session.commit()
    stats = build_report_stats(db_session, run.id)
    assert stats["priority"]["unknown"]["total"] >= 1


def test_empty_run(db_session, sample_project, client):
    case = client.post(
        f"/api/projects/{sample_project['id']}/test-cases",
        json={"title": "c", "steps": [{"step_number": 1, "action": "a", "expected_result": "b"}]},
    ).json()
    client.post(f"/api/test-cases/{case['id']}/submit-review")
    client.post(f"/api/test-cases/{case['id']}/review", json={"verdict": "approved"})
    run = create_run(db_session, sample_project["id"], [case["id"]], CONFIG)
    stats = build_report_stats(db_session, run.id)
    assert stats["overview"]["total"] == 1
    assert stats["overview"]["pass_rate"] == 0.0  # pending -> denominator guard
