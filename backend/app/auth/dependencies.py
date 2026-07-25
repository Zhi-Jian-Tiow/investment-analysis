"""FastAPI-specific auth dependency. Kept separate from security.py, which is
deliberately framework-free so its crypto helpers stay directly unit-testable.
"""

import uuid

import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.errors import unauthorized

from .models import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Validates the session cookie's JWT and its token_version against the DB
    (architecture §14.1 — token_version is how logout/password-change/deletion
    revoke every outstanding session for a user, since the JWT itself is
    stateless and can't otherwise be invalidated before it expires).
    """
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise unauthorized("invalid_token", "Authentication required.")

    try:
        payload = jwt.decode(token, settings.jwt_public_key, algorithms=["RS256"])
    except jwt.ExpiredSignatureError:
        raise unauthorized("token_expired", "Your session has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise unauthorized("invalid_token", "Invalid authentication token.")

    try:
        user_id = uuid.UUID(payload.get("user_id", ""))
    except (ValueError, AttributeError, TypeError):
        raise unauthorized("invalid_token", "Invalid authentication token.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise unauthorized("invalid_token", "Invalid authentication token.")
    if user.token_version != payload.get("token_version"):
        raise unauthorized("token_revoked", "This session has been revoked. Please log in again.")

    return user
