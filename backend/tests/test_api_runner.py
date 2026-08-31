"""ApiRunner + assertion executor tests (P9-003, AC-9-02, P14 B-4)."""

from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.execution.api_runner import ApiRunner, _check_assertion
from app.schemas.api_test_case import ApiAssertion


def _case(method="POST", url="/api/x", headers=None, body=None, assertions=None):
    return SimpleNamespace(
        method=method, url=url, headers=headers or {}, body=body, assertions=assertions or []
    )


# --- assertion executor (pure) ---

def test_status_assertion_pass_fail():
    ok, _ = _check_assertion({"type": "status", "expected": 200}, 200, {}, {}, 0)
    assert ok
    ok, _ = _check_assertion({"type": "status", "expected": 200}, 401, {}, {}, 0)
    assert not ok


def test_json_field_assertion():
    body = {"user": {"name": "alice"}}
    ok, _ = _check_assertion({"type": "json_field", "path": "user.name", "expected": "alice"}, 200, body, {}, 0)
    assert ok
    ok, _ = _check_assertion({"type": "json_field", "path": "user.name", "expected": "bob"}, 200, body, {}, 0)
    assert not ok
    ok, _ = _check_assertion({"type": "json_field", "path": "token", "expected": "non_empty"}, 200, {"token": "x"}, {}, 0)
    assert ok
    ok, _ = _check_assertion({"type": "json_field", "path": "token", "expected": "non_empty"}, 200, {}, {}, 0)
    assert not ok


def test_header_assertion():
    ok, _ = _check_assertion({"type": "header", "name": "content-type", "expected": "application/json"},
                             200, {}, {"content-type": "application/json"}, 0)
    assert ok
    ok, _ = _check_assertion({"type": "header", "name": "content-type", "expected": "text/html"},
                             200, {}, {"content-type": "application/json"}, 0)
    assert not ok


def test_response_time_assertion():
    ok, _ = _check_assertion({"type": "response_time", "expected_ms": 100}, 200, {}, {}, 50)
    assert ok
    ok, _ = _check_assertion({"type": "response_time", "expected_ms": 100}, 200, {}, {}, 150)
    assert not ok


def test_response_time_greater_than():
    # B-4: greater_than semantics — 5000ms >= 3000ms passes.
    ok, _ = _check_assertion({"type": "response_time", "expected_ms": 3000, "name": "greater_than"}, 200, {}, {}, 5000)
    assert ok
    ok, _ = _check_assertion({"type": "response_time", "expected_ms": 3000, "name": "greater_than"}, 200, {}, {}, 2000)
    assert not ok


def test_response_time_less_than_default():
    # B-4: name defaults to less_than (backward compat).
    ok, _ = _check_assertion({"type": "response_time", "expected_ms": 3000}, 200, {}, {}, 2000)
    assert ok
    ok, _ = _check_assertion({"type": "response_time", "expected_ms": 3000, "name": "less_than"}, 200, {}, {}, 5000)
    assert not ok


def test_response_time_invalid_name_rejected():
    with pytest.raises(ValidationError):
        ApiAssertion(type="response_time", expected_ms=3000, name="greater")


# --- ApiRunner with MockTransport ---

def _mock_ok_handler(request):
    return httpx.Response(200, json={"token": "abc"}, headers={"content-type": "application/json"})


def test_execute_all_assertions_pass():
    case = _case(
        assertions=[
            {"type": "status", "expected": 200},
            {"type": "json_field", "path": "token", "expected": "non_empty"},
        ]
    )
    outcome = ApiRunner(transport=httpx.MockTransport(_mock_ok_handler)).execute(case, "http://test")
    assert outcome.status == "passed"
    assert len(outcome.steps) == 3  # send + 2 assertions
    assert outcome.steps[0].description == "发送请求"


def test_execute_status_assertion_fails():
    case = _case(assertions=[{"type": "status", "expected": 201}])
    outcome = ApiRunner(transport=httpx.MockTransport(_mock_ok_handler)).execute(case, "http://test")
    assert outcome.status == "failed"
    assert outcome.steps[1].status == "failed"
    assert "status == 201" in outcome.steps[1].message


def test_execute_connection_error_fails_send_step():
    def handler(request):
        raise httpx.ConnectError("Connection refused")

    case = _case(assertions=[{"type": "status", "expected": 200}])
    outcome = ApiRunner(transport=httpx.MockTransport(handler)).execute(case, "http://test")
    assert outcome.status == "failed"
    assert outcome.steps[0].status == "failed"
    assert "Connection refused" in outcome.error
