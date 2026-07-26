"""Broker-list schemas (FE-1.1) plus Position/Lot create-and-response schemas
(BE-2.1). DividendTranche schemas belong to Epic 3 (BE-3.x).
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CATEGORY_TAGS = ("Dividend", "Volatile", "Growth")


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


class CreatePositionRequest(BaseModel):
    """Matches components/schemas/CreatePositionRequest in
    03-openapi-specification.md, plus `stock_name` — the OpenAPI spec omits it,
    but the physical schema (§3.6) requires positions.stock_name as
    user-entered at creation, and VR-003 requires it as a mandatory field.
    """

    stock_code: str = Field(..., min_length=1, max_length=20)
    stock_name: str = Field(..., min_length=1, max_length=100)
    shares: int
    purchase_price: Decimal
    broker_id: UUID
    purchase_date: date
    category_tag: str = "Dividend"
    notes: str | None = Field(None, max_length=500)

    @field_validator("stock_code", "stock_name")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, value: int) -> int:
        # VR-004
        if value < 1:
            raise ValueError("Number of shares must be greater than zero")
        if value > 99_999_999:
            raise ValueError("Number of shares cannot exceed 99,999,999")
        return value

    @field_validator("purchase_price")
    @classmethod
    def validate_purchase_price(cls, value: Decimal) -> Decimal:
        # VR-005
        if value <= 0:
            raise ValueError("Purchase price must be greater than zero")
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -4:
            raise ValueError("Purchase price can have at most 4 decimal places")
        return value

    @field_validator("purchase_date")
    @classmethod
    def validate_purchase_date(cls, value: date) -> date:
        # VR-006
        if value > date.today():
            raise ValueError("Purchase date cannot be in the future")
        return value

    @field_validator("category_tag")
    @classmethod
    def validate_category_tag(cls, value: str) -> str:
        if value not in _CATEGORY_TAGS:
            raise ValueError(f"category_tag must be one of {_CATEGORY_TAGS}")
        return value


class LotResponse(BaseModel):
    """Matches components/schemas/LotResponse in 03-openapi-specification.md."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position_id: UUID
    shares: int
    purchase_price: Decimal
    purchase_date: date
    broker_id: UUID = Field(validation_alias="broker_config_id")
    initial_amount: Decimal
    brokerage_fee: Decimal
    clearing_fee: Decimal
    stamp_duty: Decimal
    all_in_cost: Decimal
    version: int
    created_at: datetime
    updated_at: datetime


class PositionResponse(BaseModel):
    """Matches components/schemas/PositionResponse (via PositionSummaryResponse)
    in 03-openapi-specification.md, with fields that depend on later epics
    left at their documented-nullable defaults:
    - dividend_tranches: always [] until Epic 3 exists
    - total_dividend_income_ytd: always "0.00" until Epic 3
    - current_price/price_source/price_last_refreshed_at/current_market_value/
      unrealised_pnl: always null until the price-feed epic exists (all
      nullable in the spec for exactly this "no price ever retrieved" case,
      BAS EC-005)

    `warnings` is additive (not in the OpenAPI spec) — carries EC-001's
    "added to existing position" notice and EC-004's non-trading-day notice.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stock_code: str
    stock_name: str
    category_tag: str
    total_shares: int
    total_all_in_cost: Decimal
    blended_purchase_price: Decimal
    total_dividend_income_ytd: Decimal = Decimal("0.00")
    current_price: Decimal | None = None
    price_source: str | None = None
    price_last_refreshed_at: datetime | None = None
    current_market_value: Decimal | None = None
    unrealised_pnl: Decimal | None = None
    lots: list[LotResponse]
    dividend_tranches: list[dict] = Field(default_factory=list)
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    warnings: list[str] = Field(default_factory=list)
