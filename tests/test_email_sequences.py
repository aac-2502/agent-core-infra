"""Email sequence + template context tests."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch


def test_send_after_is_real_timestamp_not_sql_string():
    """Regression: send_after used to be the literal string
    "NOW() + INTERVAL '72 hours'". PostgREST inserts JSON values as-is —
    it does not evaluate SQL expressions — so Postgres rejected it as an
    invalid timestamp. It must be a real ISO datetime instead."""
    from lib.email.sequences import trigger_sequence

    queued = []

    async def fake_insert(table, data, schema="public"):
        queued.append(data)
        return data

    with patch("lib.email.sequences.insert", new=fake_insert), \
         patch("lib.email.sequences.send_template", new=AsyncMock()):
        asyncio.run(trigger_sequence("user@test.com", "agentcv_paid", {"product": "agentcv"}))

    assert len(queued) == 2  # nurture_1 @72h, upsell @240h — delivery @0h sends immediately
    for row in queued:
        assert "NOW()" not in row["send_after"]
        parsed = datetime.fromisoformat(row["send_after"])
        assert parsed > datetime.now(timezone.utc)


def test_unknown_sequence_is_a_noop():
    from lib.email.sequences import trigger_sequence

    with patch("lib.email.sequences.insert", new=AsyncMock()) as mock_insert, \
         patch("lib.email.sequences.send_template", new=AsyncMock()) as mock_send:
        asyncio.run(trigger_sequence("user@test.com", "does_not_exist", {}))

    mock_insert.assert_not_called()
    mock_send.assert_not_called()


def test_load_template_merges_default_context():
    from lib.email.resend_client import _load_template

    html = _load_template("delivery", {"product": "agentcv", "downloads_html": ""})
    assert "promykon.com" in html
    assert "$promykon_url" not in html


def test_load_template_caller_overrides_defaults():
    from lib.email.resend_client import _load_template

    html = _load_template("delivery", {
        "product":      "agentcv",
        "downloads_html": "",
        "promykon_url":   "https://custom.example.com",
    })
    assert "custom.example.com" in html
    assert "promykon.com\"" not in html
