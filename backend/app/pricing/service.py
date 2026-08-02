"""Price refresh orchestration (BE-5.1). Implements architecture §13.2's
refresh_prices.py algorithm. scripts/refresh_prices.py is a thin entrypoint;
all the actual logic lives here so it's unit-testable against a fake
PriceProvider instead of the real network.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import get_system_config, release_price_refresh_lock, try_acquire_price_refresh_lock
from app.monitoring import sentry_alert, sentry_checkin
from app.portfolio.models import Lot, Position
from app.pricing.models import PriceSnapshot
from app.pricing.provider import PriceProvider

logger = structlog.get_logger()

MONITOR_SLUG = "price-refresh"
_MAX_CONCURRENT_FETCHES = 10  # HIGH-R-004
_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (5.0, 15.0)  # architecture §13.2 step 6a / §15.1
_DEFAULT_DEVIATION_MAX_PCT = Decimal("75")  # MED-R-006 fallback if system_config is unset/unparseable
_MAJORITY_FAILURE_THRESHOLD = Decimal("0.5")


@dataclass
class RefreshResult:
    skipped_reason: str | None = None
    fetched: list[str] = field(default_factory=list)
    rejected_deviation: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def total_attempted(self) -> int:
        return len(self.fetched) + len(self.rejected_deviation) + len(self.failed)


def is_non_trading_day(today: date, holidays: list[str]) -> bool:
    """Weekend, or a date present in system_config's `bursa_holidays`."""
    if today.weekday() >= 5:
        return True
    return today.isoformat() in holidays


async def _load_holidays(db: AsyncSession) -> list[str]:
    raw = await get_system_config(db, "bursa_holidays")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


async def _load_deviation_max_pct(db: AsyncSession) -> Decimal:
    raw = await get_system_config(db, "price_deviation_max_pct")
    if not raw:
        return _DEFAULT_DEVIATION_MAX_PCT
    try:
        return Decimal(raw)
    except InvalidOperation:
        return _DEFAULT_DEVIATION_MAX_PCT


async def _unique_active_stock_codes(db: AsyncSession) -> list[str]:
    """architecture §13.2 step 4's own pseudocode (`SELECT DISTINCT
    l.stock_code FROM lots l JOIN positions p ...`) references a
    `lots.stock_code` column that doesn't exist in the actual physical
    schema — stock_code lives on Position, not Lot. Corrected to match the
    real schema; the intent (unique stock codes across active lots of
    active positions) is unchanged.
    """
    result = await db.execute(
        select(Position.stock_code)
        .join(Lot, Lot.position_id == Position.id)
        .where(Lot.is_deleted.is_(False), Position.is_deleted.is_(False))
        .distinct()
    )
    return [row[0] for row in result.all()]


async def _fetch_with_retry(
    provider: PriceProvider, stock_code: str, backoff_seconds: tuple[float, ...]
) -> Decimal | None:
    """architecture §15.1: attempt 1 immediate, then one retry per configured
    backoff. Returns None (never raises) once every attempt is exhausted —
    the caller decides what a None means; this function's only job is the
    retry loop itself.
    """
    delays: tuple[float, ...] = (0.0, *backoff_seconds)
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            return await provider.fetch_price(stock_code)
        except Exception as exc:  # noqa: BLE001 - PriceProvider.fetch_price's contract is "raises PriceFetchError", but we must not let a provider bug abort the whole batch either (per-stock isolation, R-001)
            logger.warning("price_fetch_failed", stock_code=stock_code, attempt=attempt, error=str(exc))
    return None


