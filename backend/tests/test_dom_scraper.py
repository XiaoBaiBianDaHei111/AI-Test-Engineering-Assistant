"""DOM scraper tests (P016 5-1 T5a / T5b). Pure summarization + stats/cache."""

from app.services.ai.dom_scraper import DomScraper


def test_summarize_strips_script_and_style():
    s = DomScraper()
    html = (
        "<html><head><style>.x{color:red}</style><script>alert('x')</script></head>"
        "<body><div>Username field</div>hello</body></html>"
    )
    summary = s._summarize(html, "user", "pass")
    assert "alert" not in summary
    assert "color:red" not in summary
    assert "hello" in summary


def test_summarize_redacts_credentials():
    # T5b privacy: credentials must never leak into the injected prompt.
    s = DomScraper()
    html = '<div>value="secret_password"</div>'
    summary = s._summarize(html, "my_user", "secret_password")
    assert "secret_password" not in summary
    assert "my_user" not in summary
    assert "***" in summary


def test_summarize_truncates():
    s = DomScraper()
    html = "<div>" + ("x" * 20000) + "</div>"
    summary = s._summarize(html, "u", "p")
    assert len(summary) <= 8000


def test_scrape_caches_and_records_stats(monkeypatch):
    s = DomScraper()
    calls = {"n": 0}

    def fake_once(username, password, target_url):
        calls["n"] += 1
        return "summary-x"

    monkeypatch.setattr(s, "_scrape_once", fake_once)
    assert s.scrape("u", "p", "http://x") == "summary-x"
    assert s.scrape("u", "p", "http://x") == "summary-x"  # cached
    assert calls["n"] == 1
    assert s.stats == {"ok": 1, "fail": 0}


def test_scrape_failure_increments_fail(monkeypatch):
    s = DomScraper()
    monkeypatch.setattr(s, "_scrape_once", lambda *a: None)
    assert s.scrape("u", "p", "http://y") is None
    assert s.stats == {"ok": 0, "fail": 1}
