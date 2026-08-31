"""State-machine transition tables + validation helper (R002 Suggestion 1).

Legal transitions are linear with a terminal ``archived`` state:
    Requirement: parsed -> confirmed -> archived
    TestPoint:   extracted -> confirmed -> archived

Any other transition (including backwards, e.g. confirmed -> parsed) raises
``InvalidTransitionError`` (409, code=INVALID_TRANSITION).
"""

from app.core.exceptions import InvalidTransitionError

REQUIREMENT_TRANSITIONS: dict[str, set[str]] = {
    "parsed": {"confirmed", "archived"},
    "confirmed": {"archived"},
    "archived": set(),
}

TEST_POINT_TRANSITIONS: dict[str, set[str]] = {
    "extracted": {"confirmed", "archived"},
    "confirmed": {"archived"},
    "archived": set(),
}

# TestCase state machine (frozen in P000 section 12 / P004 section 6.2):
#   draft -> pending_review -> approved / needs_work -> executed -> archived
#   needs_work -> pending_review (resubmit after edit)
#   approved -> needs_work (R004-P004 MINOR-001: editing an approved case
#   invalidates its review and requires re-review)
TEST_CASE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending_review", "archived"},
    "pending_review": {"approved", "needs_work", "archived"},
    "approved": {"executed", "needs_work", "archived"},
    "needs_work": {"pending_review", "archived"},
    "executed": {"archived"},
    "archived": set(),
}

# FailureAnalysis state machine (P007 section 6.2, deviation D4):
#   pending -> classified (auto-analysis writes a classified result)
#   classified -> confirmed (human confirmation)
# No rollback / no archive semantics.
FAILURE_ANALYSIS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"classified"},
    "classified": {"confirmed"},
    "confirmed": set(),
}


def validate_transition(
    entity: str, current: str, new: str, transitions: dict[str, set[str]]
) -> None:
    """Raise InvalidTransitionError if ``current -> new`` is not allowed.

    A no-op (``current == new``) is always allowed so PATCH with an unchanged
    status does not spuriously fail.
    """
    if current == new:
        return
    if new not in transitions.get(current, set()):
        raise InvalidTransitionError(
            f"Invalid {entity} status transition",
            {"from": current, "to": new},
        )