async def _fetch_all(
    provider: PriceProvider, stock_codes: list[str], backoff_seconds: tuple[float, ...], max_concurrent: int
) -> dict[str, Decimal | None]:
    """HIGH-R-004: bounded-concurrency parallel fetch. Network I/O only —
    deliberately does no DB access here, since an AsyncSession isn't safe
    for concurrent use across coroutines. DB reads/writes happen afterward,
    sequentially, in run_price_refresh's own loop.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_one(stock_code: str) -> tuple[str, Decimal | None]:
        async with semaphore:
            price = await _fetch_with_retry(provider, stock_code, backoff_seconds)
        return stock_code, price

    results = await asyncio.gather(*(fetch_one(code) for code in stock_codes))
    return dict(results)


async def _latest_snapshot_price(db: AsyncSession, stock_code: str) -> PriceSnapshot | None:
    result = await db.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.stock_code == stock_code)
        .order_by(PriceSnapshot.trading_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _deviation_pct(new_price: Decimal, previous_price: Decimal) -> Decimal:
    return abs(new_price - previous_price) / previous_price * 100


async def _upsert_snapshot(db: AsyncSession, stock_code: str, trading_date: date, price: Decimal) -> None:
    """UPSERTed via an ORM look-up + insert-or-update rather than a
    dialect-specific `INSERT ... ON CONFLICT` — this runs once per stock in a
    small daily batch (not a bulk-insert hot path), and staying
    dialect-agnostic means the exact same code path runs against both the
    SQLite test harness and real Postgres.
    """
    result = await db.execute(
        select(PriceSnapshot).where(PriceSnapshot.stock_code == stock_code, PriceSnapshot.trading_date == trading_date)
    )
    existing = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.price = price
        existing.source = "automated"
        existing.last_refreshed_at = now
    else:
        db.add(
            PriceSnapshot(stock_code=stock_code, price=price, source="automated", trading_date=trading_date, last_refreshed_at=now)
        )


async def run_price_refresh(
    db: AsyncSession,
    provider: PriceProvider,
    *,
    today: date | None = None,
    backoff_seconds: tuple[float, ...] = _RETRY_BACKOFF_SECONDS,
    max_concurrent: int = _MAX_CONCURRENT_FETCHES,
) -> RefreshResult:
    """architecture §13.2 steps 1-9.

    Deliberately does NOT write a `source='stale'` PriceSnapshot row for a
    stock whose fetch failed or whose price was rejected by the deviation
    guard — see this story's Implementation Record for the reasoning. A
    failed/rejected stock simply leaves its most recent snapshot untouched;
    that row's own `last_refreshed_at` ages naturally, which is exactly what
    the frontend's 28-hour staleness check (architecture §13.2, "Stale
    detection on frontend") already keys off. `source='stale'` remains a
    valid, schema-allowed value for a future story to use (e.g. an explicit
    sweep), but nothing in BE-5.1 needs to write it to satisfy this story's
    own AC.
    """
    today = today or date.today()
    result = RefreshResult()

    holidays = await _load_holidays(db)
    if is_non_trading_day(today, holidays):
        result.skipped_reason = "non_trading_day"
        sentry_checkin(MONITOR_SLUG, "ok", skipped="non_trading_day")
        return result

    # MED-R-004: warn if the calendar looks like nobody's updated it this year.
    if not any(h.startswith(str(today.year)) for h in holidays):
        logger.warning("holiday_calendar_possibly_stale", year=today.year)

    if not await try_acquire_price_refresh_lock(db):
        result.skipped_reason = "lock_held"
        logger.warning("price_refresh_lock_contention")
        sentry_checkin(MONITOR_SLUG, "ok", skipped="lock_held")
        return result

    try:
        deviation_max_pct = await _load_deviation_max_pct(db)
        stock_codes = await _unique_active_stock_codes(db)

        prices = await _fetch_all(provider, stock_codes, backoff_seconds, max_concurrent)

        for stock_code, price in prices.items():
            if price is None:
                result.failed.append(stock_code)
                sentry_alert("warning", "price_fetch_exhausted_retries", stock_code=stock_code)
                continue

            previous = await _latest_snapshot_price(db, stock_code)
            if previous is not None:
                deviation = _deviation_pct(price, previous.price)
                if deviation > deviation_max_pct:
                    logger.warning(
                        "price_deviation_guard",
                        stock_code=stock_code,
                        previous_price=str(previous.price),
                        new_price=str(price),
                        deviation_pct=str(deviation),
                        action="CORPORATE_ACTION_CANDIDATE",
                    )
                    result.rejected_deviation.append(stock_code)
                    continue

            await _upsert_snapshot(db, stock_code, today, price)
            result.fetched.append(stock_code)

        await db.commit()

        failed_count = len(result.failed) + len(result.rejected_deviation)
        if result.total_attempted and Decimal(failed_count) / Decimal(result.total_attempted) > _MAJORITY_FAILURE_THRESHOLD:
            sentry_alert(
                "critical",
                "price_refresh_majority_failed",
                failed=len(result.failed),
                rejected_deviation=len(result.rejected_deviation),
                total=result.total_attempted,
            )

        sentry_checkin(
            MONITOR_SLUG,
            "ok",
            fetched=len(result.fetched),
            rejected_deviation=len(result.rejected_deviation),
            failed=len(result.failed),
        )
    except Exception:
        sentry_checkin(MONITOR_SLUG, "error")
        raise
    finally:
        await release_price_refresh_lock(db)

    return result
