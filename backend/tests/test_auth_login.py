import pytest

from app.rate_limit import limiter


async def _register(client, seeded_broker, email="ahmad@email.com", password="Invest2026"):
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 201
    return resp


@pytest.mark.asyncio
async def test_login_happy_path(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "Invest2026"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "ahmad@email.com"
    assert "expires_at" in body
    assert "bursatrack_session" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_generic_error(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "WrongPass1"})

    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] == "invalid_credentials"
    assert body["message"] == "Email or password is incorrect."


@pytest.mark.asyncio
async def test_login_unknown_email_identical_error(client):
    resp = await client.post("/auth/login", json={"email": "nobody@email.com", "password": "WrongPass1"})

    assert resp.status_code == 401
    body = resp.json()
    # Same code and message as a wrong password for a real account — no
    # account enumeration (BAS US-002).
    assert body["error"] == "invalid_credentials"
    assert body["message"] == "Email or password is incorrect."


@pytest.mark.asyncio
async def test_login_locks_after_five_failures_from_same_ip(client, seeded_broker):
    await _register(client, seeded_broker)

    for _ in range(4):
        resp = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "WrongPass1"})
        assert resp.status_code == 401

    # The 5/minute SlowAPI rate limit on /auth/login shares the same threshold
    # number as BR-016's lockout (5 failures/10min) but is a separate,
    # independent mechanism. Reset it here so this test isolates lockout
    # behaviour specifically, rather than incidentally tripping the generic
    # rate limiter first.
    limiter.reset()

    fifth = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "WrongPass1"})
    assert fifth.status_code == 401

    limiter.reset()

    # 6th attempt — even with the CORRECT password — is locked out.
    sixth = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "Invest2026"})
    assert sixth.status_code == 429
    body = sixth.json()
    assert body["error"] == "account_locked"
    assert body["message"] == "Too many failed attempts. Please wait 10 minutes before trying again."
    assert "Retry-After" in sixth.headers


@pytest.mark.asyncio
async def test_login_lockout_resets_on_success(client, seeded_broker):
    await _register(client, seeded_broker)

    for _ in range(4):
        resp = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "WrongPass1"})
        assert resp.status_code == 401
    limiter.reset()

    success = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "Invest2026"})
    assert success.status_code == 200
    limiter.reset()

    # Counter reset by the successful login (BR-016) — 4 more failures should
    # not lock the account.
    for _ in range(4):
        resp = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "WrongPass1"})
        assert resp.status_code == 401
    limiter.reset()

    still_open = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "Invest2026"})
    assert still_open.status_code == 200


@pytest.mark.asyncio
async def test_login_rate_limited_after_five_per_minute(client, seeded_broker):
    await _register(client, seeded_broker)

    for _ in range(5):
        resp = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "Invest2026"})
        assert resp.status_code == 200

    sixth = await client.post("/auth/login", json={"email": "ahmad@email.com", "password": "Invest2026"})
    assert sixth.status_code == 429
    assert sixth.json()["error"] == "rate_limit_exceeded"
