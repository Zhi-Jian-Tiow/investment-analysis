from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import select, update

import app.auth.router as auth_router
from app.auth.models import PendingToken, User
from app.auth.security import hash_token

GENERIC_MESSAGE = "If an account with that email exists, a reset link has been sent."


async def _register(client, seeded_broker, email="ahmad@email.com", password="Invest2026"):
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 201
    return resp


async def _request_reset_and_capture_token(client, monkeypatch, email: str) -> str:
    captured: dict[str, str] = {}

    async def fake_send(to_email: str, raw_token: str, settings=None) -> None:
        captured["token"] = raw_token

    monkeypatch.setattr(auth_router, "send_password_reset_email", fake_send)

    resp = await client.post("/auth/password-reset-request", json={"email": email})
    assert resp.status_code == 200
    assert resp.json()["message"] == GENERIC_MESSAGE
    return captured["token"]


@pytest.mark.asyncio
async def test_reset_request_for_existing_email_returns_generic_message(client, seeded_broker, monkeypatch):
    await _register(client, seeded_broker)
    token = await _request_reset_and_capture_token(client, monkeypatch, "ahmad@email.com")
    assert token  # an email really was queued with a real token


@pytest.mark.asyncio
async def test_reset_request_for_unknown_email_returns_identical_message_and_sends_nothing(client, monkeypatch):
    send_calls = []

    async def fake_send(to_email: str, raw_token: str, settings=None) -> None:
        send_calls.append((to_email, raw_token))

    monkeypatch.setattr(auth_router, "send_password_reset_email", fake_send)

    resp = await client.post("/auth/password-reset-request", json={"email": "nobody@email.com"})

    assert resp.status_code == 200
    assert resp.json()["message"] == GENERIC_MESSAGE
    assert send_calls == []


@pytest.mark.asyncio
async def test_reset_completes_changes_password_and_invalidates_old_session(client, seeded_broker, monkeypatch):
    await _register(client, seeded_broker)

    reset_token = await _request_reset_and_capture_token(client, monkeypatch, "ahmad@email.com")

    complete_resp = await client.post(
        "/auth/password-reset", json={"token": reset_token, "new_password": "NewPass2026"}
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["message"] == "Password updated successfully. Please log in."

    # Old password no longer works.
    old_login = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "Invest2026"})
    assert old_login.status_code == 401

    # New password works.
    new_login = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "NewPass2026"})
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_reset_invalidates_sessions_that_predate_it(client, client_with_cookie, seeded_broker, monkeypatch):
    register_resp = await _register(client, seeded_broker)
    old_token = register_resp.cookies["bursatrack_session"]

    reset_token = await _request_reset_and_capture_token(client, monkeypatch, "ahmad@email.com")
    await client.post("/auth/password-reset", json={"token": reset_token, "new_password": "NewPass2026"})

    # BR-019/EX-011: the session cookie issued at registration, before the
    # reset, must be rejected as revoked (token_version no longer matches).
    async with await client_with_cookie({"bursatrack_session": old_token}) as stale_client:
        resp = await stale_client.post("/auth/refresh")
    assert resp.status_code == 401
    assert resp.json()["error"] == "token_revoked"


@pytest.mark.asyncio
async def test_reset_marks_a_never_verified_email_as_verified(client, seeded_broker, monkeypatch, db_session):
    register_resp = await _register(client, seeded_broker)
    user_id = register_resp.json()["user"]["id"]
    assert register_resp.json()["user"]["email_verified"] is False

    reset_token = await _request_reset_and_capture_token(client, monkeypatch, "ahmad@email.com")
    await client.post("/auth/password-reset", json={"token": reset_token, "new_password": "NewPass2026"})

    result = await db_session.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one()
    assert user.email_verified is True


@pytest.mark.asyncio
async def test_reset_rejects_an_invalid_token(client):
    resp = await client.post("/auth/password-reset", json={"token": "does-not-exist", "new_password": "NewPass2026"})

    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_token"
    assert resp.json()["message"] == "This reset link is invalid."


@pytest.mark.asyncio
async def test_reset_rejects_an_expired_token(client, seeded_broker, monkeypatch, db_session):
    await _register(client, seeded_broker)
    reset_token = await _request_reset_and_capture_token(client, monkeypatch, "ahmad@email.com")

    await db_session.execute(
        update(PendingToken)
        .where(PendingToken.token_hash == hash_token(reset_token))
        .values(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    )
    await db_session.commit()

    resp = await client.post("/auth/password-reset", json={"token": reset_token, "new_password": "NewPass2026"})

    assert resp.status_code == 400
    assert "expired" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_reset_rejects_an_already_used_token(client, seeded_broker, monkeypatch):
    await _register(client, seeded_broker)
    reset_token = await _request_reset_and_capture_token(client, monkeypatch, "ahmad@email.com")

    first = await client.post("/auth/password-reset", json={"token": reset_token, "new_password": "NewPass2026"})
    assert first.status_code == 200

    second = await client.post("/auth/password-reset", json={"token": reset_token, "new_password": "AnotherPass1"})
    assert second.status_code == 400
    assert "already been used" in second.json()["message"].lower()


@pytest.mark.asyncio
async def test_second_reset_request_invalidates_the_first_link(client, seeded_broker, monkeypatch):
    """HIGH-R-011: requesting a new reset token deletes the previous one —
    only the most recently emailed link should ever work."""
    await _register(client, seeded_broker)

    first_token = await _request_reset_and_capture_token(client, monkeypatch, "ahmad@email.com")
    second_token = await _request_reset_and_capture_token(client, monkeypatch, "ahmad@email.com")
    assert first_token != second_token

    stale_attempt = await client.post(
        "/auth/password-reset", json={"token": first_token, "new_password": "NewPass2026"}
    )
    assert stale_attempt.status_code == 400
    assert stale_attempt.json()["error"] == "invalid_token"

    fresh_attempt = await client.post(
        "/auth/password-reset", json={"token": second_token, "new_password": "NewPass2026"}
    )
    assert fresh_attempt.status_code == 200


@pytest.mark.asyncio
async def test_reset_new_password_must_meet_complexity_rules(client, seeded_broker, monkeypatch):
    await _register(client, seeded_broker)
    reset_token = await _request_reset_and_capture_token(client, monkeypatch, "ahmad@email.com")

    resp = await client.post("/auth/password-reset", json={"token": reset_token, "new_password": "nouppercase1"})

    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_failed"


@pytest.mark.asyncio
async def test_reset_request_rate_limited_after_three_per_minute(client):
    for i in range(3):
        resp = await client.post("/auth/password-reset-request", json={"email": f"user{i}@email.com"})
        assert resp.status_code == 200

    fourth = await client.post("/auth/password-reset-request", json={"email": "user4@email.com"})
    assert fourth.status_code == 429
    assert fourth.json()["error"] == "rate_limit_exceeded"
