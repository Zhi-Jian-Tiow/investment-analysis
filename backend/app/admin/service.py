"""Admin-domain service functions. Other modules call record_audit_event rather
than instantiating AuditLog directly (architecture P-008 — service-layer access
across module boundaries, no direct cross-module table writes).
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AuditLog


async def record_audit_event(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=metadata,
        )
    )
    await db.flush()
