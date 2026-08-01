from uuid import uuid4

import pytest

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


async def _create_position(client, broker, *, stock_code="1023", stock_name="CIMB GROUP HOLDINGS BHD", shares=5000):
    resp = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": stock_code,
            "stock_name": stock_name,
            "shares": shares,
            "purchase_price": "8.3800",
            "broker_id": str(broker.id),
            "purchase_date": "2020-01-15",
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


@pytest.mark.asyncio
async def test_calendar_empty_state_returns_empty_tranches(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.get("/api/v1/portfolio/dividends")

    assert resp.status_code == 200
    assert resp.json() == {"tranches": []}


@pytest.mark.asyncio
async def test_calendar_requires_authentication(client):
    resp = await client.get("/api/v1/portfolio/dividends")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_calendar_includes_stock_name_and_code(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker, stock_code="1023", stock_name="CIMB")
    await _log_dividend(client, position["id"])

    resp = await client.get("/api/v1/portfolio/dividends")

    assert resp.status_code == 200
    entries = resp.json()["tranches"]
    assert len(entries) == 1
    assert entries[0]["stock_code"] == "1023"
    assert entries[0]["stock_name"] == "CIMB"
    assert entries[0]["total_amount"] == "1000.00"


@pytest.mark.asyncio
async def test_calendar_defaults_to_current_calendar_year(client, seeded_broker, db_session):
    """OpenAPI: `year` query param 'Defaults to the current calendar year if
    omitted.'"""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    await _log_dividend(
        client, position["id"], tranche_label="1st", payment_date="2025-03-15", ex_dividend_date="2025-02-28"
    )
    current_year_entry = await _log_dividend(
        client, position["id"], tranche_label="1st", payment_date="2026-03-15", ex_dividend_date="2026-02-28"
    )

    resp = await client.get("/api/v1/portfolio/dividends")

    assert resp.status_code == 200
    entries = resp.json()["tranches"]
    assert len(entries) == 1
    assert entries[0]["id"] == current_year_entry["id"]
    assert entries[0]["year"] == 2026


@pytest.mark.asyncio
async def test_calendar_year_query_param_filters_explicitly(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche_2025 = await _log_dividend(
        client, position["id"], tranche_label="1st", payment_date="2025-03-15", ex_dividend_date="2025-02-28"
    )
    await _log_dividend(
        client, position["id"], tranche_label="1st", payment_date="2026-03-15", ex_dividend_date="2026-02-28"
    )

    resp = await client.get("/api/v1/portfolio/dividends", params={"year": 2025})

    assert resp.status_code == 200
    entries = resp.json()["tranches"]
    assert len(entries) == 1
    assert entries[0]["id"] == tranche_2025["id"]


@pytest.mark.asyncio
async def test_calendar_ordered_by_ex_dividend_date_falling_back_to_payment_date(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    # Later ex-date, logged first.
    later = await _log_dividend(
        client, position["id"], tranche_label="2nd", payment_date="2026-08-01", ex_dividend_date="2026-07-15"
    )
    # Earlier ex-date, logged second.
    earlier = await _log_dividend(
        client, position["id"], tranche_label="1st", payment_date="2026-03-15", ex_dividend_date="2026-02-28"
    )
    # No ex-date at all -> falls back to payment_date, which sits between the two above.
    no_ex_date = await _log_dividend(
        client, position["id"], tranche_label="3rd", payment_date="2026-05-01", ex_dividend_date=None
    )

    resp = await client.get("/api/v1/portfolio/dividends")

    entries = resp.json()["tranches"]
    assert [e["id"] for e in entries] == [earlier["id"], no_ex_date["id"], later["id"]]


@pytest.mark.asyncio
async def test_calendar_spans_multiple_positions(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position_a = await _create_position(client, broker, stock_code="1023", stock_name="CIMB")
    position_b = await _create_position(client, broker, stock_code="1155", stock_name="MAYBANK")
    await _log_dividend(client, position_a["id"])
    await _log_dividend(client, position_b["id"])

    resp = await client.get("/api/v1/portfolio/dividends")

    entries = resp.json()["tranches"]
    assert len(entries) == 2
    assert {e["stock_code"] for e in entries} == {"1023", "1155"}


@pytest.mark.asyncio
async def test_calendar_excludes_soft_deleted_tranches(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    tranche = await _log_dividend(client, position["id"])

    await client.delete(f"/api/v1/portfolio/dividends/{tranche['id']}")

    resp = await client.get("/api/v1/portfolio/dividends")
    assert resp.json()["tranches"] == []


@pytest.mark.asyncio
async def test_calendar_excludes_tranches_on_soft_deleted_positions(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    await _log_dividend(client, position["id"])

    await client.delete(f"/api/v1/portfolio/positions/{position['id']}")

    resp = await client.get("/api/v1/portfolio/dividends")
    assert resp.json()["tranches"] == []


@pytest.mark.asyncio
async def test_calendar_excludes_another_users_tranches(client, client_with_cookie, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    await _log_dividend(client, position["id"])

    async with await client_with_cookie({}) as other_client:
        register_resp = await other_client.post(
            "/auth/register",
            json={"email": "someone-else@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
        )
        other_cookie = register_resp.cookies["bursatrack_session"]

    async with await client_with_cookie({"bursatrack_session": other_cookie}) as other_client:
        resp = await other_client.get("/api/v1/portfolio/dividends")

    assert resp.status_code == 200
    assert resp.json()["tranches"] == []


@pytest.mark.asyncio
async def test_calendar_is_paid_flag_reflects_past_payment_date(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    # A payment_date safely in the past relative to "today" (2026-08-01 per this session's system clock).
    await _log_dividend(
        client, position["id"], tranche_label="1st", payment_date="2026-01-05", ex_dividend_date="2025-12-20"
    )

    resp = await client.get("/api/v1/portfolio/dividends")

    entries = resp.json()["tranches"]
    assert len(entries) == 1
    assert entries[0]["is_paid"] is True
