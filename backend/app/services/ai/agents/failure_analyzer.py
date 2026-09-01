"""Failure analyzer agent (LLM layer, Phase 7): context -> four-way classification.

Rule-layer misses fall through here. Output is validated against
``FailureAnalysisItem`` (category literal + confidence 0-1 + non-empty reason/fix),
repaired <=2 times, and audited. Failure raises AppError(422) so the orchestrator
does not persist a row (D2).
"""

import json

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.schemas.ai import FailureAnalysisItem
from app.services.ai.audit import record_audit
from app.services.ai.prompts import render_prompt
from app.services.ai.providers import LLMProvider, get_provider
from app.services.ai.structured import run_with_repair

AGENT_NAME = "failure_analyzer"
LIST_KEY = "analysis"


def normalize_analysis(item: dict) -> dict:
    """Clamp confidence to [0,1] rounded to 2 decimals."""
    confidence = float(item.get("confidence", 0.0))
    item["confidence"] = round(min(1.0, max(0.0, confidence)), 2)
    return item


def analyze_with_llm(db: Session, context: dict, provider: LLMProvider | None = None) -> dict:
    """Classify a failure with the LLM. Returns a normalized analysis dict.

    Raises AppError(422) on failure (unavailable / empty / invalid after repair).
    """
    provider = provider or get_provider()

    system, template, prompt_schema_version = render_prompt(AGENT_NAME)
    user = template.replace("{context}", json.dumps(context, ensure_ascii=False))

    outcome = run_with_repair(
        lambda s, u: provider.chat(s, u, json_mode=True, agent=AGENT_NAME),
        system,
        user,
        FailureAnalysisItem,
        LIST_KEY,
        max_repairs=2,
        title_key=None,
    )

    if outcome.status == "failed":
        record_audit(
            db, AGENT_NAME, prompt_schema_version, user,
            f"failed: {outcome.error_code}", outcome.tokens_in, outcome.tokens_out,
            outcome.latency_ms, "failed", failure_excerpt=outcome.raw_output,
        )
        raise AppError(
            422,
            outcome.error_code or "AI_OUTPUT_INVALID",
            "Failure analysis failed",
            {"code": outcome.error_code},
        )

    if not outcome.items:
        record_audit(
            db, AGENT_NAME, prompt_schema_version, user,
            "failed: empty analysis", outcome.tokens_in, outcome.tokens_out,
            outcome.latency_ms, "failed", failure_excerpt=outcome.raw_output,
        )
        raise AppError(422, "AI_EMPTY_RESULT", "Failure analysis returned no result", {})

    item = normalize_analysis(outcome.items[0])
    record_audit(
        db, AGENT_NAME, prompt_schema_version, user,
        f"{outcome.status}: category={item['category']}",
        outcome.tokens_in, outcome.tokens_out, outcome.latency_ms, outcome.status,
    )
    return item
