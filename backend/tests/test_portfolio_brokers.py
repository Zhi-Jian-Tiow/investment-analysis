import pytest


@pytest.mark.asyncio
async def test_list_brokers_works_without_authentication(client, seeded_broker):
    """FE-1.1: the registration page needs this list before any session
    exists — must not require login."""
    resp = await client.get("/api/v1/brokers")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["brokers"]) == 1
    assert body["brokers"][0]["name"] == "Maybank IB"
    assert body["brokers"][0]["is_system"] is True


@pytest.mark.asyncio
async def test_list_brokers_excludes_other_users_custom_brokers(client, seeded_broker, db_session):
    from uuid import uuid4

    from app.portfolio.models import BrokerConfig

    # A custom broker belonging to someone else must never appear, whether
    # the caller is anonymous or authenticated as a different user.
    other_users_broker = BrokerConfig(
        id=uuid4(),
        name="Someone Else's Custom Broker",
        fee_type="flat",
        flat_fee="5.00",
        is_system=False,
        created_by_user_id=uuid4(),
    )
    db_session.add(other_users_broker)
    await db_session.commit()

    resp = await client.get("/api/v1/brokers")

    assert resp.status_code == 200
    names = [b["name"] for b in resp.json()["brokers"]]
    assert "Someone Else's Custom Broker" not in names
    assert names == ["Maybank IB"]
