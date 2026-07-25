from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user_optional
from app.auth.models import User
from app.database import get_db
from app.rate_limit import limiter

from .schemas import BrokerConfigResponse, BrokerListResponse
from .service import list_brokers

# Position/Lot/Dividend/Dashboard/Sell-Calculator routes belong to Epics 2-4.
# Only the broker read-list exists so far — added to unblock FE-1.1's
# registration-form dropdown (see app.auth.dependencies.get_current_user_optional).
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
