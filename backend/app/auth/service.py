"""BE-1.1: User Registration & Email Verification (FR-001).

Login/logout/refresh (BE-1.2) and password reset (BE-1.3) are separate stories
and are not implemented here yet.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import record_audit_event
from app.config import Settings
from app.errors import invalid_token, validation_error
from app.portfolio.service import create_portfolio, get_broker

from app.auth.security import (
    hash_password,
    hash_token,
    generate_raw_token,
    create_access_token,
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

    access_token, expires_at = create_access_token(
        user_id=str(user.id),
        token_version=user.token_version,
        private_key=settings.jwt_private_key,
        expiry=timedelta(days=settings.jwt_access_token_expiry_days),
    )

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
