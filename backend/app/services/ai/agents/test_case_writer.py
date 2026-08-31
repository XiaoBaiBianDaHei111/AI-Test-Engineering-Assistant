"""Test-case writer agent — one test point -> 1..3 structured test cases.

Reuses the Phase 2 structured-output pipeline. It does NOT persist anything;
persistence (with system-injected requirement_id / test_point_id / case_id) is
the batch orchestrator's job, which keeps this agent simple to unit-test.
"""

import json

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models import Requirement, TestPoint
from app.schemas.ai import SCHEMA_VERSION, TestCaseItem
from app.services.ai.audit import record_audit
from app.services.ai.prompts import render_prompt
from app.services.ai.providers import LLMProvider, get_provider
from app.services.ai.structured import run_with_repair, warnings_from_dropped

AGENT_NAME = "test_case_writer"
LIST_KEY = "test_cases"


def _context_json(requirement: Requirement, test_point: TestPoint) -> str:
    requirement_json = json.dumps(
        {
            "title": requirement.title,
            "description": requirement.description,
            "acceptance_criteria": requirement.acceptance_criteria,
            "risks": requirement.risks,
        },
        ensure_ascii=False,
        indent=2,
    )
    test_point_json = json.dumps(
        {
            "title": test_point.title,
            "technique": test_point.technique,
            "description": test_point.description,
        },
        ensure_ascii=False,
        indent=2,
    )
    return requirement_json, test_point_json


def generate_for_test_point(
    db: Session, test_point: TestPoint, provider: LLMProvider | None = None
) -> dict:
    """Generate test cases for one test point. Raises AppError(422) on failure.

    Returns ``{items, warnings, status, tokens_in, tokens_out, latency_ms}``.
    ``items`` are validated+deduped dicts (no case_id / requirement_id /
    test_point_id — those are injected by the caller).
    """
    provider = provider or get_provider()

    requirement = db.get(Requirement, test_point.requirement_id)
    if requirement is None:
        raise NotFoundError(
            "Requirement not found", {"requirement_id": test_point.requirement_id}
        )

    system, template, prompt_schema_version = render_prompt(AGENT_NAME)
    requirement_json, test_point_json = _context_json(requirement, test_point)
    user = (
        template.replace("{requirement}", requirement_json).replace(
            "{test_point}", test_point_json
        )
    )

    outcome = run_with_repair(
        lambda s, u: provider.chat(s, u, json_mode=True, agent=AGENT_NAME),
        system,
        user,
        TestCaseItem,
        LIST_KEY,
        max_repairs=2,
    )

    output_summary = f"{outcome.status}: {len(outcome.items)} cases"
    record_audit(
        db, AGENT_NAME, prompt_schema_version, user, output_summary,
        outcome.tokens_in, outcome.tokens_out, outcome.latency_ms, outcome.status,
        failure_excerpt=outcome.raw_output if outcome.status == "failed" else None,
    )

    if outcome.status == "failed":
        raise AppError(
            422,
            outcome.error_code or "AI_OUTPUT_INVALID",
            "Test case generation failed",
            {"test_point_id": test_point.id, "code": outcome.error_code},
        )

    return {
        "items": outcome.items,
        "warnings": warnings_from_dropped(outcome.dropped),
        "status": outcome.status,
        "tokens_in": outcome.tokens_in,
        "tokens_out": outcome.tokens_out,
        "latency_ms": outcome.latency_ms,
    }
