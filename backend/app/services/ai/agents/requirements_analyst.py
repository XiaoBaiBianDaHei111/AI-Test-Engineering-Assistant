"""Requirements-analysis agent.

Long-PRD segmentation (P000 §14.5 / P002 §6.5, MINOR-003 fallback):
  > threshold  -> split by Markdown headings
  no headings  -> split by blank-line paragraphs
  no paragraphs-> fixed-size character chunks

Then each segment runs the structured-output pipeline; results are merged and
deduped (batch + against existing project requirements) and persisted as
``Requirement(status=parsed, source=ai)``.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError, NotFoundError, ValidationFailedError
from app.models import Project, Requirement
from app.schemas.ai import RequirementItem
from app.services.ai.audit import record_audit
from app.services.ai.prompts import render_prompt
from app.services.ai.providers import LLMProvider, get_provider
from app.services.ai.structured import run_with_repair, warnings_from_dropped

AGENT_NAME = "requirements_analyst"
LIST_KEY = "requirements"

_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)


def segment_text(text: str, max_chars: int) -> list[str]:
    """Split ``text`` into segments each <= ``max_chars`` (best-effort)."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sections = _split_by_headings(text)
    if not sections:
        sections = _split_by_paragraphs(text, max_chars)
    if not sections:
        sections = [text]

    segments: list[str] = []
    for section in sections:
        if len(section) <= max_chars:
            segments.append(section)
        else:
            segments.extend(_split_by_chunks(section, max_chars))
    return [s for s in segments if s]


def _split_by_headings(text: str) -> list[str]:
    matches = list(_HEADING_RE.finditer(text))
    if len(matches) < 2:
        return []
    sections: list[str] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(text[match.start() : end].strip())
    if matches[0].start() > 0:
        prefix = text[: matches[0].start()].strip()
        if prefix:
            sections.insert(0, prefix)
    return [s for s in sections if s]


def _split_by_paragraphs(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) <= 1:
        return []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks if len(chunks) >= 2 else []


def _split_by_chunks(text: str, max_chars: int) -> list[str]:
    return [text[i : i + max_chars].strip() for i in range(0, len(text), max_chars) if text[i : i + max_chars].strip()]


def analyze_requirements(
    db: Session,
    project_id: int,
    prd_text: str,
    provider: LLMProvider | None = None,
) -> dict:
    provider = provider or get_provider()

    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", {"id": project_id})
    prd_text = prd_text.strip()
    if not prd_text:
        raise ValidationFailedError("prd_text must not be empty", {"prd_text": ""})

    system, template, prompt_schema_version = render_prompt(AGENT_NAME)
    segments = segment_text(prd_text, settings.llm_max_input_chars)

    all_items: list[dict] = []
    all_dropped: list[dict] = []
    status = "success"
    error_code: str | None = None
    failure_excerpt: str | None = None
    tokens_in = tokens_out = latency = 0

    for segment in segments:
        user = template.replace("{prd_text}", segment)
        outcome = run_with_repair(
            lambda s, u: provider.chat(s, u, json_mode=True, agent=AGENT_NAME),
            system,
            user,
            RequirementItem,
            LIST_KEY,
            max_repairs=2,
        )
        all_items.extend(outcome.items)
        all_dropped.extend(outcome.dropped)
        tokens_in += outcome.tokens_in
        tokens_out += outcome.tokens_out
        latency += outcome.latency_ms
        if outcome.status == "retry":
            status = "retry"
        if outcome.status == "failed":
            status = "failed"
            error_code = outcome.error_code
            failure_excerpt = outcome.raw_output
            break

    if status == "failed":
        record_audit(
            db, AGENT_NAME, prompt_schema_version, prd_text,
            f"failed: {error_code}", tokens_in, tokens_out, latency, "failed",
            failure_excerpt=failure_excerpt,
        )
        raise AppError(
            422,
            error_code or "AI_OUTPUT_INVALID",
            "Requirements analysis failed",
            {"code": error_code},
        )

    # Cross-segment + batch dedupe.
    items = _dedupe_items(all_items)

    # Dedupe against existing project requirements (skip + warning).
    existing_titles = {
        r.title.strip().lower()
        for r in db.scalars(select(Requirement).where(Requirement.project_id == project_id))
    }
    to_insert: list[dict] = []
    warnings = warnings_from_dropped(all_dropped)
    for item in items:
        key = item["title"].strip().lower()
        if key in existing_titles:
            warnings.append(f"与已有需求重复，已跳过：{item['title']}")
            continue
        existing_titles.add(key)
        to_insert.append(item)

    output_summary = f"created {len(to_insert)} requirements; dropped {len(all_dropped)}"
    audit = record_audit(
        db, AGENT_NAME, prompt_schema_version, prd_text, output_summary,
        tokens_in, tokens_out, latency, status,
    )

    created: list[Requirement] = []
    for item in to_insert:
        requirement = Requirement(
            project_id=project_id,
            status="parsed",
            source="ai",
            doc_ref=f"ai://analyze/{audit.id}",
            **item,
        )
        db.add(requirement)
        created.append(requirement)
    db.commit()
    for requirement in created:
        db.refresh(requirement)

    api_status = "success" if not warnings else "partial"
    return {"status": api_status, "requirements": created, "warnings": warnings}


def _dedupe_items(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        key = item["title"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
