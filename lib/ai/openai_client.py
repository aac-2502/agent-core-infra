"""
AI client — agent-core-infra
Supports OpenAI and Google Gemini (via OpenAI-compatible endpoint).
Set AI_PROVIDER=gemini + GEMINI_API_KEY to use Gemini for free.
"""
import asyncio
import os
from openai import AsyncOpenAI, RateLimitError
from collections import defaultdict

# ── Provider config ──────────────────────────────────────────────────────────

_PROVIDER_CONFIG = {
    "openai": {
        "base_url": None,  # default OpenAI endpoint
        "api_key_env": "OPENAI_API_KEY",
        "model_fast": "gpt-4o-mini",
        "model_smart": "gpt-4o",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "model_fast": "gemini-2.0-flash",
        "model_smart": "gemini-2.0-flash",
    },
}

_COSTS = {
    "gpt-4o":              {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":         {"input": 0.15,  "output": 0.60},
    "gemini-2.0-flash":    {"input": 0.00,  "output": 0.00},  # free tier
    "gemini-1.5-pro":      {"input": 1.25,  "output": 5.00},
    "gemini-1.5-flash":    {"input": 0.075, "output": 0.30},
}

_client: AsyncOpenAI | None = None
_cost_log: dict[str, float] = defaultdict(float)


def _provider() -> str:
    return os.getenv("AI_PROVIDER", "openai").lower()


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        cfg = _PROVIDER_CONFIG[_provider()]
        _client = AsyncOpenAI(
            api_key=os.getenv(cfg["api_key_env"], ""),
            base_url=cfg["base_url"],
        )
    return _client


def default_model(speed: str = "fast") -> str:
    """Return the default model for the active provider. speed='fast'|'smart'"""
    cfg = _PROVIDER_CONFIG[_provider()]
    env_key = f"AI_MODEL_{speed.upper()}"
    return os.getenv(env_key, cfg[f"model_{speed}"])


def _log_cost(product: str, model: str, usage) -> float:
    costs = _COSTS.get(model, {"input": 0, "output": 0})
    cost = (
        getattr(usage, "prompt_tokens", 0) * costs["input"]
        + getattr(usage, "completion_tokens", 0) * costs["output"]
    ) / 1_000_000
    _cost_log[product] += cost
    return cost


async def complete(
    messages: list[dict],
    model: str | None = None,
    product: str = "unknown",
    json_mode: bool = False,
    max_tokens: int = 2000,
    retries: int = 3,
    speed: str = "fast",
) -> str:
    """
    Call the configured AI provider.
    If model is None, uses the provider default for the given speed ('fast'|'smart').
    """
    if model is None:
        model = default_model(speed)

    kwargs: dict = dict(model=model, messages=messages, max_tokens=max_tokens)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(retries):
        try:
            resp = await _get_client().chat.completions.create(**kwargs)
            _log_cost(product, model, resp.usage)
            return resp.choices[0].message.content
        except RateLimitError as e:
            if attempt == retries - 1:
                raise
            # Parse retryDelay from Gemini error (e.g. "retryDelay: '57s'")
            import re as _re
            m = _re.search(r"retryDelay.*?'(\d+)s'", str(e))
            wait = int(m.group(1)) + 5 if m else 65
            await asyncio.sleep(wait)
        except Exception:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)


def get_costs() -> dict:
    return dict(_cost_log)
