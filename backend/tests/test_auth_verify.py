from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.auth.models import PendingToken
from app.auth.security import hash_token


async def _register_and_capture_token(client, monkeypatch, email: str, broker_id: str) -> str:
    captured: dict[str, str] = {}

    async def fake_send(to_email: str, raw_token: str, settings=None) -> None:
        captured["token"] = raw_token

    # send_verification_email is imported into app.auth.router and called via
    # BackgroundTasks — patch it where the router looks it up.
    import app.auth.router as auth_router

    monkeypatch.setattr(auth_router, "send_verification_email", fake_send)

    resp = await client.post("/auth/register", json={"email": email, "password": "Invest2026", "broker_id": broker_id})
    assert resp.status_code == 201
    return captured["token"]


@pytest.mark.asyncio
async def test_verify_happy_path(client, seeded_broker, monkeypatch):
    token = await _register_and_capture_token(client, monkeypatch, "ahmad@email.com", str(seeded_broker.id))

    resp = await client.get("/auth/verify", params={"token": token})

    assert resp.status_code == 200
    assert resp.json()["email_verified"] is True


@pytest.mark.asyncio
async def test_verify_invalid_token_rejected(client):
    resp = await client.get("/auth/verify", params={"token": "does-not-exist"})

    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_token"


@pytest.mark.asyncio
async def test_verify_expired_token_rejected(client, seeded_broker, monkeypatch, db_session):
    token = await _register_and_capture_token(client, monkeypatch, "farah@email.com", str(seeded_broker.id))

    await db_session.execute(
        update(PendingToken)
        .where(PendingToken.token_hash == hash_token(token))
        .values(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    )
    await db_session.commit()

    resp = await client.get("/auth/verify", params={"token": token})

    assert resp.status_code == 400
    assert "expired" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_verify_already_used_token_rejected(client, seeded_broker, monkeypatch):
    token = await _register_and_capture_token(client, monkeypatch, "david@email.com", str(seeded_broker.id))

    first = await client.get("/auth/verify", params={"token": token})
    assert first.status_code == 200

    second = await client.get("/auth/verify", params={"token": token})
    assert second.status_code == 400
    assert "already been used" in second.json()["message"].lower()
