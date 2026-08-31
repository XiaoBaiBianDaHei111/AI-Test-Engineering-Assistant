"""LLM client tests (P2-003). Real mode (P013)."""

import httpx
import pytest

from app.services.ai.llm_client import LLMClient
from app.services.ai.providers import LLMUnavailableError


def _ok_response(request):
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3},
        },
    )


def _client(handler, api_key="secret", max_retries=2):
    return LLMClient(
        api_key=api_key,
        transport=httpx.MockTransport(handler),
        base_delay=0.0,
        max_retries=max_retries,
    )


# --- DeepSeek LLMClient ---------------------------------------------------

def test_chat_returns_content_and_usage():
    client = _client(_ok_response)
    result = client.chat("sys", "user")
    assert result.content == "{}"
    assert result.tokens_in == 7
    assert result.tokens_out == 3
    assert result.latency_ms >= 0


def test_retry_on_5xx_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={})
        return _ok_response(request)

    result = _client(handler).chat("sys", "user")
    assert result.content == "{}"
    assert calls["n"] == 2


def test_retry_exhausts_on_5xx():
    def handler(request):
        return httpx.Response(500, json={})

    with pytest.raises(LLMUnavailableError):
        _client(handler).chat("sys", "user")


def test_4xx_raises_llm_unavailable_without_retry():
    # F3: non-retryable 4xx (401) -> clear LLMUnavailableError, no retry.
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, json={"error": "invalid key"})

    with pytest.raises(LLMUnavailableError) as exc:
        _client(handler).chat("sys", "user")
    assert "401" in str(exc.value)
    assert calls["n"] == 1


def test_429_still_retries():
    # F3: 429 is retryable (rate limit) — first attempt 429, second succeeds.
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={})
        return _ok_response(request)

    result = _client(handler).chat("sys", "user")
    assert result.content == "{}"
    assert calls["n"] == 2


def test_retry_on_transport_error():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(LLMUnavailableError):
        _client(handler).chat("sys", "user")


def test_missing_api_key_raises():
    client = LLMClient(api_key="", transport=httpx.MockTransport(_ok_response))
    with pytest.raises(LLMUnavailableError):
        client.chat("sys", "user")


# --- R004 MINOR-001 / Suggestion 1 fixes -------------------------------

def test_deepseek_provider_singleton():
    from app.services.ai import providers

    providers.close_all()  # ensure clean state
    first = providers.get_provider()
    second = providers.get_provider()
    assert first is second  # same connection-pool instance reused
    providers.close_all()


def test_backoff_does_not_sleep_after_last_attempt(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.ai.llm_client.time.sleep", lambda s: sleeps.append(s))

    def handler(request):
        return httpx.Response(500, json={})

    client = LLMClient(
        api_key="k",
        transport=httpx.MockTransport(handler),
        base_delay=1.0,
        max_retries=2,
    )
    with pytest.raises(LLMUnavailableError):
        client.chat("sys", "user")
    # 3 attempts total; sleep on attempts 0 and 1 only (not the final attempt).
    assert len(sleeps) == 2
