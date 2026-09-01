"""Script generator agent (P5-004): approved test case -> structured Playwright steps.

The AI produces structured steps (description + single-expression code); the
system assembles the skeleton and static-validates it (with repair, <=2) before
execution. Returns the assembled script text, never executes it.
"""

import json

from sqlalchemy.orm import Session

from app.models import Requirement, TestCase
from app.schemas.ai import ScriptStepItem
from app.services.ai.agents.script_assembler import (
    build_script_repair_prompt,
    render_skeleton,
    validate_script,
)
from app.services.ai.audit import record_audit
from app.services.ai.dom_scraper import get_dom_scraper
from app.services.ai.prompts import render_prompt
from app.services.ai.providers import LLMProvider, get_provider
from app.services.ai.structured import run_with_repair

AGENT_NAME = "script_generator"
LIST_KEY = "script"


def _login_required(test_case: TestCase) -> bool:
    """P016 5-2: a test case needs a login preamble when test_data carries
    credentials (username/password) or an explicit ``login`` flag."""
    td = test_case.test_data or {}
    return bool(td.get("login")) or bool(td.get("username")) or bool(td.get("password"))


def _login_steps(test_case: TestCase) -> list[tuple[str, str]]:
    """Deterministic login preamble (role-based, external-site compatible).

    Credentials come from test_data (defaults are the SauceDemo demo creds); the
    steps are inserted AFTER the first goto and do NOT re-navigate (no goto /
    forbidden tokens), so they never re-trigger the BASE_URL rule.
    """
    if not _login_required(test_case):
        return []
    td = test_case.test_data or {}
    username = td.get("username") or "standard_user"
    password = td.get("password") or "secret_sauce"
    return [
        ("登录：输入用户名", f'page.get_by_role("textbox", name="Username").fill("{username}")'),
        ("登录：输入密码", f'page.get_by_role("textbox", name="Password").fill("{password}")'),
        ("登录：提交", 'page.get_by_role("button", name="Login").click()'),
    ]


def _dom_summary_for_case(test_case: TestCase, config: dict) -> str | None:
    """T5a (P016 5-1): scrape the post-login DOM summary for prompt injection.

    Env-gated + best-effort; returns None when no browser / no credentials target.
    """
    td = test_case.test_data or {}
    if not (td.get("username") or td.get("password")):
        return None
    username = td.get("username") or "standard_user"
    password = td.get("password") or "secret_sauce"
    target_url = td.get("target_url") or config.get("base_url") or "http://localhost:8001"
    return get_dom_scraper().scrape(username, password, target_url)


def _context_json(test_case: TestCase) -> tuple[str, str]:
    test_case_json = json.dumps(
        {
            "title": test_case.title,
            "precondition": test_case.precondition,
            "steps": [
                {"action": s.action, "expected_result": s.expected_result}
                for s in test_case.steps
            ],
            "expected_result": test_case.expected_result,
            "test_data": test_case.test_data,
            "type": test_case.type,
            "priority": test_case.priority,
        },
        ensure_ascii=False,
        indent=2,
    )
    return test_case_json


def generate_script(
    db: Session,
    test_case: TestCase,
    config: dict,
    provider: LLMProvider | None = None,
) -> dict:
    """Generate + assemble + static-validate a script (with repair <=2).

    Returns ``{status, script_text, steps, error_code, tokens_in, tokens_out,
    latency_ms}``. ``status`` is ``success`` | ``retry`` | ``failed``. On
    ``failed`` the caller records a blocked case; never raises for validation.
    """
    provider = provider or get_provider()

    requirement = db.get(Requirement, test_case.requirement_id) if test_case.requirement_id else None
    requirement_json = json.dumps(
        {
            "title": requirement.title if requirement else "",
            "acceptance_criteria": requirement.acceptance_criteria if requirement else [],
        },
        ensure_ascii=False,
        indent=2,
    )
    system, template, prompt_schema_version = render_prompt(AGENT_NAME)
    test_case_json = _context_json(test_case)
    user = template.replace("{test_case}", test_case_json).replace("{requirement}", requirement_json)

    # T5a (P016 5-1): inject the post-login DOM summary (env-gated, best-effort)
    # so selectors are grounded in the real target, not demo semantics.
    dom_summary = _dom_summary_for_case(test_case, config)
    if dom_summary:
        user += "\n\n目标站登录后 DOM 摘要（仅供选择器参考，不得编造不存在的元素）：\n" + dom_summary

    base_url = config.get("base_url", "http://localhost:8001")
    qa_mode = config.get("qa_mode", "none")

    current_user = user
    last_output = ""
    tokens_in = tokens_out = latency = 0
    status = "success"
    last_error_code: str | None = None
    failure_excerpt: str | None = None
    validation_errors: list[str] = []

    for attempt in range(1, 4):  # 1 initial + 2 repairs
        outcome = run_with_repair(
            lambda s, u: provider.chat(s, u, json_mode=True, agent=AGENT_NAME),
            system,
            current_user,
            ScriptStepItem,
            LIST_KEY,
            max_repairs=2,
            title_key=None,
        )
        tokens_in += outcome.tokens_in
        tokens_out += outcome.tokens_out
        latency += outcome.latency_ms
        last_output = current_user

        if outcome.status == "failed":
            status = "failed"
            last_error_code = outcome.error_code
            failure_excerpt = outcome.raw_output
            break

        steps = [(item["description"], item["code"]) for item in outcome.items]
        if not (3 <= len(steps) <= 15):
            status = "retry"
            last_error_code = "SCRIPT_INVALID_STEPS"
            validation_errors = [f"步骤数量须 3~15，当前 {len(steps)}"]
            current_user = build_script_repair_prompt(user, validation_errors, current_user)
            continue

        # T4 (P016 5-2): inject the deterministic login preamble right after the
        # first goto when the case needs login (system-side, not AI-side).
        login_steps = _login_steps(test_case)
        if login_steps and steps and "page.goto(" in steps[0][1]:
            steps = steps[:1] + login_steps + steps[1:]

        script_text = render_skeleton(steps, base_url, qa_mode)
        errors = validate_script(script_text, steps)
        if not errors:
            if attempt > 1:
                status = "retry"
            record_audit(
                db, AGENT_NAME, prompt_schema_version, user,
                f"{status}: {len(steps)} steps", tokens_in, tokens_out, latency, status,
            )
            return {
                "status": status, "script_text": script_text, "steps": steps,
                "error_code": None, "tokens_in": tokens_in, "tokens_out": tokens_out,
                "latency_ms": latency,
            }

        status = "retry"
        last_error_code = "SCRIPT_VALIDATION_FAILED"
        validation_errors = errors
        current_user = build_script_repair_prompt(user, errors, last_output)

    # T1 (P016 5-3): surface static-validation errors as the failure excerpt, so
    # blocked cases are reproducible (previously this path had excerpt=None).
    excerpt = failure_excerpt
    if validation_errors:
        excerpt = f"{last_error_code}: " + "; ".join(validation_errors)
    record_audit(
        db, AGENT_NAME, prompt_schema_version, user,
        f"failed: {last_error_code}", tokens_in, tokens_out, latency, "failed",
        failure_excerpt=excerpt,
    )
    return {
        "status": "failed", "script_text": None, "steps": [],
        "error_code": last_error_code or "SCRIPT_VALIDATION_FAILED",
        "tokens_in": tokens_in, "tokens_out": tokens_out, "latency_ms": latency,
    }
