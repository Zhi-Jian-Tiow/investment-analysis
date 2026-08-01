from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.admin.models import AuditLog
from app.portfolio.models import BrokerConfig, DividendTranche


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


def _dividend_body(position_id, **overrides):
    body = {
        "position_id": position_id,
        "tranche_label": "1st",
        "per_share_amount": "0.200000",
        "qualifying_shares": 5000,
        "payment_date": "2026-03-15",
        "ex_dividend_date": "2026-02-28",
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_add_dividend_happy_path_stores_total_amount(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))

    assert resp.status_code == 201
    body = resp.json()
    assert body["position_id"] == position["id"]
    assert body["tranche_label"] == "1st"
    assert body["qualifying_shares"] == 5000
    assert body["total_amount"] == "1000.00"
    assert body["year"] == 2026
    assert body["version"] == 1


@pytest.mark.asyncio
async def test_add_dividend_requires_authentication(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    await client.post("/auth/logout")

    resp = await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_add_dividend_returns_404_for_nonexistent_position(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.post("/api/v1/portfolio/dividends", json=_dividend_body(str(uuid4())))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_dividend_returns_404_for_another_users_position(client, client_with_cookie, seeded_broker, db_session):
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
        resp = await other_client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_dividend_rejects_qualifying_shares_above_position_total(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker, shares=5000)

    resp = await client.post(
        "/api/v1/portfolio/dividends", json=_dividend_body(position["id"], qualifying_shares=5001)
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "validation_failed"
    assert any(f["field"] == "qualifying_shares" for f in body["fields"])


@pytest.mark.asyncio
async def test_add_dividend_allows_qualifying_shares_below_position_total_ec023(client, seeded_broker, db_session):
    """EC-023: deliberately logging fewer qualifying shares than the current
    position total is a valid, intentional state — not an error."""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker, shares=7000)

    resp = await client.post(
        "/api/v1/portfolio/dividends", json=_dividend_body(position["id"], qualifying_shares=5000)
    )

    assert resp.status_code == 201
    assert resp.json()["qualifying_shares"] == 5000


@pytest.mark.asyncio
async def test_add_dividend_rejects_zero_or_negative_per_share_amount(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.post(
        "/api/v1/portfolio/dividends", json=_dividend_body(position["id"], per_share_amount="0")
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_dividend_rejects_more_than_six_decimal_places(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.post(
        "/api/v1/portfolio/dividends", json=_dividend_body(position["id"], per_share_amount="0.1234567")
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_dividend_rejects_payment_date_more_than_30_days_future(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.post(
        "/api/v1/portfolio/dividends", json=_dividend_body(position["id"], payment_date="2099-01-01")
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_dividend_rejects_ex_dividend_date_after_payment_date(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.post(
        "/api/v1/portfolio/dividends",
        json=_dividend_body(position["id"], payment_date="2026-03-15", ex_dividend_date="2026-03-16"),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_dividend_rejects_ninth_tranche_in_same_year_br014(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    labels = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]
    for i, label in enumerate(labels):
        resp = await client.post(
            "/api/v1/portfolio/dividends",
            json=_dividend_body(
                position["id"], tranche_label=label, payment_date=f"2026-01-{i + 1:02d}", ex_dividend_date=None
            ),
        )
        assert resp.status_code == 201, f"tranche {label} unexpectedly failed"

    ninth = await client.post(
        "/api/v1/portfolio/dividends",
        json=_dividend_body(position["id"], tranche_label="1st", payment_date="2026-01-09", ex_dividend_date=None),
    )
    assert ninth.status_code == 422
    assert "Maximum of 8" in ninth.json()["message"]


@pytest.mark.asyncio
async def test_add_dividend_rejects_duplicate_tranche_label_same_year(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    first = await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/portfolio/dividends", json=_dividend_body(position["id"], payment_date="2026-07-01")
    )
    assert duplicate.status_code == 422
    assert any(f["field"] == "tranche_label" for f in duplicate.json()["fields"])


@pytest.mark.asyncio
async def test_add_dividend_allows_same_label_in_different_years(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    y2025 = await client.post(
        "/api/v1/portfolio/dividends",
        json=_dividend_body(position["id"], payment_date="2025-03-15", ex_dividend_date="2025-02-28"),
    )
    y2026 = await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))

    assert y2025.status_code == 201
    assert y2026.status_code == 201
    assert y2025.json()["year"] == 2025
    assert y2026.json()["year"] == 2026


@pytest.mark.asyncio
async def test_add_dividend_writes_dividend_created_audit_log(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))
    assert resp.status_code == 201
    tranche_id = resp.json()["id"]

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "DIVIDEND_CREATED"))
    entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].entity_type == "DividendTranche"
    assert str(entries[0].entity_id) == tranche_id


@pytest.mark.asyncio
async def test_position_detail_includes_dividend_tranches_and_income_ytd(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))

    resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["dividend_tranches"]) == 1
    assert body["dividend_tranches"][0]["total_amount"] == "1000.00"
    assert body["total_dividend_income_ytd"] == "1000.00"


@pytest.mark.asyncio
async def test_dashboard_includes_dividend_income_ytd(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))

    resp = await client.get("/api/v1/portfolio/dashboard")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_dividend_income_ytd"] == "1000.00"
    assert body["positions"][0]["total_dividend_income_ytd"] == "1000.00"


@pytest.mark.asyncio
async def test_yield_uses_all_in_cost_not_pre_fee_initial_amount(client, seeded_broker, db_session):
    """DoD: yield calculation must use all-in cost, with the explicit
    negative assertion that it does NOT equal income / pre-fee initial
    amount (BAS US-011). The backend never computes yield% itself (client
    does, via decimal.js) — this test verifies the two ingredients it
    returns (income, all-in cost) actually differ from (income, a
    hypothetical pre-fee cost), proving all_in_cost — not initial_amount —
    is the field a correct client-side yield calculation must use.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker, shares=5000, purchase_price="8.3800")
    await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))

    resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}")
    body = resp.json()

    income = float(body["total_dividend_income_ytd"])
    all_in_cost = float(body["total_all_in_cost"])
    pre_fee_initial_amount = float(body["lots"][0]["initial_amount"])

    correct_yield = income / all_in_cost
    incorrect_yield = income / pre_fee_initial_amount

    assert all_in_cost != pre_fee_initial_amount
    assert correct_yield != incorrect_yield
    assert correct_yield < incorrect_yield  # all-in cost > initial amount, so true yield is lower


@pytest.mark.asyncio
async def test_ec022_adding_lot_does_not_change_existing_dividend_total_amount(client, seeded_broker, db_session):
    """P0 regression test (BAS §14, mandatory, cannot be skipped). This is
    the full invariant BE-2.2's precursor test could only partially assert
    since DividendTranche didn't exist yet — extends it now from the other
    direction: logging a dividend, then adding a lot, must never change the
    already-stored total_amount.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker, shares=5000, purchase_price="8.3800")

    dividend_resp = await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))
    assert dividend_resp.status_code == 201
    assert dividend_resp.json()["total_amount"] == "1000.00"

    add_lot_resp = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={"shares": 2000, "purchase_price": "9.0000", "broker_id": str(broker.id), "purchase_date": "2026-04-02"},
    )
    assert add_lot_resp.status_code == 201

    result = await db_session.execute(
        select(DividendTranche).where(DividendTranche.id == UUID(dividend_resp.json()["id"]))
    )
    reloaded_tranche = result.scalar_one()
    assert str(reloaded_tranche.total_amount) == "1000.00"
    assert reloaded_tranche.qualifying_shares == 5000

    position_resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}")
    position_body = position_resp.json()
    assert position_body["total_shares"] == 7000  # position DID grow...
    assert position_body["dividend_tranches"][0]["total_amount"] == "1000.00"  # ...but the dividend did NOT


