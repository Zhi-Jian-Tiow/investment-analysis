from uuid import UUID, uuid4

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


async def _create_position(client, broker, *, stock_code="1023", shares=5000, purchase_price="8.3800"):
    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": stock_code,
            "stock_name": "CIMB GROUP HOLDINGS BHD",
            "shares": shares,
            "purchase_price": purchase_price,
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-15",
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_add_lot_matches_bas_us_004_numeric_example(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={
            "shares": 2000,
            "purchase_price": "9.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-04-02",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["position_id"] == position["id"]
    assert body["initial_amount"] == "18000.00"
    assert body["brokerage_fee"] == "18.00"
    assert body["clearing_fee"] == "5.40"
    assert body["stamp_duty"] == "18.00"
    assert body["all_in_cost"] == "18041.40"
    assert body["version"] == 1


@pytest.mark.asyncio
async def test_add_lot_updates_position_aggregates_on_next_read(client, seeded_broker, db_session):
    """BR-010/BR-011: aggregates are computed at query time — verified here
    by re-adding a position for the same stock code (which surfaces the
    up-to-date aggregate via the EC-001 redirect path in BE-2.1's endpoint)
    rather than a dedicated GET position-detail endpoint, which doesn't
    exist yet (no Epic 2 story requires it before FE-2.2).
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    add_lot_resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={
            "shares": 2000,
            "purchase_price": "9.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-04-02",
        },
    )
    assert add_lot_resp.status_code == 201

    reread = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB GROUP HOLDINGS BHD",
            "shares": 1,
            "purchase_price": "1.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-15",
        },
    )
    assert reread.status_code == 201
    body = reread.json()
    assert body["id"] == position["id"]
    assert len(body["lots"]) == 3
    # 5000 + 2000 + 1 shares; 41996.47 (lot 1) + 18041.40 (lot 2) + lot 3's own all-in cost.
    assert body["total_shares"] == 7001


@pytest.mark.asyncio
async def test_add_lot_broker_is_overridable_and_independent_of_position_default(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker_a = await _percentage_broker(db_session, rate="0.001", minimum_fee="8.00")
    broker_b = BrokerConfig(id=uuid4(), name="MooMoo", fee_type="flat", flat_fee="3.00", is_system=True)
    db_session.add(broker_b)
    await db_session.commit()
    await db_session.refresh(broker_b)

    position = await _create_position(client, broker_a)

    resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={
            "shares": 2000,
            "purchase_price": "9.0000",
            "broker_id": str(broker_b.id),
            "purchase_date": "2026-04-02",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["broker_id"] == str(broker_b.id)
    assert body["brokerage_fee"] == "3.00"


@pytest.mark.asyncio
async def test_add_lot_requires_authentication(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    await client.post("/auth/logout")

    resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={
            "shares": 100,
            "purchase_price": "1.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-15",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_lot_returns_404_for_nonexistent_position(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)

    resp = await client.post(
        f"/api/v1/portfolio/positions/{uuid4()}/lots",
        json={
            "shares": 100,
            "purchase_price": "1.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-15",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_lot_returns_404_for_another_users_position(client, client_with_cookie, seeded_broker, db_session):
    """BAS §9: ownership-check failures must be indistinguishable from
    a missing resource — 404, never 403."""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    other_client_factory = client_with_cookie
    async with await other_client_factory({}) as other_client:
        register_resp = await other_client.post(
            "/auth/register",
            json={"email": "someone-else@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
        )
        assert register_resp.status_code == 201
        other_cookie = register_resp.cookies["bursatrack_session"]

    async with await other_client_factory({"bursatrack_session": other_cookie}) as other_client:
        resp = await other_client.post(
            f"/api/v1/portfolio/positions/{position['id']}/lots",
            json={
                "shares": 100,
                "purchase_price": "1.0000",
                "broker_id": str(broker.id),
                "purchase_date": "2026-01-15",
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_lot_returns_404_for_soft_deleted_position(client, seeded_broker, db_session):
    """EC-006 precursor: soft-delete isn't implemented until BE-2.4, but the
    lookup already excludes is_deleted=true positions — verified directly
    against the DB row here rather than via a delete endpoint that doesn't
    exist yet.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    from app.portfolio.models import Position

    result = await db_session.execute(select(Position).where(Position.id == UUID(position["id"])))
    db_position = result.scalar_one()
    db_position.is_deleted = True
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={
            "shares": 100,
            "purchase_price": "1.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-15",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_lot_non_trading_day_gives_soft_warning_not_block(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={
            "shares": 100,
            "purchase_price": "1.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-17",  # a Saturday
        },
    )
    assert resp.status_code == 201
    assert any("not a Bursa trading day" in w for w in resp.json()["warnings"])


@pytest.mark.asyncio
async def test_add_lot_writes_lot_created_audit_log(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={
            "shares": 2000,
            "purchase_price": "9.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-04-02",
        },
    )
    assert resp.status_code == 201
    lot_id = resp.json()["id"]

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "LOT_CREATED"))
    entries = result.scalars().all()
    # One from _create_position's first lot, one from this add-lot call.
    assert len(entries) == 2
    assert str(entries[-1].entity_id) == lot_id


@pytest.mark.asyncio
async def test_add_lot_does_not_mutate_existing_lot_ec022_precursor(client, seeded_broker, db_session):
    """P0 invariant precursor (EC-022/BR-009): adding a lot must never alter
    any previously-created Lot's own stored fee fields. The full invariant
    (that DividendTranche.total_amount also stays untouched) can't be tested
    yet since DividendTranche doesn't exist until Epic 3 (BE-3.1) — this test
    covers the Lot-level half of the invariant now and should be extended
    when BE-3.1 lands.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    first_lot = position["lots"][0]

    resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={
            "shares": 2000,
            "purchase_price": "9.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-04-02",
        },
    )
    assert resp.status_code == 201

    from app.portfolio.models import Lot

    result = await db_session.execute(select(Lot).where(Lot.id == UUID(first_lot["id"])))
    reloaded_first_lot = result.scalar_one()
    assert str(reloaded_first_lot.all_in_cost) == first_lot["all_in_cost"]
    assert reloaded_first_lot.shares == first_lot["shares"]
    assert reloaded_first_lot.version == first_lot["version"]
