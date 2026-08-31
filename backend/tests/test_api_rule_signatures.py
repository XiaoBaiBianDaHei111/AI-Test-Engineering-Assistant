"""API ENV rule signature tests (P9-007, AC-9-03)."""

import pytest

from app.core.config import settings
from app.services.analysis.rule_classifier import API_ENV_SIGNATURES, rule_classify


@pytest.mark.parametrize("signature", API_ENV_SIGNATURES)
def test_each_api_env_signature_locks_env_issue(signature):
    decision = rule_classify(f"httpx.{signature} while connecting to http://localhost:8001")
    assert decision is not None
    assert decision.category == "ENV_ISSUE"
    assert decision.confidence == settings.failure_rule_confidence
    assert decision.source == "rule"


def test_assertion_mismatch_not_locked():
    assert rule_classify("status == 200 (actual 401)") is None
    assert rule_classify("Error: expected: 'a'\nreceived: 'b'") is None


def test_locator_signatures_still_lock_broken_locator():
    decision = rule_classify("Timeout waiting for get_by_test_id(\"login-btn\")")
    assert decision is not None and decision.category == "BROKEN_LOCATOR"
