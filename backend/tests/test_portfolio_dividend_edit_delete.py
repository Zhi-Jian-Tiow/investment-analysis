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


async def _log_dividend(client, position_id, **overrides):
    body = {
        "position_id": position_id,
        "tranche_label": "1st",
        "per_share_amount": "0.200000",
        "qualifying_shares": 5000,
        "payment_date": "2026-03-15",
        "ex_dividend_date": "2026-02-28",
    }
    body.update(overrides)
    resp = await client.post("/api/v1/portfolio/dividends", json=body)
    assert resp.status_code == 201
    return resp.json()


# ---------- BAS US-012 numeric scenarios ----------


@pytest.mark.asyncio
async def test_edit_per_share_amount_recalculates_using_stored_qualifying_shares(client, seeded_broker, db_session):
    """BAS US-012 scenario 1: 0.20 -> 0.22, stored qualifying_shares=5000
    (not the live position total) -> total_amount = 1100.00."""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker, shares=5000)
    tranche = await _log_dividend(client, position["id"])

    resp = await client.patch(
        f"/api/v1/portfolio/dividends/{tranche['id']}", json={"per_share_amount": "0.220000", "version": 1}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["per_share_amount"] == "0.220000"
    assert body["qualifying_shares"] == 5000
    assert body["total_amount"] == "1100.00"
    assert body["version"] == 2


@pytest.mark.asyncio
async def test_edit_qualifying_shares_recalculates_using_existing_per_share_amount(client, seeded_broker, db_session):
    """BAS US-012 scenario 2: qualifying_shares 5000 -> 3000, existing
    per_share_amount=0.20 -> total_amount = 600.00."""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker, shares=5000)
    tranche = await _log_dividend(client, position["id"])

    resp = await client.patch(
        f"/api/v1/portfolio/dividends/{tranche['id']}", json={"qualifying_shares": 3000, "version": 1}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["qualifying_shares"] == 3000
    assert body["per_share_amount"] == "0.200000"
    assert body["total_amount"] == "600.00"


@pytest.mark.asyncio
async def test_edit_qualifying_shares_exceeding_position_total_rejected_with_exact_copy(client, seeded_broker, db_session):
    """BAS US-012 error scenario: exact required error copy."""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker, shares=5000)
    tranche = await _log_dividend(client, position["id"])

    resp = await client.patch(
        f"/api/v1/portfolio/dividends/{tranche['id']}", json={"qualifying_shares": 6000, "version": 1}
    )

    assert resp.status_code == 422
    body = resp.json()
    field = next(f for f in body["fields"] if f["field"] == "qualifying_shares")
    assert field["constraint"] == "Qualifying shares cannot exceed the position's current total shares (5,000)"


# ---------- Optimistic locking (EX-008) ----------


@pytest.mark.asyncio
async def test_edit_dividend_stale_version_returns_409(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])

    first = await client.patch(
        f"/api/v1/portfolio/dividends/{tranche['id']}", json={"per_share_amount": "0.220000", "version": 1}
    )
    assert first.status_code == 200
    assert first.json()["version"] == 2

    stale = await client.patch(
        f"/api/v1/portfolio/dividends/{tranche['id']}", json={"per_share_amount": "0.250000", "version": 1}
    )

    assert stale.status_code == 409
    body = stale.json()
    assert body["error"] == "version_conflict"

    result = await db_session.execute(select(DividendTranche).where(DividendTranche.id == UUID(tranche["id"])))
    reloaded = result.scalar_one()
    assert str(reloaded.per_share_amount) == "0.220000"
    assert reloaded.version == 2


@pytest.mark.asyncio
async def test_edit_dividend_rejects_empty_body(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])

    resp = await client.patch(f"/api/v1/portfolio/dividends/{tranche['id']}", json={"version": 1})
    assert resp.status_code == 422


# ---------- Ownership ----------


