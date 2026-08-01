from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.admin.models import AuditLog
from app.portfolio.models import BrokerConfig, Lot


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


async def _add_lot(client, position_id, broker, *, shares=2000, purchase_price="9.0000"):
    resp = await client.post(
        f"/api/v1/portfolio/positions/{position_id}/lots",
        json={
            "shares": shares,
            "purchase_price": purchase_price,
            "broker_id": str(broker.id),
            "purchase_date": "2026-04-02",
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_delete_lot_soft_deletes_and_returns_204(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    second_lot = await _add_lot(client, position["id"], broker)

    resp = await client.delete(f"/api/v1/portfolio/positions/{position['id']}/lots/{second_lot['id']}")

    assert resp.status_code == 204
    assert resp.content == b""

    result = await db_session.execute(select(Lot).where(Lot.id == UUID(second_lot["id"])))
    db_lot = result.scalar_one()
    assert db_lot.is_deleted is True
    assert db_lot.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_lot_updates_position_aggregates_on_next_read(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    second_lot = await _add_lot(client, position["id"], broker)

    await client.delete(f"/api/v1/portfolio/positions/{position['id']}/lots/{second_lot['id']}")

    resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}")
    body = resp.json()
    assert len(body["lots"]) == 1
    assert body["total_shares"] == 5000
    assert body["total_all_in_cost"] == "41996.47"  # only the first lot (BAS US-003 happy path) remains


@pytest.mark.asyncio
async def test_delete_lot_blocks_deleting_the_only_lot(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    only_lot = position["lots"][0]

    resp = await client.delete(f"/api/v1/portfolio/positions/{position['id']}/lots/{only_lot['id']}")

    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "last_lot"

    result = await db_session.execute(select(Lot).where(Lot.id == UUID(only_lot["id"])))
    assert result.scalar_one().is_deleted is False


@pytest.mark.asyncio
async def test_delete_lot_returns_404_for_nonexistent_lot(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.delete(f"/api/v1/portfolio/positions/{position['id']}/lots/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_lot_returns_404_for_lot_in_another_position(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position_a = await _create_position(client, broker, stock_code="1023")
    position_b = await _create_position(client, broker, stock_code="5000")
    lot_from_b = position_b["lots"][0]

    resp = await client.delete(f"/api/v1/portfolio/positions/{position_a['id']}/lots/{lot_from_b['id']}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_lot_returns_404_for_another_users_position(client, client_with_cookie, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    second_lot = await _add_lot(client, position["id"], broker)

    async with await client_with_cookie({}) as other_client:
        register_resp = await other_client.post(
            "/auth/register",
            json={"email": "someone-else@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
        )
        other_cookie = register_resp.cookies["bursatrack_session"]

    async with await client_with_cookie({"bursatrack_session": other_cookie}) as other_client:
        resp = await other_client.delete(f"/api/v1/portfolio/positions/{position['id']}/lots/{second_lot['id']}")
    assert resp.status_code == 404

    result = await db_session.execute(select(Lot).where(Lot.id == UUID(second_lot["id"])))
    assert result.scalar_one().is_deleted is False


@pytest.mark.asyncio
async def test_delete_lot_requires_authentication(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    second_lot = await _add_lot(client, position["id"], broker)
    await client.post("/auth/logout")

    resp = await client.delete(f"/api/v1/portfolio/positions/{position['id']}/lots/{second_lot['id']}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_lot_writes_lot_deleted_audit_log(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    second_lot = await _add_lot(client, position["id"], broker)

    resp = await client.delete(f"/api/v1/portfolio/positions/{position['id']}/lots/{second_lot['id']}")
    assert resp.status_code == 204

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "LOT_DELETED"))
    entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].entity_type == "Lot"
    assert str(entries[0].entity_id) == second_lot["id"]


@pytest.mark.asyncio
async def test_deleted_lot_excluded_from_position_lots_and_not_re_deletable(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    second_lot = await _add_lot(client, position["id"], broker)

    first = await client.delete(f"/api/v1/portfolio/positions/{position['id']}/lots/{second_lot['id']}")
    second = await client.delete(f"/api/v1/portfolio/positions/{position['id']}/lots/{second_lot['id']}")

    assert first.status_code == 204
    assert second.status_code == 404
