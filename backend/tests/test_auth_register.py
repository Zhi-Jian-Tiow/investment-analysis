from datetime import date, timedelta

import pytest


@pytest.mark.asyncio
async def test_register_happy_path(client, seeded_broker):
    resp = await client.post(
        "/auth/register",
        json={"email": "ahmad@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == "ahmad@email.com"
    assert body["user"]["account_status"] == "trial"
    assert body["user"]["email_verified"] is False
    assert body["user"]["trial_expiry_date"] == (date.today() + timedelta(days=14)).isoformat()
    assert "expires_at" in body
    assert "bursatrack_session" in resp.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client, seeded_broker):
    payload = {"email": "ahmad@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)}

    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 422
    body = second.json()
    assert body["error"] == "validation_failed"
    assert any(f["field"] == "email" for f in body["fields"])


@pytest.mark.asyncio
async def test_register_password_without_uppercase_rejected(client, seeded_broker):
    resp = await client.post(
        "/auth/register",
        json={"email": "farah@email.com", "password": "invest2026", "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_failed"


@pytest.mark.asyncio
async def test_register_password_without_digit_rejected(client, seeded_broker):
    resp = await client.post(
        "/auth/register",
        json={"email": "farah@email.com", "password": "Investment", "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_failed"


@pytest.mark.asyncio
async def test_register_password_too_short_rejected(client, seeded_broker):
    resp = await client.post(
        "/auth/register",
        json={"email": "farah@email.com", "password": "Inv2026", "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email_format_rejected(client, seeded_broker):
    resp = await client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_unknown_broker_rejected(client):
    resp = await client.post(
        "/auth/register",
        json={
            "email": "david@email.com",
            "password": "Invest2026",
            "broker_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert any(f["field"] == "broker_id" for f in body["fields"])


@pytest.mark.asyncio
async def test_register_rate_limited_after_three_per_minute(client, seeded_broker):
    for i in range(3):
        resp = await client.post(
            "/auth/register",
            json={"email": f"user{i}@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
        )
        assert resp.status_code == 201

    fourth = await client.post(
        "/auth/register",
        json={"email": "user4@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    assert fourth.status_code == 429
    assert fourth.json()["error"] == "rate_limit_exceeded"
