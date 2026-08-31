"""Test-point extraction agent.

Extracts test points from a *confirmed* requirement (Gate 2). Runs the
structured-output pipeline, dedupes (batch + against the requirement's existing
test points), and persists as ``TestPoint(status=extracted)``.
"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models import TestPoint
from app.schemas.ai import SCHEMA_VERSION, TestPointItem
from app.services.ai.audit import record_audit
from app.services.ai.prompts import render_prompt
from app.services.ai.providers import LLMProvider, get_provider
from app.services.ai.structured import run_with_repair, warnings_from_dropped
from app.services.assets.test_point_service import get_requirement_or_404

AGENT_NAME = "test_point_extractor"
LIST_KEY = "test_points"


def extract_test_points(
    db: Session,
    requirement_id: int,
    provider: LLMProvider | None = None,
) -> dict:
    provider = provider or get_provider()

    requirement = get_requirement_or_404(db, requirement_id)
    if requirement.status != "confirmed":
        raise ConflictError(
            "Requirement must be confirmed before extracting test points",
            {"requirement_id": requirement_id, "status": requirement.status},
        )

    system, template, prompt_schema_version = render_prompt(AGENT_NAME)
    requirement_text = json.dumps(
        {
            "title": requirement.title,
            "description": requirement.description,
            "acceptance_criteria": requirement.acceptance_criteria,
            "risks": requirement.risks,
        },
        ensure_ascii=False,
        indent=2,
    )
    user = template.replace("{requirement}", requirement_text)

    outcome = run_with_repair(
        lambda s, u: provider.chat(s, u, json_mode=True, agent=AGENT_NAME),
        system,
        user,
        TestPointItem,
        LIST_KEY,
        max_repairs=2,
    )

    if outcome.status == "failed":
        record_audit(
            db, AGENT_NAME, prompt_schema_version, requirement_text,
            f"failed: {outcome.error_code}", outcome.tokens_in, outcome.tokens_out,
            outcome.latency_ms, "failed", failure_excerpt=outcome.raw_output,
        )
        raise AppError(
            422,
            outcome.error_code or "AI_OUTPUT_INVALID",
            "Test point extraction failed",
            {"code": outcome.error_code},
        )

    # Dedupe against the requirement's existing test points (R003 MINOR-001).
    existing_titles = {
        tp.title.strip().lower()
        for tp in db.scalars(
            select(TestPoint).where(TestPoint.requirement_id == requirement_id)
        )
    }
    to_insert: list[dict] = []
    warnings = warnings_from_dropped(outcome.dropped)
    for item in outcome.items:
        key = item["title"].strip().lower()
        if key in existing_titles:
            warnings.append(f"与已有测试点重复，已跳过：{item['title']}")
            continue
        existing_titles.add(key)
        to_insert.append(item)

    output_summary = f"created {len(to_insert)} test points; dropped {len(outcome.dropped)}"
    record_audit(
        db, AGENT_NAME, prompt_schema_version, requirement_text, output_summary,
        outcome.tokens_in, outcome.tokens_out, outcome.latency_ms, outcome.status,
    )

    created: list[TestPoint] = []
    for item in to_insert:
        test_point = TestPoint(
            requirement_id=requirement_id, status="extracted", **item
        )
        db.add(test_point)
        created.append(test_point)
    db.commit()
    for test_point in created:
        db.refresh(test_point)

    api_status = "success" if not warnings else "partial"
    return {"status": api_status, "test_points": created, "warnings": warnings}
