from uuid import uuid4

import pytest
from sqlalchemy import select

from app.admin.models import AuditLog
from app.portfolio.models import BrokerConfig


async def _register(client, seeded_broker):
    resp = await client.post(
        "/auth/register",
        json={"email": "ahmad@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 201
    return resp


async def _percentage_broker(db_session, rate="0.001", minimum_fee="8.00") -> BrokerConfig:
    broker = BrokerConfig(
        id=uuid4(), name="Maybank Investment", fee_type="percentage", rate=rate, minimum_fee=minimum_fee, is_system=True
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker


@pytest.mark.asyncio
async def test_add_position_happy_path_matches_bas_worked_example(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)

    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB GROUP HOLDINGS BHD",
            "shares": 5000,
            "purchase_price": "8.3800",
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-15",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["stock_code"] == "1023"
    assert body["total_shares"] == 5000
    assert body["total_all_in_cost"] == "41996.47"
    assert body["blended_purchase_price"] == "8.3800"
    assert len(body["lots"]) == 1
    lot = body["lots"][0]
    assert lot["initial_amount"] == "41900.00"
    assert lot["brokerage_fee"] == "41.90"
    assert lot["clearing_fee"] == "12.57"
    assert lot["stamp_duty"] == "42.00"
    assert lot["all_in_cost"] == "41996.47"
    assert lot["version"] == 1
    assert body["warnings"] == []
    # Fields that depend on later epics stay at their documented defaults.
    assert body["dividend_tranches"] == []
    assert body["total_dividend_income_ytd"] == "0.00"
    assert body["current_price"] is None


@pytest.mark.asyncio
async def test_add_position_requires_authentication(client, seeded_broker):
    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB",
            "shares": 100,
            "purchase_price": "1.0000",
            "broker_id": str(seeded_broker.id),
            "purchase_date": "2026-01-15",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_position_rejects_zero_shares(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB",
            "shares": 0,
            "purchase_price": "1.0000",
            "broker_id": str(seeded_broker.id),
            "purchase_date": "2026-01-15",
        },
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "validation_failed"
    assert any(f["field"] == "shares" for f in body["fields"])
    assert any("greater than zero" in f["constraint"] for f in body["fields"])


@pytest.mark.asyncio
async def test_add_position_rejects_future_purchase_date(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB",
            "shares": 100,
            "purchase_price": "1.0000",
            "broker_id": str(seeded_broker.id),
            "purchase_date": "2099-01-01",
        },
    )

    assert resp.status_code == 422
    body = resp.json()
    assert any("cannot be in the future" in f["constraint"] for f in body["fields"])


@pytest.mark.asyncio
async def test_add_position_rejects_price_with_too_many_decimals(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB",
            "shares": 100,
            "purchase_price": "1.00001",
            "broker_id": str(seeded_broker.id),
            "purchase_date": "2026-01-15",
        },
    )

    assert resp.status_code == 422
    body = resp.json()
    assert any("4 decimal places" in f["constraint"] for f in body["fields"])


@pytest.mark.asyncio
async def test_add_position_unknown_broker_returns_validation_error(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB",
            "shares": 100,
            "purchase_price": "1.0000",
            "broker_id": str(uuid4()),
            "purchase_date": "2026-01-15",
        },
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "validation_failed"
    assert any(f["field"] == "broker_id" for f in body["fields"])


@pytest.mark.asyncio
async def test_add_position_duplicate_stock_code_adds_lot_not_new_position(client, seeded_broker, db_session):
    """EC-001: the second add-position call for the same active stock code
    must add a Lot to the existing Position, not create a duplicate."""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)

    first = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB GROUP HOLDINGS BHD",
            "shares": 5000,
            "purchase_price": "8.3800",
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-15",
        },
    )
    assert first.status_code == 201
    position_id = first.json()["id"]

    second = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB GROUP HOLDINGS BHD",
            "shares": 2000,
            "purchase_price": "9.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-04-02",
        },
    )

    assert second.status_code == 201
    body = second.json()
    assert body["id"] == position_id
    assert len(body["lots"]) == 2
    assert body["total_shares"] == 7000
    assert body["total_all_in_cost"] == "60037.87"
    # (41900.00 + 18000.00) / 7000, quantized to 4dp (BR-026 price precision).
    assert body["blended_purchase_price"] == "8.5571"
    assert any("already have a" in w and "added to your existing position" in w for w in body["warnings"])


@pytest.mark.asyncio
async def test_add_position_zero_brokerage_is_valid(client, seeded_broker, db_session):
    """EC-002: a custom broker with rate=0 is a valid, non-error scenario."""
    await _register(client, seeded_broker)
    zero_rate_broker = await _percentage_broker(db_session, rate="0", minimum_fee="0")

    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB",
            "shares": 1000,
            "purchase_price": "1.0000",
            "broker_id": str(zero_rate_broker.id),
            "purchase_date": "2026-01-15",
        },
    )

    assert resp.status_code == 201
    assert resp.json()["lots"][0]["brokerage_fee"] == "0.00"


@pytest.mark.asyncio
async def test_add_position_non_trading_day_gives_soft_warning_not_block(client, seeded_broker, db_session):
    """EC-004: a weekend purchase date is accepted with a warning, not blocked."""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)

    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB",
            "shares": 100,
            "purchase_price": "1.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-17",  # a Saturday
        },
    )

    assert resp.status_code == 201
    assert any("not a Bursa trading day" in w for w in resp.json()["warnings"])


@pytest.mark.asyncio
async def test_add_position_writes_lot_created_audit_log(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)

    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB",
            "shares": 100,
            "purchase_price": "1.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-15",
        },
    )
    assert resp.status_code == 201
    lot_id = resp.json()["lots"][0]["id"]

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "LOT_CREATED"))
    entries = result.scalars().all()
    assert len(entries) == 1
    assert str(entries[0].entity_id) == lot_id
    assert entries[0].entity_type == "Lot"
