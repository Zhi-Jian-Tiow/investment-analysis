import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.admin.models import SystemConfig
from app.admin.service import get_system_config
from app.pricing.models import PriceSnapshot
from app.pricing.provider import PriceFetchError
from app.pricing.service import is_non_trading_day, run_price_refresh

_A_MONDAY = date(2026, 8, 3)
_A_SUNDAY = date(2026, 8, 2)
_FAST_BACKOFF = (0.0, 0.0)  # tests never wait on the real 5s/15s backoff


class FakePriceProvider:
    """responses: stock_code -> Decimal (success) | Exception instance (failure)."""

    def __init__(self, responses: dict[str, object]):
        self.responses = responses
        self.calls: list[str] = []

    async def fetch_price(self, stock_code: str) -> Decimal:
        self.calls.append(stock_code)
        value = self.responses.get(stock_code)
        if isinstance(value, BaseException):
            raise value
        if value is None:
            raise PriceFetchError(f"no fixture configured for {stock_code}")
        return value


async def _register(client, seeded_broker):
    resp = await client.post(
        "/auth/register",
        json={"email": "ahmad@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 201


async def _create_position(client, broker, stock_code, shares=1000):
    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": stock_code,
            "stock_name": f"Stock {stock_code}",
            "shares": shares,
            "purchase_price": "1.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2020-01-15",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_is_non_trading_day_weekend():
    assert is_non_trading_day(_A_SUNDAY, []) is True
    assert is_non_trading_day(_A_MONDAY, []) is False


def test_is_non_trading_day_holiday():
    assert is_non_trading_day(_A_MONDAY, ["2026-08-03"]) is True
    assert is_non_trading_day(_A_MONDAY, ["2026-08-04"]) is False


@pytest.mark.asyncio
async def test_full_success_writes_automated_snapshots(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")
    await _create_position(client, seeded_broker, "1155")

    provider = FakePriceProvider({"1023": Decimal("8.4200"), "1155": Decimal("9.2000")})
    result = await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert result.skipped_reason is None
    assert sorted(result.fetched) == ["1023", "1155"]
    assert result.failed == []
    assert result.rejected_deviation == []

    rows = (await db_session.execute(select(PriceSnapshot))).scalars().all()
    by_code = {r.stock_code: r for r in rows}
    assert by_code["1023"].price == Decimal("8.4200")
    assert by_code["1023"].source == "automated"
    assert by_code["1023"].trading_date == _A_MONDAY
    assert by_code["1155"].price == Decimal("9.2000")


@pytest.mark.asyncio
async def test_partial_failure_isolates_per_stock(client, seeded_broker, db_session):
    """R-001: one stock's failure never aborts another's fetch or write."""
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")
    await _create_position(client, seeded_broker, "1155")

    provider = FakePriceProvider({"1023": Decimal("8.4200"), "1155": PriceFetchError("timeout")})
    result = await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert result.fetched == ["1023"]
    assert result.failed == ["1155"]

    rows = (await db_session.execute(select(PriceSnapshot))).scalars().all()
    assert [r.stock_code for r in rows] == ["1023"]  # no row written at all for the failed stock


@pytest.mark.asyncio
async def test_all_retries_exhausted_before_giving_up(client, seeded_broker, db_session):
    """architecture §15.1: attempt 1 + 2 retries = 3 total attempts."""
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")

    provider = FakePriceProvider({"1023": PriceFetchError("down")})
    await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert provider.calls == ["1023", "1023", "1023"]


@pytest.mark.asyncio
async def test_complete_outage_fires_critical_alert(client, seeded_broker, db_session, monkeypatch):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")
    await _create_position(client, seeded_broker, "1155")

    alerts: list[tuple] = []
    monkeypatch.setattr("app.pricing.service.sentry_alert", lambda level, message, **kw: alerts.append((level, message, kw)))

    provider = FakePriceProvider({"1023": PriceFetchError("down"), "1155": PriceFetchError("down")})
    await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    critical = [a for a in alerts if a[0] == "critical"]
    assert len(critical) == 1
    assert critical[0][1] == "price_refresh_majority_failed"


@pytest.mark.asyncio
async def test_minority_failure_does_not_fire_critical_alert(client, seeded_broker, db_session, monkeypatch):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")
    await _create_position(client, seeded_broker, "1155")
    await _create_position(client, seeded_broker, "1295")

    alerts: list[tuple] = []
    monkeypatch.setattr("app.pricing.service.sentry_alert", lambda level, message, **kw: alerts.append((level, message, kw)))

    provider = FakePriceProvider(
        {"1023": Decimal("8.42"), "1155": Decimal("9.20"), "1295": PriceFetchError("down")}
    )
    await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert [a for a in alerts if a[0] == "critical"] == []


@pytest.mark.asyncio
async def test_deviation_guard_rejects_and_does_not_overwrite(client, seeded_broker, db_session):
    """MED-R-006: >75% move from the previous snapshot is rejected, logged
    as CORPORATE_ACTION_CANDIDATE, and does not overwrite the existing row."""
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")

    db_session.add(
        PriceSnapshot(
            stock_code="1023",
            price=Decimal("8.0000"),
            source="automated",
            trading_date=_A_MONDAY - timedelta(days=1),
            last_refreshed_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    await db_session.commit()

    # 8.00 -> 20.00 is a 150% move, well past the 75% default threshold.
    provider = FakePriceProvider({"1023": Decimal("20.0000")})
    result = await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert result.rejected_deviation == ["1023"]
    assert result.fetched == []

    rows = (await db_session.execute(select(PriceSnapshot).where(PriceSnapshot.stock_code == "1023"))).scalars().all()
    assert len(rows) == 1  # no new row for today; yesterday's untouched
    assert rows[0].price == Decimal("8.0000")


@pytest.mark.asyncio
async def test_first_ever_fetch_skips_deviation_guard(client, seeded_broker, db_session):
    """No previous snapshot means nothing to compare against — any positive
    price is accepted regardless of magnitude."""
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")

    provider = FakePriceProvider({"1023": Decimal("999.0000")})
    result = await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert result.fetched == ["1023"]
    assert result.rejected_deviation == []


@pytest.mark.asyncio
async def test_configurable_deviation_threshold(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")
    db_session.add(SystemConfig(key="price_deviation_max_pct", value="10"))
    db_session.add(
        PriceSnapshot(
            stock_code="1023", price=Decimal("8.0000"), source="automated", trading_date=_A_MONDAY - timedelta(days=1)
        )
    )
    await db_session.commit()

    # 8.00 -> 9.00 is a 12.5% move: fine under the default 75% threshold,
    # rejected once system_config tightens it to 10%.
    provider = FakePriceProvider({"1023": Decimal("9.0000")})  # 12.5% move
    result = await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert result.rejected_deviation == ["1023"]


@pytest.mark.asyncio
async def test_holiday_skips_entirely(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")
    db_session.add(SystemConfig(key="bursa_holidays", value='["2026-08-03"]'))
    await db_session.commit()

    provider = FakePriceProvider({"1023": Decimal("8.42")})
    result = await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert result.skipped_reason == "non_trading_day"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_weekend_skips_entirely_without_holiday_config(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")

    provider = FakePriceProvider({"1023": Decimal("8.42")})
    result = await run_price_refresh(db_session, provider, today=_A_SUNDAY, backoff_seconds=_FAST_BACKOFF)

    assert result.skipped_reason == "non_trading_day"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_lock_contention_skips_run(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")
    db_session.add(SystemConfig(key="price_refresh_lock", value=datetime.now(timezone.utc).isoformat()))
    await db_session.commit()

    provider = FakePriceProvider({"1023": Decimal("8.42")})
    result = await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert result.skipped_reason == "lock_held"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_stale_lock_beyond_ttl_is_reacquired(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")
    stale_time = datetime.now(timezone.utc) - timedelta(hours=3)
    db_session.add(SystemConfig(key="price_refresh_lock", value=stale_time.isoformat()))
    await db_session.commit()

    provider = FakePriceProvider({"1023": Decimal("8.42")})
    result = await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert result.skipped_reason is None
    assert result.fetched == ["1023"]


@pytest.mark.asyncio
async def test_lock_released_after_successful_run(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")

    provider = FakePriceProvider({"1023": Decimal("8.42")})
    await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert await get_system_config(db_session, "price_refresh_lock") is None


@pytest.mark.asyncio
async def test_lock_released_even_if_the_job_raises(client, seeded_broker, db_session, monkeypatch):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated crash mid-run")

    monkeypatch.setattr("app.pricing.service._fetch_all", _boom)

    provider = FakePriceProvider({"1023": Decimal("8.42")})
    with pytest.raises(RuntimeError):
        await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert await get_system_config(db_session, "price_refresh_lock") is None


@pytest.mark.asyncio
async def test_running_twice_same_day_upserts_not_duplicates(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, "1023")

    first = FakePriceProvider({"1023": Decimal("8.4200")})
    await run_price_refresh(db_session, first, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    second = FakePriceProvider({"1023": Decimal("8.5000")})
    await run_price_refresh(db_session, second, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    rows = (await db_session.execute(select(PriceSnapshot).where(PriceSnapshot.stock_code == "1023"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].price == Decimal("8.5000")


@pytest.mark.asyncio
async def test_only_active_lots_of_active_positions_are_refreshed(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    kept = await _create_position(client, seeded_broker, "1023")
    deleted = await _create_position(client, seeded_broker, "1155")
    await client.delete(f"/api/v1/portfolio/positions/{deleted['id']}")

    provider = FakePriceProvider({"1023": Decimal("8.42"), "1155": Decimal("9.20")})
    result = await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)

    assert result.fetched == ["1023"]
    assert "1155" not in provider.calls


@pytest.mark.asyncio
async def test_batch_orchestration_overhead_is_fast(client, seeded_broker, db_session):
    """Not a real yfinance timing benchmark (that depends on network
    latency this test can't control) — confirms the concurrency/retry
    orchestration itself isn't the bottleneck for 16 stocks."""
    await _register(client, seeded_broker)
    codes = [str(1000 + i) for i in range(16)]
    for code in codes:
        await _create_position(client, seeded_broker, code)

    provider = FakePriceProvider({code: Decimal("8.42") for code in codes})

    start = time.perf_counter()
    result = await run_price_refresh(db_session, provider, today=_A_MONDAY, backoff_seconds=_FAST_BACKOFF)
    elapsed = time.perf_counter() - start

    assert len(result.fetched) == 16
    assert elapsed < 5.0
