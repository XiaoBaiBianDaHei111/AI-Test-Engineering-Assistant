"""AI audit log API tests (P2-006). Real mode (P013)."""

import pytest

from app.services.ai.audit import record_audit


def test_audit_empty(client):
    assert client.get("/api/ai/audit").json() == []


def test_record_audit_stores_failure_excerpt(db_session):
    # B-2: a failed audit row carries the raw output excerpt (truncated to 2000).
    excerpt = "x" * 3000
    log = record_audit(
        db_session, "api_test_case_generator", 7, "input", "failed: AI_OUTPUT_INVALID",
        1, 2, 3, "failed", failure_excerpt=excerpt,
    )
    assert log.failure_excerpt == excerpt[:2000]
    # Success rows leave the excerpt unset.
    ok = record_audit(
        db_session, "api_test_case_generator", 7, "input", "success: 3 cases",
        1, 2, 3, "success",
    )
    assert ok.failure_excerpt is None


@pytest.mark.real
def test_audit_after_analyze_has_complete_fields(require_llm_key, sample_project, client):
    client.post(
        "/api/ai/analyze-requirement",
        json={"project_id": sample_project["id"], "prd_text": "PRD 文本"},
    )
    logs = client.get("/api/ai/audit").json()
    assert len(logs) >= 1
    log = logs[0]
    assert log["agent_name"] == "requirements_analyst"
    assert log["schema_version"] == 7
    assert log["status"] in ("success", "retry")
    assert isinstance(log["tokens_in"], int)
    assert isinstance(log["tokens_out"], int)
    assert isinstance(log["latency_ms"], int)
    assert len(log["input_hash"]) > 0
    assert len(log["input_summary"]) > 0


@pytest.mark.real
def test_audit_filter_by_agent_and_status(require_llm_key, confirmed_requirement, client):
    client.post(
        "/api/ai/extract-test-points", json={"requirement_id": confirmed_requirement["id"]}
    )
    logs = client.get("/api/ai/audit", params={"agent": "test_point_extractor"}).json()
    assert logs and all(log["agent_name"] == "test_point_extractor" for log in logs)
    retry_logs = client.get("/api/ai/audit", params={"status": "retry"}).json()
    assert all(log["status"] == "retry" for log in retry_logs)


@pytest.mark.real
def test_audit_respects_limit(require_llm_key, sample_project, client):
    client.post(
        "/api/ai/analyze-requirement",
        json={"project_id": sample_project["id"], "prd_text": "PRD 文本"},
    )
    logs = client.get("/api/ai/audit", params={"limit": 1}).json()
    assert len(logs) <= 1
