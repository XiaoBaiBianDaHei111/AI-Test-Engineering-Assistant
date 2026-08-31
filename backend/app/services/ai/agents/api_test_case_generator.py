"""API test-case generator agent (Phase 9): interface description -> APITestCase list.

Reuses the Phase 2 structured-output pipeline; does NOT persist anything. The
caller persists with project_id/requirement_id injected (not trusted from the LLM).
"""

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.schemas.ai import SCHEMA_VERSION, ApiTestCaseItem
from app.services.ai.audit import record_audit
from app.services.ai.prompts import render_prompt
from app.services.ai.providers import LLMProvider, get_provider
from app.services.ai.structured import run_with_repair, warnings_from_dropped

AGENT_NAME = "api_test_case_generator"
LIST_KEY = "api_test_cases"


def generate_api_test_cases(
    db: Session, description: str, provider: LLMProvider | None = None
) -> dict:
    """Generate API test cases from a description. Raises AppError(422) on failure.

    Returns ``{items, warnings, status, tokens_in, tokens_out, latency_ms}``.
    """
    provider = provider or get_provider()

    system, template, prompt_schema_version = render_prompt(AGENT_NAME)
    user = template.replace("{description}", description)

    outcome = run_with_repair(
        lambda s, u: provider.chat(s, u, json_mode=True, agent=AGENT_NAME),
        system,
        user,
        ApiTestCaseItem,
        LIST_KEY,
        max_repairs=2,
        title_key="name",
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
            "API test case generation failed",
            {"code": outcome.error_code},
        )

    return {
        "items": outcome.items,
        "warnings": warnings_from_dropped(outcome.dropped),
        "status": outcome.status,
        "tokens_in": outcome.tokens_in,
        "tokens_out": outcome.tokens_out,
        "latency_ms": outcome.latency_ms,
    }
