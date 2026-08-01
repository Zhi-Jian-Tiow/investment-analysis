from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.portfolio.models import BrokerConfig, DividendTranche, Lot, Portfolio, Position


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


async def _portfolio_id(db_session, register_resp):
    user_id = UUID(register_resp.json()["user"]["id"])
    result = await db_session.execute(select(Portfolio).where(Portfolio.user_id == user_id))
    return result.scalar_one().id


def _seed_position(portfolio_id, stock_code, broker_id, *, lots=2, tranches=2):
    """Directly constructs a Position with `lots` Lots and `tranches`
    DividendTranches (bypassing the API and its rate limiter — this is a
    fixture builder for BE-4.1's own batched-query correctness test, not a
    test of validation/fee logic, which is already covered elsewhere).
    Returns (position, lot_rows, tranche_rows, expected_all_in_cost, expected_income_ytd).
    """
    position = Position(id=uuid4(), portfolio_id=portfolio_id, stock_code=stock_code, stock_name=f"Stock {stock_code}")
    all_in_cost = Decimal("0.00")
    lot_rows = []
    for i in range(lots):
        cost = Decimal("1010.00") + i
        lot_rows.append(
            Lot(
                id=uuid4(),
                position_id=position.id,
                shares=1000,
                purchase_price=Decimal("1.0000"),
                initial_amount=Decimal("1000.00"),
                brokerage_fee=Decimal("8.00"),
                clearing_fee=Decimal("0.30"),
                stamp_duty=Decimal("2.00") + i,
                all_in_cost=cost,
                purchase_date=date(2026, 1, 15),
                broker_config_id=broker_id,
            )
        )
        all_in_cost += cost

    income_ytd = Decimal("0.00")
    labels = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]
    tranche_rows = []
    for i in range(tranches):
        total = Decimal("100.00") + i
        tranche_rows.append(
            DividendTranche(
                id=uuid4(),
                position_id=position.id,
                tranche_label=labels[i],
                per_share_amount=Decimal("0.100000"),
                qualifying_shares=1000,
                total_amount=total,
                year=2026,
                payment_date=date(2026, 3, 1),
            )
        )
        income_ytd += total

    return position, lot_rows, tranche_rows, all_in_cost, income_ytd


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


