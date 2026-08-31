"""Rule classifier tests (P7-002, MAJOR-005, AC-7-01)."""

import pytest

from app.core.config import settings
from app.services.analysis.rule_classifier import (
    PRELOGIN_REDIRECT_SIGNATURES,
    STRONG_SIGNATURES,
    rule_classify,
)


@pytest.mark.parametrize("signature", STRONG_SIGNATURES)
def test_each_strong_signature_locks_broken_locator(signature):
    decision = rule_classify(f"Playwright error: {signature} some-detail")
    assert decision is not None
    assert decision.category == "BROKEN_LOCATOR"
    assert decision.confidence == settings.failure_rule_confidence
    assert decision.source == "rule"


@pytest.mark.parametrize("signature", PRELOGIN_REDIRECT_SIGNATURES)
def test_each_prelogin_signature_flags_needs_human(signature):
    # P016 5-4: unauthenticated-redirect signatures map to BROKEN_LOCATOR but
    # flag needs_human with a "前置缺失" reason.
    decision = rule_classify(
        f"Locator.click: Timeout 30000ms exceeded.\nCall log: {signature} not found"
    )
    assert decision is not None
    assert decision.category == "BROKEN_LOCATOR"
    assert decision.needs_human is True
    assert "前置缺失" in (decision.reason or "")


def test_real_selector_change_error_locked():
    # A realistic Python Playwright locator timeout (snake_case).
    decision = rule_classify(
        "Timeout 15000ms exceeded.\nwaiting for get_by_test_id(\"login-btn\")"
    )
    assert decision is not None
    assert decision.category == "BROKEN_LOCATOR"


def test_assertion_mismatch_not_locked():
    decision = rule_classify("Error: expect(...).toBe(...) \nexpected: '首页'\nreceived: '登录'")
    assert decision is None


def test_get_by_text_missing_not_locked():
    decision = rule_classify("Timeout waiting for get_by_text(\"登录成功\")")
    assert decision is None


def test_plain_error_not_locked():
    assert rule_classify("Something else happened") is None


def test_empty_error_not_locked():
    assert rule_classify("") is None
    assert rule_classify(None) is None
