"""
Health checker — agent-core-infra
Verifies connectivity and config for every external service.
Call run_all() on startup or from a /health endpoint.
"""
import asyncio
import os
import time
from typing import TypedDict, Any


class CheckResult(TypedDict):
    ok: bool
    latency_ms: float | None
    error: str | None


REQUIRED_ENV_VARS = [
    "OPENAI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY",
    "R2_SECRET_KEY",
    "R2_BUCKET",
    "RESEND_API_KEY",
    "EMAIL_FROM_DOMAIN",
    "LEMON_SQUEEZY_API_KEY",
    "LEMON_STORE_ID",
    "LEMON_WEBHOOK_SECRET",
]


def _timed(fn):
    """Decorator: wraps an async check, adds latency_ms and catches exceptions."""
    async def wrapper() -> CheckResult:
        t = time.monotonic()
        try:
            result: dict[str, Any] = await fn()
            result["latency_ms"] = round((time.monotonic() - t) * 1000, 1)
            return result  # type: ignore[return-value]
        except Exception as exc:
            return {"ok": False, "error": str(exc), "latency_ms": None}
    return wrapper


async def check_env() -> CheckResult:
    missing = [k for k in REQUIRED_ENV_VARS if not os.getenv(k)]
    return {
        "ok": not missing,
        "missing": missing,
        "latency_ms": 0.0,
        "error": f"Missing env vars: {missing}" if missing else None,
    }  # type: ignore[return-value]


@_timed
async def check_supabase() -> dict:
    from ..db.supabase_client import get_client
    client = get_client()
    client.table("leads").select("id").limit(1).execute()
    return {"ok": True, "error": None}


@_timed
async def check_openai() -> dict:
    import httpx
    key = os.getenv("OPENAI_API_KEY", "")
    async with httpx.AsyncClient(timeout=8.0) as c:
        r = await c.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        ok = r.status_code == 200
        return {"ok": ok, "error": None if ok else f"HTTP {r.status_code}"}


@_timed
async def check_r2() -> dict:
    from ..storage.r2_client import _get_client, R2_BUCKET
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, lambda: _get_client().list_objects_v2(Bucket=R2_BUCKET, MaxKeys=1)
    )
    return {"ok": True, "error": None}


@_timed
async def check_resend() -> dict:
    import httpx
    key = os.getenv("RESEND_API_KEY", "")
    async with httpx.AsyncClient(timeout=8.0) as c:
        r = await c.get(
            "https://api.resend.com/domains",
            headers={"Authorization": f"Bearer {key}"},
        )
        ok = r.status_code == 200
        return {"ok": ok, "error": None if ok else f"HTTP {r.status_code}"}


async def run_all() -> dict:
    """
    Run all checks concurrently. Returns:
    {
        "ok": bool,            # True only if every check passed
        "env": CheckResult,    # env var presence
        "services": {
            "supabase": CheckResult,
            "openai":   CheckResult,
            "r2":       CheckResult,
            "resend":   CheckResult,
        }
    }
    """
    env, *service_results = await asyncio.gather(
        check_env(),
        check_supabase(),
        check_openai(),
        check_r2(),
        check_resend(),
        return_exceptions=True,
    )

    def safe(r: Any) -> CheckResult:
        if isinstance(r, Exception):
            return {"ok": False, "error": str(r), "latency_ms": None}
        return r

    services = {
        "supabase": safe(service_results[0]),
        "openai":   safe(service_results[1]),
        "r2":       safe(service_results[2]),
        "resend":   safe(service_results[3]),
    }

    all_ok = env["ok"] and all(s["ok"] for s in services.values())
    return {"ok": all_ok, "env": env, "services": services}
