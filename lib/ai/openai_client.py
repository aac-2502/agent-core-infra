"""
AI client — agent-core-infra
Multi-provider with automatic failover. OpenAI, Gemini, and Groq ride the
OpenAI-compatible chat completions endpoint; Anthropic uses its native SDK.

Configure:
  AI_PROVIDER=groq                        # primary provider
  AI_FALLBACK_PROVIDERS=anthropic,openai  # comma-separated, tried in order if the
                                           # primary is rate-limited or errors out
  AI_MODEL_FAST / AI_MODEL_SMART          # override the primary provider's model
                                           # for a given speed tier
"""
import asyncio
import os
import re
from collections import defaultdict

from openai import AsyncOpenAI, RateLimitError as OpenAIRateLimitError
from anthropic import AsyncAnthropic, RateLimitError as AnthropicRateLimitError

# ── Provider config ──────────────────────────────────────────────────────────

_PROVIDER_CONFIG = {
    "openai": {
        "kind": "openai_compatible",
        "base_url": None,  # default OpenAI endpoint
        "api_key_env": "OPENAI_API_KEY",
        "model_fast": "gpt-4o-mini",
        "model_smart": "gpt-4o",
    },
    "gemini": {
        "kind": "openai_compatible",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "model_fast": "gemini-2.0-flash",
        "model_smart": "gemini-2.0-flash",
    },
    "groq": {
        "kind": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model_fast": "llama-3.3-70b-versatile",
        "model_smart": "llama-3.3-70b-versatile",
    },
    "anthropic": {
        "kind": "anthropic",
        "api_key_env": "ANTHROPIC_API_KEY",
        "model_fast": "claude-haiku-4-5",
        "model_smart": "claude-sonnet-5",
    },
}

_COSTS = {
    "gpt-4o":                  {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":             {"input": 0.15,  "output": 0.60},
    "gemini-2.0-flash":        {"input": 0.00,  "output": 0.00},  # free tier
    "gemini-1.5-pro":          {"input": 1.25,  "output": 5.00},
    "gemini-1.5-flash":        {"input": 0.075, "output": 0.30},
    "llama-3.3-70b-versatile": {"input": 0.00,  "output": 0.00},  # groq free tier
    "claude-sonnet-5":         {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5":        {"input": 1.00,  "output": 5.00},
    "claude-opus-4-8":         {"input": 5.00,  "output": 25.00},
}

_openai_clients: dict[str, AsyncOpenAI] = {}
_anthropic_client: AsyncAnthropic | None = None
_cost_log: dict[str, float] = defaultdict(float)
_cost_log_by_model: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))


def _provider_chain() -> list[str]:
    """Primary provider (AI_PROVIDER) first, then AI_FALLBACK_PROVIDERS in order."""
    primary = os.getenv("AI_PROVIDER", "openai").lower()
    fallback = [p.strip().lower() for p in os.getenv("AI_FALLBACK_PROVIDERS", "").split(",") if p.strip()]
    chain = [primary] + [p for p in fallback if p != primary]
    unknown = [p for p in chain if p not in _PROVIDER_CONFIG]
    if unknown:
        raise ValueError(f"Unknown AI provider(s) {unknown}. Configured: {list(_PROVIDER_CONFIG)}")
    return chain


def _get_openai_client(provider: str) -> AsyncOpenAI:
    if provider not in _openai_clients:
        cfg = _PROVIDER_CONFIG[provider]
        _openai_clients[provider] = AsyncOpenAI(
            api_key=os.getenv(cfg["api_key_env"], ""),
            base_url=cfg["base_url"],
        )
    return _openai_clients[provider]


def _get_anthropic_client() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    return _anthropic_client


