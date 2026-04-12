"""
LLM Provider Abstraction Layer — hot-swappable providers via env vars.

Usage:
    LLM_PROVIDER=minimax|anthropic|gemini
    LLM_MODEL=<model-name>  (overrides per-provider default)

Each provider implements:
    complete(model, prompt, **kwargs) -> str           (sync, non-streaming)
    complete_with_reason(model, prompt, **kwargs) -> (str, str)  (sync + finish_reason)
    acomplete(model, prompt, **kwargs) -> str          (async, non-streaming)
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from typing import Literal
from dotenv import load_dotenv

load_dotenv()

# ── Provider type ──────────────────────────────────────────────────────────────

LLMProviderType = Literal["minimax", "anthropic", "gemini", "cerebras"]

# ── Env var names ──────────────────────────────────────────────────────────────

_PROVIDER = os.getenv("LLM_PROVIDER", "minimax")

_MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
_MINIMAX_BASE_URL = "https://api.minimax.io/v1"
_MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")

_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
_ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")

_CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
_CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
_CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "qwen-3-235b-a22b-instruct-2507")

_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "300"))
_MAX_RETRIES = 3


def _is_rate_limit(exc: Exception) -> tuple[bool, str]:
    """Check if an exception is a 429 error — don't retry these.

    Returns (is_rate_limit, error_message).
    error_message is the human-readable part from the response body for quota errors.
    """
    msg = str(exc)
    if "429" not in msg:
        return False, ""
    # Distinguish quota-exceeded (do not retry, show clear message)
    # from generic rate limits
    if "quota" in msg.lower() or "exceeded" in msg.lower():
        return True, "Quota exceeded — Gemini free tier limit reached"
    if "Too Many Requests" in msg or "rate" in msg.lower():
        return True, "Rate limited — Gemini API"
    return True, "429 error"


# ── Base protocol ─────────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """Abstract LLM provider."""

    @abstractmethod
    def complete(self, model: str, prompt: str, **kwargs) -> str:
        """Synchronous non-streaming completion. Returns text only."""
        ...

    @abstractmethod
    def complete_with_reason(
        self, model: str, prompt: str, **kwargs
    ) -> tuple[str, str]:
        """Synchronous non-streaming completion. Returns (text, finish_reason)."""
        ...

    @abstractmethod
    async def acomplete(self, model: str, prompt: str, **kwargs) -> str:
        """Async non-streaming completion."""
        ...


# ── MiniMax Provider ──────────────────────────────────────────────────────────

class MiniMaxProvider(LLMProvider):
    """MiniMax via OpenAI-compatible chat completions API."""

    def complete(self, model: str, prompt: str, **kwargs) -> str:
        text, _ = self.complete_with_reason(model, prompt, **kwargs)
        return text

    def complete_with_reason(self, model: str, prompt: str, **kwargs) -> tuple[str, str]:
        import httpx
        effective_model = model or _MINIMAX_MODEL
        messages = [{"role": "user", "content": prompt}]
        last_error = ""

        for attempt in range(_MAX_RETRIES):
            try:
                with httpx.Client(
                    base_url=_MINIMAX_BASE_URL,
                    headers={
                        "Authorization": f"Bearer {_MINIMAX_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    timeout=httpx.Timeout(60.0, connect=30.0),
                ) as client:
                    resp = client.post(
                        "/chat/completions",
                        json={
                            "model": effective_model,
                            "messages": messages,
                            "stream": False,
                            "temperature": 0.0,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"], "stop"
            except Exception as e:
                last_error = str(e)
                is_rl, _ = _is_rate_limit(e)
                if is_rl:
                    return f"Error: {last_error}", "error"
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)

        return f"Error: {last_error}", "error"

    async def acomplete(self, model: str, prompt: str, **kwargs) -> str:
        import httpx
        effective_model = model or _MINIMAX_MODEL
        messages = [{"role": "user", "content": prompt}]

        async with httpx.AsyncClient(
            base_url=_MINIMAX_BASE_URL,
            headers={
                "Authorization": f"Bearer {_MINIMAX_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=30.0),
        ) as client:
            resp = await client.post(
                "/chat/completions",
                json={
                    "model": effective_model,
                    "messages": messages,
                    "stream": False,
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


# ── Anthropic Provider ────────────────────────────────────────────────────────

class AnthropicProvider(LLMProvider):
    """Anthropic Claude via their /v1/messages endpoint."""

    def complete(self, model: str, prompt: str, **kwargs) -> str:
        text, _ = self.complete_with_reason(model, prompt, **kwargs)
        return text

    def complete_with_reason(self, model: str, prompt: str, **kwargs) -> tuple[str, str]:
        import httpx
        effective_model = model or _ANTHROPIC_MODEL
        last_error = ""

        for attempt in range(_MAX_RETRIES):
            try:
                with httpx.Client(
                    base_url=_ANTHROPIC_BASE_URL,
                    headers={
                        "x-api-key": _ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    timeout=httpx.Timeout(60.0, connect=30.0),
                ) as client:
                    resp = client.post(
                        "/messages",
                        json={
                            "model": effective_model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 4096,
                            "temperature": 0.0,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data["content"][0]["text"], data.get("stop_reason", "end_turn")
            except Exception as e:
                last_error = str(e)
                is_rl, _ = _is_rate_limit(e)
                if is_rl:
                    return f"Error: {last_error}", "error"
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)

        return f"Error: {last_error}", "error"

    async def acomplete(self, model: str, prompt: str, **kwargs) -> str:
        import httpx
        effective_model = model or _ANTHROPIC_MODEL

        async with httpx.AsyncClient(
            base_url=_ANTHROPIC_BASE_URL,
            headers={
                "x-api-key": _ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=30.0),
        ) as client:
            resp = await client.post(
                "/messages",
                json={
                    "model": effective_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4096,
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]


# ── Gemini Provider ───────────────────────────────────────────────────────────

class GeminiProvider(LLMProvider):
    """Google Gemini via the REST generativeLanguage API."""

    def complete(self, model: str, prompt: str, **kwargs) -> str:
        text, _ = self.complete_with_reason(model, prompt, **kwargs)
        return text

    def complete_with_reason(self, model: str, prompt: str, **kwargs) -> tuple[str, str]:
        import httpx
        effective_model = model or _GEMINI_MODEL
        last_error = ""

        for attempt in range(_MAX_RETRIES):
            try:
                with httpx.Client(
                    base_url=_GEMINI_BASE_URL,
                    headers={"content-type": "application/json"},
                    timeout=httpx.Timeout(60.0, connect=30.0),
                ) as client:
                    resp = client.post(
                        f"/models/{effective_model}:generateContent",
                        params={"key": _GEMINI_API_KEY},
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "temperature": 0.0,
                                "maxOutputTokens": 16384,
                            },
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return text, "stop"
            except Exception as e:
                last_error = str(e)
                if _is_rate_limit(e):
                    return f"Error: {last_error}", "error"
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)

        return f"Error: {last_error}", "error"

    async def acomplete(self, model: str, prompt: str, **kwargs) -> str:
        import httpx
        effective_model = model or _GEMINI_MODEL

        async with httpx.AsyncClient(
            base_url=_GEMINI_BASE_URL,
            headers={"content-type": "application/json"},
            timeout=httpx.Timeout(60.0, connect=30.0),
        ) as client:
            resp = await client.post(
                f"/models/{effective_model}:generateContent",
                params={"key": _GEMINI_API_KEY},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.0,
                        "maxOutputTokens": 16384,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]


# ── Cerebras Provider ──────────────────────────────────────────────────────────

class CerebrasProvider(LLMProvider):
    """Cerebras via OpenAI-compatible chat completions API."""

    def complete(self, model: str, prompt: str, **kwargs) -> str:
        text, _ = self.complete_with_reason(model, prompt, **kwargs)
        return text

    def complete_with_reason(self, model: str, prompt: str, **kwargs) -> tuple[str, str]:
        import httpx
        effective_model = model or _CEREBRAS_MODEL
        messages = [{"role": "user", "content": prompt}]
        last_error = ""

        for attempt in range(_MAX_RETRIES):
            try:
                with httpx.Client(
                    base_url=_CEREBRAS_BASE_URL,
                    headers={
                        "Authorization": f"Bearer {_CEREBRAS_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    timeout=httpx.Timeout(60.0, connect=30.0),
                ) as client:
                    resp = client.post(
                        "/chat/completions",
                        json={
                            "model": effective_model,
                            "messages": messages,
                            "stream": False,
                            "temperature": 0.0,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"], "stop"
            except Exception as e:
                last_error = str(e)
                is_rl, _ = _is_rate_limit(e)
                if is_rl:
                    # Rate limit — wait up to 30s before retrying instead of failing fast
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(30)
                        continue
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)

        return f"Error: {last_error}", "error"

    async def acomplete(self, model: str, prompt: str, **kwargs) -> str:
        import httpx
        effective_model = model or _CEREBRAS_MODEL
        messages = [{"role": "user", "content": prompt}]

        async with httpx.AsyncClient(
            base_url=_CEREBRAS_BASE_URL,
            headers={
                "Authorization": f"Bearer {_CEREBRAS_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=30.0),
        ) as client:
            resp = await client.post(
                "/chat/completions",
                json={
                    "model": effective_model,
                    "messages": messages,
                    "stream": False,
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


# ── Fallback Provider ─────────────────────────────────────────────────────────

class FallbackProvider(LLMProvider):
    """Tries a chain of (provider, model) pairs in order, moving to the next on 429."""

    def __init__(self, chain: list[tuple[LLMProvider, str]]):
        self._chain = chain

    def _try_chain(self, method: str, prompt: str, **kwargs):
        last_error = ""
        for provider, model in self._chain:
            try:
                result = getattr(provider, method)(model, prompt, **kwargs)
                # If the result is an error string from a previous provider, skip
                if isinstance(result, str) and result.startswith("Error:") and "429" in result:
                    last_error = result
                    print(f"[fallback] {provider.__class__.__name__}({model}) → 429, trying next")
                    continue
                if isinstance(result, tuple) and isinstance(result[0], str) and result[0].startswith("Error:") and "429" in result[0]:
                    last_error = result[0]
                    print(f"[fallback] {provider.__class__.__name__}({model}) → 429, trying next")
                    continue
                return result
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "Too Many Requests" in last_error.lower() or "rate" in last_error.lower():
                    print(f"[fallback] {provider.__class__.__name__}({model}) → 429, trying next")
                    continue
                # Non-429 error: still try next provider
                print(f"[fallback] {provider.__class__.__name__}({model}) → {e}, trying next")
                continue
        return f"Error: all providers failed. Last: {last_error}"

    def complete(self, model: str, prompt: str, **kwargs) -> str:
        return self._try_chain("complete", prompt, **kwargs)

    def complete_with_reason(self, model: str, prompt: str, **kwargs) -> tuple[str, str]:
        result = self._try_chain("complete_with_reason", prompt, **kwargs)
        if isinstance(result, tuple):
            return result
        return result, "error"

    async def acomplete(self, model: str, prompt: str, **kwargs) -> str:
        last_error = ""
        for provider, model_ in self._chain:
            try:
                result = await provider.acomplete(model_, prompt, **kwargs)
                if isinstance(result, str) and result.startswith("Error:") and "429" in result:
                    last_error = result
                    print(f"[fallback] {provider.__class__.__name__}({model_}) → 429, trying next")
                    continue
                return result
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "Too Many Requests" in last_error.lower():
                    print(f"[fallback] {provider.__class__.__name__}({model_}) → 429, trying next")
                    continue
                print(f"[fallback] {provider.__class__.__name__}({model_}) → {e}, trying next")
                continue
        return f"Error: all providers failed. Last: {last_error}"


# ── Factory ───────────────────────────────────────────────────────────────────

_provider_cache: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return the current LLM provider (cached).

    When LLM_PROVIDER=auto (or unset), uses a fallback chain:
      1. Gemini 2.5 Flash Lite  (fast, generous free tier)
      2. Cerebras qwen-3-235b   (fast inference, 1M tokens/day free)
      3. Cerebras llama3.1-8b   (smallest, highest rate limits)
    """
    global _provider_cache
    if _provider_cache is None:
        if _PROVIDER == "anthropic":
            _provider_cache = AnthropicProvider()
        elif _PROVIDER == "gemini":
            _provider_cache = GeminiProvider()
        elif _PROVIDER == "cerebras":
            _provider_cache = CerebrasProvider()
        elif _PROVIDER == "minimax":
            _provider_cache = MiniMaxProvider()
        else:
            # "auto" or anything else — fallback chain
            gemini = GeminiProvider()
            cerebras = CerebrasProvider()
            _provider_cache = FallbackProvider([
                (gemini,   _GEMINI_MODEL),
                (cerebras, "qwen-3-235b-a22b-instruct-2507"),
                (cerebras, "llama3.1-8b"),
            ])
    return _provider_cache


# ── Public API (mirrors ChatGPT_API signature) ────────────────────────────────

def complete(model: str, prompt: str, **kwargs) -> str:
    """Sync non-streaming LLM call. Delegates to current provider."""
    return get_provider().complete(model, prompt, **kwargs)


def complete_with_reason(model: str, prompt: str, **kwargs) -> tuple[str, str]:
    """Sync non-streaming LLM call with finish reason."""
    return get_provider().complete_with_reason(model, prompt, **kwargs)


async def acomplete(model: str, prompt: str, **kwargs) -> str:
    """Async non-streaming LLM call."""
    return await get_provider().acomplete(model, prompt, **kwargs)
