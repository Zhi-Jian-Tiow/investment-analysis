"""Single authoritative fee-calculation module (architecture P-003, P-005, G-001).

Every code path that produces a Lot's fee breakdown — Add Position (BE-2.1),
Add Lot (BE-2.2), Edit Lot (BE-2.3), Sell Calculator, CSV import — must call
into this module rather than duplicating BR-001–BR-007. Decimal only; no
float/double anywhere in this file (R-003 mitigation, BE-2.1 DoD).

Stamp duty rate (BR-006/BR-015) and the clearing-fee cap (BR-005) are
hardcoded here rather than read from a `system_config` table, since that
table doesn't exist yet (deferred to the epic that adds fee-config
administration). Revisit when that table lands.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from app.portfolio.models import BrokerConfig

_TWO_PLACES = Decimal("0.01")
_CLEARING_FEE_RATE = Decimal("0.0003")  # BR-005: 0.03%
_CLEARING_FEE_CAP = Decimal("1000.00")  # BR-005: regulatory cap per contract
_STAMP_DUTY_PER_THOUSAND = Decimal("1.00")  # BR-006/BR-015: RM1 per RM1,000
_STAMP_DUTY_MINIMUM = Decimal("1.00")  # BR-006


def round_myr(value: Decimal) -> Decimal:
    """BR-025: round half away from zero to 2dp. All inputs here are
    non-negative, so ROUND_HALF_UP (Python's ties-away-from-zero mode) is
    equivalent to "half away from zero" for our domain.
    """
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LotFees:
    initial_amount: Decimal
    brokerage_fee: Decimal
    clearing_fee: Decimal
    stamp_duty: Decimal
    all_in_cost: Decimal


def compute_initial_amount(shares: int, purchase_price: Decimal) -> Decimal:
    return round_myr(Decimal(shares) * purchase_price)


def compute_brokerage_fee(initial_amount: Decimal, broker: BrokerConfig) -> Decimal:
    """BR-001 (percentage, with minimum) / BR-002 (flat) / BR-003 (per lot,
    not per position — enforced by callers invoking this once per Lot).
    """
    if broker.fee_type == "percentage":
        assert broker.rate is not None and broker.minimum_fee is not None
        fee = round_myr(initial_amount * broker.rate)
        return max(fee, broker.minimum_fee)
    assert broker.flat_fee is not None
    return round_myr(broker.flat_fee)


def compute_clearing_fee(initial_amount: Decimal) -> Decimal:
    """BR-005: 0.03%, capped at RM1,000 per contract."""
    fee = round_myr(initial_amount * _CLEARING_FEE_RATE)
    return min(fee, _CLEARING_FEE_CAP)


def compute_stamp_duty(initial_amount: Decimal) -> Decimal:
    """BR-006: ROUNDUP(initial_amount / 1000, 0) x RM1, RM1 minimum."""
    blocks = (initial_amount / Decimal("1000")).to_integral_value(rounding=ROUND_CEILING)
    duty = round_myr(blocks * _STAMP_DUTY_PER_THOUSAND)
    return max(duty, _STAMP_DUTY_MINIMUM)


def calculate_lot_fees(shares: int, purchase_price: Decimal, broker: BrokerConfig) -> LotFees:
    """BR-007: all-in cost = initial_amount + brokerage_fee + clearing_fee +
    stamp_duty, each component individually rounded before summing.
    """
    initial_amount = compute_initial_amount(shares, purchase_price)
    brokerage_fee = compute_brokerage_fee(initial_amount, broker)
    clearing_fee = compute_clearing_fee(initial_amount)
    stamp_duty = compute_stamp_duty(initial_amount)
    all_in_cost = round_myr(initial_amount + brokerage_fee + clearing_fee + stamp_duty)
    return LotFees(
        initial_amount=initial_amount,
        brokerage_fee=brokerage_fee,
        clearing_fee=clearing_fee,
        stamp_duty=stamp_duty,
        all_in_cost=all_in_cost,
    )


def is_non_trading_day(value: date) -> bool:
    """EC-004: soft warning for weekends. Malaysian public holidays are not
    checked — that requires a maintained Bursa holiday calendar, out of scope
    for this story (no such reference data source exists yet in the schema).
    """
    return value.weekday() >= 5
