"""Portfolio-domain service functions. Other modules (e.g. auth) call into this
module rather than querying portfolio tables directly (architecture P-008 — no
cross-module database joins; access goes through service-layer interfaces).

BE-1.1 needs broker lookup + portfolio creation at registration. FE-1.1 needs
list_brokers to populate the registration form's broker dropdown (see
app.auth.dependencies.get_current_user_optional for why this is reachable
pre-login). Position/Lot/DividendTranche CRUD and the fee calculator belong
to Epic 2 (BE-2.x) and Epic 4 (BE-4.2) — not implemented yet.
"""

import uuid

from sqlalchemy import or_, select
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
