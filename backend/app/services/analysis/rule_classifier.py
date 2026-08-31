"""Deterministic failure rule classifier (Phase 7, MAJOR-005).

Python Playwright error signatures (NOT the JS camelCase variants) that lock a
failure as ``BROKEN_LOCATOR`` with fixed confidence. Deliberately decoupled from
``execution.runner._LOCATOR_ERROR_MARKERS`` (a wide element_found heuristic):
this module uses only *precise* signatures so we never over-lock on a generic
``Timeout``.
"""

from dataclasses import dataclass

from app.core.config import settings

# Strong signatures -> BROKEN_LOCATOR (confidence fixed, decision_source=rule).
STRONG_SIGNATURES: tuple[str, ...] = (
    "strict mode violation",
    "waiting for get_by_test_id(",
    "waiting for get_by_role(",
    "waiting for locator('[data-testid",
    'waiting for locator("[data-testid',
    "did not match any elements",
    "resolved to 0 elements",
    "locator.click:",
    "locator.fill:",
    "locator.check:",
)

# Not-lock conditions (checked first): these hint at REAL_BUG, so defer to the LLM.
ASSERTION_MISMATCH = ("expected:", "received:")
GET_BY_TEXT_MISSING = "waiting for get_by_text("

# P016 5-4: "unauthenticated redirect" signatures — the page redirected to the
# login page so a post-login element is missing. These are flow/precondition
# failures (not locator/DOM-contract bugs), so they map to BROKEN_LOCATOR but
# flag needs_human with a "前置缺失" reason.
PRELOGIN_REDIRECT_SIGNATURES: tuple[str, ...] = (
    "net::ERR_CONNECTION_CLOSED",
    "Add to cart",
    "product_sort_container",
    "cart_item",
    "inventory_list",
    "shopping_cart_badge",
)

# Phase 9: API connection/environment errors -> ENV_ISSUE (deterministic).
API_ENV_SIGNATURES: tuple[str, ...] = (
    "ConnectError",
    "connect error",
    "Connection refused",
    "NewConnectionError",
    "ConnectTimeout",
    "ReadTimeout",
    "RemoteProtocolError",
    "socket.gaierror",
    "Name or service not known",
    "Max retries exceeded",
)


@dataclass
class RuleDecision:
    category: str  # "BROKEN_LOCATOR" | "ENV_ISSUE"
    confidence: float
    source: str  # "rule"
    reason: str | None = None
    fix: str | None = None
    needs_human: bool = False


def rule_classify(error_text: str | None) -> RuleDecision | None:
    """Classify a failure error string with the rule table.

    Returns a ``RuleDecision`` when a strong locator / API-env signature matches,
    or ``None`` when the rule layer should defer to the LLM (including the
    explicit not-lock conditions and unknown errors).
    """
    if not error_text:
        return None

    # Not-lock conditions take precedence (never lock a likely REAL_BUG).
    if ASSERTION_MISMATCH[0] in error_text and ASSERTION_MISMATCH[1] in error_text:
        return None
    if GET_BY_TEXT_MISSING in error_text:
        return None

    # P016 5-4: unauthenticated-redirect (flow/precondition) mapping first — a
    # post-login element is missing because the page redirected to login.
    for signature in PRELOGIN_REDIRECT_SIGNATURES:
        if signature in error_text:
            return RuleDecision(
                "BROKEN_LOCATOR", settings.failure_rule_confidence, "rule",
                reason="疑似前置缺失：未登录/重定向导致目标元素不存在，需人工确认",
                fix="为用例补充登录前置（precondition/test_data 凭据，T4 登录步骤注入）后重跑",
                needs_human=True,
            )

    for signature in STRONG_SIGNATURES:
        if signature in error_text:
            return RuleDecision("BROKEN_LOCATOR", settings.failure_rule_confidence, "rule")

    for signature in API_ENV_SIGNATURES:
        if signature in error_text:
            return RuleDecision("ENV_ISSUE", settings.failure_rule_confidence, "rule")

    return None
