"""Portfolio-domain service functions. Other modules (e.g. auth) call into this
module rather than querying portfolio tables directly (architecture P-008 — no
cross-module database joins; access goes through service-layer interfaces).

BE-1.1 needs broker lookup + portfolio creation at registration. FE-1.1 needs
list_brokers to populate the registration form's broker dropdown (see
app.auth.dependencies.get_current_user_optional for why this is reachable
pre-login). BE-2.1 adds position/lot creation. DividendTranche CRUD belongs to
Epic 3 (BE-3.x) — not implemented yet.
"""

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import record_audit_event
from app.errors import validation_error
from app.portfolio.calculator import calculate_lot_fees, is_non_trading_day
from app.portfolio.models import BrokerConfig, Lot, Portfolio, Position
from app.portfolio.schemas import CreatePositionRequest


async def get_broker(db: AsyncSession, broker_id: uuid.UUID) -> BrokerConfig | None:
    """VR-007: broker_id must reference an existing BrokerConfig.

    Note: the BAS's Entity 8 description mentions an `is_active` flag for hiding
    retired brokers from new dropdowns, but the physical schema (Stage 3, the
    authoritative downstream artifact) has no such column on broker_configs —
    only `is_system`. This function therefore checks existence only.
    """
    result = await db.execute(select(BrokerConfig).where(BrokerConfig.id == broker_id))
    return result.scalar_one_or_none()


async def get_portfolio_for_user(db: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    """Every user has exactly one Portfolio, created at registration
    (portfolios_user_unique, BE-1.1) — this always resolves for an
    authenticated user.
    """
    result = await db.execute(select(Portfolio).where(Portfolio.user_id == user_id))
    portfolio = result.scalar_one_or_none()
    assert portfolio is not None, "every user must have a portfolio (created at registration)"
    return portfolio


async def create_portfolio(db: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    """FR-001 step 6: every new User gets exactly one empty Portfolio
    (portfolios_user_unique enforces one-per-user at V1, per BAS Entity 2).
    """
    portfolio = Portfolio(user_id=user_id)
    db.add(portfolio)
    await db.flush()
    return portfolio


async def list_brokers(db: AsyncSession, user_id: uuid.UUID | None) -> list[BrokerConfig]:
    """System broker configs, always — plus the caller's own custom configs
    when authenticated. `user_id=None` (the pre-login/registration case)
    returns system brokers only.
    """
    conditions = [BrokerConfig.is_system.is_(True)]
    if user_id is not None:
        conditions.append(BrokerConfig.created_by_user_id == user_id)

    result = await db.execute(select(BrokerConfig).where(or_(*conditions)).order_by(BrokerConfig.name))
    return list(result.scalars().all())


async def get_active_position_by_stock(
    db: AsyncSession, portfolio_id: uuid.UUID, stock_code: str
) -> Position | None:
    """EC-001: an active (non-deleted) position for this stock code already
    existing in the portfolio redirects Add Position into an Add Lot.
    """
    result = await db.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id,
            Position.stock_code == stock_code,
            Position.is_deleted.is_(False),
        )
    )
    return result.scalar_one_or_none()


async def get_position_lots(db: AsyncSession, position_id: uuid.UUID) -> list[Lot]:
    result = await db.execute(
        select(Lot)
        .where(Lot.position_id == position_id, Lot.is_deleted.is_(False))
        .order_by(Lot.purchase_date, Lot.created_at)
    )
    return list(result.scalars().all())


def position_aggregates(lots: list[Lot]) -> tuple[int, Decimal, Decimal]:
    """BR-010 (total_shares) / BR-011 (total_all_in_cost), plus the blended
    purchase price derived from them. Computed at query time, never stored
    redundantly on the Position row (architecture ADR-004).
    """
    total_shares = sum((lot.shares for lot in lots), 0)
    total_all_in_cost = sum((lot.all_in_cost for lot in lots), Decimal("0.00"))
    total_initial_amount = sum((lot.initial_amount for lot in lots), Decimal("0.00"))
    # Price-per-share precision (4dp, BR-026), not the 2dp monetary-amount
    # convention (BR-025) — matches purchase_price's own NUMERIC(12,4) column.
    blended_purchase_price = (
        (total_initial_amount / total_shares).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if total_shares
        else Decimal("0.0000")
    )
    return total_shares, total_all_in_cost, blended_purchase_price


async def create_position(
    db: AsyncSession, user_id: uuid.UUID, portfolio_id: uuid.UUID, data: CreatePositionRequest
) -> tuple[Position, list[Lot], list[str]]:
    """BE-2.1: creates a new Position + its first Lot, or — per EC-001 — adds
    a Lot to an already-existing active position for the same stock code
    instead of creating a duplicate Position.
    """
    broker = await get_broker(db, data.broker_id)
    if broker is None:
        raise validation_error(
            "One or more fields failed validation.",
            fields=[{"field": "broker_id", "constraint": "must reference an existing broker", "received": None}],
        )

    fees = calculate_lot_fees(data.shares, data.purchase_price, broker)

    warnings: list[str] = []
    if is_non_trading_day(data.purchase_date):
        warnings.append(
            f"Note: {data.purchase_date.isoformat()} is not a Bursa trading day. "
            "Please verify the purchase date."
        )

    existing_position = await get_active_position_by_stock(db, portfolio_id, data.stock_code)

    if existing_position is not None:
        position = existing_position
        warnings.append(
            f"You already have a {position.stock_name} position. "
            "This lot has been added to your existing position."
        )
    else:
        position = Position(
            portfolio_id=portfolio_id,
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            category_tag=data.category_tag,
        )
        db.add(position)
        await db.flush()

    lot = Lot(
        position_id=position.id,
        shares=data.shares,
        purchase_price=data.purchase_price,
        initial_amount=fees.initial_amount,
        brokerage_fee=fees.brokerage_fee,
        clearing_fee=fees.clearing_fee,
        stamp_duty=fees.stamp_duty,
        all_in_cost=fees.all_in_cost,
        purchase_date=data.purchase_date,
        broker_config_id=broker.id,
    )
    db.add(lot)
    await db.flush()

    metadata: dict[str, Any] = {
        "stock_code": position.stock_code,
        "shares": data.shares,
        "purchase_price": str(data.purchase_price),
        "all_in_cost": str(fees.all_in_cost),
    }
    await record_audit_event(
        db, user_id=user_id, action="LOT_CREATED", entity_type="Lot", entity_id=lot.id, metadata=metadata
    )

    await db.commit()

    lots = await get_position_lots(db, position.id)
    return position, lots, warnings
