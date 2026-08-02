"""price_snapshots (BursaTrack-DB-Stage3-Physical-Schema.md §3.10). Pulled
forward from Epic 9 for BE-5.1 — see alembic/versions/0012 for the full
rationale, including why `stock_code` has no FK to a `stocks` reference table.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceSnapshot(Base):
    """One row per (stock_code, trading_date). `source` distinguishes an
    automated yfinance fetch from a user's manual override (BE-5.2) from a
    carried-forward/rejected value (BE-5.1's own deviation guard and
    exhausted-retries path — see pricing/service.py). Never updated in place
    across trading days: each new trading day gets its own row, UPSERTed only
    within that same day if the job runs more than once.
    """

    __tablename__ = "price_snapshots"
    __table_args__ = (
        CheckConstraint("price > 0", name="price_snapshots_price_positive"),
        CheckConstraint("source IN ('automated', 'manual', 'stale')", name="price_snapshots_source_check"),
        UniqueConstraint("stock_code", "trading_date", name="price_snapshots_unique_per_day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    stock_code: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
