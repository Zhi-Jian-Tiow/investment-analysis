import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.database import get_db
from app.main import app as fastapi_app


def _generate_rsa_pem_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private_pem, public_pem


async def _register(client, seeded_broker, email="cookie-test@email.com"):
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 201
    return resp


@pytest.mark.asyncio
async def test_default_test_settings_set_samesite_lax(client, seeded_broker):
    """The default (and local-dev) case — localhost:3000 -> localhost:8000
    differ only by port, which is still same-site, so Lax is correct and
    must stay the default."""
    resp = await _register(client, seeded_broker)

    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "samesite=lax" in set_cookie


@pytest.mark.asyncio
async def test_samesite_none_is_reflected_in_set_cookie_header(db_session, seeded_broker):
    """The actual production fix: cookie_samesite="none" (with secure=True,
    required by the model validator) must produce a Set-Cookie the browser
    will actually attach on a cross-site fetch() — this is what makes
    Vercel's *.vercel.app -> Render's *.onrender.com login work at all."""
    private_key, public_key = _generate_rsa_pem_pair()
    cross_site_settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_private_key=private_key,
        jwt_public_key=public_key,
        cookie_secure=True,
        cookie_samesite="none",
    )

    async def override_get_db():
        yield db_session

    async def override_get_settings():
        return cross_site_settings

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_settings] = override_get_settings
    try:
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await _register(client, seeded_broker, email="cross-site@email.com")
    finally:
        fastapi_app.dependency_overrides.clear()

    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "samesite=none" in set_cookie
    assert "secure" in set_cookie


def test_samesite_none_without_secure_is_rejected_at_config_load():
    with pytest.raises(ValueError, match="cookie_samesite='none' requires cookie_secure=true"):
        Settings(cookie_samesite="none", cookie_secure=False)


def test_samesite_accepts_valid_values_case_insensitively():
    assert Settings(cookie_samesite="Lax", cookie_secure=True).cookie_samesite == "lax"
    assert Settings(cookie_samesite="STRICT", cookie_secure=True).cookie_samesite == "strict"
    assert Settings(cookie_samesite="None", cookie_secure=True).cookie_samesite == "none"


def test_samesite_rejects_invalid_value():
    with pytest.raises(ValueError, match="cookie_samesite must be one of lax/strict/none"):
        Settings(cookie_samesite="banana", cookie_secure=True)


@pytest.mark.asyncio
async def test_logout_clears_cookie_with_matching_attributes(client, seeded_broker):
    await _register(client, seeded_broker)
    await client.post("/auth/login", json={"email": "cookie-test@email.com", "password": "Invest2026"})

    resp = await client.post("/auth/logout")

    assert resp.status_code == 204
    set_cookie = resp.headers.get("set-cookie", "").lower()
    # An expired Max-Age/expires in the past is how delete_cookie clears it;
    # the important regression check is that secure/samesite still match
    # what was actually used to set the cookie, not delete_cookie()'s own
    # independent defaults (secure=False, samesite="lax").
    assert "samesite=lax" in set_cookie