@pytest.mark.asyncio
async def test_dashboard_never_returns_a_yield_field(client, seeded_broker, db_session):
    """BE-4.1's own AC text lists `dividend_yield` among the per-position
    fields, but the OpenAPI spec's PortfolioResponse description is explicit
    that yield is "intentionally absent" and always computed client-side
    (P0-API-001/FC-002) — the same architecture call already made for
    FE-3.1's per-position yield. Confirms the server never leaks one, under
    either key name a client might expect.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    created = await client.post(
        "/api/v1/portfolio/positions",
        json={
            "stock_code": "1023",
            "stock_name": "CIMB",
            "shares": 5000,
            "purchase_price": "8.3800",
            "broker_id": str(
                broker.id),
            "purchase_date": "2026-01-15",
        },
    )
    position_id = created.json()["id"]
    await client.post(
        "/api/v1/portfolio/dividends",
        json={
            "position_id": position_id,
            "tranche_label": "1st",
            "per_share_amount": "0.200000",
            "qualifying_shares": 5000,
            "payment_date": "2026-03-15",
            "ex_dividend_date": "2026-02-28",
        },
    )

    resp = await client.get("/api/v1/portfolio/dashboard")

    body = resp.json()
    assert "dividend_yield" not in body
    assert "dividend_yield" not in body["positions"][0]
    assert "yield" not in body["positions"][0]


@pytest.mark.asyncio
async def test_dashboard_price_fields_null_until_price_feed_epic(client, seeded_broker, db_session):
    """EC-005: no price has ever been retrieved (Epic 5 doesn't exist yet),
    so market value/P&L must render as null, never RM0.00 or a computed
    zero."""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    await client.post(
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

    resp = await client.get("/api/v1/portfolio/dashboard")

    body = resp.json()
    assert body["last_price_refresh_at"] is None
    position = body["positions"][0]
    assert position["current_price"] is None
    assert position["price_source"] is None
    assert position["price_last_refreshed_at"] is None
    assert position["current_market_value"] is None
    assert position["unrealised_pnl"] is None


@pytest.mark.asyncio
async def test_dashboard_aggregates_dividend_income_across_positions(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position_a = await client.post(
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
    position_b = await client.post(
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
    await client.post(
        "/api/v1/portfolio/dividends",
        json={
            "position_id": position_a.json()["id"],
            "tranche_label": "1st",
            "per_share_amount": "0.200000",
            "qualifying_shares": 5000,
            "payment_date": "2026-03-15",
            "ex_dividend_date": "2026-02-28",
        },
    )
    await client.post(
        "/api/v1/portfolio/dividends",
        json={
            "position_id": position_b.json()["id"],
            "tranche_label": "1st",
            "per_share_amount": "0.150000",
            "qualifying_shares": 1000,
            "payment_date": "2026-03-15",
            "ex_dividend_date": "2026-02-28",
        },
    )

    resp = await client.get("/api/v1/portfolio/dashboard")

    body = resp.json()
    assert body["total_dividend_income_ytd"] == "1150.00"  # 1000.00 + 150.00
    cimb = next(p for p in body["positions"] if p["stock_code"] == "1023")
    maybank = next(p for p in body["positions"] if p["stock_code"] == "1155")
    assert cimb["total_dividend_income_ytd"] == "1000.00"
    assert maybank["total_dividend_income_ytd"] == "150.00"


@pytest.mark.asyncio
async def test_dashboard_excludes_soft_deleted_lots_from_aggregates(client, seeded_broker, db_session):
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
    position = created.json()
    second_lot = await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={
            "shares": 200,
            "purchase_price": "1.0000",
            "broker_id": str(broker.id),
            "purchase_date": "2026-02-01",
        },
    )
    await client.delete(f"/api/v1/portfolio/positions/{position['id']}/lots/{second_lot.json()['id']}")

    resp = await client.get("/api/v1/portfolio/dashboard")

    cimb = next(p for p in resp.json()["positions"] if p["stock_code"] == "1023")
    assert cimb["total_shares"] == 100  # only the surviving lot


@pytest.mark.asyncio
async def test_dashboard_excludes_soft_deleted_dividend_tranches_from_income(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    created = await client.post(
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
    position_id = created.json()["id"]
    tranche = await client.post(
        "/api/v1/portfolio/dividends",
        json={
            "position_id": position_id,
            "tranche_label": "1st",
            "per_share_amount": "0.200000",
            "qualifying_shares": 5000,
            "payment_date": "2026-03-15",
            "ex_dividend_date": "2026-02-28",
        },
    )
    await client.delete(f"/api/v1/portfolio/dividends/{tranche.json()['id']}")

    resp = await client.get("/api/v1/portfolio/dashboard")

    cimb = next(p for p in resp.json()["positions"] if p["stock_code"] == "1023")
    assert cimb["total_dividend_income_ytd"] == "0.00"


@pytest.mark.asyncio
async def test_dashboard_batched_query_correctness_across_many_positions(client, seeded_broker, db_session):
    """Regression test for list_positions_for_dashboard's batched read (the
    N+1 fix): seeds 10 positions x 2 lots x 2 tranches directly via the ORM
    (bypassing the API's rate limiter, which a loop of this size would trip)
    and confirms the grouped-by-position_id aggregation is exactly right —
    no cross-position leakage, no dropped rows. The <3s/50-position NFR
    itself is verified separately via a live smoke test against real
    Postgres (this in-memory SQLite harness can't stand in for that).
    """
    register_resp = await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    portfolio_id = await _portfolio_id(db_session, register_resp)

    expected_total_cost = Decimal("0.00")
    expected_total_income = Decimal("0.00")
    for i in range(10):
        position, lot_rows, tranche_rows, all_in_cost, income_ytd = _seed_position(
            portfolio_id, stock_code=f"{1000 + i}", broker_id=broker.id
        )
        db_session.add(position)
        db_session.add_all(lot_rows)
        db_session.add_all(tranche_rows)
        expected_total_cost += all_in_cost
        expected_total_income += income_ytd
    await db_session.commit()

    resp = await client.get("/api/v1/portfolio/dashboard")

    body = resp.json()
    assert len(body["positions"]) == 10
    assert Decimal(body["total_all_in_cost"]) == expected_total_cost
    assert Decimal(body["total_dividend_income_ytd"]) == expected_total_income
    # Each position's own aggregate reflects only its own rows, not another's.
    for position in body["positions"]:
        assert Decimal(position["total_all_in_cost"]) == Decimal("2021.00")
        assert Decimal(position["total_dividend_income_ytd"]) == Decimal("201.00")
