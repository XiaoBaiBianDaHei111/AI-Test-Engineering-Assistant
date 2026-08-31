"""Self-contained HTML report generator (Phase 8, M1).

Produces a single-file HTML report (inline CSS, no external CDN) from the
``report_stats`` dict. Screenshots <=200KB are base64-embedded (MINOR-002); larger
or non-image evidence becomes a relative ``/api/evidence/{id}/content`` link that
shows a "服务模式可查看" placeholder when opened offline.
"""

import base64
import html as _html
from typing import Callable

SCREENSHOT_EMBED_LIMIT = 200 * 1024  # 200 KB

_CSS = """
body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; margin: 24px; color: #1f2937; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 16px; border-bottom: 2px solid #e5e7eb; padding-bottom: 4px; margin-top: 24px; }
table { border-collapse: collapse; width: 100%; margin-top: 8px; font-size: 13px; }
th, td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #f9fafb; }
.meta { color: #6b7280; font-size: 13px; }
.pass { color: #15803d; font-weight: 600; }
.fail { color: #b91c1c; font-weight: 600; }
.blocked { color: #a16207; font-weight: 600; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; color: #fff; }
.badge.BROKEN_LOCATOR { background: #dc2626; }
.badge.REAL_BUG { background: #ea580c; }
.badge.FLAKY { background: #ca8a04; }
.badge.ENV_ISSUE { background: #6b7280; }
.badge.GO { background: #16a34a; }
.badge.CONDITIONAL_GO { background: #ca8a04; }
.badge.NO_GO { background: #dc2626; }
.screenshot { display: inline-block; margin: 4px; text-align: center; }
.screenshot img { max-width: 260px; border: 1px solid #e5e7eb; border-radius: 4px; }
.placeholder { color: #9ca3af; font-style: italic; }
.reason { background: #fef9c3; padding: 6px 8px; border-radius: 4px; margin: 4px 0; }
"""


def _esc(value) -> str:
    return _html.escape(str(value), quote=True)


