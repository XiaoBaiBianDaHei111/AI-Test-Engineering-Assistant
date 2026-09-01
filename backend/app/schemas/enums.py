"""Shared enums used across request/response schemas."""

from enum import StrEnum


class RequirementStatus(StrEnum):
    parsed = "parsed"
    confirmed = "confirmed"
    archived = "archived"


class AssetSource(StrEnum):
    ai = "ai"
    manual = "manual"


class TestPointStatus(StrEnum):
    extracted = "extracted"
    confirmed = "confirmed"
    archived = "archived"


class TestPointTechnique(StrEnum):
    equivalence = "equivalence"
    boundary = "boundary"
    state_transition = "state_transition"
    exception = "exception"
    error_guessing = "error_guessing"


class TestCasePriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TestCaseType(StrEnum):
    smoke = "smoke"
    functional = "functional"
    boundary = "boundary"
    exception = "exception"
    performance = "performance"
    security = "security"
    compatibility = "compatibility"


class TestCaseStatus(StrEnum):
    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    needs_work = "needs_work"
    executed = "executed"
    archived = "archived"
