"""script_generator agent tests (P5-004; P013 real mode)."""

import json

import pytest

from app.models import AIAuditLog
from app.models import TestCase as _TestCase
from app.services.ai.agents.script_generator import generate_script
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


def _load(db_session, case_id):
    return db_session.get(_TestCase, case_id)


@pytest.mark.real
def test_generate_script_valid(require_llm_key, db_session, sample_project, client):
    case = _approved_case(client, sample_project["id"])
    result = generate_script(db_session, _load(db_session, case["id"]), CONFIG)
    assert result["status"] in ("success", "retry")
    assert result["script_text"] is not None
    assert "STEPS = [" in result["script_text"]
    assert len(result["steps"]) >= 3
    # last step must assert
    assert "expect(" in result["script_text"]


class _BadScriptProvider:
    """Deterministic stub: emits steps that fail static validation (no goto)."""

    def chat(self, system, user, json_mode=True, agent=""):
        content = json.dumps({"script": [
            {"description": "点", "code": 'page.get_by_test_id("x").click()'},
            {"description": "填", "code": 'page.get_by_test_id("y").fill("1")'},
            {"description": "校验", "code": 'expect(page.get_by_test_id("z")).to_contain_text("ok")'},
        ]})
        return ChatResult(content=content, tokens_in=1, tokens_out=1, latency_ms=1)


def test_generate_script_validation_failure_writes_excerpt(db_session, sample_project, client):
    # T1 (P016 5-3): static-validation failures surface their errors in the
    # audit failure_excerpt (previously None).
    case = _approved_case(client, sample_project["id"])
    result = generate_script(
        db_session, _load(db_session, case["id"]), CONFIG, provider=_BadScriptProvider()
    )
    assert result["status"] == "failed"

    log = db_session.query(AIAuditLog).order_by(AIAuditLog.id.desc()).first()
    assert log is not None
    assert log.status == "failed"
    assert "SCRIPT_VALIDATION_FAILED" in (log.failure_excerpt or "")
    assert "首步" in (log.failure_excerpt or "")


class _GoodScriptProvider:
    """Deterministic stub: emits a valid 3-step script (goto + heading + assert)."""

    def chat(self, system, user, json_mode=True, agent=""):
        content = json.dumps({"script": [
            {"description": "打开", "code": "page.goto(BASE_URL)"},
            {"description": "查看", "code": 'page.get_by_role("heading", name="Products")'},
            {"description": "校验", "code": 'expect(page.get_by_role("heading", name="Products")).to_be_visible()'},
        ]})
        return ChatResult(content=content, tokens_in=1, tokens_out=1, latency_ms=1)


def _login_case(db_session, client, project_id):
    case = _approved_case(client, project_id)
    tc = _load(db_session, case["id"])
    tc.test_data = {"username": "standard_user", "password": "secret_sauce"}
    db_session.commit()
    return tc


def test_login_precondition_injected(db_session, sample_project, client):
    # T4 (P016 5-2): a case with credentials gets the deterministic login preamble
    # injected after the first goto.
    from app.services.ai.agents.script_generator import _login_required, _login_steps

    tc = _login_case(db_session, client, sample_project["id"])
    assert _login_required(tc) is True
    assert len(_login_steps(tc)) == 3

    result = generate_script(db_session, tc, CONFIG, provider=_GoodScriptProvider())
    assert result["status"] == "success"
    script = result["script_text"]
    assert "Username" in script
    assert "Password" in script
    assert "Login" in script
    # login steps come right after the goto (before the case steps)
    assert script.index("Username") < script.index("Products")


def test_no_login_when_no_credentials(db_session, sample_project, client):
    from app.services.ai.agents.script_generator import _login_required, _login_steps

    case = _approved_case(client, sample_project["id"])
    tc = _load(db_session, case["id"])
    assert _login_required(tc) is False
    assert _login_steps(tc) == []
