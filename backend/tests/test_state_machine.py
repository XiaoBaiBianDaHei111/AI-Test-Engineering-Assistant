"""State-machine transition validation tests (P2-005, R002 Suggestion 1)."""

import pytest

from app.core.exceptions import InvalidTransitionError
from app.services.state_machine import (
    REQUIREMENT_TRANSITIONS,
    TEST_CASE_TRANSITIONS,
    TEST_POINT_TRANSITIONS,
    validate_transition,
)


def test_requirement_legal_transitions():
    validate_transition("requirement", "parsed", "confirmed", REQUIREMENT_TRANSITIONS)
    validate_transition("requirement", "parsed", "archived", REQUIREMENT_TRANSITIONS)
    validate_transition("requirement", "confirmed", "archived", REQUIREMENT_TRANSITIONS)


def test_requirement_noop_allowed():
    validate_transition("requirement", "confirmed", "confirmed", REQUIREMENT_TRANSITIONS)


@pytest.mark.parametrize(
    "current,new",
    [("confirmed", "parsed"), ("archived", "confirmed"), ("archived", "parsed")],
)
def test_requirement_illegal_transitions(current, new):
    with pytest.raises(InvalidTransitionError) as exc:
        validate_transition("requirement", current, new, REQUIREMENT_TRANSITIONS)
    assert exc.value.code == "INVALID_TRANSITION"
    assert exc.value.status_code == 409


def test_test_point_legal_transitions():
    validate_transition("test point", "extracted", "confirmed", TEST_POINT_TRANSITIONS)
    validate_transition("test point", "extracted", "archived", TEST_POINT_TRANSITIONS)
    validate_transition("test point", "confirmed", "archived", TEST_POINT_TRANSITIONS)


@pytest.mark.parametrize(
    "current,new",
    [("confirmed", "extracted"), ("archived", "confirmed"), ("archived", "extracted")],
)
def test_test_point_illegal_transitions(current, new):
    with pytest.raises(InvalidTransitionError):
        validate_transition("test point", current, new, TEST_POINT_TRANSITIONS)


def test_test_case_legal_transitions():
    validate_transition("test case", "draft", "pending_review", TEST_CASE_TRANSITIONS)
    validate_transition("test case", "pending_review", "approved", TEST_CASE_TRANSITIONS)
    validate_transition("test case", "pending_review", "needs_work", TEST_CASE_TRANSITIONS)
    validate_transition("test case", "needs_work", "pending_review", TEST_CASE_TRANSITIONS)
    validate_transition("test case", "approved", "executed", TEST_CASE_TRANSITIONS)
    validate_transition("test case", "approved", "needs_work", TEST_CASE_TRANSITIONS)
    validate_transition("test case", "executed", "archived", TEST_CASE_TRANSITIONS)


@pytest.mark.parametrize(
    "status",
    ["draft", "pending_review", "approved", "needs_work", "executed"],
)
def test_test_case_direct_archive(status):
    # archived is terminal and reachable from any non-terminal state.
    validate_transition("test case", status, "archived", TEST_CASE_TRANSITIONS)


@pytest.mark.parametrize(
    "current,new",
    [
        ("draft", "approved"),          # draft -> approved direct jump
        ("draft", "needs_work"),        # draft -> needs_work (no review yet)
        ("pending_review", "draft"),    # backwards
        ("approved", "pending_review"), # backwards
        ("executed", "approved"),       # backwards
        ("archived", "draft"),          # un-archive
    ],
)
def test_test_case_illegal_transitions(current, new):
    with pytest.raises(InvalidTransitionError):
        validate_transition("test case", current, new, TEST_CASE_TRANSITIONS)
