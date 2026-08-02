from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from app.auth.models import User
from app.portfolio.models import BrokerConfig
from app.pricing.models import PriceSnapshot
from app.pricing.service import run_price_refresh

_TODAY = date(2026, 8, 3)


async def _register(client, seeded_broker, email="ahmad@email.com"):
    resp = await client.post(
        "/auth/register",
        json={"email": email, "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 201
    return resp.json()["user"]


async def _percentage_broker(db_session, rate="0.001", minimum_fee="8.00") -> BrokerConfig:
    broker = BrokerConfig(
        id=uuid4(), name="Maybank Investment", fee_type="percentage", rate=rate, minimum_fee=minimum_fee, is_system=True
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


async def _create_position(client, broker, *, stock_code="1023", shares=5000, purchase_price="8.3800"):
    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": stock_code,
            "stock_name": "CIMB GROUP HOLDINGS BHD",
            "shares": shares,
            "purchase_price": purchase_price,
            "broker_id": str(broker.id),
            "purchase_date": "2020-01-15",
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _set_account_status(db_session, user_id: str, status: str) -> None:
    await db_session.execute(update(User).where(User.id == UUID(user_id)).values(account_status=status))
    await db_session.commit()


class FakePriceProvider:
    def __init__(self, responses: dict[str, object]):
        self.responses = responses

    async def fetch_price(self, stock_code: str) -> Decimal:
        value = self.responses[stock_code]
        if isinstance(value, BaseException):
            raise value
        return value


# ---------- GET /pricing/prices ----------


@pytest.mark.asyncio
async def test_get_prices_returns_latest_snapshot_per_code(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    db_session.add(PriceSnapshot(stock_code="1023", price=Decimal("8.4200"), source="automated", trading_date=_TODAY))
    db_session.add(PriceSnapshot(stock_code="1155", price=Decimal("9.2000"), source="manual", trading_date=_TODAY))
    await db_session.commit()

    resp = await client.get("/api/v1/pricing/prices", params={"codes": ["1023", "1155"]})

    assert resp.status_code == 200
    prices = {p["stock_code"]: p for p in resp.json()["prices"]}
    assert prices["1023"]["price"] == "8.4200"
    assert prices["1023"]["source"] == "automated"
    assert prices["1155"]["source"] == "manual"


@pytest.mark.asyncio
async def test_get_prices_returns_only_the_latest_trading_date(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    db_session.add(
        PriceSnapshot(stock_code="1023", price=Decimal("8.0000"), source="automated", trading_date=_TODAY - timedelta(days=1))
    )
    db_session.add(PriceSnapshot(stock_code="1023", price=Decimal("8.4200"), source="automated", trading_date=_TODAY))
    await db_session.commit()

    resp = await client.get("/api/v1/pricing/prices", params={"codes": ["1023"]})

    prices = resp.json()["prices"]
    assert len(prices) == 1
    assert prices[0]["price"] == "8.4200"


@pytest.mark.asyncio
async def test_get_prices_omits_codes_with_no_snapshot_ever(client, seeded_broker, db_session):
    """EC-005: no price ever retrieved is not the same as stale — the code
    simply doesn't appear, rather than a fabricated stale entry."""
    await _register(client, seeded_broker)

    resp = await client.get("/api/v1/pricing/prices", params={"codes": ["9999"]})

    assert resp.status_code == 200
    assert resp.json()["prices"] == []


@pytest.mark.asyncio
async def test_get_prices_requires_authentication(client):
    resp = await client.get("/api/v1/pricing/prices", params={"codes": ["1023"]})
    assert resp.status_code == 401


# ---------- POST /pricing/manual-override ----------


@pytest.mark.asyncio
async def test_manual_override_creates_manual_snapshot(client, seeded_broker, db_session):
    user = await _register(client, seeded_broker)

    resp = await client.post(
        "/api/v1/pricing/manual-override",
        json={"stock_code": "1023", "price": "8.5000", "trading_date": "2026-08-03"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["stock_code"] == "1023"
    assert body["price"] == "8.5000"
    assert body["source"] == "manual"

    row = (
        await db_session.execute(select(PriceSnapshot).where(PriceSnapshot.stock_code == "1023"))
    ).scalar_one()
    assert row.created_by_user_id == UUID(user["id"])


@pytest.mark.asyncio
async def test_manual_override_updates_existing_row_same_day_not_duplicate(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    db_session.add(PriceSnapshot(stock_code="1023", price=Decimal("8.0000"), source="automated", trading_date=_TODAY))
    await db_session.commit()

    resp = await client.post(
        "/api/v1/pricing/manual-override",
        json={"stock_code": "1023", "price": "8.5000", "trading_date": "2026-08-03"},
    )

    assert resp.status_code == 201
    rows = (await db_session.execute(select(PriceSnapshot).where(PriceSnapshot.stock_code == "1023"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].price == Decimal("8.5000")
    assert rows[0].source == "manual"


@pytest.mark.asyncio
async def test_manual_override_records_audit_event(client, seeded_broker, db_session):
    from app.admin.models import AuditLog

    await _register(client, seeded_broker)
    await client.post(
        "/api/v1/pricing/manual-override",
        json={"stock_code": "1023", "price": "8.5000", "trading_date": "2026-08-03"},
    )

    entry = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "PRICE_OVERRIDE_CREATED"))
    ).scalar_one()
    assert entry.entity_type == "PriceSnapshot"
    assert entry.metadata_["stock_code"] == "1023"


@pytest.mark.asyncio
async def test_manual_override_rejects_non_positive_price(client, seeded_broker):
    await _register(client, seeded_broker)
    resp = await client.post(
        "/api/v1/pricing/manual-override",
        json={"stock_code": "1023", "price": "0", "trading_date": "2026-08-03"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_manual_override_rejects_more_than_4dp(client, seeded_broker):
    await _register(client, seeded_broker)
    resp = await client.post(
        "/api/v1/pricing/manual-override",
        json={"stock_code": "1023", "price": "8.42001", "trading_date": "2026-08-03"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_manual_override_requires_authentication(client):
    resp = await client.post(
        "/api/v1/pricing/manual-override",
        json={"stock_code": "1023", "price": "8.42", "trading_date": "2026-08-03"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_manual_override_blocked_for_trial_expired_account(client, seeded_broker, db_session):
    """BAS EC-020: manual price entry is a write action, blocked read-only."""
    user = await _register(client, seeded_broker)
    await _set_account_status(db_session, user["id"], "trial_expired")

    resp = await client.post(
        "/api/v1/pricing/manual-override",
        json={"stock_code": "1023", "price": "8.42", "trading_date": "2026-08-03"},
    )

    assert resp.status_code == 422
    assert resp.json()["error"] == "trial_expired"


@pytest.mark.asyncio
async def test_manual_override_allowed_for_active_account(client, seeded_broker, db_session):
    user = await _register(client, seeded_broker)
    await _set_account_status(db_session, user["id"], "active")

    resp = await client.post(
        "/api/v1/pricing/manual-override",
        json={"stock_code": "1023", "price": "8.42", "trading_date": "2026-08-03"},
    )

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_manual_override_is_shared_system_data_across_users(client, client_with_cookie, seeded_broker, db_session):
    """BE-5.2 Technical Constraints: not per-user — visible to any user
    holding the same stock, until the next automated refresh supersedes it."""
    await _register(client, seeded_broker, email="ahmad@email.com")
    await client.post(
        "/api/v1/pricing/manual-override",
        json={"stock_code": "1023", "price": "8.5000", "trading_date": "2026-08-03"},
    )

    async with await client_with_cookie({}) as other_client:
        register_resp = await other_client.post(
            "/auth/register",
            json={"email": "farah@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
        )
        other_cookie = register_resp.cookies["bursatrack_session"]

    async with await client_with_cookie({"bursatrack_session": other_cookie}) as other_client:
        resp = await other_client.get("/api/v1/pricing/prices", params={"codes": ["1023"]})

    assert resp.status_code == 200
    prices = resp.json()["prices"]
    assert len(prices) == 1
    assert prices[0]["source"] == "manual"
    assert prices[0]["price"] == "8.5000"


# ---------- BR-023: full outage -> manual override -> next refresh supersedes ----------


@pytest.mark.asyncio
async def test_full_outage_then_manual_override_then_next_refresh_supersedes(client, seeded_broker, db_session):
    """DoD: mirrors the BAS Integration/Scenario Tests table end to end,
    tying BE-5.1's cron and BE-5.2's manual override together."""
    await _register(client, seeded_broker)
    await _create_position(client, seeded_broker, stock_code="1023")

    # 1. Full outage: the automated refresh fails for every stock.
    outage_provider = FakePriceProvider({"1023": Exception("yfinance down")})
    result = await run_price_refresh(db_session, outage_provider, today=_TODAY, backoff_seconds=(0.0, 0.0))
    assert result.failed == ["1023"]
    assert (await db_session.execute(select(PriceSnapshot))).scalars().all() == []

    # 2. User enters a manual override.
    override_resp = await client.post(
        "/api/v1/pricing/manual-override",
        json={"stock_code": "1023", "price": "8.5000", "trading_date": _TODAY.isoformat()},
    )
    assert override_resp.status_code == 201
    assert override_resp.json()["source"] == "manual"

    # 3. The next successful automated refresh supersedes the override.
    success_provider = FakePriceProvider({"1023": Decimal("8.6000")})
    await run_price_refresh(db_session, success_provider, today=_TODAY, backoff_seconds=(0.0, 0.0))

    rows = (await db_session.execute(select(PriceSnapshot).where(PriceSnapshot.stock_code == "1023"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].source == "automated"
    assert rows[0].price == Decimal("8.6000")
