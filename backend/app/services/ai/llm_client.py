"""DeepSeek (OpenAI-compatible) provider: httpx + timeout + exponential backoff retry.

Retry semantics (ADOPT TestForge llm-caller.js): retry on timeout / transport
errors / 429 / 5xx with exponential backoff capped at 10s. Token usage is read
from the DeepSeek ``usage`` field when present.
"""

import time

import httpx

from app.core.config import settings
from app.services.ai.providers import ChatResult, LLMProvider, LLMUnavailableError


class LLMClient(LLMProvider):
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        base_delay: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model or settings.llm_model
        self.timeout = timeout if timeout is not None else settings.llm_timeout_seconds
        self.max_retries = max_retries if max_retries is not None else settings.llm_max_retries
        self.base_delay = (
            base_delay if base_delay is not None else settings.llm_retry_base_delay_seconds
        )
        self._client = httpx.Client(timeout=self.timeout, transport=transport)

    def chat(self, system: str, user: str, json_mode: bool = True, agent: str = "") -> ChatResult:
        if not self.api_key:
            raise LLMUnavailableError(
                "LLM_API_KEY is not configured for the deepseek provider"
            )

        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": settings.llm_temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        last_error = "unknown"
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                response = self._client.post(url, json=payload, headers=headers)
                latency_ms = int((time.monotonic() - started) * 1000)
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                    self._backoff(attempt)
                    continue
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {}) or {}
                return ChatResult(
                    content=content,
                    tokens_in=usage.get("prompt_tokens", 0),
                    tokens_out=usage.get("completion_tokens", 0),
                    latency_ms=latency_ms,
                )
            except httpx.HTTPStatusError as exc:
                # Non-retryable 4xx (429/5xx are handled above via backoff+continue,
                # so this only fires for 401/400/403 etc.). Surface clearly, no retry.
                status = exc.response.status_code
                body = (exc.response.text or "")[:200]
                raise LLMUnavailableError(f"LLM HTTP {status}: {body}") from exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self._backoff(attempt)
                continue

        raise LLMUnavailableError(f"LLM call failed after retries: {last_error}")

    def close(self) -> None:
        """Close the underlying httpx connection pool."""
        self._client.close()

    def _backoff(self, attempt: int) -> None:
        # No sleep after the final failed attempt (we are about to raise anyway).
        if attempt >= self.max_retries:
            return
        delay = min(self.base_delay * (2**attempt), 10.0)
        if delay > 0:
            time.sleep(delay)
