"""Quality summarizer agent tests (P8-006, AC-8-05). Real mode (P013)."""

import pytest

from app.services.ai.agents.quality_summarizer import (
    analyze_with_llm,
    derive_recommendation,
)

STATS = {"overview": {"pass_rate": 1.0, "blocked": 0}}


def test_derive_recommendation_go():
    assert derive_recommendation(1.0, 0) == "GO"


def test_derive_recommendation_conditional():
    assert derive_recommendation(0.85, 1) == "CONDITIONAL_GO"


def test_derive_recommendation_no_go():
    assert derive_recommendation(0.5, 0) == "NO_GO"


@pytest.mark.real
def test_valid_output(require_llm_key, db_session):
    item = analyze_with_llm(db_session, STATS)
    assert isinstance(item["overall_score"], int)
    assert 0 <= item["overall_score"] <= 100
    assert item["reasoning"]
    assert isinstance(item["risk_factors"], list)
