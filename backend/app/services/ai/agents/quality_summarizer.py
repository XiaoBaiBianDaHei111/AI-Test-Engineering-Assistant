"""Quality summarizer agent (LLM layer, Phase 8, M2).

The LLM is asked for a quality conclusion, but its ``recommendation`` and
``overall_score`` are never trusted: the service recomputes them from the pass
rate / blocked count via ``derive_recommendation`` (same "rule overrides the LLM"
pattern as the reviewer verdict). The LLM only supplies ``risk_factors`` and
``reasoning``.
"""

import json

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.schemas.ai import QualitySummaryItem
from app.services.ai.audit import record_audit
from app.services.ai.prompts import render_prompt
from app.services.ai.providers import LLMProvider, get_provider
from app.services.ai.structured import run_with_repair

AGENT_NAME = "quality_summarizer"
LIST_KEY = "quality_summary"


def derive_recommendation(pass_rate: float, blocked_count: int) -> str:
    """Rule-derived release recommendation (MINOR-001: never trust the LLM)."""
    if pass_rate >= 1.0 and blocked_count == 0:
        return "GO"
    if pass_rate >= 0.8:
        return "CONDITIONAL_GO"
    return "NO_GO"


def normalize_summary(item: dict) -> dict:
    item["overall_score"] = int(min(100, max(0, int(item.get("overall_score", 0)))))
    item["risk_factors"] = (item.get("risk_factors") or [])[:5]
    return item


def analyze_with_llm(db: Session, stats: dict, provider: LLMProvider | None = None) -> dict:
    """Return the LLM's normalized summary (risk_factors/reasoning only matter).

    Raises AppError(422) on failure (unavailable / empty / invalid after repair) so
    the service does not persist a row (D2).
    """
    provider = provider or get_provider()

    system, template, prompt_schema_version = render_prompt(AGENT_NAME)
    user = template.replace("{stats}", json.dumps(stats, ensure_ascii=False))

    outcome = run_with_repair(
        lambda s, u: provider.chat(s, u, json_mode=True, agent=AGENT_NAME),
        system,
        user,
        QualitySummaryItem,
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
            422, outcome.error_code or "AI_OUTPUT_INVALID", "Quality summary failed",
            {"code": outcome.error_code},
        )

    if not outcome.items:
        record_audit(
            db, AGENT_NAME, prompt_schema_version, user,
            "failed: empty quality summary", outcome.tokens_in, outcome.tokens_out,
            outcome.latency_ms, "failed", failure_excerpt=outcome.raw_output,
        )
        raise AppError(422, "AI_EMPTY_RESULT", "Quality summary returned no result", {})

    item = normalize_summary(outcome.items[0])
    record_audit(
        db, AGENT_NAME, prompt_schema_version, user,
        f"{outcome.status}: recommendation={item['recommendation']}",
        outcome.tokens_in, outcome.tokens_out, outcome.latency_ms, outcome.status,
    )
    return item
