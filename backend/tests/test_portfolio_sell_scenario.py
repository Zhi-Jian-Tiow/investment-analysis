from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import update

from app.portfolio.models import BrokerConfig, Lot


async def _register(client, seeded_broker):
    resp = await client.post(
        "/auth/register",
        json={"email": "ahmad@email.com", "password": "Invest2026", "broker_id": str(seeded_broker.id)},
    )
    assert resp.status_code == 201
    return resp


async def _percentage_broker(db_session, name="Maybank Investment", rate="0.001", minimum_fee="8.00") -> BrokerConfig:
    broker = BrokerConfig(
        id=uuid4(), name=name, fee_type="percentage", rate=rate, minimum_fee=minimum_fee, is_system=True
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


@pytest.mark.asyncio
async def test_sell_scenario_matches_bas_us015_worked_example(client, seeded_broker, db_session):
    """BAS US-015/016: CIMB 5,000 shares, all-in cost RM41,996.47, Maybank
    (0.10%, min RM8). At RM8.42: gross=42100.00, brokerage=42.10,
    clearing=12.63, stamp=43.00, net~=42002.27, P/L~=+5.80, break-even.
    """
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)
    assert position["total_all_in_cost"] == "41996.47"

    resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}/sell-scenario")

    assert resp.status_code == 200
    body = resp.json()
    assert body["position_id"] == position["id"]
    assert body["shares_to_sell"] == 5000
    assert body["buy_cost_basis"] == "41996.47"
    assert body["broker_id"] == str(broker.id)
    assert body["disclaimer_required"] is True

    row = next(r for r in body["scenarios"] if r["price"] == "8.4200")
    assert row["gross_proceeds"] == "42100.00"
    assert row["projected_brokerage"] == "42.10"
    assert row["projected_clearing_fee"] == "12.63"
    assert row["projected_stamp_duty"] == "43.00"
    assert row["projected_all_in_sell_cost"] == "97.73"
    assert row["projected_net_proceeds"] == "42002.27"
    assert row["profit_loss"] == "5.80"
    assert row["break_even"] is True

    break_even_rows = [r for r in body["scenarios"] if r["break_even"]]
    assert len(break_even_rows) == 1
    assert break_even_rows[0]["price"] == "8.4200"


@pytest.mark.asyncio
async def test_sell_scenario_default_ladder_has_18_rows_ascending(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}/sell-scenario")

    prices = [Decimal(r["price"]) for r in resp.json()["scenarios"]]
    assert len(prices) == 18
    assert prices == sorted(prices)
    # base_price (blended_purchase_price 8.3800) + 0.01 .. +0.05, then +0.10 .. +0.70
    assert prices[0] == Decimal("8.3900")
    assert prices[4] == Decimal("8.4300")
    assert prices[5] == Decimal("8.4800")
    assert prices[-1] == Decimal("9.0800")


@pytest.mark.asyncio
async def test_sell_scenario_partial_sale_proportional_cost_basis(client, seeded_broker, db_session):
    """BR-024: sell 2,000 of 5,000 shares -> (2000/5000) x 41996.47 = 16798.59."""
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}/sell-scenario", params={"shares": 2000})

    assert resp.status_code == 200
    body = resp.json()
    assert body["shares_to_sell"] == 2000
    assert body["buy_cost_basis"] == "16798.59"
    # gross proceeds should reflect 2,000 shares, not the full 5,000
    row = next(r for r in body["scenarios"] if r["price"] == "8.4200")
    assert row["gross_proceeds"] == "16840.00"  # 2000 x 8.42


@pytest.mark.asyncio
async def test_sell_scenario_rejects_shares_above_position_total(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker, shares=1000)

    resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}/sell-scenario", params={"shares": 1001})

    assert resp.status_code == 422
    assert resp.json()["fields"][0]["field"] == "shares"


