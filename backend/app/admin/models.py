"""audit_log (BursaTrack-DB-Stage3-Physical-Schema.md §3.12).

system_config and system_deletion_log (§3.11, §3.13) belong to later epics
(fee config administration, PDPA hard-delete) and are added when those stories
are implemented.
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
)

AUDIT_LOG_ENTITY_TYPES = ("User", "Lot")


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
