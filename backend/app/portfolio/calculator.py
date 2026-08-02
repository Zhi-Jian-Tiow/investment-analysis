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

from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from app.portfolio.models import BrokerConfig

_TWO_PLACES = Decimal("0.01")
_FOUR_PLACES = Decimal("0.0001")
_CLEARING_FEE_RATE = Decimal("0.0003")  # BR-005: 0.03%
_CLEARING_FEE_CAP = Decimal("1000.00")  # BR-005: regulatory cap per contract
_STAMP_DUTY_PER_THOUSAND = Decimal("1.00")  # BR-006/BR-015: RM1 per RM1,000
_STAMP_DUTY_MINIMUM = Decimal("1.00")  # BR-006

# BAS Workflow 6 / US-015-016: "current price + 0.01...0.05, then 0.10...0.70
# in 0.05 steps" — 5 + 13 = 18 rows. Decimal arithmetic throughout so the
# ladder is exact (no float drift), matching BR-025's rounding discipline.
_SELL_SCENARIO_LADDER_OFFSETS: tuple[Decimal, ...] = tuple(
    [Decimal("0.01"), Decimal("0.02"), Decimal("0.03"), Decimal("0.04"), Decimal("0.05")]
    + [Decimal("0.05") * n for n in range(2, 15)]  # 0.10, 0.15, ..., 0.70
)


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


def compute_market_value_and_pnl(
    total_shares: int, current_price: Decimal | None, total_all_in_cost: Decimal
) -> tuple[Decimal | None, Decimal | None]:
    """BR-025: current_market_value = total_shares x current_price;
    unrealised_pnl = current_market_value - total_all_in_cost. Both null
    when there's no price data at all (EC-005) — never a false RM0.00.
    """
    if current_price is None:
        return None, None
    market_value = round_myr(Decimal(total_shares) * current_price)
    pnl = round_myr(market_value - total_all_in_cost)
    return market_value, pnl


@dataclass(frozen=True)
class SellScenarioRow:
    price: Decimal
    gross_proceeds: Decimal
    brokerage_fee: Decimal
    clearing_fee: Decimal
    stamp_duty: Decimal
    all_in_sell_cost: Decimal
    net_proceeds: Decimal
    profit_loss: Decimal
    break_even: bool = False


def default_sell_scenario_prices(base_price: Decimal) -> list[Decimal]:
    """BE-4.2: the default scenario ladder, anchored on `base_price` — a
    stand-in for "current price" (BAS Workflow 6's actual wording) since
    Epic 5 (live pricing) doesn't exist yet. See BE-4.2's Implementation
    Record for why the position's blended_purchase_price is used instead.
    """
    return [(base_price + offset).quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP) for offset in _SELL_SCENARIO_LADDER_OFFSETS]


def calculate_sell_scenario_row(
    price: Decimal, shares_to_sell: int, buy_cost_basis: Decimal, broker: BrokerConfig
) -> SellScenarioRow:
    """BR-004: sell-side brokerage/clearing/stamp duty use the exact same
    formulas as buy-side (calculate_lot_fees), applied to gross sell
    proceeds instead of the buy-side initial_amount — reusing
    compute_brokerage_fee/compute_clearing_fee/compute_stamp_duty directly,
    per this story's own Dependencies note.
    """
    gross_proceeds = round_myr(price * shares_to_sell)
    brokerage_fee = compute_brokerage_fee(gross_proceeds, broker)
    clearing_fee = compute_clearing_fee(gross_proceeds)
    stamp_duty = compute_stamp_duty(gross_proceeds)
    # "all_in_sell_cost": the sell-side mirror of BR-007's all_in_cost — the
    # total transaction cost (fees only), not gross_proceeds + fees. The
    # OpenAPI spec's own worked example for this field (42197.73, i.e.
    # gross + fees) is inconsistent with its sibling projected_net_proceeds
    # example (42002.27, i.e. gross - fees) on the same row; this is the
    # economically sensible reading — see BE-4.2's Implementation Record.
    all_in_sell_cost = round_myr(brokerage_fee + clearing_fee + stamp_duty)
    net_proceeds = round_myr(gross_proceeds - all_in_sell_cost)
    profit_loss = round_myr(net_proceeds - buy_cost_basis)
    return SellScenarioRow(
        price=price,
        gross_proceeds=gross_proceeds,
        brokerage_fee=brokerage_fee,
        clearing_fee=clearing_fee,
        stamp_duty=stamp_duty,
        all_in_sell_cost=all_in_sell_cost,
        net_proceeds=net_proceeds,
        profit_loss=profit_loss,
    )


def build_sell_scenario_rows(
    prices: list[Decimal], shares_to_sell: int, buy_cost_basis: Decimal, broker: BrokerConfig
) -> list[SellScenarioRow]:
    """Computes one row per price (ascending order expected — callers sort
    `prices` first) and flags only the lowest-price row with a non-negative
    profit_loss as `break_even` (BAS US-015: "the RM8.42 row is highlighted
    as Break-even" — singular, not every profitable row).
    """
    rows = [calculate_sell_scenario_row(p, shares_to_sell, buy_cost_basis, broker) for p in prices]
    for i, row in enumerate(rows):
        if row.profit_loss >= 0:
            rows[i] = replace(row, break_even=True)
            break
    return rows


def is_non_trading_day(value: date) -> bool:
    """EC-004: soft warning for weekends. Malaysian public holidays are not
    checked — that requires a maintained Bursa holiday calendar, out of scope
    for this story (no such reference data source exists yet in the schema).
    """
    return value.weekday() >= 5
