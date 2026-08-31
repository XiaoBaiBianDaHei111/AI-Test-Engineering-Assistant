"""Priority-distribution post-check tests (AC-3-04)."""

from app.services.ai.agents.test_case_generator import check_priority_distribution


def test_main_flow_with_high_priority_no_warning():
    assert check_priority_distribution({"equivalence"}, {"P0", "P2"}) == []


def test_main_flow_missing_high_priority_warns():
    warnings = check_priority_distribution({"equivalence", "state_transition"}, {"P2", "P3"})
    assert len(warnings) == 1
    assert "priority" in warnings[0]


def test_no_main_flow_no_warning():
    assert check_priority_distribution({"exception", "boundary"}, {"P2"}) == []


def test_empty_techniques_no_warning():
    assert check_priority_distribution(set(), {"P2"}) == []
