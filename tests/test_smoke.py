"""Smoke tests — verify imports and basic instantiation."""

def test_imports():
    from lib.ai import complete, get_costs
    from lib.db import insert, update, select_one, upsert_lead
    from lib.storage import upload_artifact, signed_url, upload_and_sign
    from lib.email import send_email, send_template, send_delivery
    from lib.payments import get_provider, CheckoutResult
    from lib.agents import BaseAgent, BaseJobState, with_retry
    from lib.pdf import render_pdf, render_report, render_document


def test_base_agent_is_abstract():
    import pytest
    from lib.agents import BaseAgent
    with pytest.raises(TypeError):
        BaseAgent()  # cannot instantiate abstract class


def test_retry_decorator():
    import asyncio
    from lib.agents.retry import retryable

    call_count = 0

    @retryable(retries=3, base_delay=0)
    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("not yet")
        return "ok"

    result = asyncio.run(flaky())
    assert result == "ok"
    assert call_count == 3
