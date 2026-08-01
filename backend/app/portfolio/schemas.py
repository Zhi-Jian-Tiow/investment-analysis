"""Broker-list schemas (FE-1.1) plus Position/Lot/DividendTranche
create-and-response schemas (BE-2.x, BE-3.1).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_CATEGORY_TAGS = ("Dividend", "Volatile", "Growth")
_TRANCHE_LABELS = ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th")


def _check_shares(value: int) -> int:
    # VR-004 — shared by every request schema that creates/edits a Lot.
    if value < 1:
        raise ValueError("Number of shares must be greater than zero")
    if value > 99_999_999:
        raise ValueError("Number of shares cannot exceed 99,999,999")
    return value


def _check_purchase_price(value: Decimal) -> Decimal:
    # VR-005
    if value <= 0:
        raise ValueError("Purchase price must be greater than zero")
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -4:
        raise ValueError("Purchase price can have at most 4 decimal places")
    return value


def _check_purchase_date(value: date) -> date:
    # VR-006
    if value > date.today():
        raise ValueError("Purchase date cannot be in the future")
    return value


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
        return _check_shares(value)

    @field_validator("purchase_price")
    @classmethod
    def validate_purchase_price(cls, value: Decimal) -> Decimal:
        return _check_purchase_price(value)

    @field_validator("purchase_date")
    @classmethod
    def validate_purchase_date(cls, value: date) -> date:
        return _check_purchase_date(value)

    @field_validator("category_tag")
    @classmethod
    def validate_category_tag(cls, value: str) -> str:
        if value not in _CATEGORY_TAGS:
            raise ValueError(f"category_tag must be one of {_CATEGORY_TAGS}")
        return value


class CreateLotRequest(BaseModel):
    """Matches components/schemas/CreateLotRequest in
    03-openapi-specification.md — adds a lot to an already-existing position,
    so no stock_code/stock_name/category_tag here (those live on the Position).
    """

    shares: int
    purchase_price: Decimal
    broker_id: UUID
    purchase_date: date

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, value: int) -> int:
        return _check_shares(value)

    @field_validator("purchase_price")
    @classmethod
    def validate_purchase_price(cls, value: Decimal) -> Decimal:
        return _check_purchase_price(value)

    @field_validator("purchase_date")
    @classmethod
    def validate_purchase_date(cls, value: date) -> date:
        return _check_purchase_date(value)


class UpdatePositionRequest(BaseModel):
    """Matches components/schemas/UpdatePositionRequest in
    03-openapi-specification.md — metadata only (category_tag, notes); lot
    financial fields are edited via UpdateLotRequest instead.
    """

    category_tag: str | None = None
    notes: str | None = Field(None, max_length=500)

    @field_validator("category_tag")
    @classmethod
    def validate_category_tag(cls, value: str | None) -> str | None:
        if value is not None and value not in _CATEGORY_TAGS:
            raise ValueError(f"category_tag must be one of {_CATEGORY_TAGS}")
        return value


class UpdateLotRequest(BaseModel):
    """Matches components/schemas/UpdateLotRequest in
    03-openapi-specification.md. At least one of shares/purchase_price/
    broker_id/purchase_date must be present in addition to `version`.
    """

    shares: int | None = None
    purchase_price: Decimal | None = None
    broker_id: UUID | None = None
    purchase_date: date | None = None
    version: int = Field(..., ge=1)

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, value: int | None) -> int | None:
        return _check_shares(value) if value is not None else value

    @field_validator("purchase_price")
    @classmethod
    def validate_purchase_price(cls, value: Decimal | None) -> Decimal | None:
        return _check_purchase_price(value) if value is not None else value

    @field_validator("purchase_date")
    @classmethod
    def validate_purchase_date(cls, value: date | None) -> date | None:
        return _check_purchase_date(value) if value is not None else value

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "UpdateLotRequest":
        if self.shares is None and self.purchase_price is None and self.broker_id is None and self.purchase_date is None:
            raise ValueError("At least one of shares, purchase_price, broker_id, or purchase_date must be provided")
        return self


class LotResponse(BaseModel):
    """Matches components/schemas/LotResponse in 03-openapi-specification.md.

    `warnings` is additive (not in the OpenAPI spec) — carries EC-004's
    non-trading-day notice, consistent with PositionResponse's own `warnings`
    (BE-2.1).
    """

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
    warnings: list[str] = Field(default_factory=list)


class CreateDividendRequest(BaseModel):
    """Matches components/schemas/CreateDividendRequest in
    03-openapi-specification.md. `year` is not a client input — it's always
    derived from `payment_date` (VR-012: "Default: YEAR(payment_date);
    editable" describes the field's semantics generally, but this endpoint's
    schema has no year field at all, so there is nothing to override at
    creation time).
    """

    position_id: UUID
    tranche_label: str
    per_share_amount: Decimal
    qualifying_shares: int = Field(..., ge=1)
    payment_date: date
    ex_dividend_date: date | None = None

    @field_validator("tranche_label")
    @classmethod
    def validate_tranche_label(cls, value: str) -> str:
        if value not in _TRANCHE_LABELS:
            raise ValueError(f"tranche_label must be one of {_TRANCHE_LABELS}")
        return value

    @field_validator("per_share_amount")
    @classmethod
    def validate_per_share_amount(cls, value: Decimal) -> Decimal:
        # VR-008
        if value <= 0:
            raise ValueError("Dividend per share must be greater than zero")
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -6:
            raise ValueError("Dividend per share can have at most 6 decimal places")
        return value

    @field_validator("payment_date")
    @classmethod
    def validate_payment_date(cls, value: date) -> date:
        # VR-009
        if value > date.today() + timedelta(days=30):
            raise ValueError("Payment date cannot be more than 30 days in the future")
        return value

    @model_validator(mode="after")
    def validate_ex_dividend_date(self) -> "CreateDividendRequest":
        # VR-010
        if self.ex_dividend_date is not None and self.ex_dividend_date > self.payment_date:
            raise ValueError("Ex-dividend date must be before or on the payment date")
        return self


class DividendTrancheResponse(BaseModel):
    """Matches components/schemas/DividendTrancheResponse in
    03-openapi-specification.md.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position_id: UUID
    tranche_label: str
    per_share_amount: Decimal
    qualifying_shares: int
    total_amount: Decimal
    payment_date: date
    ex_dividend_date: date | None = None
    year: int
    version: int
    created_at: datetime
    updated_at: datetime


