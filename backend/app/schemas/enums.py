"""Shared enums used across request/response schemas."""

from enum import Enum


class RequirementStatus(str, Enum):
    parsed = "parsed"
    confirmed = "confirmed"
    archived = "archived"


class AssetSource(str, Enum):
    ai = "ai"
    manual = "manual"


class TestPointStatus(str, Enum):
    extracted = "extracted"
    confirmed = "confirmed"
    archived = "archived"


class TestPointTechnique(str, Enum):
    equivalence = "equivalence"
    boundary = "boundary"
    state_transition = "state_transition"
    exception = "exception"
    error_guessing = "error_guessing"


class TestCasePriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TestCaseType(str, Enum):
    smoke = "smoke"
    functional = "functional"
    boundary = "boundary"
    exception = "exception"
    performance = "performance"
    security = "security"
    compatibility = "compatibility"


class TestCaseStatus(str, Enum):
    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    needs_work = "needs_work"
    executed = "executed"
    archived = "archived"
