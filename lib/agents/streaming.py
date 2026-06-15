"""
SSE streaming utilities — agent-core-infra
Provides Server-Sent Events helpers for FastAPI status endpoints.
"""
import asyncio
import json
from typing import Any, AsyncGenerator


def _encode(data: Any, event: str = "message") -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def sse_event(data: Any, event: str = "message") -> str:
    return _encode(data, event)


async def job_stream(
    job_store: dict,
    job_id: str,
    poll_interval: float = 0.5,
    timeout_seconds: float = 300.0,
) -> AsyncGenerator[str, None]:
    """
    Yield SSE frames from an in-memory job_store until the job is terminal.
    In production, swap job_store for a Redis wrapper that implements .get().
    """
    elapsed = 0.0
    while elapsed < timeout_seconds:
        job = job_store.get(job_id)
        if job is None:
            yield _encode({"status": "not_found"}, "error")
            return

        yield _encode(job)

        if job.get("status") in ("done", "error"):
            return

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    yield _encode({"status": "error", "message": "stream timeout"}, "error")


def make_progress_event(
    job_id: str,
    progress: int,
    message: str,
    status: str = "processing",
    artifact_urls: dict | None = None,
    error: str | None = None,
) -> dict:
    """Construct a typed progress payload for job_store updates."""
    return {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "message": message,
        "artifact_urls": artifact_urls or {},
        "error": error,
    }
