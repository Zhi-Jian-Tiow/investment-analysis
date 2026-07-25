"""Only the read-side broker-list schemas needed by FE-1.1 exist so far.
Position/Lot/Dividend request-response schemas belong to Epic 2 (BE-2.x) and
Epic 3 (BE-3.x).
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BrokerConfigResponse(BaseModel):
    """Matches components/schemas/BrokerConfigResponse in
    03-openapi-specification.md exactly."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    fee_type: str
    rate: Decimal | None = None
    minimum_fee: Decimal | None = None
    flat_fee: Decimal | None = None
    is_system: bool
    created_by_user_id: UUID | None = None
    created_at: datetime


class BrokerListResponse(BaseModel):
    brokers: list[BrokerConfigResponse]