def _pct(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def _overview_table(stats: dict) -> str:
    o = stats.get("overview", {})
    rows = [
        ("总用例数", o.get("total", 0)),
        ("通过", o.get("passed", 0)),
        ("失败", o.get("failed", 0)),
        ("阻塞", o.get("blocked", 0)),
        ("跳过", o.get("skipped", 0)),
        ("通过率", _pct(o.get("pass_rate", 0))),
        ("耗时", f"{o.get('duration_ms', 0)} ms"),
    ]
    body = "".join(f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>" for k, v in rows)
    return f"<table>{body}</table>"


def _priority_table(stats: dict) -> str:
    header = "<tr><th>优先级</th><th>总数</th><th>通过</th><th>失败</th><th>通过率</th></tr>"
    rows = []
    for priority, bucket in stats.get("priority", {}).items():
        rows.append(
            f"<tr><td>{_esc(priority)}</td><td>{bucket.get('total', 0)}</td>"
            f"<td class='pass'>{bucket.get('passed', 0)}</td>"
            f"<td class='fail'>{bucket.get('failed', 0)}</td>"
            f"<td>{_pct(bucket.get('pass_rate', 0))}</td></tr>"
        )
    return f"<table>{header}{''.join(rows)}</table>"


def _failure_category_table(stats: dict) -> str:
    header = "<tr><th>分类</th><th>数量</th></tr>"
    rows = [
        f"<tr><td><span class='badge {_esc(cat)}'>{_esc(cat)}</span></td><td>{count}</td></tr>"
        for cat, count in stats.get("failure_categories", {}).items()
    ]
    return f"<table>{header}{''.join(rows)}</table>"


def _failure_analysis_list(stats: dict) -> str:
    items = []
    for case in stats.get("cases", []):
        fa = case.get("failure_analysis")
        if not fa:
            continue
        items.append(
            f"<li><strong>{_esc(case.get('case_label', ''))}</strong> "
            f"<span class='badge {_esc(fa.get('category', ''))}'>{_esc(fa.get('category', ''))}</span>"
            f"<div class='reason'>原因：{_esc(fa.get('reason', ''))}<br/>建议：{_esc(fa.get('suggested_fix', ''))}</div></li>"
        )
    if not items:
        return "<p class='placeholder'>无失败分析</p>"
    return f"<ul>{''.join(items)}</ul>"


def _cases_table(stats: dict) -> str:
    header = "<tr><th>用例</th><th>优先级</th><th>状态</th><th>耗时</th><th>错误</th></tr>"
    rows = []
    for case in stats.get("cases", []):
        status = case.get("status", "")
        status_cls = {"passed": "pass", "failed": "fail", "blocked": "blocked"}.get(status, "")
        rows.append(
            f"<tr><td>{_esc(case.get('case_label', ''))}</td>"
            f"<td>{_esc(case.get('priority', 'unknown'))}</td>"
            f"<td class='{status_cls}'>{_esc(status)}</td>"
            f"<td>{case.get('duration_ms', 0)} ms</td>"
            f"<td>{_esc((case.get('error') or '')[:300])}</td></tr>"
        )
    return f"<table>{header}{''.join(rows)}</table>"


def _evidence_section(stats: dict, screenshot_provider) -> str:
    parts = []
    for case in stats.get("cases", []):
        evidence = case.get("evidence", {})
        shots = evidence.get("screenshots", [])
        if shots:
            parts.append(f"<h3>{_esc(case.get('case_label', ''))} — 截图</h3>")
        for shot in shots:
            shot_id = shot.get("id")
            size = shot.get("size_bytes") or 0
            content_url = f"/api/evidence/{shot_id}/content"
            img_html = ""
            if screenshot_provider is not None and size <= SCREENSHOT_EMBED_LIMIT:
                data = screenshot_provider(shot_id)
                if data:
                    b64 = base64.b64encode(data).decode("ascii")
                    img_html = f"<img src='data:image/png;base64,{b64}' alt='step {shot.get('step_number', '')}'/>"
            if not img_html:
                img_html = (
                    f"<a href='{content_url}'>"
                    "<span class='placeholder'>服务模式可查看（离线打开无此证据）</span></a>"
                )
            parts.append(f"<span class='screenshot'>{img_html}<br/><span class='meta'>步骤 {shot.get('step_number', '')} · {size} B</span></span>")

        for kind, label in (("trace", "Trace"), ("console", "Console"), ("network", "Network")):
            for item in evidence.get(kind, []):
                url = f"/api/evidence/{item.get('id')}/content"
                parts.append(
                    f"<p class='meta'>{_esc(label)}：<a href='{url}'>服务模式可查看</a></p>"
                )
    if not parts:
        return "<p class='placeholder'>无证据</p>"
    return "".join(parts)


def render(stats: dict, screenshot_provider: Callable[[int], bytes | None] | None = None) -> str:
    """Render a self-contained HTML report string."""
    meta = (
        f"<p class='meta'>Run #{_esc(stats.get('run_id'))} · {_esc(stats.get('run_name', ''))} "
        f"· 状态 {_esc(stats.get('run_status', ''))}</p>"
    )
    return (
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"<title>测试报告 {_esc(stats.get('run_name', ''))}</title><style>{_CSS}</style></head><body>"
        f"<h1>测试报告</h1>{meta}"
        "<h2>总览</h2>" + _overview_table(stats) +
        "<h2>按优先级通过率</h2>" + _priority_table(stats) +
        "<h2>失败分类分布</h2>" + _failure_category_table(stats) +
        "<h2>用例明细</h2>" + _cases_table(stats) +
        "<h2>失败分析</h2>" + _failure_analysis_list(stats) +
        "<h2>证据</h2>" + _evidence_section(stats, screenshot_provider) +
        "</body></html>"
    )
