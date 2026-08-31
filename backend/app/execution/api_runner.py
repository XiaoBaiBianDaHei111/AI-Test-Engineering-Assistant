"""httpx-based API test runner + assertion executor (Phase 9).

Sends one request and evaluates the APITestCase's assertions step-by-step:
step 1 = "发送请求" (passed/failed), steps 2..N = each assertion. Returns the
shared ``CaseOutcome`` shape so API cases reuse the run_batch / evidence /
failure-analysis / report pipeline.
"""

import time
from typing import Any

import httpx

from app.core.config import settings
from app.execution.runner import (
    CaseOutcome,
    EvidenceArtifacts,
    NetworkEvidence,
    StepOutcome,
)

ASSERTION_DESCRIPTIONS = {
    "status": lambda a: f"status == {a.get('expected')}",
    "json_field": lambda a: f"json_field {a.get('path')} == {a.get('expected', 'non_empty')}",
    "response_time": lambda a: f"response_time <= {a.get('expected_ms')}ms",
    "header": lambda a: f"header {a.get('name')} == {a.get('expected')}",
}


def _get_json_path(body: Any, path: str) -> Any:
    """Navigate a dot-separated path into a parsed JSON body; None if missing."""
    if not isinstance(body, (dict, list)) or not path:
        return None
    current = body
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def _check_assertion(assertion: dict, status_code: int, body: Any, headers, elapsed_ms: int) -> tuple[bool, str]:
    atype = assertion.get("type")
    if atype == "status":
        expected = assertion.get("expected")
        ok = status_code == expected
        return ok, f"status == {expected} (actual {status_code})"
    if atype == "json_field":
        path = assertion.get("path")
        expected = assertion.get("expected", "non_empty")
        value = _get_json_path(body, path)
        if value is None:
            return False, f"json_field {path} 不存在"
        if expected == "non_empty":
            ok = value not in (None, "", [], {})
            return ok, f"json_field {path} 非空 (actual {value!r})"
        ok = value == expected
        return ok, f"json_field {path} == {expected!r} (actual {value!r})"
    if atype == "response_time":
        expected_ms = assertion.get("expected_ms", 0)
        # B-4: honor the direction (name). Default less_than keeps backward compat.
        direction = assertion.get("name") or "less_than"
        if direction == "greater_than":
            ok = elapsed_ms >= expected_ms
            op = ">="
        else:
            ok = elapsed_ms <= expected_ms
            op = "<="
        return ok, f"response_time {op} {expected_ms}ms (actual {elapsed_ms}ms)"
    if atype == "header":
        name = assertion.get("name", "")
        expected = assertion.get("expected", "")
        actual = headers.get(name, "")
        ok = str(actual).lower() == str(expected).lower()
        return ok, f"header {name} == {expected!r} (actual {actual!r})"
    return False, f"unknown assertion type: {atype}"


class ApiRunner:
    """Executes an APITestCase via httpx (transport injectable for CI zero-network)."""

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=settings.api_request_timeout_seconds, transport=self._transport
        )

    def execute(self, api_case, base_url: str) -> CaseOutcome:
        method = api_case.method
        url = api_case.url if api_case.url.startswith("http") else f"{base_url}{api_case.url}"
        assertions = api_case.assertions or []

        started = time.monotonic()
        evidence = EvidenceArtifacts()
        steps: list[StepOutcome] = []

        try:
            request_started = time.monotonic()
            with self._client() as client:
                response = client.request(
                    method, url, headers=api_case.headers or None, json=api_case.body
                )
            elapsed_ms = int((time.monotonic() - request_started) * 1000)
            raw_body = response.text or ""

            # Parse body for json_field assertions.
            body: Any = None
            try:
                body = response.json()
            except Exception:  # noqa: BLE001 - non-JSON body is fine
                body = None

            # Truncated response body for evidence (D3).
            truncated = len(raw_body) > settings.api_response_body_max_chars
            response_body = raw_body[:settings.api_response_body_max_chars]

            steps.append(StepOutcome(
                1, "发送请求", "passed",
                f"{method} {url} -> {response.status_code}", elapsed_ms, True,
            ))

            status = "passed"
            error = ""
            for index, assertion in enumerate(assertions, start=2):
                ok, message = _check_assertion(
                    assertion, response.status_code, body, response.headers, elapsed_ms
                )
                steps.append(StepOutcome(
                    index, ASSERTION_DESCRIPTIONS.get(assertion.get("type"), lambda a: "断言")(assertion),
                    "passed" if ok else "failed", message, 0, True,
                ))
                if not ok:
                    status = "failed"
                    error = message
                    break

            evidence.network.append(NetworkEvidence(
                url=url, method=method, status=response.status_code,
                resource_type="api", duration_ms=elapsed_ms,
                response_body=response_body, body_truncated=truncated,
            ))
        except Exception as exc:  # noqa: BLE001 - connection error -> failed send step
            steps.append(StepOutcome(1, "发送请求", "failed", str(exc), 0, False))
            status = "failed"
            error = str(exc)
            evidence.network.append(NetworkEvidence(
                url=url, method=method, status=0, resource_type="api",
                duration_ms=int((time.monotonic() - started) * 1000),
            ))

        return CaseOutcome(
            status=status,
            duration_ms=int((time.monotonic() - started) * 1000),
            steps=steps,
            error=error,
            evidence=evidence,
        )
