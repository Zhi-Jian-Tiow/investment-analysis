"""Portfolio-domain service functions. Other modules (e.g. auth) call into this
module rather than querying portfolio tables directly (architecture P-008 — no
cross-module database joins; access goes through service-layer interfaces).

Only the two functions BE-1.1 needs (broker lookup, portfolio creation at
registration) are implemented so far. Position/Lot/DividendTranche CRUD and the
fee calculator belong to Epic 2 (BE-2.x) and Epic 4 (BE-4.2).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.portfolio.models import BrokerConfig, Portfolio


async def get_broker(db: AsyncSession, broker_id: uuid.UUID) -> BrokerConfig | None:
    """VR-007: broker_id must reference an existing BrokerConfig.

    Note: the BAS's Entity 8 description mentions an `is_active` flag for hiding
    retired brokers from new dropdowns, but the physical schema (Stage 3, the
    authoritative downstream artifact) has no such column on broker_configs —
    only `is_system`. This function therefore checks existence only.
    """
    result = await db.execute(select(BrokerConfig).where(BrokerConfig.id == broker_id))
    return result.scalar_one_or_none()


async def create_portfolio(db: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    """FR-001 step 6: every new User gets exactly one empty Portfolio
    (portfolios_user_unique enforces one-per-user at V1, per BAS Entity 2).
    """
    portfolio = Portfolio(user_id=user_id)
    db.add(portfolio)
    await db.flush()
    return portfolio