@pytest.mark.asyncio
async def test_sell_scenario_custom_price_added_to_ladder(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.get(
        f"/api/v1/portfolio/positions/{position['id']}/sell-scenario", params={"price": "10.0000"}
    )

    assert resp.status_code == 200
    prices = [r["price"] for r in resp.json()["scenarios"]]
    assert "10.0000" in prices
    assert len(prices) == 19  # 18 default + 1 custom


@pytest.mark.asyncio
async def test_sell_scenario_rejects_invalid_custom_price(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.get(
        f"/api/v1/portfolio/positions/{position['id']}/sell-scenario", params={"price": "not-a-number"}
    )

    assert resp.status_code == 422
    assert resp.json()["fields"][0]["field"] == "price"


@pytest.mark.asyncio
async def test_sell_scenario_default_broker_is_most_recently_created_active_lot(client, seeded_broker, db_session):
    """A-006: default sell broker is the most recently created active lot's
    broker for multi-lot, multi-broker positions. Explicitly back-dates the
    first lot's created_at (rather than relying on real-clock ordering
    between two API calls) so the test is deterministic regardless of the
    test DB's timestamp resolution — SQLite's CURRENT_TIMESTAMP is
    second-granular and would otherwise tie.
    """
    await _register(client, seeded_broker)
    broker_old = await _percentage_broker(db_session, name="Old Broker", rate="0.001", minimum_fee="8.00")
    broker_new = await _percentage_broker(db_session, name="New Broker", rate="0.005", minimum_fee="10.00")
    position = await _create_position(client, broker_old)
    first_lot_id = position["lots"][0]["id"]

    await db_session.execute(
        update(Lot)
        .where(Lot.id == UUID(first_lot_id))
        .values(created_at=datetime.now(timezone.utc) - timedelta(days=1))
    )
    await db_session.commit()

    await client.post(
        f"/api/v1/portfolio/positions/{position['id']}/lots",
        json={
            "shares": 1000,
            "purchase_price": "8.3800",
            "broker_id": str(broker_new.id),
            "purchase_date": "2020-02-15",
        },
    )

    resp = await client.get(f"/api/v1/portfolio/positions/{position['id']}/sell-scenario")

    assert resp.json()["broker_id"] == str(broker_new.id)


@pytest.mark.asyncio
async def test_sell_scenario_broker_override(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    override_broker = await _percentage_broker(db_session, name="Override Broker", rate="0.02", minimum_fee="20.00")
    position = await _create_position(client, broker)

    resp = await client.get(
        f"/api/v1/portfolio/positions/{position['id']}/sell-scenario",
        params={"broker_id": str(override_broker.id)},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["broker_id"] == str(override_broker.id)
    row = next(r for r in body["scenarios"] if r["price"] == "8.4200")
    # 42100 x 0.02 = 842.00, well above the 20.00 minimum
    assert row["projected_brokerage"] == "842.00"


@pytest.mark.asyncio
async def test_sell_scenario_rejects_nonexistent_broker_override(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    resp = await client.get(
        f"/api/v1/portfolio/positions/{position['id']}/sell-scenario",
        params={"broker_id": str(uuid4())},
    )

    assert resp.status_code == 422
    assert resp.json()["fields"][0]["field"] == "broker_id"


@pytest.mark.asyncio
async def test_sell_scenario_is_not_persisted(client, seeded_broker, db_session):
    await _register(client, seeded_broker)
    broker = await _percentage_broker(db_session)
    position = await _create_position(client, broker)

    await client.get(f"/api/v1/portfolio/positions/{position['id']}/sell-scenario")
    await client.get(f"/api/v1/portfolio/positions/{position['id']}/sell-scenario", params={"shares": 2000})

    after = await client.get(f"/api/v1/portfolio/positions/{position['id']}")
    body = after.json()
    assert len(body["lots"]) == 1  # unchanged
    assert body["total_shares"] == 5000  # unchanged despite the shares=2000 scenario call


@pytest.mark.asyncio
async def test_sell_scenario_returns_404_for_foreign_position(client, client_with_cookie, seeded_broker, db_session):
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
        resp = await other_client.get(f"/api/v1/portfolio/positions/{position['id']}/sell-scenario")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sell_scenario_returns_404_for_missing_position(client, seeded_broker):
    await _register(client, seeded_broker)

    resp = await client.get(f"/api/v1/portfolio/positions/{uuid4()}/sell-scenario")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sell_scenario_requires_authentication(client):
    resp = await client.get(f"/api/v1/portfolio/positions/{uuid4()}/sell-scenario")
    assert resp.status_code == 401
