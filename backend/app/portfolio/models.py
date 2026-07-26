"""broker_configs, portfolios, positions, lots (BursaTrack-DB-Stage3-Physical-Schema.md
§3.4-3.7). dividend_tranches (§3.8) belongs to Epic 3 and is added when those
stories are implemented.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
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


class Position(Base):
    """No FK from stock_code to a `stocks` reference table yet — that table is
    seeded in Epic 9 (see BE-2.1's Dependencies). stock_name is user-entered at
    creation time (physical schema §3.6 comment), not derived.
    """

    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("category_tag IN ('Dividend', 'Volatile', 'Growth')", name="positions_category_tag_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("portfolios.id", ondelete="RESTRICT"), nullable=False
    )
    stock_code: Mapped[str] = mapped_column(String, nullable=False)
    stock_name: Mapped[str] = mapped_column(String, nullable=False)
    category_tag: Mapped[str] = mapped_column(String, nullable=False, default="Dividend")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Lot(Base):
    """All fee components stored individually; all_in_cost = initial_amount +
    brokerage_fee + clearing_fee + stamp_duty, enforced by the application
    (portfolio/calculator.py) rather than a DB CHECK expression (physical
    schema §3.7 comment).
    """

    __tablename__ = "lots"
    __table_args__ = (
        CheckConstraint("shares >= 1", name="lots_shares_positive"),
        CheckConstraint("purchase_price > 0", name="lots_purchase_price_positive"),
        CheckConstraint("initial_amount > 0", name="lots_initial_amount_positive"),
        CheckConstraint("brokerage_fee >= 0", name="lots_brokerage_fee_nonneg"),
        CheckConstraint("clearing_fee >= 0", name="lots_clearing_fee_nonneg"),
        CheckConstraint("stamp_duty >= 0", name="lots_stamp_duty_nonneg"),
        CheckConstraint("all_in_cost > 0", name="lots_all_in_cost_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    position_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("positions.id", ondelete="RESTRICT"), nullable=False
    )
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    initial_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    brokerage_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    clearing_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    stamp_duty: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    all_in_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    broker_config_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("broker_configs.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
