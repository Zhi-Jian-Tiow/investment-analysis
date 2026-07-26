from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.admin.models import AuditLog
from app.portfolio.models import BrokerConfig, Lot, Position


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
async def test_delete_position_soft_deletes_position_and_returns_204(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.delete(f"/api/v1/portfolio/positions/{position['id']}")

    assert resp.status_code == 204
    assert resp.content == b""

    result = await db_session.execute(select(Position).where(Position.id == UUID(position["id"])))
    db_position = result.scalar_one()
    assert db_position.is_deleted is True
    assert db_position.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_position_cascades_to_active_lots(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={"shares": 2000, "purchase_price": "9.0000", "broker_id": str(broker.id), "purchase_date": "2026-04-02"},
    )

    resp = await client.delete(f"/api/v1/portfolio/positions/{position['id']}")
    assert resp.status_code == 204

    result = await db_session.execute(select(Lot).where(Lot.position_id == UUID(position["id"])))
    lots = result.scalars().all()
    assert len(lots) == 2
    assert all(lot.is_deleted is True and lot.deleted_at is not None for lot in lots)


@pytest.mark.asyncio
async def test_delete_position_writes_position_deleted_audit_log(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.delete(f"/api/v1/portfolio/positions/{position['id']}")
    assert resp.status_code == 204

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "POSITION_DELETED"))
    entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].entity_type == "Position"
    assert str(entries[0].entity_id) == position["id"]


@pytest.mark.asyncio
async def test_deleted_position_no_longer_visible_via_get(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    await client.delete(f"/api/v1/portfolio/positions/{position['id']}")
    resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_is_idempotent_second_call_returns_404_not_an_error(client, seeded_broker, db_session):
    """DoD: deletion is idempotent — a second delete attempt doesn't corrupt
    state or double-apply anything. Since the ownership lookup excludes
    already-deleted positions (the same filter GET/PATCH use), a repeat
    DELETE naturally 404s rather than silently no-op'ing with 204 — the end
    state (soft-deleted, once) is identical either way.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    first = await client.delete(f"/api/v1/portfolio/positions/{position['id']}")
    second = await client.delete(f"/api/v1/portfolio/positions/{position['id']}")

    assert first.status_code == 204
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_delete_position_returns_404_for_nonexistent_position(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.delete(f"/api/v1/portfolio/positions/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_position_returns_404_for_another_users_position(client, client_with_cookie, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    async with await client_with_cookie({}) as other_client:
        register_resp = await other_client.post(
            "/auth/register",
            json={"email": "someone-else@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
        )
        other_cookie = register_resp.cookies["bursatrack_session"]

    async with await client_with_cookie({"bursatrack_session": other_cookie}) as other_client:
        resp = await other_client.delete(f"/api/v1/portfolio/positions/{position['id']}")
    assert resp.status_code == 404

    # Confirm it was NOT actually deleted by the other user's attempt.
    result = await db_session.execute(select(Position).where(Position.id == UUID(position["id"])))
    assert result.scalar_one().is_deleted is False


@pytest.mark.asyncio
async def test_delete_position_requires_authentication(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    await client.post("/auth/logout")

    resp = await client.delete(f"/api/v1/portfolio/positions/{position['id']}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_lot_to_soft_deleted_position_returns_404_ec006_precursor(client, seeded_broker, db_session):
    """EC-006: attempting to log something against a soft-deleted position
    (bypassing the UI) must 404. No dividend endpoint exists yet (Epic 3) to
    test the literal AC, but the same ownership-check mechanism already
    guards the Add Lot endpoint, so this exercises the identical code path.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    await client.delete(f"/api/v1/portfolio/positions/{position['id']}")

    resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={"shares": 100, "purchase_price": "1.0000", "broker_id": str(broker.id), "purchase_date": "2026-01-15"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_re_adding_stock_code_after_delete_creates_new_position_ec001_exception(client, seeded_broker, db_session):
    """EC-001 exception path: the old soft-deleted position for a stock code
    is not resurrected — a fresh Add Position call creates a brand new one.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    first_position = await _create_position(client, broker, stock_code="1023")

    await client.delete(f"/api/v1/portfolio/positions/{first_position['id']}")

    second = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB GROUP HOLDINGS BHD",
            "shares": 1000,
            "purchase_price": "8.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-05-01",
        },
    )

    assert second.status_code == 201
    body = second.json()
    assert body["id"] != first_position["id"]
    assert len(body["lots"]) == 1
    assert body["total_shares"] == 1000
    assert body["warnings"] == []  # no "added to existing position" notice — this is a genuinely new Position
