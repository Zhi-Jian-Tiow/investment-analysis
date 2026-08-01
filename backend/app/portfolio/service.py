"""Portfolio-domain service functions. Other modules (e.g. auth) call into this
module rather than querying portfolio tables directly (architecture P-008 — no
cross-module database joins; access goes through service-layer interfaces).

BE-1.1 needs broker lookup + portfolio creation at registration. FE-1.1 needs
list_brokers to populate the registration form's broker dropdown (see
app.auth.dependencies.get_current_user_optional for why this is reachable
pre-login). BE-2.1 adds position/lot creation. BE-3.1 adds dividend tranche
logging; BE-3.2 adds editing/deleting a tranche; BE-3.3 adds the calendar
aggregation read.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, NamedTuple

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import record_audit_event
from app.errors import last_lot_cannot_be_deleted, not_found, validation_error, version_conflict
from app.portfolio.calculator import calculate_lot_fees, is_non_trading_day, round_myr
from app.portfolio.models import BrokerConfig, DividendTranche, Lot, Portfolio, Position
from app.portfolio.schemas import (
    CreateDividendRequest,
    CreateLotRequest,
    CreatePositionRequest,
    UpdateDividendRequest,
    UpdateLotRequest,
    UpdatePositionRequest,
)


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


async def delete_lot(
    db: AsyncSession, user_id: uuid.UUID, portfolio_id: uuid.UUID, position_id: uuid.UUID, lot_id: uuid.UUID
) -> None:
    """Backfills DELETE /api/v1/portfolio/positions/{id}/lots/{lot_id} — fully
    documented in 03-openapi-specification.md (x-audit-event: LOT_DELETED)
    since the API design phase but never claimed by a user story in Epic 2.
    Implemented now as a deliberate small scope addition alongside BE-2.4
    (Delete Position), since the delete/soft-delete machinery was already
    being built. Soft-deletes a single Lot; position aggregates are
    recomputed at query time, so no further update is needed for them to
    reflect the deletion (architecture ADR-004, same as add/edit lot).

    Blocks deleting a position's last remaining active lot (own judgment
    call, not spec-mandated — see errors.last_lot_cannot_be_deleted) since a
    zero-lot Position is a degenerate state with no other story defining
    what it should mean; the caller should delete the Position instead.
    """
    await get_owned_active_position(db, portfolio_id, position_id)
    lot = await get_owned_lot(db, position_id, lot_id)

    active_lots = await get_position_lots(db, position_id)
    if len(active_lots) <= 1:
        raise last_lot_cannot_be_deleted()

    lot.is_deleted = True
    lot.deleted_at = datetime.now(timezone.utc)

    await record_audit_event(
        db,
        user_id=user_id,
        action="LOT_DELETED",
        entity_type="Lot",
        entity_id=lot.id,
        metadata={"position_id": str(position_id), "shares": lot.shares, "all_in_cost": str(lot.all_in_cost)},
    )

    await db.commit()


async def delete_position(db: AsyncSession, user_id: uuid.UUID, portfolio_id: uuid.UUID, position_id: uuid.UUID) -> None:
    """BE-2.4: soft-deletes a Position and cascades to all its active Lots
    and DividendTranches (BE-3.1 extends the cascade to the latter, as
    flagged in BE-2.4's own Implementation Record) in a single transaction.
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
    await db.execute(
        update(DividendTranche)
        .where(DividendTranche.position_id == position.id, DividendTranche.is_deleted.is_(False))
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


async def get_position_dividend_tranches(db: AsyncSession, position_id: uuid.UUID) -> list[DividendTranche]:
    result = await db.execute(
        select(DividendTranche)
        .where(DividendTranche.position_id == position_id, DividendTranche.is_deleted.is_(False))
        .order_by(DividendTranche.payment_date, DividendTranche.created_at)
    )
    return list(result.scalars().all())


def position_dividend_income_ytd(tranches: list[DividendTranche]) -> Decimal:
    """BR-012: position_total_dividend_income = SUM(total_amount) across
    non-deleted tranches where year = current calendar year. Uses each
    tranche's own stored `year` (set from payment_date at logging time,
    BE-3.1) — never re-derived from `date.today()` at read time, so a
    tranche logged for a prior year never silently drops out of "YTD" mid-way
    through re-reads within the same year it was logged (it simply never
    counted as YTD once that year ends, by design).
    """
    current_year = date.today().year
    return sum(
        (t.total_amount for t in tranches if t.year == current_year),
        Decimal("0.00"),
    )


def _check_qualifying_shares_bound(qualifying_shares: int, position_total_shares: int) -> None:
    # VR-011 — shared by create (BE-3.1) and edit (BE-3.2, the "on edit" clause).
    if qualifying_shares > position_total_shares:
        raise validation_error(
            "One or more fields failed validation.",
            fields=[
                {
                    "field": "qualifying_shares",
                    "constraint": f"Qualifying shares cannot exceed the position's current total shares ({position_total_shares:,})",
                    "received": str(qualifying_shares),
                }
            ],
        )


def _check_tranche_year_constraints(
    tranches_for_year: list[DividendTranche], year: int, tranche_label: str, stock_name: str
) -> None:
    """BR-014 (max 8 per year) and the duplicate-label rule (not spec-mandated
    — see create_dividend_tranche's docstring). Shared by create and edit;
    callers must pre-filter `tranches_for_year` to exclude the tranche being
    edited itself.
    """
    if len(tranches_for_year) >= 8:
        raise validation_error(
            f"Maximum of 8 dividend tranches per year reached for {stock_name} ({year}).",
            fields=[{"field": "tranche_label", "constraint": "maximum of 8 tranches per year", "received": None}],
        )

    if any(t.tranche_label == tranche_label for t in tranches_for_year):
        raise validation_error(
            "One or more fields failed validation.",
            fields=[
                {
                    "field": "tranche_label",
                    "constraint": f"A {tranche_label} tranche already exists for {year}",
                    "received": tranche_label,
                }
            ],
        )


async def create_dividend_tranche(
    db: AsyncSession, user_id: uuid.UUID, portfolio_id: uuid.UUID, data: CreateDividendRequest
) -> DividendTranche:
    """BE-3.1 — P0 CRITICAL. Implements BR-009/BR-027: total_amount is
    computed ONCE here, from the request's own qualifying_shares (which
    defaults client-side to the position's current total shares, but is
    user-overridable), and stored. It is never recomputed from a future
    position_total_shares — that is the entire point of this story.
    """
    position = await get_owned_active_position(db, portfolio_id, data.position_id)

    year = data.payment_date.year

    lots = await get_position_lots(db, position.id)
    position_total_shares, _, _ = position_aggregates(lots)
    _check_qualifying_shares_bound(data.qualifying_shares, position_total_shares)

    existing_tranches = await get_position_dividend_tranches(db, position.id)
    tranches_for_year = [t for t in existing_tranches if t.year == year]
    _check_tranche_year_constraints(tranches_for_year, year, data.tranche_label, position.stock_name)

    total_amount = round_myr(data.per_share_amount * data.qualifying_shares)

    tranche = DividendTranche(
        position_id=position.id,
        tranche_label=data.tranche_label,
        per_share_amount=data.per_share_amount,
        qualifying_shares=data.qualifying_shares,
        total_amount=total_amount,
        year=year,
        payment_date=data.payment_date,
        ex_dividend_date=data.ex_dividend_date,
    )
    db.add(tranche)
    await db.flush()

    metadata: dict[str, Any] = {
        "position_id": str(position.id),
        "tranche_label": data.tranche_label,
        "per_share_amount": str(data.per_share_amount),
        "qualifying_shares": data.qualifying_shares,
        "total_amount": str(total_amount),
    }
    await record_audit_event(
        db, user_id=user_id, action="DIVIDEND_CREATED", entity_type="DividendTranche", entity_id=tranche.id, metadata=metadata
    )

    await db.commit()
    await db.refresh(tranche)
    return tranche


async def get_owned_dividend_tranche(db: AsyncSession, portfolio_id: uuid.UUID, tranche_id: uuid.UUID) -> DividendTranche:
    """Dividends aren't nested under a position_id in the URL (unlike Lots) —
    `PATCH/DELETE /dividends/{id}` only carries the tranche id — so ownership
    is verified by joining through the tranche's own Position to the caller's
    portfolio. Returns 404, never 403, matching every other ownership check
    in this module.
    """
    result = await db.execute(
        select(DividendTranche)
        .join(Position, DividendTranche.position_id == Position.id)
        .where(
            DividendTranche.id == tranche_id,
            DividendTranche.is_deleted.is_(False),
            Position.portfolio_id == portfolio_id,
            Position.is_deleted.is_(False),
        )
    )
    tranche = result.scalar_one_or_none()
    if tranche is None:
        raise not_found()
    return tranche


async def update_dividend_tranche(
    db: AsyncSession, user_id: uuid.UUID, portfolio_id: uuid.UUID, tranche_id: uuid.UUID, data: UpdateDividendRequest
) -> DividendTranche:
    """BE-3.2 — BAS US-012. total_amount is always recomputed from the
    resulting per_share_amount x qualifying_shares (whichever changed, using
    the tranche's own previously-stored value for whichever didn't) — never
    from the current position_total_shares (that's still BR-009/BR-027's
    invariant; only an explicit edit like this one may change total_amount).
    """
    tranche = await get_owned_dividend_tranche(db, portfolio_id, tranche_id)

    new_per_share_amount = data.per_share_amount if data.per_share_amount is not None else tranche.per_share_amount
    new_qualifying_shares = (
        data.qualifying_shares if data.qualifying_shares is not None else tranche.qualifying_shares
    )
    new_tranche_label = data.tranche_label if data.tranche_label is not None else tranche.tranche_label
    new_payment_date = data.payment_date if data.payment_date is not None else tranche.payment_date
    new_ex_dividend_date = data.ex_dividend_date if data.ex_dividend_date is not None else tranche.ex_dividend_date
    new_year = new_payment_date.year

    if new_ex_dividend_date is not None and new_ex_dividend_date > new_payment_date:
        # VR-010, re-validated against the merged (existing + override) dates.
        raise validation_error(
            "One or more fields failed validation.",
            fields=[
                {
                    "field": "ex_dividend_date",
                    "constraint": "Ex-dividend date must be before or on the payment date",
                    "received": new_ex_dividend_date.isoformat(),
                }
            ],
        )

    position = await get_owned_active_position(db, portfolio_id, tranche.position_id)
    lots = await get_position_lots(db, position.id)
    position_total_shares, _, _ = position_aggregates(lots)
    _check_qualifying_shares_bound(new_qualifying_shares, position_total_shares)

    existing_tranches = await get_position_dividend_tranches(db, position.id)
    tranches_for_year = [t for t in existing_tranches if t.year == new_year and t.id != tranche.id]
    _check_tranche_year_constraints(tranches_for_year, new_year, new_tranche_label, position.stock_name)

    previous_values = {
        "tranche_label": tranche.tranche_label,
        "per_share_amount": str(tranche.per_share_amount),
        "qualifying_shares": tranche.qualifying_shares,
        "payment_date": tranche.payment_date.isoformat(),
        "ex_dividend_date": tranche.ex_dividend_date.isoformat() if tranche.ex_dividend_date else None,
        "year": tranche.year,
        "total_amount": str(tranche.total_amount),
    }

    new_total_amount = round_myr(new_per_share_amount * new_qualifying_shares)

    result = await db.execute(
        update(DividendTranche)
        .where(DividendTranche.id == tranche_id, DividendTranche.version == data.version)
        .values(
            tranche_label=new_tranche_label,
            per_share_amount=new_per_share_amount,
            qualifying_shares=new_qualifying_shares,
            payment_date=new_payment_date,
            ex_dividend_date=new_ex_dividend_date,
            year=new_year,
            total_amount=new_total_amount,
            version=DividendTranche.version + 1,
        )
    )
    if result.rowcount == 0:
        await db.rollback()
        raise version_conflict()

    new_values = {
        "tranche_label": new_tranche_label,
        "per_share_amount": str(new_per_share_amount),
        "qualifying_shares": new_qualifying_shares,
        "payment_date": new_payment_date.isoformat(),
        "ex_dividend_date": new_ex_dividend_date.isoformat() if new_ex_dividend_date else None,
        "year": new_year,
        "total_amount": str(new_total_amount),
    }
    await record_audit_event(
        db,
        user_id=user_id,
        action="DIVIDEND_UPDATED",
        entity_type="DividendTranche",
        entity_id=tranche.id,
        metadata={"previous_values": previous_values, "new_values": new_values},
    )

    await db.commit()
    await db.refresh(tranche)
    return tranche


async def delete_dividend_tranche(db: AsyncSession, user_id: uuid.UUID, portfolio_id: uuid.UUID, tranche_id: uuid.UUID) -> None:
    """BE-3.2: soft-delete only (A-010). Position/portfolio dividend-income
    YTD naturally excludes it afterward since position_dividend_income_ytd
    already sums non-deleted tranches only.
    """
    tranche = await get_owned_dividend_tranche(db, portfolio_id, tranche_id)

    tranche.is_deleted = True
    tranche.deleted_at = datetime.now(timezone.utc)

    await record_audit_event(
        db,
        user_id=user_id,
        action="DIVIDEND_DELETED",
        entity_type="DividendTranche",
        entity_id=tranche.id,
        metadata={"position_id": str(tranche.position_id), "total_amount": str(tranche.total_amount)},
    )

    await db.commit()


class DividendCalendarRow(NamedTuple):
    tranche: DividendTranche
    stock_code: str
    stock_name: str
    is_paid: bool
    is_upcoming: bool


async def get_dividend_calendar(db: AsyncSession, portfolio_id: uuid.UUID, year: int) -> list[DividendCalendarRow]:
    """BE-3.3. Scoped by calendar `year` (OpenAPI's documented query param,
    defaulting to the current year) — not the AC's "future dates plus the
    trailing 30 days" framing, which reads as describing FE-3.3's eventual
    default *view* of this data (a year's worth of entries is a superset a
    frontend can filter further) rather than a distinct backend query
    contract. See BE-3.3's Implementation Record for the full reasoning.

    Excludes tranches on soft-deleted positions too, not just soft-deleted
    tranches — a position's own soft-delete already cascades to its tranches
    (BE-2.4, extended in BE-3.1), so this filter is largely redundant with
    that in practice, but explicit here for defense in depth.
    """
    result = await db.execute(
        select(DividendTranche, Position.stock_code, Position.stock_name)
        .join(Position, DividendTranche.position_id == Position.id)
        .where(
            Position.portfolio_id == portfolio_id,
            Position.is_deleted.is_(False),
            DividendTranche.is_deleted.is_(False),
            DividendTranche.year == year,
        )
    )
    rows = result.all()

    today = date.today()
    entries = [
        DividendCalendarRow(
            tranche=tranche,
            stock_code=stock_code,
            stock_name=stock_name,
            is_paid=tranche.payment_date < today,
            is_upcoming=today <= (tranche.ex_dividend_date or tranche.payment_date) <= today + timedelta(days=7),
        )
        for tranche, stock_code, stock_name in rows
    ]

    # OpenAPI: "ascending by ex_dividend_date (falling back to payment_date)".
    entries.sort(key=lambda e: e.tranche.ex_dividend_date or e.tranche.payment_date)
    return entries
