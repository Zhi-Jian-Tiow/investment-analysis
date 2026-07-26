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


# ---------- GET position detail ----------


@pytest.mark.asyncio
async def test_get_position_returns_current_state(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == position["id"]
    assert body["total_shares"] == 5000
    assert len(body["lots"]) == 1


@pytest.mark.asyncio
async def test_get_position_returns_404_for_another_users_position(client, client_with_cookie, seeded_broker, db_session):
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
        resp = await other_client.get(f"/api/v1/portfolio/positions/{position['id']}")
    assert resp.status_code == 404


# ---------- PATCH position metadata ----------


@pytest.mark.asyncio
async def test_patch_position_updates_category_tag_and_notes(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}",
        json={"category_tag": "Growth", "notes": "Long-term hold"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["category_tag"] == "Growth"
    assert body["notes"] == "Long-term hold"
    # Lot financial fields must be untouched by a metadata-only edit.
    assert body["lots"][0]["all_in_cost"] == position["lots"][0]["all_in_cost"]


@pytest.mark.asyncio
async def test_patch_position_rejects_invalid_category_tag(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}",
        json={"category_tag": "NotARealCategory"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_position_writes_position_updated_audit_log(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}",
        json={"category_tag": "Volatile"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "POSITION_UPDATED"))
    entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].entity_type == "Position"
    assert entries[0].metadata_["previous_values"]["category_tag"] == "Dividend"
    assert entries[0].metadata_["new_values"]["category_tag"] == "Volatile"


@pytest.mark.asyncio
async def test_patch_position_returns_404_for_another_users_position(client, client_with_cookie, seeded_broker, db_session):
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
        resp = await other_client.patch(
            f"/api/v1/portfolio/positions/{position['id']}", json={"category_tag": "Growth"}
        )
    assert resp.status_code == 404


# ---------- PATCH lot (optimistic locking) ----------


@pytest.mark.asyncio
async def test_patch_lot_recalculates_fees_and_increments_version(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    lot = position["lots"][0]
    assert lot["version"] == 1

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}/lots/{lot['id']}",
        json={"shares": 4000, "version": 1},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["shares"] == 4000
    assert body["version"] == 2
    # initial_amount recalculated: 4000 * 8.38 = 33520.00
    assert body["initial_amount"] == "33520.00"
    assert body["brokerage_fee"] == "33.52"
    assert any("Dividend records were not changed" in w for w in body["warnings"])


@pytest.mark.asyncio
async def test_patch_lot_without_shares_change_has_no_ec015_notice(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    lot = position["lots"][0]

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}/lots/{lot['id']}",
        json={"purchase_price": "9.0000", "version": 1},
    )

    assert resp.status_code == 200
    assert resp.json()["warnings"] == []


@pytest.mark.asyncio
async def test_patch_lot_stale_version_returns_409(client, seeded_broker, db_session):
    """EX-008: a second session's PATCH using a now-stale `version` must be
    rejected — even though this test simulates it sequentially rather than
    with true concurrency, it exercises the exact same conditional-UPDATE
    code path a real race would hit.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    lot = position["lots"][0]

    first = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}/lots/{lot['id']}",
        json={"shares": 4000, "version": 1},
    )
    assert first.status_code == 200
    assert first.json()["version"] == 2

    stale = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}/lots/{lot['id']}",
        json={"shares": 3000, "version": 1},
    )

    assert stale.status_code == 409
    body = stale.json()
    assert body["error"] == "version_conflict"
    assert body["message"] == "This record was modified by another session. Please refresh and try again."

    # The stale request must not have been applied.
    result = await db_session.execute(select(Lot).where(Lot.id == UUID(lot["id"])))
    reloaded = result.scalar_one()
    assert reloaded.shares == 4000
    assert reloaded.version == 2


@pytest.mark.asyncio
async def test_patch_lot_broker_override_recalculates_with_new_broker(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker_a = await _percentage_broker(db_session, rate="0.001", minimum_fee="8.00")
    broker_b = BrokerConfig(id=uuid4(), name="MooMoo", fee_type="flat", flat_fee="3.00", is_system=True)
    db_session.add(broker_b)
    await db_session.commit()
    await db_session.refresh(broker_b)

    position = await _create_position(client, broker_a)
    lot = position["lots"][0]

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}/lots/{lot['id']}",
        json={"broker_id": str(broker_b.id), "version": 1},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["broker_id"] == str(broker_b.id)
    assert body["brokerage_fee"] == "3.00"


@pytest.mark.asyncio
async def test_patch_lot_rejects_empty_body(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    lot = position["lots"][0]

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}/lots/{lot['id']}",
        json={"version": 1},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_lot_revalidates_vr004_shares(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    lot = position["lots"][0]

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}/lots/{lot['id']}",
        json={"shares": 0, "version": 1},
    )
    assert resp.status_code == 422
    assert any("greater than zero" in f["constraint"] for f in resp.json()["fields"])


@pytest.mark.asyncio
async def test_patch_lot_returns_404_for_lot_in_another_position(client, seeded_broker, db_session):
    """Ownership is verified on both the position and the lot — a lot must
    belong to the position named in the path, even if both positions belong
    to the same user.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position_a = await _create_position(client, broker, stock_code="1023")
    position_b = await _create_position(client, broker, stock_code="5000")
    lot_from_b = position_b["lots"][0]

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position_a['id']}/lots/{lot_from_b['id']}",
        json={"shares": 100, "version": 1},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_lot_returns_404_for_another_users_position(client, client_with_cookie, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    lot = position["lots"][0]

    async with await client_with_cookie({}) as other_client:
        register_resp = await other_client.post(
            "/auth/register",
            json={"email": "someone-else@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
        )
        other_cookie = register_resp.cookies["bursatrack_session"]

    async with await client_with_cookie({"bursatrack_session": other_cookie}) as other_client:
        resp = await other_client.patch(
            f"/api/v1/portfolio/positions/{position['id']}/lots/{lot['id']}",
            json={"shares": 100, "version": 1},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_lot_writes_lot_updated_audit_log_with_previous_and_new_values(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    lot = position["lots"][0]

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}/lots/{lot['id']}",
        json={"shares": 4000, "version": 1},
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "LOT_UPDATED"))
    entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].entity_type == "Lot"
    assert entries[0].metadata_["previous_values"]["shares"] == 5000
    assert entries[0].metadata_["new_values"]["shares"] == 4000


@pytest.mark.asyncio
async def test_patch_lot_does_not_mutate_other_lots_ec015_precursor(client, seeded_broker, db_session):
    """EC-015 precursor: editing one lot's share count must not affect any
    other lot on the same position. The full EC-015 invariant (that
    DividendTranche totals also stay untouched) is deferred to BE-3.1, same
    as BE-2.2's EC-022 precursor.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    first_lot = position["lots"][0]

    add_lot_resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={"shares": 2000, "purchase_price": "9.0000", "broker_id": str(broker.id), "purchase_date": "2026-04-02"},
    )
    second_lot = add_lot_resp.json()

    resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}/lots/{second_lot['id']}",
        json={"shares": 1000, "version": 1},
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(Lot).where(Lot.id == UUID(first_lot["id"])))
    reloaded_first_lot = result.scalar_one()
    assert reloaded_first_lot.shares == 5000
    assert str(reloaded_first_lot.all_in_cost) == first_lot["all_in_cost"]
