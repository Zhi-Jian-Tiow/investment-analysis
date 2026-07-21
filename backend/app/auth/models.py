"""users, pending_tokens (BursaTrack-DB-Stage3-Physical-Schema.md §3.1-3.2).

pending_email_notifications (§3.3) belongs to Epic 8 (PDPA hard-delete
notification gate, MED-R-005) and is added when that story is implemented.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "account_status IN ('trial', 'active', 'grace_period', 'trial_expired', 'pending_deletion')",
            name="users_account_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    account_status: Mapped[str] = mapped_column(String, nullable=False, default="trial")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stripe_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    default_broker_config_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("broker_configs.id", ondelete="SET NULL"), nullable=True
    )
    trial_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    trial_expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    subscription_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subscription_renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deletion_requested_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    permanent_deletion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PendingToken(Base):
    """Single-use, short-lived tokens for email verification / password reset /
    deletion cancellation (architecture §14.1). Only the SHA-256 hash of the raw
    token is ever stored.
    """

    __tablename__ = "pending_tokens"
    __table_args__ = (
        CheckConstraint(
            "type IN ('email_verification', 'password_reset', 'deletion_cancellation')",
            name="pending_tokens_type_check",
        ),
        UniqueConstraint("token_hash", name="pending_tokens_hash_unique"),
        UniqueConstraint("user_id", "type", name="pending_tokens_user_type_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