@pytest.mark.asyncio
async def test_edit_dividend_returns_404_for_nonexistent_tranche(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.patch(
        f"/api/v1/portfolio/dividends/{uuid4()}", json={"per_share_amount": "0.220000", "version": 1}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_edit_dividend_returns_404_for_another_users_tranche(client, client_with_cookie, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])

    async with await client_with_cookie({}) as other_client:
        register_resp = await other_client.post(
            "/auth/register",
            json={"email": "someone-else@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
        )
        other_cookie = register_resp.cookies["bursatrack_session"]

    async with await client_with_cookie({"bursatrack_session": other_cookie}) as other_client:
        resp = await other_client.patch(
            f"/api/v1/portfolio/dividends/{tranche['id']}", json={"per_share_amount": "0.220000", "version": 1}
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_edit_dividend_requires_authentication(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])
    await client.post("/auth/logout")

    resp = await client.patch(
        f"/api/v1/portfolio/dividends/{tranche['id']}", json={"per_share_amount": "0.220000", "version": 1}
    )
    assert resp.status_code == 401


# ---------- BR-014 / duplicate-label re-validated on edit ----------


@pytest.mark.asyncio
async def test_edit_dividend_moving_year_revalidates_br014_cap(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    # Fill 2025 with 8 tranches.
    for i, label in enumerate(["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]):
        await _log_dividend(
            client, position["id"], tranche_label=label, payment_date=f"2025-01-{i + 1:02d}", ex_dividend_date=None
        )

    # A 2026 tranche, then try to move it into the full 2025 year via payment_date.
    tranche_2026 = await _log_dividend(client, position["id"], payment_date="2026-01-01", ex_dividend_date=None)

    resp = await client.patch(
        f"/api/v1/portfolio/dividends/{tranche_2026['id']}", json={"payment_date": "2025-06-01", "version": 1}
    )

    assert resp.status_code == 422
    assert "Maximum of 8" in resp.json()["message"]


@pytest.mark.asyncio
async def test_edit_dividend_allows_changing_own_year_without_self_counting(client, seeded_broker, db_session):
    """Moving a tranche's payment_date within the SAME year it's already in
    must not count itself against the 8-per-year cap."""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"], payment_date="2026-03-15")

    resp = await client.patch(
        f"/api/v1/portfolio/dividends/{tranche['id']}", json={"payment_date": "2026-06-01", "version": 1}
    )

    assert resp.status_code == 200
    assert resp.json()["year"] == 2026


@pytest.mark.asyncio
async def test_edit_dividend_tranche_label_rejects_duplicate_in_same_year(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    await _log_dividend(client, position["id"], tranche_label="1st", payment_date="2026-01-01", ex_dividend_date=None)
    second = await _log_dividend(
        client, position["id"], tranche_label="2nd", payment_date="2026-02-01", ex_dividend_date=None
    )

    resp = await client.patch(
        f"/api/v1/portfolio/dividends/{second['id']}", json={"tranche_label": "1st", "version": 1}
    )

    assert resp.status_code == 422
    assert any(f["field"] == "tranche_label" for f in resp.json()["fields"])


@pytest.mark.asyncio
async def test_edit_dividend_ex_dividend_date_after_payment_date_rejected(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"], payment_date="2026-03-15", ex_dividend_date=None)

    resp = await client.patch(
        f"/api/v1/portfolio/dividends/{tranche['id']}", json={"ex_dividend_date": "2026-03-16", "version": 1}
    )
    assert resp.status_code == 422


# ---------- Audit log ----------


@pytest.mark.asyncio
async def test_edit_dividend_writes_dividend_updated_audit_log(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])

    resp = await client.patch(
        f"/api/v1/portfolio/dividends/{tranche['id']}", json={"per_share_amount": "0.220000", "version": 1}
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "DIVIDEND_UPDATED"))
    entries = result.scalars().all()
    assert len(entries) == 1
    assert entries[0].entity_type == "DividendTranche"
    assert entries[0].metadata_["previous_values"]["total_amount"] == "1000.00"
    assert entries[0].metadata_["new_values"]["total_amount"] == "1100.00"


# ---------- Delete ----------


@pytest.mark.asyncio
async def test_delete_dividend_soft_deletes_and_returns_204(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])

    resp = await client.delete(f"/api/v1/portfolio/dividends/{tranche['id']}")

    assert resp.status_code == 204
    assert resp.content == b""

    result = await db_session.execute(select(DividendTranche).where(DividendTranche.id == UUID(tranche["id"])))
    db_tranche = result.scalar_one()
    assert db_tranche.is_deleted is True
    assert db_tranche.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_dividend_excludes_it_from_position_and_dashboard_income(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])

    pre_delete = await client.get(f"/api/v1/portfolio/positions/{position['id']}")
    assert pre_delete.json()["total_dividend_income_ytd"] == "1000.00"

    await client.delete(f"/api/v1/portfolio/dividends/{tranche['id']}")

    post_delete = await client.get(f"/api/v1/portfolio/positions/{position['id']}")
    assert post_delete.json()["total_dividend_income_ytd"] == "0.00"
    assert post_delete.json()["dividend_tranches"] == []

    dashboard = await client.get("/api/v1/portfolio/dashboard")
    assert dashboard.json()["total_dividend_income_ytd"] == "0.00"


@pytest.mark.asyncio
async def test_delete_dividend_returns_404_for_nonexistent_tranche(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.delete(f"/api/v1/portfolio/dividends/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_dividend_returns_404_for_another_users_tranche(client, client_with_cookie, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])

    async with await client_with_cookie({}) as other_client:
        register_resp = await other_client.post(
            "/auth/register",
            json={"email": "someone-else@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
        )
        other_cookie = register_resp.cookies["bursatrack_session"]

    async with await client_with_cookie({"bursatrack_session": other_cookie}) as other_client:
        resp = await other_client.delete(f"/api/v1/portfolio/dividends/{tranche['id']}")
    assert resp.status_code == 404

    result = await db_session.execute(select(DividendTranche).where(DividendTranche.id == UUID(tranche["id"])))
    assert result.scalar_one().is_deleted is False


@pytest.mark.asyncio
async def test_delete_dividend_requires_authentication(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])
    await client.post("/auth/logout")

    resp = await client.delete(f"/api/v1/portfolio/dividends/{tranche['id']}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_dividend_writes_dividend_deleted_audit_log(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])

    resp = await client.delete(f"/api/v1/portfolio/dividends/{tranche['id']}")
    assert resp.status_code == 204

    result = await db_session.execute(select(AuditLog).where(AuditLog.action == "DIVIDEND_DELETED"))
    entries = result.scalars().all()
    assert len(entries) == 1
    assert str(entries[0].entity_id) == tranche["id"]
