"""Generation-time login DOM scraper (P016 5-1 / T5a). Env-gated, best-effort.

The scraper runs a headless Playwright login against the target (using test_data
credentials) and returns a script/style-stripped, credential-redacted text summary
(<=8KB) of the post-login DOM. That summary is injected into the ``script_generator``
prompt so selectors match the real target. Any failure (no browser / network /
timeout) returns ``None`` and the caller degrades to the no-DOM behavior.
"""

import re
import threading

MAX_SUMMARY_CHARS = 8000

_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>", re.IGNORECASE)
_STYLE_RE = re.compile(r"<style[\s\S]*?</style>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


class DomScraper:
    """Scrapes post-login DOM summaries; caches per target URL (T5b stats)."""

    def __init__(self) -> None:
        self._cache: dict[str, str | None] = {}
        self.stats: dict[str, int] = {"ok": 0, "fail": 0}

    def scrape(self, username: str, password: str, target_url: str) -> str | None:
        if target_url in self._cache:
            return self._cache[target_url]
        summary = self._scrape_once(username, password, target_url)
        self._cache[target_url] = summary
        self.stats["ok" if summary is not None else "fail"] += 1
        return summary

    def _scrape_once(self, username: str, password: str, target_url: str) -> str | None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception:  # noqa: BLE001 - playwright not installed
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto(target_url, timeout=15000)
                    # Best-effort login (SauceDemo-compatible role locators). If the
                    # login form is absent (already public), just keep the page.
                    try:
                        page.get_by_role("textbox", name="Username").fill(username, timeout=5000)
                        page.get_by_role("textbox", name="Password").fill(password, timeout=5000)
                        page.get_by_role("button", name="Login").click(timeout=5000)
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:  # noqa: BLE001 - login not present / already authed
                        pass
                    html = page.content()
                finally:
                    browser.close()
        except Exception:  # noqa: BLE001 - no browser / network / timeout
            return None
        return self._summarize(html, username, password)

    def _summarize(self, html: str, username: str, password: str) -> str:
        """Strip script/style, collapse whitespace, truncate, redact credentials."""
        cleaned = _SCRIPT_RE.sub("", html)
        cleaned = _STYLE_RE.sub("", cleaned)
        text = _TAG_RE.sub(" ", cleaned)
        text = re.sub(r"\s+", " ", text).strip()
        text = text[:MAX_SUMMARY_CHARS]
        # Privacy (T5b): credentials must never leak into the prompt.
        for secret in (password, username):
            if secret:
                text = text.replace(secret, "***")
        return text


_singleton: DomScraper | None = None
_lock = threading.Lock()


def get_dom_scraper() -> DomScraper:
    """Return the process-wide scraper singleton (injectable in tests)."""
    global _singleton
    with _lock:
        if _singleton is None:
            _singleton = DomScraper()
        return _singleton
