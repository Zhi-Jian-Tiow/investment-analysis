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
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import record_audit_event
from app.errors import not_found, validation_error, version_conflict
from app.portfolio.calculator import calculate_lot_fees, is_non_trading_day
from app.portfolio.models import BrokerConfig, Lot, Portfolio, Position
from app.portfolio.schemas import CreateLotRequest, CreatePositionRequest, UpdateLotRequest, UpdatePositionRequest


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


async def list_positions_for_portfolio(db: AsyncSession, portfolio_id: uuid.UUID) -> list[Position]:
    """FE-2.1: backs GET /api/v1/portfolio/dashboard — the only spec-documented
    way to list a user's positions (there is no separate list-positions
    endpoint). Excludes soft-deleted positions.
    """
    result = await db.execute(
        select(Position)
        .where(Position.portfolio_id == portfolio_id, Position.is_deleted.is_(False))
        .order_by(Position.created_at)
    )
    return list(result.scalars().all())


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


async def get_owned_active_position(db: AsyncSession, portfolio_id: uuid.UUID, position_id: uuid.UUID) -> Position:
    """Ownership check returns 404, never 403, whether the position doesn't
    exist, belongs to another user, or has been soft-deleted (BAS §9
    URL-level enforcement; API security review AA-001-009; EC-006 for the
    soft-deleted case).
    """
    result = await db.execute(
        select(Position).where(
            Position.id == position_id,
            Position.portfolio_id == portfolio_id,
            Position.is_deleted.is_(False),
        )
    )
    position = result.scalar_one_or_none()
    if position is None:
        raise not_found()
    return position


def _purchase_date_warnings(purchase_date: date) -> list[str]:
    """EC-004: non-trading-day purchase dates are a soft warning, never a
    block. Shared by every code path that creates a Lot.
    """
    if is_non_trading_day(purchase_date):
        return [f"Note: {purchase_date.isoformat()} is not a Bursa trading day. Please verify the purchase date."]
    return []


async def _insert_lot(
    db: AsyncSession,
    user_id: uuid.UUID,
    position: Position,
    *,
    shares: int,
    purchase_price: Decimal,
    broker: BrokerConfig,
    purchase_date: date,
) -> Lot:
    """Shared by create_position's EC-001 redirect and add_lot_to_position
    (BE-2.2) — the one place a Lot row is ever constructed, so the fee
    engine and audit logging can never drift between the two call sites.
    """
    fees = calculate_lot_fees(shares, purchase_price, broker)
    lot = Lot(
        position_id=position.id,
        shares=shares,
        purchase_price=purchase_price,
        initial_amount=fees.initial_amount,
        brokerage_fee=fees.brokerage_fee,
        clearing_fee=fees.clearing_fee,
        stamp_duty=fees.stamp_duty,
        all_in_cost=fees.all_in_cost,
        purchase_date=purchase_date,
        broker_config_id=broker.id,
    )
    db.add(lot)
    await db.flush()

    metadata: dict[str, Any] = {
        "position_id": str(position.id),
        "shares": shares,
        "purchase_price": str(purchase_price),
        "all_in_cost": str(fees.all_in_cost),
    }
    await record_audit_event(
        db, user_id=user_id, action="LOT_CREATED", entity_type="Lot", entity_id=lot.id, metadata=metadata
    )
    return lot


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

    warnings = _purchase_date_warnings(data.purchase_date)

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
            notes=data.notes,
        )
        db.add(position)
        await db.flush()

    await _insert_lot(
        db,
        user_id,
        position,
        shares=data.shares,
        purchase_price=data.purchase_price,
        broker=broker,
        purchase_date=data.purchase_date,
    )

    await db.commit()

    lots = await get_position_lots(db, position.id)
    return position, lots, warnings


async def add_lot_to_position(
    db: AsyncSession, user_id: uuid.UUID, portfolio_id: uuid.UUID, position_id: uuid.UUID, data: CreateLotRequest
) -> tuple[Lot, list[str]]:
    """BE-2.2: adds a Lot to an already-existing position. Fees are computed
    independently per lot (BR-003); position aggregates (BR-010/BR-011) are
    never stored — they're recomputed at query time by position_aggregates,
    so simply persisting this Lot is sufficient for them to reflect it on
    the next read (architecture ADR-004, HIGH-R-006).
    """
    position = await get_owned_active_position(db, portfolio_id, position_id)

    broker = await get_broker(db, data.broker_id)
    if broker is None:
        raise validation_error(
            "One or more fields failed validation.",
            fields=[{"field": "broker_id", "constraint": "must reference an existing broker", "received": None}],
        )

    warnings = _purchase_date_warnings(data.purchase_date)

    lot = await _insert_lot(
        db,
        user_id,
        position,
        shares=data.shares,
        purchase_price=data.purchase_price,
        broker=broker,
        purchase_date=data.purchase_date,
    )

    await db.commit()
    await db.refresh(lot)
    return lot, warnings


async def get_owned_lot(db: AsyncSession, position_id: uuid.UUID, lot_id: uuid.UUID) -> Lot:
    """Ownership verified on both the position and the lot — `lot.position_id`
    must equal the `{id}` in the path — to prevent cross-position lot access
    even within the same user's own portfolio (03-openapi-specification.md
    PATCH .../lots/{lot_id} description). Returns 404, never 403, matching
    get_owned_active_position's pattern.
    """
    result = await db.execute(
        select(Lot).where(Lot.id == lot_id, Lot.position_id == position_id, Lot.is_deleted.is_(False))
    )
    lot = result.scalar_one_or_none()
    if lot is None:
        raise not_found()
    return lot


