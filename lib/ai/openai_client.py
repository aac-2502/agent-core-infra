"""
OpenAI client — agent-core-infra
Rate-limited client with per-product cost tracking.
"""
import asyncio
import os
from openai import AsyncOpenAI
from collections import defaultdict

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_client: AsyncOpenAI | None = None

def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    return _client

# Cost per 1M tokens (as of mid-2025, update as needed)
_COSTS = {
    "gpt-4o":       {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":  {"input": 0.15,  "output": 0.60},
}

# Simple in-memory cost tracker (use Redis in prod)
_cost_log: dict[str, float] = defaultdict(float)

def _log_cost(product: str, model: str, usage) -> float:
    costs = _COSTS.get(model, {"input": 0, "output": 0})
    cost = (usage.prompt_tokens * costs["input"] + usage.completion_tokens * costs["output"]) / 1_000_000
    _cost_log[product] += cost
    return cost

async def complete(
    messages: list[dict],
    model: str = "gpt-4o-mini",
    product: str = "unknown",
    json_mode: bool = False,
    max_tokens: int = 2000,
    retries: int = 3,
) -> str:
    kwargs = dict(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(retries):
        try:
            resp = await _get_client().chat.completions.create(**kwargs)
            _log_cost(product, model, resp.usage)
            return resp.choices[0].message.content
        except Exception:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)

def get_costs() -> dict:
    return dict(_cost_log)
