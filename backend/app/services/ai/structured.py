"""Structured-output pipeline (P000 §14.2).

    LLM raw text
      -> tolerant JSON extraction (strip fences / find balanced {...})   [ADOPT ai-nlt _extract_json]
      -> Pydantic schema validation (per-item, list top-level)           [ADOPT TestForge validators]
      -> normalization (title dedupe, field cleaning)                    [ADOPT ai-nlt _normalize]
      -> on whole-output failure, repair prompt + regenerate (<=2 times) [ADOPT pw-qa-agent buildRepairPrompt]
      -> still failing? -> ``failed`` outcome (never silently swallowed)
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from app.services.ai.providers import ChatResult, LLMUnavailableError


class ExtractionError(Exception):
    """No parseable JSON could be found in the LLM output."""


class OutputValidationError(Exception):
    """The LLM output has a valid JSON shape but the wrong top-level structure."""


_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*([\s\S]*?)```", re.DOTALL)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub(r"\1", text)


def _extract_balanced(text: str, open_ch: str, close_ch: str) -> str | None:
    """Return the outermost balanced ``open_ch ... close_ch`` span, honoring strings."""
    start = text.find(open_ch)
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(text: str) -> object:
    """Tolerant JSON extraction: strip fences, then try whole-text parse,
    then the outermost balanced ``{...}`` / ``[...]`` block."""
    if not text or not text.strip():
        raise ExtractionError("empty response")

    cleaned = _strip_fences(text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    block = _extract_balanced(cleaned, "{", "}")
    if block:
        try:
            return json.loads(block)
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"invalid JSON object: {exc}") from exc

    block = _extract_balanced(cleaned, "[", "]")
    if block:
        try:
            return json.loads(block)
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"invalid JSON array: {exc}") from exc

    raise ExtractionError("no JSON found in response")


def normalize_title(title: str) -> str:
    return title.strip().lower()


def validate_and_normalize(
    parsed: object,
    item_schema: type[BaseModel],
    list_key: str,
    title_key: str = "title",
) -> tuple[list[dict], list[dict]]:
    """Validate the top-level ``{list_key: [...]}`` structure, validate each item
    individually (dropping invalid ones), and dedupe by normalized title.

    Returns ``(items, dropped)``. Raises ``OutputValidationError`` only when the
    top-level structure itself is wrong (which triggers repair).
    """
    if not isinstance(parsed, dict):
        raise OutputValidationError("output must be a JSON object")
    raw_list = parsed.get(list_key)
    if raw_list is None or not isinstance(raw_list, list):
        raise OutputValidationError(f"missing or invalid '{list_key}' list")

    items: list[dict] = []
    dropped: list[dict] = []
    seen: set[str] = set()
    for raw in raw_list:
        try:
            item = item_schema.model_validate(raw)
        except ValidationError as exc:
            dropped.append({"reason": "invalid_item", "detail": str(exc)[:500]})
            continue
        item_dict = item.model_dump(mode="json")
        if title_key is not None:
            key = normalize_title(item_dict[title_key])
            if key in seen:
                dropped.append({"reason": "duplicate", "title": item_dict[title_key]})
                continue
            seen.add(key)
        items.append(item_dict)
    return items, dropped


@dataclass
class StructuredOutcome:
    items: list[dict] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    attempts: int = 0
    status: str = "failed"  # success | retry | failed
    error_code: str | None = None  # AI_OUTPUT_INVALID | AI_EMPTY_RESULT | AI_UNAVAILABLE
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    # Last raw LLM output (for failure forensics, B-2). None on AI_UNAVAILABLE.
    raw_output: str | None = None


def _build_repair_prompt(
    item_schema: type[BaseModel],
    list_key: str,
    original_output: str,
    error: str,
    original_user: str,
) -> str:
    schema_json = json.dumps(item_schema.model_json_schema(), ensure_ascii=False)
    # R004 MINOR-002: keep the source document in the repair round so the model
    # still rewrites against the original input (not just the broken output).
    source_context = (original_user or "")[:4000]
    return (
        "你上一次的输出无法解析或校验失败。\n"
        f"错误信息：{error}\n\n"
        f"原始输入上下文（务必仅基于此内容重写）：\n{source_context}\n\n"
        f"上一次的原始输出：\n{original_output[:2000]}\n\n"
        "请严格按以下 JSON 结构重新输出，不要包含任何解释文字或代码围栏：\n"
        f'{{"{list_key}": [ <item>, ... ] }}\n\n'
        f"每个 item 必须符合该 JSON Schema：\n{schema_json}"
    )


def run_with_repair(
    llm_fn: Callable[[str, str], ChatResult],
    system: str,
    user: str,
    item_schema: type[BaseModel],
    list_key: str,
    max_repairs: int = 2,
    title_key: str = "title",
) -> StructuredOutcome:
    """Run one structured generation with up to ``max_repairs`` repair attempts.

    ``llm_fn(system, user) -> ChatResult`` is a closure wrapping the provider.
    ``title_key=None`` disables title dedupe (for single-object, non-title outputs).
    """
    outcome = StructuredOutcome()
    current_user = user
    last_error_code: str | None = None

    for attempt in range(1, max_repairs + 2):
        outcome.attempts = attempt
        try:
            chat = llm_fn(system, current_user)
        except LLMUnavailableError as exc:
            outcome.status = "failed"
            outcome.error_code = "AI_UNAVAILABLE"
            outcome.dropped = [{"reason": "unavailable", "detail": str(exc)}]
            return outcome

        outcome.tokens_in += chat.tokens_in
        outcome.tokens_out += chat.tokens_out
        outcome.latency_ms += chat.latency_ms
        outcome.raw_output = chat.content

        try:
            parsed = extract_json(chat.content)
            items, dropped = validate_and_normalize(parsed, item_schema, list_key, title_key)
        except (ExtractionError, OutputValidationError) as exc:
            last_error_code = "AI_OUTPUT_INVALID"
            current_user = _build_repair_prompt(
                item_schema, list_key, chat.content, str(exc), user
            )
            continue

        if not items:
            # Valid structure but no usable items: empty result or all-dropped.
            last_error_code = "AI_EMPTY_RESULT" if not dropped else "AI_OUTPUT_INVALID"
            current_user = _build_repair_prompt(
                item_schema, list_key, chat.content, "no valid items in output", user
            )
            continue

        outcome.items = items
        outcome.dropped = dropped
        outcome.status = "retry" if attempt > 1 else "success"
        outcome.error_code = None
        return outcome

    outcome.status = "failed"
    outcome.error_code = last_error_code or "AI_OUTPUT_INVALID"
    return outcome


def warnings_from_dropped(dropped: list[dict]) -> list[str]:
    """Human-readable warnings for dropped items."""
    warnings = []
    for item in dropped:
        reason = item.get("reason")
        if reason == "duplicate":
            warnings.append(f"重复项已去重：{item.get('title', '')}")
        elif reason == "invalid_item":
            warnings.append(f"无效项已丢弃：{item.get('detail', '')}")
        elif reason == "unavailable":
            warnings.append(f"LLM 不可用：{item.get('detail', '')}")
        else:
            warnings.append("无效项已丢弃")
    return warnings
