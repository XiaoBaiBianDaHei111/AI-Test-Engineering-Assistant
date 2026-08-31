"""Failure analyzer LLM agent tests (P7-004, AC-7-04). Real mode (P013)."""

import pytest

from app.services.ai.agents.failure_analyzer import analyze_with_llm

FAILURE_CATEGORIES = {"BROKEN_LOCATOR", "REAL_BUG", "FLAKY", "ENV_ISSUE"}


@pytest.mark.real
def test_valid_output(require_llm_key, db_session):
    item = analyze_with_llm(db_session, {"error": "timeout waiting for element"})
    assert item["category"] in FAILURE_CATEGORIES
    assert 0.0 <= item["confidence"] <= 1.0
    assert item["reason"]
    assert item["suggested_fix"]
