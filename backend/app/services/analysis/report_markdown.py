"""Markdown report exporter (Phase 8, M2) — rendered from report data, no AI."""


def _pct(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def render(stats: dict) -> str:
    o = stats.get("overview", {})
    lines = [
        f"# 测试报告 — {stats.get('run_name', '')}",
        "",
        f"- Run: #{stats.get('run_id')}",
        f"- 状态: {stats.get('run_status', '')}",
        f"- 通过率: {_pct(o.get('pass_rate', 0))}",
        f"- 总数/通过/失败/阻塞/跳过: {o.get('total', 0)} / {o.get('passed', 0)} / "
        f"{o.get('failed', 0)} / {o.get('blocked', 0)} / {o.get('skipped', 0)}",
        "",
        "## 按优先级通过率",
        "",
        "| 优先级 | 总数 | 通过 | 失败 | 通过率 |",
        "|---|---|---|---|---|",
    ]
    for priority, bucket in stats.get("priority", {}).items():
        lines.append(
            f"| {priority} | {bucket.get('total', 0)} | {bucket.get('passed', 0)} | "
            f"{bucket.get('failed', 0)} | {_pct(bucket.get('pass_rate', 0))} |"
        )

    lines += ["", "## 失败分类分布", ""]
    for category, count in stats.get("failure_categories", {}).items():
        lines.append(f"- {category}: {count}")

    lines += ["", "## 用例明细", ""]
    for case in stats.get("cases", []):
        lines.append(
            f"- [{case.get('status')}] {case.get('case_label')} ({case.get('duration_ms', 0)}ms)"
        )
        if case.get("error"):
            lines.append(f"  - 错误: {(case.get('error') or '')[:200]}")

    lines += ["", "## 失败分析", ""]
    for case in stats.get("cases", []):
        fa = case.get("failure_analysis")
        if fa:
            lines.append(
                f"- {case.get('case_label')}: **{fa.get('category')}** "
                f"(confidence {fa.get('confidence')})\n"
                f"  - 原因: {fa.get('reason')}\n  - 建议: {fa.get('suggested_fix')}"
            )

    return "\n".join(lines) + "\n"
