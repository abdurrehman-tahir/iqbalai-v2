"""Tests for NATS event publisher per T-012 acceptance criteria."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.events.publisher import _build_envelope, publish

# ---------------------------------------------------------------------------
# _build_envelope — pure function, no network
# ---------------------------------------------------------------------------


def test_envelope_contains_all_required_fields() -> None:
    """Per ARCH §9: envelope must have all 7 required fields."""
    envelope = _build_envelope(
        event_type="system.smoke_test",
        payload={"key": "value"},
        tenant_id="tenant-abc",
        tenant_type="school",
        user_id="user-xyz",
        session_id="sess-001",
    )
    required_fields = {
        "tenant_id",
        "tenant_type",
        "user_id",
        "session_id",
        "occurred_at",
        "event_type",
        "payload",
    }
    assert required_fields.issubset(envelope.keys())


def test_envelope_tenant_id_set_correctly() -> None:
    envelope = _build_envelope("evt", {}, tenant_id="t-123", tenant_type="school", user_id="u-456")
    assert envelope["tenant_id"] == "t-123"


def test_envelope_tenant_type_set_correctly() -> None:
    envelope = _build_envelope("evt", {}, tenant_id="t-1", tenant_type="independent", user_id="u-1")
    assert envelope["tenant_type"] == "independent"


def test_envelope_user_id_set_correctly() -> None:
    envelope = _build_envelope("evt", {}, tenant_id="t-1", tenant_type="school", user_id="u-999")
    assert envelope["user_id"] == "u-999"


def test_envelope_event_type_set_correctly() -> None:
    envelope = _build_envelope(
        "system.smoke_test", {}, tenant_id="", tenant_type="school", user_id=""
    )
    assert envelope["event_type"] == "system.smoke_test"


def test_envelope_payload_is_passed_through() -> None:
    payload = {"answer": 42, "nested": {"ok": True}}
    envelope = _build_envelope("evt", payload, tenant_id="", tenant_type="school", user_id="")
    assert envelope["payload"] == payload


def test_envelope_occurred_at_is_utc_iso_format() -> None:
    envelope = _build_envelope("evt", {}, tenant_id="", tenant_type="school", user_id="")
    occurred_at: str = envelope["occurred_at"]
    # Must be parseable and timezone-aware (ends with +00:00 or Z)
    assert "T" in occurred_at
    assert occurred_at.endswith("+00:00") or occurred_at.endswith("Z")


def test_envelope_session_id_defaults_to_empty_string() -> None:
    envelope = _build_envelope("evt", {}, tenant_id="", tenant_type="school", user_id="")
    assert envelope["session_id"] == ""


def test_envelope_is_json_serialisable() -> None:
    """Envelope must be serialisable before publish sends it over the wire."""
    envelope = _build_envelope(
        "system.smoke_test", {"x": 1}, tenant_id="t", tenant_type="school", user_id="u"
    )
    serialised = json.dumps(envelope)
    assert "system.smoke_test" in serialised


# ---------------------------------------------------------------------------
# publish() — mocked NATS connection
# ---------------------------------------------------------------------------


def _make_nats_mocks(
    js_publish_side_effect: BaseException | None = None,
) -> tuple[AsyncMock, AsyncMock]:
    """Build (mock_nc, mock_js) where jetstream() is synchronous (as nats-py requires)."""
    mock_js = AsyncMock()
    if js_publish_side_effect is not None:
        mock_js.publish.side_effect = js_publish_side_effect
    mock_nc = AsyncMock()
    # nc.jetstream() is a sync method in nats-py — use MagicMock so it returns mock_js directly.
    mock_nc.jetstream = MagicMock(return_value=mock_js)
    return mock_nc, mock_js


@pytest.mark.asyncio
async def test_publish_calls_js_publish_with_correct_subject() -> None:
    mock_nc, mock_js = _make_nats_mocks()

    with (
        patch("app.infrastructure.events.publisher.get_settings") as mock_settings,
        patch("app.infrastructure.events.publisher.nats.connect", return_value=mock_nc),
    ):
        mock_settings.return_value = MagicMock(NATS_URL="nats://localhost:4222")
        await publish(
            subject="system.smoke_test",
            event_type="system.smoke_test",
            payload={"ping": True},
            tenant_id="t-1",
            tenant_type="school",
            user_id="u-1",
        )

    mock_js.publish.assert_awaited_once()
    call_args = mock_js.publish.call_args
    assert call_args.args[0] == "system.smoke_test"


@pytest.mark.asyncio
async def test_publish_sends_valid_json_bytes() -> None:
    mock_nc, mock_js = _make_nats_mocks()

    with (
        patch("app.infrastructure.events.publisher.get_settings") as mock_settings,
        patch("app.infrastructure.events.publisher.nats.connect", return_value=mock_nc),
    ):
        mock_settings.return_value = MagicMock(NATS_URL="nats://localhost:4222")
        await publish(
            subject="system.smoke_test",
            event_type="system.smoke_test",
            payload={"hello": "world"},
        )

    raw_bytes: bytes = mock_js.publish.call_args.args[1]
    decoded = json.loads(raw_bytes.decode())
    assert decoded["event_type"] == "system.smoke_test"
    assert decoded["payload"] == {"hello": "world"}


@pytest.mark.asyncio
async def test_publish_closes_nats_connection_on_success() -> None:
    mock_nc, _ = _make_nats_mocks()

    with (
        patch("app.infrastructure.events.publisher.get_settings") as mock_settings,
        patch("app.infrastructure.events.publisher.nats.connect", return_value=mock_nc),
    ):
        mock_settings.return_value = MagicMock(NATS_URL="nats://localhost:4222")
        await publish("system.smoke_test", "system.smoke_test", {})

    mock_nc.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_closes_nats_connection_on_error() -> None:
    """Connection must be closed even when js.publish raises."""
    mock_nc, _ = _make_nats_mocks(js_publish_side_effect=RuntimeError("nats unavailable"))

    with (
        patch("app.infrastructure.events.publisher.get_settings") as mock_settings,
        patch("app.infrastructure.events.publisher.nats.connect", return_value=mock_nc),
    ):
        mock_settings.return_value = MagicMock(NATS_URL="nats://localhost:4222")
        with pytest.raises(RuntimeError, match="nats unavailable"):
            await publish("system.smoke_test", "system.smoke_test", {})

    mock_nc.close.assert_awaited_once()
