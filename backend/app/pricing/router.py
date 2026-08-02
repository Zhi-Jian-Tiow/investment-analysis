from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db
from app.errors import trial_expired_paywall
from app.rate_limit import limiter

from app.pricing.schemas import ManualPriceOverrideRequest, PriceListResponse, PriceSnapshotResponse
from app.pricing.service import create_manual_price_override, get_latest_prices

router = APIRouter(prefix="/api/v1/pricing", tags=["Pricing"])


@router.get("/prices", response_model=PriceListResponse)
@limiter.limit("60/minute")
async def get_prices(
    request: Request,
    codes: list[str] = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PriceListResponse:
    """BE-5.2. Returns the latest snapshot per requested code — may include
    source='automated'/'manual' entries, or omit a code entirely if it has
    never had a snapshot at all (EC-005: no price ever retrieved is not the
    same as stale, and isn't represented by a row here for the caller to
    misread as "stale").
    """
    latest = await get_latest_prices(db, codes)
    return PriceListResponse(
        prices=[
            PriceSnapshotResponse(
                stock_code=snapshot.stock_code,
                price=snapshot.price,
                source=snapshot.source,
                trading_date=snapshot.trading_date,
                refreshed_at=snapshot.last_refreshed_at,
            )
            for snapshot in latest.values()
        ]
    )


@router.post("/manual-override", response_model=PriceSnapshotResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def post_manual_override(
    request: Request,
    body: ManualPriceOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PriceSnapshotResponse:
    """BE-5.2 / BAS EC-020: manual price entry is a write action, blocked for
    trial_expired accounts — the one write-permission check this story adds;
    the broader Permission Matrix gate across every other write endpoint is
    Epic 7's (SubscriptionGate) job, not retrofitted here.
    """
    if current_user.account_status == "trial_expired":
        raise trial_expired_paywall(
            "Your free trial has ended. Subscribe to continue overriding prices manually."
        )

    snapshot = await create_manual_price_override(db, current_user.id, body)
    return PriceSnapshotResponse(
        stock_code=snapshot.stock_code,
        price=snapshot.price,
        source=snapshot.source,
        trading_date=snapshot.trading_date,
        refreshed_at=snapshot.last_refreshed_at,
    )
