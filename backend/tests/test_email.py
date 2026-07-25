"""Tests for app.email's real Resend-calling logic — as distinct from the
auth flow tests, which monkeypatch these functions away entirely and never
exercise this code. block_real_resend_calls (conftest.py) normally blocks
resend.Emails.send by default; these tests deliberately override it back to
a controlled fake to test OUR wrapper (retry behaviour, never-raises
guarantee, correct params/links) without ever touching the real network.
"""

import pytest

import app.email as email_module
from app.config import Settings

TEST_SETTINGS = Settings(
    resend_api_key="test-key",
    email_from_address="BursaTrack <onboarding@resend.dev>",
    frontend_base_url="https://app.bursatrack.test",
)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    # The retry path sleeps 1s between attempts; skip that in tests.
    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr(email_module.asyncio, "sleep", _instant_sleep)


@pytest.mark.asyncio
async def test_send_verification_email_success_on_first_attempt(monkeypatch):
    calls = []

    def fake_send(params):
        calls.append(params)
        return {"id": "email_123"}

    monkeypatch.setattr(email_module.resend.Emails, "send", fake_send)

    await email_module.send_verification_email("ahmad@email.com", "raw-token-abc", TEST_SETTINGS)

    assert len(calls) == 1
    sent = calls[0]
    assert sent["to"] == ["ahmad@email.com"]
    assert sent["from"] == "BursaTrack <onboarding@resend.dev>"
    assert "https://app.bursatrack.test/verify?token=raw-token-abc" in sent["html"]


@pytest.mark.asyncio
async def test_send_password_reset_email_builds_the_correct_link(monkeypatch):
    calls = []
    monkeypatch.setattr(email_module.resend.Emails, "send", lambda params: calls.append(params))

    await email_module.send_password_reset_email("ahmad@email.com", "raw-token-xyz", TEST_SETTINGS)

    assert len(calls) == 1
    assert "https://app.bursatrack.test/reset-password?token=raw-token-xyz" in calls[0]["html"]
    assert calls[0]["subject"] == "Reset your BursaTrack password"


@pytest.mark.asyncio
async def test_send_retries_once_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    def flaky_send(params):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("simulated transient network error")
        return {"id": "email_456"}

    monkeypatch.setattr(email_module.resend.Emails, "send", flaky_send)

    await email_module.send_verification_email("ahmad@email.com", "raw-token-abc", TEST_SETTINGS)

    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_send_never_raises_even_after_exhausting_retries(monkeypatch):
    attempts = {"count": 0}

    def always_fails(params):
        attempts["count"] += 1
        raise RuntimeError("simulated permanent failure")

    monkeypatch.setattr(email_module.resend.Emails, "send", always_fails)

    # Must not raise — BAS EX-007/EX-011: email failure must never block or
    # fail the calling flow.
    await email_module.send_verification_email("ahmad@email.com", "raw-token-abc", TEST_SETTINGS)

    assert attempts["count"] == 2  # initial attempt + exactly 1 retry, no more
