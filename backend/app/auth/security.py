"""Password hashing and JWT helpers (architecture §14.1).

Kept free of any FastAPI/Settings coupling so it can be unit-tested directly and
so callers (auth.service) stay in control of which settings/expiry to use.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

BCRYPT_COST_FACTOR = 12


def hash_password(password: str) -> str:
    """Synchronous, CPU-bound bcrypt hash. Callers MUST run this in a thread
    pool executor (MED-R-002) to avoid blocking the async event loop.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_COST_FACTOR)).decode("utf-8")


# def verify_password(password: str, password_hash: str) -> bool:
#     return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_raw_token() -> str:
    """Opaque, single-use token for pending_tokens rows. Only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    *, user_id: str, token_version: int, private_key: str, expiry: timedelta
) -> tuple[str, datetime]:
    """Issues an RS256 JWT. Returns (token, expires_at) so the caller can set
    both the cookie and the API response's `expires_at` field from one call.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + expiry
    payload = {"user_id": user_id, "token_version": token_version, "iat": now, "exp": expires_at}
    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token, expires_at