@pytest.mark.asyncio
async def test_ec015_editing_lot_shares_does_not_change_existing_dividend_total_amount(client, seeded_broker, db_session):
    """The EC-015 half of the same invariant, verified via editing a lot's
    share count (BE-2.3's PATCH endpoint) rather than adding a new one.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker, shares=5000, purchase_price="8.3800")
    lot = position["lots"][0]

    dividend_resp = await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))
    assert dividend_resp.status_code == 201

    edit_resp = await client.patch(
        f"/api/v1/portfolio/positions/{position['id']}/lots/{lot['id']}",
        json={"shares": 8000, "version": 1},
    )
    assert edit_resp.status_code == 200

    result = await db_session.execute(
        select(DividendTranche).where(DividendTranche.id == UUID(dividend_resp.json()["id"]))
    )
    reloaded_tranche = result.scalar_one()
    assert str(reloaded_tranche.total_amount) == "1000.00"
    assert reloaded_tranche.qualifying_shares == 5000


@pytest.mark.asyncio
async def test_delete_position_cascades_to_dividend_tranches(client, seeded_broker, db_session):
    """BE-2.4's Implementation Record flagged this cascade extension as
    pending until DividendTranche existed — now that BE-3.1 has landed it,
    verify the cascade actually covers it.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    dividend_resp = await client.post("/api/v1/portfolio/dividends", json=_dividend_body(position["id"]))
    tranche_id = dividend_resp.json()["id"]

    resp = await client.delete(f"/api/v1/portfolio/positions/{position['id']}")
    assert resp.status_code == 204

    result = await db_session.execute(select(DividendTranche).where(DividendTranche.id == UUID(tranche_id)))
    reloaded_tranche = result.scalar_one()
    assert reloaded_tranche.is_deleted is True
    assert reloaded_tranche.deleted_at is not None
