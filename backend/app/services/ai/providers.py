"""Provider abstraction + factory (real DeepSeek only, P013)."""

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMUnavailableError(Exception):
    """Raised when an LLM call fails after all HTTP-level retries."""


@dataclass
class ChatResult:
    """A single completed chat-completion call."""

    content: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0


class LLMProvider(ABC):
    """A single (non-repairing) chat completion call.

    ``agent`` is an opaque hint (kept for call-site stability; the real provider
    ignores it). ``provider`` is injectable per-call for dependency inversion.
    """

    @abstractmethod
    def chat(self, system: str, user: str, json_mode: bool = True, agent: str = "") -> ChatResult:
        raise NotImplementedError


# Reuse one DeepSeek LLMClient (and its httpx connection pool) across requests
# instead of leaking a new pool per request.
_deepseek_singleton: "LLMProvider | None" = None
_deepseek_lock = threading.Lock()


def get_provider() -> LLMProvider:
    """Return the lazily-created DeepSeek LLMClient singleton."""
    global _deepseek_singleton
    with _deepseek_lock:
        if _deepseek_singleton is None:
            from app.services.ai.llm_client import LLMClient

            _deepseek_singleton = LLMClient()
        return _deepseek_singleton


def close_all() -> None:
    """Close the shared provider (called on app shutdown via lifespan)."""
    global _deepseek_singleton
    with _deepseek_lock:
        provider = _deepseek_singleton
        _deepseek_singleton = None
    if provider is not None and hasattr(provider, "close"):
        provider.close()
