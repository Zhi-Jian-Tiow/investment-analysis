from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_user_optional
from app.auth.models import User
from app.database import get_db
from app.errors import validation_error
from app.rate_limit import limiter

from app.portfolio.calculator import compute_market_value_and_pnl
from app.portfolio.models import DividendTranche, Lot, Position
from app.pricing.models import PriceSnapshot
from app.portfolio.schemas import (
    BrokerConfigResponse,
    BrokerListResponse,
    CreateDividendRequest,
    CreateLotRequest,
    CreatePositionRequest,
    DividendCalendarEntry,
    DividendCalendarResponse,
    DividendTrancheResponse,
    LotResponse,
    PortfolioResponse,
    PositionResponse,
    PositionSummaryResponse,
    SellScenarioResponse,
    SellScenarioRowResponse,
    UpdateDividendRequest,
    UpdateLotRequest,
    UpdatePositionRequest,
)
from app.portfolio.service import (
    add_lot_to_position,
    compute_sell_scenario,
    create_dividend_tranche,
    create_position,
    delete_dividend_tranche,
    delete_lot,
    delete_position,
    get_dividend_calendar,
    get_owned_active_position,
    get_portfolio_for_user,
    get_position_dividend_tranches,
    get_position_lots,
    list_brokers,
    list_positions_for_dashboard,
    position_aggregates,
    position_dividend_income_ytd,
    update_dividend_tranche,
    update_lot,
    update_position_metadata,
)
from app.pricing.service import get_latest_prices

# Dashboard/Sell-Calculator routes belong to Epic 4. Position/Lot creation is
# added in BE-2.1/BE-2.2; edit in BE-2.3; delete in BE-2.4; dividend logging
# (this file) in BE-3.1.
router = APIRouter(prefix="/api/v1", tags=["Portfolio"])


def _build_position_response(
    position: Position,
    lots: list[Lot],
    tranches: list[DividendTranche] | None = None,
    warnings: list[str] | None = None,
    price_snapshot: PriceSnapshot | None = None,
) -> PositionResponse:
    """BE-5.2: `price_snapshot` is the position's stock_code's latest
    PriceSnapshot, if any (Epic 5 — always None before BE-5.1 existed).
    `current_market_value`/`unrealised_pnl` are derived from it here, not
    stored anywhere (architecture ADR-004 — computed at read time, same as
    every other position aggregate).
    """
    total_shares, total_all_in_cost, blended_purchase_price = position_aggregates(lots)
    tranches = tranches or []
    current_price = price_snapshot.price if price_snapshot else None
    current_market_value, unrealised_pnl = compute_market_value_and_pnl(total_shares, current_price, total_all_in_cost)
    return PositionResponse(
        id=position.id,
        stock_code=position.stock_code,
        stock_name=position.stock_name,
        category_tag=position.category_tag,
        notes=position.notes,
        total_shares=total_shares,
        total_all_in_cost=total_all_in_cost,
        blended_purchase_price=blended_purchase_price,
        total_dividend_income_ytd=position_dividend_income_ytd(tranches),
        current_price=current_price,
        price_source=price_snapshot.source if price_snapshot else None,
        price_last_refreshed_at=price_snapshot.last_refreshed_at if price_snapshot else None,
        current_market_value=current_market_value,
        unrealised_pnl=unrealised_pnl,
        lots=[LotResponse.model_validate(lot) for lot in lots],
        dividend_tranches=[DividendTrancheResponse.model_validate(t) for t in tranches],
        is_deleted=position.is_deleted,
        created_at=position.created_at,
        updated_at=position.updated_at,
        warnings=warnings or [],
    )


