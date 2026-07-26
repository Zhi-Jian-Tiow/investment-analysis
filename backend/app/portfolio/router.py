from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_user_optional
from app.auth.models import User
from app.database import get_db
from app.rate_limit import limiter

from .schemas import BrokerConfigResponse, BrokerListResponse, CreatePositionRequest, LotResponse, PositionResponse
from .service import create_position, get_portfolio_for_user, list_brokers, position_aggregates

# Dividend/Dashboard/Sell-Calculator routes belong to Epics 3-4. Position/Lot
# creation is added here (BE-2.1); Add Lot/Edit/Delete follow in BE-2.2-2.4.
router = APIRouter(prefix="/api/v1", tags=["Portfolio"])


@router.get("/brokers", response_model=BrokerListResponse)
@limiter.limit("60/minute")
async def get_brokers(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> BrokerListResponse:
    brokers = await list_brokers(db, user_id=current_user.id if current_user else None)
    return BrokerListResponse(brokers=[BrokerConfigResponse.model_validate(b) for b in brokers])


@router.post("/portfolio/positions", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def add_position(
    request: Request,
    body: CreatePositionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PositionResponse:
    portfolio = await get_portfolio_for_user(db, current_user.id)
    position, lots, warnings = await create_position(db, current_user.id, portfolio.id, body)

    total_shares, total_all_in_cost, blended_purchase_price = position_aggregates(lots)

    return PositionResponse(
        id=position.id,
        stock_code=position.stock_code,
        stock_name=position.stock_name,
        category_tag=position.category_tag,
        total_shares=total_shares,
        total_all_in_cost=total_all_in_cost,
        blended_purchase_price=blended_purchase_price,
        lots=[LotResponse.model_validate(lot) for lot in lots],
        is_deleted=position.is_deleted,
        created_at=position.created_at,
        updated_at=position.updated_at,
        warnings=warnings,
    )
