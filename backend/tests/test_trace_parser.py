"""Trace parser tests (P6-006, AC-6-04)."""

import io
import json
import zipfile

import pytest

from app.services.analysis import trace_parser
from app.services.analysis.trace_parser import TraceParseError, parse_trace


def _trace(lines: list[dict]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("trace.trace", "\n".join(json.dumps(line) for line in lines))
    return buf.getvalue()


def test_parse_actions_paired():
    lines = [
        {"type": "before", "callId": "c1", "startTime": 0, "apiName": "page.goto"},
        {"type": "after", "callId": "c1", "endTime": 15, "apiName": "page.goto"},
        {"type": "before", "callId": "c2", "startTime": 20, "apiName": "page.get_by_test_id"},
        {"type": "after", "callId": "c2", "endTime": 25, "apiName": "page.get_by_test_id"},
    ]
    result = parse_trace(_trace(lines))
    assert len(result["actions"]) == 2
    assert result["actions"][0]["api_name"] == "page.goto"
    assert result["actions"][0]["duration_ms"] == 15
    assert result["actions"][1]["api_name"] == "page.get_by_test_id"
    assert result["actions"][1]["duration_ms"] == 5


def test_parse_action_error_message():
    lines = [
        {"type": "before", "callId": "c1", "startTime": 0, "apiName": "page.get_by_test_id"},
        {"type": "after", "callId": "c1", "endTime": 10, "apiName": "page.get_by_test_id",
         "error": {"message": "Timeout waiting for get_by_test_id('login-btn')"}},
    ]
    result = parse_trace(_trace(lines))
    assert result["actions"][0]["error"] == "Timeout waiting for get_by_test_id('login-btn')"


def test_parse_network_paired():
    lines = [
        {"type": "request", "sha1": "r1", "url": "http://localhost:8001/demo/",
         "method": "GET", "status": 200, "resourceType": "document", "startTime": 0, "endTime": 8},
        {"type": "response", "sha1": "r1", "status": 200},
    ]
    result = parse_trace(_trace(lines))
    assert len(result["network"]) == 1
    net = result["network"][0]
    assert net["url"] == "http://localhost:8001/demo/"
    assert net["method"] == "GET"
    assert net["status"] == 200
    assert net["resource_type"] == "document"
    assert net["duration_ms"] == 8


def test_parse_console():
    lines = [
        {"type": "console", "messageType": "error", "text": "登录失败"},
        {"type": "console", "messageType": "log", "text": "demo loaded"},
    ]
    result = parse_trace(_trace(lines))
    assert result["console"] == [
        {"type": "error", "text": "登录失败"},
        {"type": "log", "text": "demo loaded"},
    ]


def test_parse_snapshot_refs_collected():
    lines = [
        {"type": "before", "callId": "c1", "startTime": 0, "apiName": "x", "beforeSnapshot": "snap-1"},
        {"type": "after", "callId": "c1", "endTime": 5, "apiName": "x", "afterSnapshot": "snap-2"},
    ]
    result = parse_trace(_trace(lines))
    assert "snap-1" in result["snapshots"]
    assert "snap-2" in result["snapshots"]


def test_unknown_events_skipped():
    lines = [
        {"type": "mystery", "foo": "bar"},
        {"type": "console", "messageType": "log", "text": "ok"},
    ]
    result = parse_trace(_trace(lines))
    assert result["console"] == [{"type": "log", "text": "ok"}]
    assert result["actions"] == []


def test_malformed_line_tolerated():
    text = json.dumps({"type": "console", "messageType": "log", "text": "ok"}) + "\nNOT JSON\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("trace.trace", text)
    result = parse_trace(buf.getvalue())
    assert len(result["console"]) == 1


def test_corrupt_zip_raises():
    with pytest.raises(TraceParseError):
        parse_trace(b"this is not a zip")


def test_missing_trace_file_raises():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("other.txt", "nope")
    with pytest.raises(TraceParseError):
        parse_trace(buf.getvalue())


def test_truncation_limit(monkeypatch):
    monkeypatch.setattr(trace_parser, "ACTION_LIMIT", 2)
    lines = [
        {"type": "before", "callId": f"c{i}", "startTime": i, "apiName": f"s{i}"} for i in range(5)
    ]
    result = parse_trace(_trace(lines))
    assert len(result["actions"]) == 2
    assert result["truncated"] is True
