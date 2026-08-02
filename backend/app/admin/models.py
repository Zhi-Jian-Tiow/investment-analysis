"""audit_log, system_config (BursaTrack-DB-Stage3-Physical-Schema.md §3.11-3.12).

system_config is pulled forward from Epic 9 (DEP-9.4/BE-8.3) for BE-5.1 — the
price refresh cron needs somewhere to store the Bursa holiday calendar, the
price deviation threshold, and its process lock. Only the table itself and
plain get/set access are built here; BE-8.3's admin PATCH endpoint (with its
own TTLCache and ADMIN_API_KEY auth) is still deferred.

system_deletion_log (§3.13) belongs to Epic 8 (PDPA hard-delete) and is added
when that story is implemented.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Only the action/entity values emitted by implemented BE stories so far.
# Extend this tuple (and add a migration) as later epics introduce new audit events.
AUDIT_LOG_ACTIONS = (
    "USER_REGISTERED",
    "USER_LOGIN",
    "PASSWORD_CHANGED",
    "LOT_CREATED",
    "LOT_UPDATED",
    "LOT_DELETED",
    "POSITION_UPDATED",
    "POSITION_DELETED",
    "DIVIDEND_CREATED",
    "DIVIDEND_UPDATED",
    "DIVIDEND_DELETED",
    "PRICE_OVERRIDE_CREATED",
)

AUDIT_LOG_ENTITY_TYPES = ("User", "Lot", "Position", "DividendTranche", "PriceSnapshot")


def _sql_in_list(values: tuple[str, ...]) -> str:
    # A plain f"{values!r}" breaks for single-element tuples: Python's repr adds
    # a trailing comma ("('User',)") which is invalid SQL IN-list syntax.
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


class AuditLog(Base):
    """Immutable, append-only (architecture §14.7). CASCADE-deleted only via the
    PDPA hard-delete job's removal of the parent User row (HIGH-R-007).
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(f"action IN {_sql_in_list(AUDIT_LOG_ACTIONS)}", name="audit_log_action_check"),
        CheckConstraint(
            f"entity_type IN {_sql_in_list(AUDIT_LOG_ENTITY_TYPES)}", name="audit_log_entity_type_check"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # Column is named "metadata" in the DB; mapped to a differently-named Python
    # attribute because `metadata` is reserved on SQLAlchemy declarative classes
    # (Base.metadata is the schema MetaData object).
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SystemConfig(Base):
    """Key-value store for operational parameters (physical schema §3.11).
    `value` is always TEXT — callers parse to whatever type they need
    (Decimal, JSON, an ISO timestamp). `value IS NULL` is a valid state (e.g.
    `price_refresh_lock` when no lock is currently held).
    """

    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
