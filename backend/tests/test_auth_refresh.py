from datetime import timedelta

import pytest

from app.auth.security import create_access_token


@pytest.mark.asyncio
async def test_refresh_issues_a_new_cookie(client, seeded_broker):
    register_resp = await client.post(
        "/auth/register",
        json={"email": "ahmad@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    original_expires_at = register_resp.json()["expires_at"]

    resp = await client.post("/auth/refresh")

    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "ahmad@email.com"
    assert "bursatrack_session" in resp.cookies
    # A freshly-issued 7-day expiry should not be earlier than the one minted
    # at registration moments earlier.
    assert body["expires_at"] >= original_expires_at


@pytest.mark.asyncio
async def test_refresh_requires_a_session_cookie(client):
    resp = await client.post("/auth/refresh")

    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_token"


@pytest.mark.asyncio
async def test_refresh_rejects_a_malformed_cookie(client_with_cookie):
    async with await client_with_cookie({"bursatrack_session": "not-a-jwt"}) as c:
        resp = await c.post("/auth/refresh")

    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_token"


@pytest.mark.asyncio
async def test_refresh_rejects_an_expired_token(client, client_with_cookie, seeded_broker, test_settings):
    register_resp = await client.post(
        "/auth/register",
        json={"email": "ahmad@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    user_id = register_resp.json()["user"]["id"]

    expired_token, _ = create_access_token(
        user_id=user_id,
        token_version=0,
        private_key=test_settings.jwt_private_key,
        expiry=timedelta(days=-1),
    )

    async with await client_with_cookie({"bursatrack_session": expired_token}) as c:
        resp = await c.post("/auth/refresh")

    assert resp.status_code == 401
    assert resp.json()["error"] == "token_expired"
