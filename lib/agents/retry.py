"""
Retry with exponential backoff — agent-core-infra
"""
import asyncio
import functools
from typing import Callable, Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


async def with_retry(
    fn: Callable,
    *args,
    retries: int = 3,
    base_delay: float = 1.0,
    **kwargs,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))
    raise last_exc  # type: ignore[misc]


def retryable(retries: int = 3, base_delay: float = 1.0):
    """Decorator — wraps an async function with exponential backoff retry."""
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await with_retry(fn, *args, retries=retries, base_delay=base_delay, **kwargs)
        return wrapper  # type: ignore[return-value]
    return decorator
