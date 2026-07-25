import pytest


@pytest.mark.asyncio
async def test_logout_invalidates_the_session(client, client_with_cookie, seeded_broker):
    register_resp = await client.post(
        "/auth/register",
        json={"email": "ahmad@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    old_token = register_resp.cookies["bursatrack_session"]

    logout_resp = await client.post("/auth/logout")
    assert logout_resp.status_code == 204

    # The client's cookie jar cookie is now cleared by the server's
    # delete_cookie — a fresh authenticated request with no cookie fails...
    no_cookie_resp = await client.post("/auth/logout")
    assert no_cookie_resp.status_code == 401
    assert no_cookie_resp.json()["error"] == "invalid_token"

    # ...and the OLD (pre-logout) token is now rejected as revoked, since
    # token_version no longer matches (proves logout invalidates every
    # outstanding JWT for the user, not just the calling session's cookie).
    async with await client_with_cookie({"bursatrack_session": old_token}) as stale_client:
        stale_resp = await stale_client.post("/auth/refresh")
    assert stale_resp.status_code == 401
    assert stale_resp.json()["error"] == "token_revoked"


@pytest.mark.asyncio
async def test_logout_requires_authentication(client):
    resp = await client.post("/auth/logout")

    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_token"
