"""Admin-domain service functions. Other modules call record_audit_event rather
than instantiating AuditLog directly (architecture P-008 — service-layer access
across module boundaries, no direct cross-module table writes).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AuditLog, SystemConfig


async def record_audit_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=metadata,
        )
    )
    await db.flush()


async def get_system_config(db: AsyncSession, key: str) -> str | None:
    """Plain, uncached read. BE-8.3's own TTLCache is a request-path
    optimization for the (not yet built) fee-calculation hot path — the
    price refresh cron reads each key at most a few times per run, so
    there's no case for caching here.
    """
    result = await db.execute(select(SystemConfig.value).where(SystemConfig.key == key))
    return result.scalar_one_or_none()


async def set_system_config(db: AsyncSession, key: str, value: str | None) -> None:
    await db.execute(update(SystemConfig).where(SystemConfig.key == key).values(value=value))
    await db.commit()


_PRICE_REFRESH_LOCK_KEY = "price_refresh_lock"
_PRICE_REFRESH_LOCK_TTL = timedelta(hours=2)  # HIGH-R-004


async def try_acquire_price_refresh_lock(db: AsyncSession) -> bool:
    """HIGH-R-004: a run already in progress within the last 2 hours blocks a
    duplicate run. Single atomic UPDATE (not a separate SELECT-then-UPDATE)
    so two processes racing to acquire the lock can't both succeed — the
    WHERE clause only matches a row that is actually free, and only one
    concurrent UPDATE can win it.

    Timestamps are stored as `datetime.isoformat()` (always UTC, always the
    same format) specifically so this WHERE clause can compare them as plain
    TEXT and still get correct chronological ordering.
    """
    now = datetime.now(timezone.utc)
    stale_before = (now - _PRICE_REFRESH_LOCK_TTL).isoformat()
    result = await db.execute(
        update(SystemConfig)
        .where(
            SystemConfig.key == _PRICE_REFRESH_LOCK_KEY,
            or_(SystemConfig.value.is_(None), SystemConfig.value < stale_before),
        )
        .values(value=now.isoformat())
    )
    if result.rowcount > 0:
        await db.commit()
        return True

    # No row matched the UPDATE — either a fresh lock is genuinely held, or
    # the `price_refresh_lock` row doesn't exist at all yet (production:
    # migration 0012's seed row was somehow lost; tests: the SQLite harness
    # never runs migrations, only Base.metadata.create_all). A value=NULL
    # row would already have matched the UPDATE above, so reaching here with
    # no existing row is the only way get_system_config can still read None.
    if await get_system_config(db, _PRICE_REFRESH_LOCK_KEY) is None:
        try:
            db.add(SystemConfig(key=_PRICE_REFRESH_LOCK_KEY, value=now.isoformat()))
            await db.commit()
            return True
        except IntegrityError:
            # Lost a race with another process inserting the same row first.
            await db.rollback()
            return False

    await db.rollback()
    return False


async def release_price_refresh_lock(db: AsyncSession) -> None:
    """Cleared on both normal exit and exception (architecture §13.2 step 1)
    — a job that crashes must not leave the lock held for the full 2-hour
    TTL, or every run in between gets skipped for no reason.
    """
    await set_system_config(db, _PRICE_REFRESH_LOCK_KEY, None)
