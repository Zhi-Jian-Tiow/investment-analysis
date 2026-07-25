import pytest

import app.auth.router as auth_router


async def _register_and_capture_first_token(client, monkeypatch, seeded_broker) -> str:
    captured: dict[str, str] = {}

    async def fake_send(to_email: str, raw_token: str, settings=None) -> None:
        captured["token"] = raw_token

    monkeypatch.setattr(auth_router, "send_verification_email", fake_send)

    resp = await client.post(
        "/auth/register",
        json={"email": "ahmad@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 201
    return captured["token"]


@pytest.mark.asyncio
async def test_resend_verification_requires_authentication(client):
    resp = await client.post("/auth/resend-verification")

    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_token"


@pytest.mark.asyncio
async def test_resend_verification_issues_a_new_working_token(client, seeded_broker, monkeypatch):
    first_token = await _register_and_capture_first_token(client, monkeypatch, seeded_broker)

    captured = {}

    async def fake_send(to_email: str, raw_token: str, settings=None) -> None:
        captured["token"] = raw_token

    monkeypatch.setattr(auth_router, "send_verification_email", fake_send)

    resp = await client.post("/auth/resend-verification")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Verification email sent. Please check your inbox."

    second_token = captured["token"]
    assert second_token != first_token

    # HIGH-R-011: the first (pre-resend) link is now invalidated...
    stale = await client.get("/auth/verify", params={"token": first_token})
    assert stale.status_code == 400
    assert stale.json()["error"] == "invalid_token"

    # ...only the newly-sent one works.
    fresh = await client.get("/auth/verify", params={"token": second_token})
    assert fresh.status_code == 200
    assert fresh.json()["email_verified"] is True


@pytest.mark.asyncio
async def test_resend_verification_is_a_no_op_once_already_verified(client, seeded_broker, monkeypatch):
    first_token = await _register_and_capture_first_token(client, monkeypatch, seeded_broker)
    verify_resp = await client.get("/auth/verify", params={"token": first_token})
    assert verify_resp.status_code == 200

    send_calls = []

    async def fake_send(to_email: str, raw_token: str, settings=None) -> None:
        send_calls.append(raw_token)

    monkeypatch.setattr(auth_router, "send_verification_email", fake_send)

    resp = await client.post("/auth/resend-verification")

    assert resp.status_code == 200
    assert send_calls == []  # no email queued — nothing to verify anymore
