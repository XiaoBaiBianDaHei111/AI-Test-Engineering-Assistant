"""Script assembly + static validation (P5-005, MAJOR-004).

The AI only produces structured steps (description + single-expression code);
the system renders the deterministic skeleton and validates the assembled file
before execution. Validation failures feed the repair prompt (<=2 retries).
"""

import ast
import re

_FORBIDDEN_TOKENS = (
    "http://", "https://", "os.", "subprocess", "requests", "urllib", "socket",
    "open(", "import ", "exec(", "eval(", "__", "sleep", "wait_for_timeout", "time.",
)

# P016 5-5: fragile-assertion signatures (prompt is a soft constraint; these
# static rules are the hard backstop).
_TO_HAVE_URL_TRAILING_SLASH = re.compile(r"to_have_url\([\"']([^\"']*/)[\"']\)")
_GENERIC_TEXT_DENYLIST = {
    "登录", "提交", "确定", "取消", "保存", "删除", "编辑", "返回", "添加", "首页", "详情", "列表",
    "login", "submit", "ok", "cancel", "save", "delete", "edit", "back", "add",
}
_GET_BY_TEXT = re.compile(r"get_by_text\([\"']([^\"']*)[\"']\)")

_HEADER = '''# generated for TestRunCase — 可人工编辑后重跑
from playwright.sync_api import Page, expect

BASE_URL = "{base_url}"
QA_MODE = "{qa_mode}"

STEPS = [
'''


def render_skeleton(steps: list[tuple[str, str]], base_url: str, qa_mode: str) -> str:
    """Render a deterministic executable script skeleton around the steps."""
    lines = [_HEADER.format(base_url=base_url, qa_mode=qa_mode)]
    for description, code in steps:
        lines.append(f"    ({description!r}, lambda page: {code}),")
    lines.append("]\n")
    return "".join(lines)


def validate_script(script_text: str, steps: list[tuple[str, str]]) -> list[str]:
    """Run the MAJOR-004 static checks; return a list of human-readable errors.

    Checks: whole-file syntax, import whitelist, single-expression step lambdas,
    forbidden tokens, and a final expect()/assert step.
    """
    errors: list[str] = []

    # 1. whole-file syntax
    try:
        compile(script_text, "<script>", "exec")
    except SyntaxError as exc:
        errors.append(f"语法错误：{exc}")
        return errors

    # 2. import whitelist
    try:
        tree = ast.parse(script_text)
    except SyntaxError:  # pragma: no cover - already caught above
        return errors
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            errors.append(f"禁止 import：{node.names[0].name}")
        elif isinstance(node, ast.ImportFrom) and node.module != "playwright.sync_api":
            errors.append(f"禁止 import：{node.module}")

    # 3. per-step single-expression lambda + forbidden tokens
    for index, (_, code) in enumerate(steps, start=1):
        if ";" in code:
            errors.append(f"第 {index} 步含多语句（;）")
        try:
            compile(f"lambda page: {code}", f"<step {index}>", "eval")
        except SyntaxError as exc:
            errors.append(f"第 {index} 步代码不是合法单表达式：{exc}")
        for token in _FORBIDDEN_TOKENS:
            if token in code:
                errors.append(f"第 {index} 步含禁用 token：{token}")

    # 4. last step must assert
    if steps:
        last_code = steps[-1][1]
        if "expect(" not in last_code and "assert " not in last_code:
            errors.append("末步缺少 expect()/assert 最终校验")

    # 5. first step must be a goto navigation (C-3: prevents "empty pass" scripts
    #    that never navigate and pass on a trivially-true final assertion).
    if steps and "page.goto(" not in steps[0][1]:
        errors.append("首步必须为 goto 导航（page.goto(...)）")

    # 6. fragile assertions (P016 5-5): no exact trailing-slash URL assert,
    #    no generic get_by_text.
    for index, (_, code) in enumerate(steps, start=1):
        for m in _TO_HAVE_URL_TRAILING_SLASH.finditer(code):
            errors.append(f"第 {index} 步 to_have_url 断言不得以 / 结尾：{m.group(1)}")
        for m in _GET_BY_TEXT.finditer(code):
            if m.group(1).strip() in _GENERIC_TEXT_DENYLIST:
                errors.append(f"第 {index} 步 get_by_text 使用泛文本：{m.group(1)}")

    return errors


def build_script_repair_prompt(original_user: str, errors: list[str], original_output: str) -> str:
    error_text = "\n".join(f"- {e}" for e in errors)
    return (
        "你上一次生成的脚本步骤未通过静态校验。\n"
        f"校验错误：\n{error_text}\n\n"
        f"原始输入上下文（务必仅基于此内容重写）：\n{original_user[:4000]}\n\n"
        f"上一次的原始输出：\n{original_output[:2000]}\n\n"
        "请严格按 JSON 结构重新输出，每步 code 为合法的 Python 单表达式（lambda page: <code>），"
        "末步必须包含 expect() 断言，不要包含任何解释文字或代码围栏。"
    )