class PositionSummaryResponse(BaseModel):
    """Matches components/schemas/PositionSummaryResponse in
    03-openapi-specification.md — the list-row shape used by
    GET /api/v1/portfolio/dashboard (no lots/dividend_tranches; see
    PositionResponse for the full detail shape). Same later-epic-dependent
    fields held at their documented-nullable defaults as PositionResponse.
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


class PortfolioResponse(BaseModel):
    """Matches components/schemas/PortfolioResponse in
    03-openapi-specification.md. This is documented as the Epic 4 (BE-4.1)
    dashboard endpoint, but a minimal slice of it is pulled forward here
    (FE-2.1) because it's the only spec-documented way to list a user's
    positions — there is no separate "list positions" endpoint. Aggregates
    that depend on unbuilt epics (dividend income, price refresh timestamp)
    are held at their documented-nullable/zero defaults, same pattern as
    PositionResponse.
    """

    total_all_in_cost: Decimal
    total_dividend_income_ytd: Decimal = Decimal("0.00")
    last_price_refresh_at: datetime | None = None
    positions: list[PositionSummaryResponse]


class PositionResponse(BaseModel):
    """Matches components/schemas/PositionResponse (via PositionSummaryResponse)
    in 03-openapi-specification.md. `dividend_tranches`/`total_dividend_income_ytd`
    are real as of BE-3.1. Fields that still depend on the unbuilt price-feed
    epic are left at their documented-nullable defaults:
    - current_price/price_source/price_last_refreshed_at/current_market_value/
      unrealised_pnl: always null until the price-feed epic exists (all
      nullable in the spec for exactly this "no price ever retrieved" case,
      BAS EC-005)

    `warnings` is additive (not in the OpenAPI spec) — carries EC-001's
    "added to existing position" notice and EC-004's non-trading-day notice.

    `notes` is also additive: CreatePositionRequest/UpdatePositionRequest both
    accept it, but the documented PositionResponse/PositionSummaryResponse
    schemas never include it in the read side — an apparent spec gap. Added
    here so a value the user set can actually be read back.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stock_code: str
    stock_name: str
    category_tag: str
    notes: str | None = None
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
    dividend_tranches: list[DividendTrancheResponse] = Field(default_factory=list)
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    warnings: list[str] = Field(default_factory=list)
