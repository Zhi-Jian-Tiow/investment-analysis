"""broker_configs, portfolios (BursaTrack-DB-Stage3-Physical-Schema.md §3.4-3.5).

Only these two tables are needed for BE-1.1: registration validates broker_id
against BrokerConfig and creates an empty Portfolio. positions, lots, and
dividend_tranches (§3.6-3.8) belong to Epics 2-3 and are added when those
stories are implemented.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BrokerConfig(Base):
    __tablename__ = "broker_configs"
    __table_args__ = (
        CheckConstraint("fee_type IN ('percentage', 'flat')", name="broker_configs_fee_type_check"),
        CheckConstraint(
            "(fee_type = 'percentage' AND rate IS NOT NULL AND minimum_fee IS NOT NULL AND flat_fee IS NULL)"
            " OR (fee_type = 'flat' AND flat_fee IS NOT NULL AND rate IS NULL AND minimum_fee IS NULL)",
            name="broker_configs_percentage_fields_check",
        ),
        CheckConstraint(
            "(is_system = true AND created_by_user_id IS NULL)"
            " OR (is_system = false AND created_by_user_id IS NOT NULL)",
            name="broker_configs_system_ownership_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    fee_type: Mapped[str] = mapped_column(String, nullable=False)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    minimum_fee: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    flat_fee: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (UniqueConstraint("user_id", name="portfolios_user_unique"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