def default_model(speed: str = "fast", provider: str | None = None) -> str:
    """
    Return the default model for a provider (defaults to the primary). speed='fast'|'smart'.
    AI_MODEL_FAST/AI_MODEL_SMART only override the *primary* provider's tier — a fallback
    provider always uses its own default, so a stale override can't break failover by
    pointing a fallback at a model it doesn't serve.
    """
    chain = _provider_chain()
    provider = provider or chain[0]
    cfg = _PROVIDER_CONFIG[provider]
    env_key = f"AI_MODEL_{speed.upper()}"
    if provider == chain[0] and os.getenv(env_key):
        return os.getenv(env_key)
    return cfg[f"model_{speed}"]


def _log_cost(product: str, model: str, input_tokens: int, output_tokens: int) -> float:
    costs = _COSTS.get(model, {"input": 0, "output": 0})
    cost = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000
    _cost_log[product] += cost
    _cost_log_by_model[product][model] += cost
    return cost


async def _call_openai_compatible(
    provider: str, model: str, messages: list[dict], max_tokens: int, json_mode: bool
) -> tuple[str, int, int]:
    kwargs: dict = dict(model=model, messages=messages, max_tokens=max_tokens)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await _get_openai_client(provider).chat.completions.create(**kwargs)
    usage = resp.usage
    return (
        resp.choices[0].message.content,
        getattr(usage, "prompt_tokens", 0),
        getattr(usage, "completion_tokens", 0),
    )


async def _call_anthropic(
    model: str, messages: list[dict], max_tokens: int, json_mode: bool
) -> tuple[str, int, int]:
    system = None
    claude_messages = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            claude_messages.append(m)
    if json_mode:
        system = (system or "") + "\n\nRespond with valid JSON only — no prose, no markdown fences."
    kwargs: dict = dict(model=model, messages=claude_messages, max_tokens=max_tokens)
    if system:
        kwargs["system"] = system.strip()
    resp = await _get_anthropic_client().messages.create(**kwargs)
    text = "".join(block.text for block in resp.content if block.type == "text")
    return text, resp.usage.input_tokens, resp.usage.output_tokens


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
    Call the configured AI provider. Retries transient errors (rate limits, 5xx)
    up to `retries` times per provider, then fails over to the next provider in
    AI_FALLBACK_PROVIDERS. `model`, if given, only applies to the primary provider —
    fallback providers use their own default for `speed`, since a model id from one
    provider is meaningless on another.
    """
    chain = _provider_chain()
    last_error: Exception | None = None

    for provider in chain:
        cfg = _PROVIDER_CONFIG[provider]
        active_model = model if (model and provider == chain[0]) else default_model(speed, provider)

        for attempt in range(retries):
            try:
                if cfg["kind"] == "anthropic":
                    text, in_tok, out_tok = await _call_anthropic(active_model, messages, max_tokens, json_mode)
                else:
                    text, in_tok, out_tok = await _call_openai_compatible(
                        provider, active_model, messages, max_tokens, json_mode
                    )
                _log_cost(product, active_model, in_tok, out_tok)
                return text
            except (OpenAIRateLimitError, AnthropicRateLimitError) as e:
                last_error = e
                if attempt == retries - 1:
                    break  # exhausted retries on this provider — try the next one
                m = re.search(r"retryDelay.*?'(\d+)s'", str(e))  # Gemini-style hint
                wait = int(m.group(1)) + 5 if m else 2 ** attempt * 5
                await asyncio.sleep(wait)
            except Exception as e:
                last_error = e
                if attempt == retries - 1:
                    break
                await asyncio.sleep(2 ** attempt)

    raise last_error or RuntimeError("All AI providers failed with no error captured")


def get_costs() -> dict:
    """Total cost per product, e.g. {'agentcv': 0.0431}."""
    return dict(_cost_log)


def get_costs_by_model() -> dict:
    """Cost per product broken down by model, e.g. {'agentcv': {'claude-sonnet-5': 0.031, 'llama-3.3-70b-versatile': 0.0}}."""
    return {product: dict(models) for product, models in _cost_log_by_model.items()}
