from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_user_optional
from app.auth.models import User
from app.database import get_db
from app.rate_limit import limiter

from app.portfolio.models import DividendTranche, Lot, Position
from app.portfolio.schemas import (
    BrokerConfigResponse,
    BrokerListResponse,
    CreateDividendRequest,
    CreateLotRequest,
    CreatePositionRequest,
    DividendTrancheResponse,
    LotResponse,
    PortfolioResponse,
    PositionResponse,
    PositionSummaryResponse,
    UpdateDividendRequest,
    UpdateLotRequest,
    UpdatePositionRequest,
)
from app.portfolio.service import (
    add_lot_to_position,
    create_dividend_tranche,
    create_position,
    delete_dividend_tranche,
    delete_lot,
    delete_position,
    get_owned_active_position,
    get_portfolio_for_user,
    get_position_dividend_tranches,
    get_position_lots,
    list_brokers,
    list_positions_for_portfolio,
    position_aggregates,
    position_dividend_income_ytd,
    update_dividend_tranche,
    update_lot,
    update_position_metadata,
)

# Dashboard/Sell-Calculator routes belong to Epic 4. Position/Lot creation is
# added in BE-2.1/BE-2.2; edit in BE-2.3; delete in BE-2.4; dividend logging
# (this file) in BE-3.1.
router = APIRouter(prefix="/api/v1", tags=["Portfolio"])


def _build_position_response(
    position: Position,
    lots: list[Lot],
    tranches: list[DividendTranche] | None = None,
    warnings: list[str] | None = None,
) -> PositionResponse:
    total_shares, total_all_in_cost, blended_purchase_price = position_aggregates(lots)
    tranches = tranches or []
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
    """A minimal slice of the Epic 4 (BE-4.1) dashboard endpoint, pulled
    forward for FE-2.1: it's the only spec-documented way to list a user's
    positions. Dividend income is real as of BE-3.1; price-refresh fields
    stay at their documented-nullable/zero defaults until the price-feed
    epic exists.
    """
    portfolio = await get_portfolio_for_user(db, current_user.id)
    positions = await list_positions_for_portfolio(db, portfolio.id)

    summaries: list[PositionSummaryResponse] = []
    total_all_in_cost = Decimal("0.00")
    total_dividend_income_ytd = Decimal("0.00")
    for position in positions:
        lots = await get_position_lots(db, position.id)
        tranches = await get_position_dividend_tranches(db, position.id)
        total_shares, position_all_in_cost, blended_purchase_price = position_aggregates(lots)
        position_income_ytd = position_dividend_income_ytd(tranches)
        total_all_in_cost += position_all_in_cost
        total_dividend_income_ytd += position_income_ytd
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
            )
        )

    return PortfolioResponse(
        total_all_in_cost=total_all_in_cost,
        total_dividend_income_ytd=total_dividend_income_ytd,
        positions=summaries,
    )


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

    return _build_position_response(position, lots, tranches, warnings)


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

    return _build_position_response(position, lots, tranches)


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

    return _build_position_response(position, lots, tranches)


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
