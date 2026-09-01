"""Failure analysis orchestrator (Phase 7): rule -> LLM -> confidence gate -> upsert.

``analyze_failure`` is the single entry point used both by run_batch's automatic
trigger (isolated) and the API retry endpoint. Rule hits cost zero LLM calls;
LLM misses are gated by the confidence threshold (``needs_human``).
"""

from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.exceptions import InvalidTransitionError, NotFoundError, ValidationFailedError
from app.models import FailureAnalysis, TestRunCase
from app.services.ai.agents.failure_analyzer import analyze_with_llm
from app.services.ai.providers import LLMProvider, get_provider
from app.services.analysis.failure_context import build_failure_context
from app.services.analysis.rule_classifier import rule_classify

_RULE_REASON = (
    "定位器失效（BROKEN_LOCATOR）：脚本引用的定位器（data-testid/角色）在当前页面无法匹配，"
    "属脚本/DOM 契约问题而非产品缺陷。"
)
_RULE_FIX = (
    "核对页面元素的 data-testid/角色是否变更；保持稳定的定位器契约；"
    "若页面结构变更，同步更新用例步骤与脚本定位器后重跑。"
)


def get_analysis(db: Session, run_case_id: int) -> FailureAnalysis | None:
    return db.scalar(select(FailureAnalysis).where(FailureAnalysis.run_case_id == run_case_id))


def _upsert(
    db: Session, run_case_id: int, category: str, confidence: float,
    reason: str, suggested_fix: str, decision_source: str, needs_human: bool,
) -> FailureAnalysis:
    # D6: single row per run case; re-analysis overwrites (delete + reinsert so a
    # previously-confirmed row is not an illegal state-machine transition).
    db.execute(delete(FailureAnalysis).where(FailureAnalysis.run_case_id == run_case_id))
    analysis = FailureAnalysis(
        run_case_id=run_case_id,
        category=category,
        confidence=confidence,
        reason=reason,
        suggested_fix=suggested_fix,
        decision_source=decision_source,
        needs_human=needs_human,
        status="classified",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def analyze_failure(
    db: Session, run_case_id: int, provider: LLMProvider | None = None
) -> FailureAnalysis:
    """Analyze a failed/blocked run case (rule first, then LLM, then gate)."""
    run_case = db.scalar(
        select(TestRunCase)
        .options(selectinload(TestRunCase.step_results))
        .where(TestRunCase.id == run_case_id)
    )
    if run_case is None:
        raise NotFoundError("Run case not found", {"id": run_case_id})
    if run_case.status not in {"failed", "blocked"}:
        raise ValidationFailedError(
            "Only failed/blocked run cases can be analyzed",
            {"run_case_id": run_case_id, "status": run_case.status},
        )

    script_text = ""
    if run_case.script_path and Path(run_case.script_path).exists():
        script_text = Path(run_case.script_path).read_text(encoding="utf-8")

    # Rule layer (zero LLM calls).
    decision = rule_classify(run_case.error)
    if decision is not None:
        return _upsert(
            db, run_case_id, decision.category, decision.confidence,
            decision.reason or _RULE_REASON, decision.fix or _RULE_FIX,
            "rule", needs_human=decision.needs_human,
        )

    # LLM layer + confidence gate.
    provider = provider or get_provider()
    context = build_failure_context(db, run_case, script_text)
    item = analyze_with_llm(db, context, provider)
    needs_human = item["confidence"] < settings.failure_analysis_confidence_threshold
    return _upsert(
        db, run_case_id, item["category"], item["confidence"],
        item["reason"], item["suggested_fix"], "llm", needs_human=needs_human,
    )


def confirm_analysis(db: Session, analysis_id: int) -> FailureAnalysis:
    analysis = db.get(FailureAnalysis, analysis_id)
    if analysis is None:
        raise NotFoundError("Failure analysis not found", {"id": analysis_id})
    # Only classified -> confirmed is allowed (a no-op re-confirm must 409, AC-7-08).
    if analysis.status != "classified":
        raise InvalidTransitionError(
            "Failure analysis can only be confirmed from classified",
            {"from": analysis.status, "to": "confirmed"},
        )
    analysis.status = "confirmed"
    db.commit()
    db.refresh(analysis)
    return analysis
