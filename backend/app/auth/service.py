"""BE-1.1: User Registration & Email Verification (FR-001).
BE-1.2: Login, Logout, Session Refresh & Rate Limiting (FR-002).

Password reset (BE-1.3) is a separate story and is not implemented here yet.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import record_audit_event
from app.config import Settings
from app.errors import invalid_credentials, invalid_token, validation_error
from app.portfolio.service import create_portfolio, get_broker

from app.auth.security import (
    hash_password,
    hash_token,
    generate_raw_token,
    create_access_token,
    verify_password,
)
from app.auth.models import PendingToken, User

EMAIL_VERIFICATION_TYPE = "email_verification"


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    # VR-001 / DI-011: uniqueness is case-insensitive; email is stored lowercased
    # at registration, so a lowercased lookup is sufficient here.
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def _hash_password_async(password: str) -> str:
    # MED-R-002: bcrypt is CPU-bound; run off the event loop.
    return await asyncio.get_event_loop().run_in_executor(None, hash_password, password)


async def _verify_password_async(password: str, password_hash: str) -> bool:
    # MED-R-002: bcrypt is CPU-bound; run off the event loop.
    return await asyncio.get_event_loop().run_in_executor(None, verify_password, password, password_hash)


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    # Computed once, lazily, the first time a login is attempted for an email
    # that doesn't exist. Verifying against this instead of short-circuiting
    # keeps the unknown-email and wrong-password paths the same shape of work
    # (a bcrypt check), which is cheap insurance against timing-based account
    # enumeration on top of the identical error message BAS US-002 already
    # requires. Not explicitly required by BE-1.2's AC — added because the
    # cost is negligible and the AC's own goal is "no account enumeration".
    return hash_password("no-such-account-dummy-password")


def issue_access_token(user: User, settings: Settings) -> tuple[str, datetime]:
    return create_access_token(
        user_id=str(user.id),
        token_version=user.token_version,
        private_key=settings.jwt_private_key,
        expiry=timedelta(days=settings.jwt_access_token_expiry_days),
    )


async def register_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    broker_id,
    settings: Settings,
) -> tuple[User, str, str, datetime]:
    """Returns (user, raw_verification_token, access_token, access_token_expires_at).

    The raw verification token is returned so the caller (router) can hand it to
    the BackgroundTask email sender — it is never persisted or returned to the
    client in plaintext anywhere else.
    """
    normalized_email = email.lower()

    if await get_user_by_email(db, normalized_email) is not None:
        raise validation_error(
            "One or more fields failed validation.",
            [
                {
                    "field": "email",
                    "constraint": "already registered",
                    "received": normalized_email,
                }
            ],
        )

    broker = await get_broker(db, broker_id)
    if broker is None:
        raise validation_error(
            "One or more fields failed validation.",
            [
                {
                    "field": "broker_id",
                    "constraint": "must reference an existing broker",
                    "received": str(broker_id),
                }
            ],
        )

    password_hash = await _hash_password_async(password)

    today = date.today()
    user = User(
        email=normalized_email,
        password_hash=password_hash,
        email_verified=False,
        account_status="trial",
        token_version=0,
        default_broker_config_id=broker.id,
        trial_start_date=today,
        trial_expiry_date=today + timedelta(days=settings.trial_period_days),
    )
    db.add(user)
    await db.flush()  # populate user.id for the FK rows below

    await create_portfolio(db, user.id)

    raw_token = generate_raw_token()
    db.add(
        PendingToken(
            user_id=user.id,
            type=EMAIL_VERIFICATION_TYPE,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.email_verification_token_expiry_hours),
        )
    )

    await record_audit_event(
        db,
        user_id=user.id,
        action="USER_REGISTERED",
        entity_type="User",
        entity_id=user.id,
    )

    await db.commit()
    await db.refresh(user)

    access_token, expires_at = issue_access_token(user, settings)

    return user, raw_token, access_token, expires_at


async def verify_email(db: AsyncSession, raw_token: str) -> User:
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(PendingToken).where(
            PendingToken.token_hash == token_hash,
            PendingToken.type == EMAIL_VERIFICATION_TYPE,
        )
    )
    token_row = result.scalar_one_or_none()

    if token_row is None:
        raise invalid_token("This verification link is invalid.")
    if token_row.used_at is not None:
        raise invalid_token("This verification link has already been used.")
    expires_at = token_row.expires_at
    if expires_at.tzinfo is None:
        # SQLite (used in tests) round-trips DateTime(timezone=True) as naive;
        # Postgres (production) preserves tzinfo. Normalize so this comparison
        # is correct on both backends.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise invalid_token("This verification link has expired. Request a new one?")

    token_row.used_at = datetime.now(timezone.utc)

    user_result = await db.execute(select(User).where(User.id == token_row.user_id))
    user = user_result.scalar_one()
    user.email_verified = True

    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, *, email: str, password: str, settings: Settings
) -> tuple[User, str, datetime]:
    """FR-002 / BAS US-002. Failed-attempt lockout tracking (BR-016/EX-009) is
    the caller's responsibility (app.auth.lockout, checked in the router
    before this is called) — this function only verifies credentials.
    """
    user = await get_user_by_email(db, email)

    # Always run a bcrypt check, even for an unknown email, so the unknown-
    # email and wrong-password paths take a comparable amount of time.
    password_hash = user.password_hash if user is not None else _dummy_password_hash()
    is_valid = await _verify_password_async(password, password_hash)

    if user is None or not is_valid:
        raise invalid_credentials()

    await record_audit_event(db, user_id=user.id, action="USER_LOGIN", entity_type="User", entity_id=user.id)
    await db.commit()
    await db.refresh(user)

    access_token, expires_at = issue_access_token(user, settings)
    return user, access_token, expires_at


async def logout_user(db: AsyncSession, user: User) -> None:
    """FR-002: incrementing token_version invalidates every outstanding JWT
    for this user (not just the calling session's cookie), since the JWT
    payload's token_version will no longer match on the next request
    (app.auth.dependencies.get_current_user).
    """
    user.token_version += 1
    await db.commit()