async def update_position_metadata(
    db: AsyncSession, user_id: uuid.UUID, portfolio_id: uuid.UUID, position_id: uuid.UUID, data: UpdatePositionRequest
) -> Position:
    """BE-2.3: metadata-only edit (category_tag/notes) — lot financial fields
    are never touched here.
    """
    position = await get_owned_active_position(db, portfolio_id, position_id)

    previous_values = {"category_tag": position.category_tag, "notes": position.notes}

    if data.category_tag is not None:
        position.category_tag = data.category_tag
    if data.notes is not None:
        position.notes = data.notes

    new_values = {"category_tag": position.category_tag, "notes": position.notes}

    await record_audit_event(
        db,
        user_id=user_id,
        action="POSITION_UPDATED",
        entity_type="Position",
        entity_id=position.id,
        metadata={"previous_values": previous_values, "new_values": new_values},
    )

    await db.commit()
    await db.refresh(position)
    return position


async def update_lot(
    db: AsyncSession,
    user_id: uuid.UUID,
    portfolio_id: uuid.UUID,
    position_id: uuid.UUID,
    lot_id: uuid.UUID,
    data: UpdateLotRequest,
) -> tuple[Lot, list[str]]:
    """BE-2.3: edits a Lot's financial fields using optimistic locking on
    `version`. Every field is optional except `version` — unsupplied fields
    keep their current stored value, and all four fee components are always
    recomputed from the resulting shares/purchase_price/broker (never
    accepted directly from the client, P0-API-002).
    """
    await get_owned_active_position(db, portfolio_id, position_id)
    lot = await get_owned_lot(db, position_id, lot_id)

    if data.broker_id is not None:
        broker = await get_broker(db, data.broker_id)
        if broker is None:
            raise validation_error(
                "One or more fields failed validation.",
                fields=[{"field": "broker_id", "constraint": "must reference an existing broker", "received": None}],
            )
    else:
        broker = await get_broker(db, lot.broker_config_id)
        assert broker is not None, "an existing lot must always reference a valid broker"

    new_shares = data.shares if data.shares is not None else lot.shares
    new_purchase_price = data.purchase_price if data.purchase_price is not None else lot.purchase_price
    new_purchase_date = data.purchase_date if data.purchase_date is not None else lot.purchase_date

    previous_values = {
        "shares": lot.shares,
        "purchase_price": str(lot.purchase_price),
        "purchase_date": lot.purchase_date.isoformat(),
        "broker_id": str(lot.broker_config_id),
        "all_in_cost": str(lot.all_in_cost),
    }

    fees = calculate_lot_fees(new_shares, new_purchase_price, broker)

    result = await db.execute(
        update(Lot)
        .where(Lot.id == lot_id, Lot.version == data.version)
        .values(
            shares=new_shares,
            purchase_price=new_purchase_price,
            purchase_date=new_purchase_date,
            broker_config_id=broker.id,
            initial_amount=fees.initial_amount,
            brokerage_fee=fees.brokerage_fee,
            clearing_fee=fees.clearing_fee,
            stamp_duty=fees.stamp_duty,
            all_in_cost=fees.all_in_cost,
            version=Lot.version + 1,
        )
    )
    if result.rowcount == 0:
        await db.rollback()
        raise version_conflict()

    new_values = {
        "shares": new_shares,
        "purchase_price": str(new_purchase_price),
        "purchase_date": new_purchase_date.isoformat(),
        "broker_id": str(broker.id),
        "all_in_cost": str(fees.all_in_cost),
    }
    await record_audit_event(
        db,
        user_id=user_id,
        action="LOT_UPDATED",
        entity_type="Lot",
        entity_id=lot.id,
        metadata={"previous_values": previous_values, "new_values": new_values},
    )

    await db.commit()
    await db.refresh(lot)

    warnings = _purchase_date_warnings(new_purchase_date)
    if data.shares is not None:
        # EC-015: a share-count edit never alters previously stored
        # DividendTranche.total_amount — surfaced as a notice since
        # DividendTranche doesn't exist yet to actually verify against.
        warnings.append("Position updated. Dividend records were not changed.")

    return lot, warnings


async def delete_position(db: AsyncSession, user_id: uuid.UUID, portfolio_id: uuid.UUID, position_id: uuid.UUID) -> None:
    """BE-2.4: soft-deletes a Position and cascades to all its active Lots
    (and, once Epic 3 exists, its DividendTranches) in a single transaction.
    No physical row deletion (A-010) — records remain for audit/PDPA export
    until account-level hard-delete.
    """
    position = await get_owned_active_position(db, portfolio_id, position_id)

    now = datetime.now(timezone.utc)
    position.is_deleted = True
    position.deleted_at = now

    await db.execute(
        update(Lot)
        .where(Lot.position_id == position.id, Lot.is_deleted.is_(False))
        .values(is_deleted=True, deleted_at=now)
    )

    await record_audit_event(
        db,
        user_id=user_id,
        action="POSITION_DELETED",
        entity_type="Position",
        entity_id=position.id,
        metadata={"stock_code": position.stock_code},
    )

    await db.commit()
