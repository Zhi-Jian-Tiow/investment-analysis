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


@pytest.mark.asyncio
async def test_dashboard_empty_portfolio(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.get("/api/v1/portfolio/dashboard")

    assert resp.status_code == 200
    body = resp.json()
    assert body["positions"] == []
    assert body["total_all_in_cost"] == "0.00"
    assert body["total_dividend_income_ytd"] == "0.00"
    assert body["last_price_refresh_at"] is None


@pytest.mark.asyncio
async def test_dashboard_lists_active_positions_with_aggregates(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)

    await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB",
            "shares": 5000,
            "purchase_price": "8.3800",
            "broker_id": str(broker.id),
            "purchase_date": "2026-01-15",
        },
    )
    await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1155",
            "stock_name": "MAYBANK",
            "shares": 1000,
            "purchase_price": "9.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-02-01",
        },
    )

    resp = await client.get("/api/v1/portfolio/dashboard")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["positions"]) == 2
    codes = {p["stock_code"] for p in body["positions"]}
    assert codes == {"1023", "1155"}
    cimb = next(p for p in body["positions"] if p["stock_code"] == "1023")
    assert cimb["total_shares"] == 5000
    assert cimb["total_all_in_cost"] == "41996.47"
    assert body["total_all_in_cost"] == "51017.17"  # 41996.47 + 9020.70


@pytest.mark.asyncio
async def test_dashboard_excludes_soft_deleted_positions(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)

    created = await client.post(
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
    position_id = created.json()["id"]
    await client.delete(f"/api/v1/portfolio/positions/{position_id}")

    resp = await client.get("/api/v1/portfolio/dashboard")

    assert resp.status_code == 200
    assert resp.json()["positions"] == []


@pytest.mark.asyncio
async def test_dashboard_requires_authentication(client):
    resp = await client.get("/api/v1/portfolio/dashboard")
    assert resp.status_code == 401