@router.get("/brokers", response_model=BrokerListResponse)
@limiter.limit("60/minute")
async def get_brokers(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> BrokerListResponse:
    brokers = await list_brokers(db, user_id=current_user.id if current_user else None)
    return BrokerListResponse(
        brokers=[BrokerConfigResponse.model_validate(b) for b in brokers]
    )


@router.get("/portfolio/dashboard", response_model=PortfolioResponse)
@limiter.limit("60/minute")
async def get_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """BE-4.1. `dividend_yield` from this story's AC is deliberately not on
    PositionSummaryResponse/PortfolioResponse — the OpenAPI spec's own
    PortfolioResponse description is explicit that yield is "intentionally
    absent" and always computed client-side (P0-API-001/FC-002), and the DB
    schema review (FC-005) confirms no yield column/view exists anywhere.
    Same architecture call already made for FE-3.1's per-position yield. All
    other per-position fields match BAS §7's derived-aggregates table.

    current_price/price_source/price_last_refreshed_at/current_market_value/
    unrealised_pnl (BE-5.2) are real as of Epic 5 — null only for a stock
    that has never had any PriceSnapshot at all (EC-005), not merely because
    the epic didn't exist yet.

    Uses list_positions_for_dashboard's batched read (3 queries total) rather
    than querying lots/tranches once per position — see that function's
    docstring for the NFR reasoning. Prices are batched the same way
    (get_latest_prices, one query for every stock_code on the page).
    """
    portfolio = await get_portfolio_for_user(db, current_user.id)
    rows = await list_positions_for_dashboard(db, portfolio.id)
    prices = await get_latest_prices(db, [position.stock_code for position, _, _ in rows])

    summaries: list[PositionSummaryResponse] = []
    total_all_in_cost = Decimal("0.00")
    total_dividend_income_ytd = Decimal("0.00")
    last_price_refresh_at = None
    for position, lots, tranches in rows:
        total_shares, position_all_in_cost, blended_purchase_price = position_aggregates(lots)
        position_income_ytd = position_dividend_income_ytd(tranches)
        total_all_in_cost += position_all_in_cost
        total_dividend_income_ytd += position_income_ytd

        price_snapshot = prices.get(position.stock_code)
        current_price = price_snapshot.price if price_snapshot else None
        current_market_value, unrealised_pnl = compute_market_value_and_pnl(
            total_shares, current_price, position_all_in_cost
        )
        if price_snapshot and (last_price_refresh_at is None or price_snapshot.last_refreshed_at > last_price_refresh_at):
            last_price_refresh_at = price_snapshot.last_refreshed_at

        summaries.append(
            PositionSummaryResponse(
                id=position.id,
                stock_code=position.stock_code,
                stock_name=position.stock_name,
                category_tag=position.category_tag,
                total_shares=total_shares,
                total_all_in_cost=position_all_in_cost,
                blended_purchase_price=blended_purchase_price,
                total_dividend_income_ytd=position_income_ytd,
                current_price=current_price,
                price_source=price_snapshot.source if price_snapshot else None,
                price_last_refreshed_at=price_snapshot.last_refreshed_at if price_snapshot else None,
                current_market_value=current_market_value,
                unrealised_pnl=unrealised_pnl,
            )
        )

    return PortfolioResponse(
        total_all_in_cost=total_all_in_cost,
        total_dividend_income_ytd=total_dividend_income_ytd,
        last_price_refresh_at=last_price_refresh_at,
        positions=summaries,
    )


async def _latest_price_for(db: AsyncSession, stock_code: str) -> PriceSnapshot | None:
    """Single-position convenience wrapper around get_latest_prices' bulk
    lookup. PriceSnapshot is shared system data (BE-5.2's own Technical
    Constraints) — even a just-created position can already have one, if
    another user holds the same stock_code.
    """
    prices = await get_latest_prices(db, [stock_code])
    return prices.get(stock_code)


@router.post(
    "/portfolio/positions",
    response_model=PositionResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def add_position(
    request: Request,
    body: CreatePositionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PositionResponse:
    portfolio = await get_portfolio_for_user(db, current_user.id)
    position, lots, warnings = await create_position(
        db, current_user.id, portfolio.id, body
    )
    tranches = await get_position_dividend_tranches(db, position.id)
    price_snapshot = await _latest_price_for(db, position.stock_code)

    return _build_position_response(position, lots, tranches, warnings, price_snapshot)


@router.post(
    "/portfolio/positions/{position_id}/lots",
    response_model=LotResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def add_lot(
    request: Request,
    position_id: UUID,
    body: CreateLotRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LotResponse:
    portfolio = await get_portfolio_for_user(db, current_user.id)
    lot, warnings = await add_lot_to_position(
        db, current_user.id, portfolio.id, position_id, body
    )

    response = LotResponse.model_validate(lot)
    response.warnings = warnings
    return response


@router.delete("/portfolio/positions/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_position_endpoint(
    request: Request,
    position_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    portfolio = await get_portfolio_for_user(db, current_user.id)
    await delete_position(db, current_user.id, portfolio.id, position_id)


@router.get("/portfolio/positions/{position_id}", response_model=PositionResponse)
@limiter.limit("60/minute")
async def get_position(
    request: Request,
    position_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PositionResponse:
    """Not part of any Epic 2 BE story's own AC, but flagged as a required
    gap at the end of BE-2.2: FE-2.2's position detail page and its
    SWR-driven aggregate revalidation need somewhere to read a Position's
    current state from, and this reuses BE-2.1's response-building logic
    entirely.
    """
    portfolio = await get_portfolio_for_user(db, current_user.id)
    position = await get_owned_active_position(db, portfolio.id, position_id)
    lots = await get_position_lots(db, position.id)
    tranches = await get_position_dividend_tranches(db, position.id)
    price_snapshot = await _latest_price_for(db, position.stock_code)

    return _build_position_response(position, lots, tranches, price_snapshot=price_snapshot)


def _check_scenario_price(raw: str) -> Decimal:
    """Same VR-005 rule as purchase_price (>0, at most 4dp) — the `price`
    query param uses the identical BR-026 per-share precision convention.
    """
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise validation_error(
            "One or more fields failed validation.",
            fields=[{"field": "price", "constraint": "Price must be a valid decimal number", "received": raw}],
        )
    if value <= 0:
        raise validation_error(
            "One or more fields failed validation.",
            fields=[{"field": "price", "constraint": "Price must be greater than zero", "received": raw}],
        )
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -4:
        raise validation_error(
            "One or more fields failed validation.",
            fields=[{"field": "price", "constraint": "Price can have at most 4 decimal places", "received": raw}],
        )
    return value


@router.get("/portfolio/positions/{position_id}/sell-scenario", response_model=SellScenarioResponse)
@limiter.limit("60/minute")
async def get_sell_scenario(
    request: Request,
    position_id: UUID,
    shares: int | None = Query(None, ge=1),
    price: list[str] | None = Query(None),
    broker_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SellScenarioResponse:
    """BE-4.2. Pure computation, nothing persisted. See compute_sell_scenario
    for the BR-024 partial-sale cost basis and A-006 default-broker logic.
    """
    portfolio = await get_portfolio_for_user(db, current_user.id)
    custom_prices = [_check_scenario_price(raw) for raw in (price or [])]

    result = await compute_sell_scenario(
        db,
        portfolio.id,
        position_id,
        shares_to_sell=shares,
        custom_prices=custom_prices,
        broker_id=broker_id,
    )

    return SellScenarioResponse(
        position_id=result.position.id,
        shares_to_sell=result.shares_to_sell,
        buy_cost_basis=result.buy_cost_basis,
        broker_id=result.broker.id,
        disclaimer_required=True,
        scenarios=[
            SellScenarioRowResponse(
                price=row.price,
                gross_proceeds=row.gross_proceeds,
                projected_brokerage=row.brokerage_fee,
                projected_clearing_fee=row.clearing_fee,
                projected_stamp_duty=row.stamp_duty,
                projected_all_in_sell_cost=row.all_in_sell_cost,
                projected_net_proceeds=row.net_proceeds,
                profit_loss=row.profit_loss,
                break_even=row.break_even,
            )
            for row in result.rows
        ],
    )


@router.patch("/portfolio/positions/{position_id}", response_model=PositionResponse)
@limiter.limit("60/minute")
async def patch_position(
    request: Request,
    position_id: UUID,
    body: UpdatePositionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PositionResponse:
    portfolio = await get_portfolio_for_user(db, current_user.id)
    position = await update_position_metadata(
        db, current_user.id, portfolio.id, position_id, body
    )
    lots = await get_position_lots(db, position.id)
    tranches = await get_position_dividend_tranches(db, position.id)
    price_snapshot = await _latest_price_for(db, position.stock_code)

    return _build_position_response(position, lots, tranches, price_snapshot=price_snapshot)


@router.patch(
    "/portfolio/positions/{position_id}/lots/{lot_id}", response_model=LotResponse
)
@limiter.limit("60/minute")
async def patch_lot(
    request: Request,
    position_id: UUID,
    lot_id: UUID,
    body: UpdateLotRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LotResponse:
    portfolio = await get_portfolio_for_user(db, current_user.id)
    lot, warnings = await update_lot(
        db, current_user.id, portfolio.id, position_id, lot_id, body
    )

    response = LotResponse.model_validate(lot)
    response.warnings = warnings
    return response


@router.delete("/portfolio/positions/{position_id}/lots/{lot_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_lot_endpoint(
    request: Request,
    position_id: UUID,
    lot_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Documented in 03-openapi-specification.md since the API design phase
    but never claimed by an Epic 2 user story — implemented now as a small
    deliberate scope addition alongside BE-2.4/FE-2.4.
    """
    portfolio = await get_portfolio_for_user(db, current_user.id)
    await delete_lot(db, current_user.id, portfolio.id, position_id, lot_id)


@router.post("/portfolio/dividends", response_model=DividendTrancheResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def add_dividend(
    request: Request,
    body: CreateDividendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DividendTrancheResponse:
    portfolio = await get_portfolio_for_user(db, current_user.id)
    tranche = await create_dividend_tranche(db, current_user.id, portfolio.id, body)
    return DividendTrancheResponse.model_validate(tranche)


@router.get("/portfolio/dividends", response_model=DividendCalendarResponse)
@limiter.limit("60/minute")
async def get_dividend_calendar_endpoint(
    request: Request,
    year: int | None = Query(None, ge=1990),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DividendCalendarResponse:
    """BE-3.3: chronological dividend calendar across the whole portfolio,
    scoped by calendar year (OpenAPI's documented `year` query param,
    defaulting to the current year — see get_dividend_calendar's docstring
    for why this doesn't literally implement the AC's "future + trailing 30
    days" framing).
    """
    portfolio = await get_portfolio_for_user(db, current_user.id)
    effective_year = year if year is not None else date.today().year
    rows = await get_dividend_calendar(db, portfolio.id, effective_year)

    return DividendCalendarResponse(
        tranches=[
            DividendCalendarEntry(
                id=row.tranche.id,
                position_id=row.tranche.position_id,
                stock_code=row.stock_code,
                stock_name=row.stock_name,
                tranche_label=row.tranche.tranche_label,
                per_share_amount=row.tranche.per_share_amount,
                qualifying_shares=row.tranche.qualifying_shares,
                total_amount=row.tranche.total_amount,
                payment_date=row.tranche.payment_date,
                ex_dividend_date=row.tranche.ex_dividend_date,
                year=row.tranche.year,
                version=row.tranche.version,
                created_at=row.tranche.created_at,
                updated_at=row.tranche.updated_at,
                is_paid=row.is_paid,
                is_upcoming=row.is_upcoming,
            )
            for row in rows
        ]
    )


@router.patch("/portfolio/dividends/{tranche_id}", response_model=DividendTrancheResponse)
@limiter.limit("60/minute")
async def patch_dividend(
    request: Request,
    tranche_id: UUID,
    body: UpdateDividendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DividendTrancheResponse:
    portfolio = await get_portfolio_for_user(db, current_user.id)
    tranche = await update_dividend_tranche(db, current_user.id, portfolio.id, tranche_id, body)
    return DividendTrancheResponse.model_validate(tranche)


@router.delete("/portfolio/dividends/{tranche_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_dividend_endpoint(
    request: Request,
    tranche_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    portfolio = await get_portfolio_for_user(db, current_user.id)
    await delete_dividend_tranche(db, current_user.id, portfolio.id, tranche_id)
