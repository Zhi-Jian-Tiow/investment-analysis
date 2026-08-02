"""Matches components/schemas/PriceSnapshotResponse and
ManualPriceOverrideRequest in 03-openapi-specification.md.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


class PriceSnapshotResponse(BaseModel):
    """Note: the API field is `refreshed_at`, but the DB column (and the
    Lot/DividendTranche-style convention elsewhere in this codebase) is
    `last_refreshed_at` — built explicitly in the router rather than via
    `from_attributes`, since the names don't match.
    """

    stock_code: str
    price: Decimal
    source: str
    trading_date: date
    refreshed_at: datetime


class PriceListResponse(BaseModel):
    prices: list[PriceSnapshotResponse]


class ManualPriceOverrideRequest(BaseModel):
    stock_code: str
    price: Decimal
    trading_date: date

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: Decimal) -> Decimal:
        # Same VR-005/BR-026 rule as Lot.purchase_price: >0, at most 4dp.
        if value <= 0:
            raise ValueError("Price must be greater than zero")
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -4:
            raise ValueError("Price can have at most 4 decimal places")
        return value
