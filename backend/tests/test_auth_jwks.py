import base64
from datetime import timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

from app.auth.security import create_access_token


def _b64url_to_int(value: str) -> int:
    padded = value + "=" * (-len(value) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(padded), byteorder="big")


@pytest.mark.asyncio
async def test_jwks_publishes_a_valid_key(client, test_settings):
    resp = await client.get("/auth/jwks.json")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["keys"]) == 1

    key = body["keys"][0]
    assert key["kty"] == "RSA"
    assert key["use"] == "sig"
    assert key["alg"] == "RS256"
    assert key["kid"]


@pytest.mark.asyncio
async def test_jwks_key_actually_verifies_our_tokens(client, test_settings):
    """Stronger than a field-presence check: reconstructs a public key purely
    from the JWKS response's n/e and confirms it can verify a token signed
    with our real private key — proving the published key material is
    actually correct, not just shaped correctly.
    """
    resp = await client.get("/auth/jwks.json")
    key = resp.json()["keys"][0]

    reconstructed_public_key = RSAPublicNumbers(
        e=_b64url_to_int(key["e"]),
        n=_b64url_to_int(key["n"]),
    ).public_key()

    token, _ = create_access_token(
        user_id="3c2b1a0f-1111-4a1a-9999-abcdefabcdef",
        token_version=0,
        private_key=test_settings.jwt_private_key,
        expiry=timedelta(days=1),
    )

    payload = jwt.decode(token, reconstructed_public_key, algorithms=["RS256"])
    assert payload["user_id"] == "3c2b1a0f-1111-4a1a-9999-abcdefabcdef"
