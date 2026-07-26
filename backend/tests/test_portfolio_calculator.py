from datetime import date
from decimal import Decimal

from app.portfolio.calculator import (
    calculate_lot_fees,
    compute_clearing_fee,
    compute_stamp_duty,
    is_non_trading_day,
    round_myr,
)
from app.portfolio.models import BrokerConfig


def _percentage_broker(rate: str, minimum_fee: str) -> BrokerConfig:
    return BrokerConfig(name="Test Broker", fee_type="percentage", rate=Decimal(rate), minimum_fee=Decimal(minimum_fee))


def _flat_broker(flat_fee: str) -> BrokerConfig:
    return BrokerConfig(name="Test Flat Broker", fee_type="flat", flat_fee=Decimal(flat_fee))


class TestBasWorkedExamples:
    """BAS US-003 / FR-003 worked examples — must pass numerically exactly."""

    def test_maybank_investment_happy_path(self):
        broker = _percentage_broker("0.001", "8.00")
        fees = calculate_lot_fees(5000, Decimal("8.38"), broker)

        assert fees.initial_amount == Decimal("41900.00")
        assert fees.brokerage_fee == Decimal("41.90")
        assert fees.clearing_fee == Decimal("12.57")
        assert fees.stamp_duty == Decimal("42.00")
        assert fees.all_in_cost == Decimal("41996.47")

    def test_moomoo_flat_fee(self):
        broker = _flat_broker("3.00")
        fees = calculate_lot_fees(5000, Decimal("8.38"), broker)

        assert fees.brokerage_fee == Decimal("3.00")
        assert fees.all_in_cost == Decimal("41957.57")

    def test_brokerage_minimum_applied(self):
        broker = _percentage_broker("0.001", "8.00")
        fees = calculate_lot_fees(5000, Decimal("0.60"), broker)

        assert fees.initial_amount == Decimal("3000.00")
        assert fees.brokerage_fee == Decimal("8.00")
        assert fees.clearing_fee == Decimal("0.90")
        assert fees.stamp_duty == Decimal("3.00")
        assert fees.all_in_cost == Decimal("3011.90")

    def test_add_lot_second_lot_from_us_004(self):
        broker = _percentage_broker("0.001", "8.00")
        fees = calculate_lot_fees(2000, Decimal("9.00"), broker)

        assert fees.initial_amount == Decimal("18000.00")
        assert fees.brokerage_fee == Decimal("18.00")
        assert fees.clearing_fee == Decimal("5.40")
        assert fees.stamp_duty == Decimal("18.00")


class TestBr001PercentageBrokerage:
    def test_percentage_above_minimum(self):
        broker = _percentage_broker("0.001", "8.00")
        assert calculate_lot_fees(1, Decimal("41900.00"), broker).brokerage_fee == Decimal("41.90")

    def test_percentage_minimum_applied(self):
        broker = _percentage_broker("0.001", "8.00")
        assert calculate_lot_fees(1, Decimal("3000.00"), broker).brokerage_fee == Decimal("8.00")


class TestBr002FlatBrokerage:
    def test_flat_fee_independent_of_trade_size(self):
        broker = _flat_broker("3.00")
        small = calculate_lot_fees(10, Decimal("1.00"), broker)
        large = calculate_lot_fees(100000, Decimal("50.00"), broker)
        assert small.brokerage_fee == Decimal("3.00")
        assert large.brokerage_fee == Decimal("3.00")


class TestBr005ClearingFeeCap:
    def test_clearing_fee_normal_case(self):
        assert compute_clearing_fee(Decimal("41900.00")) == Decimal("12.57")

    def test_clearing_fee_capped_at_1000(self):
        # A contract value large enough that 0.03% would exceed RM1,000.
        huge_amount = Decimal("10000000.00")
        assert compute_clearing_fee(huge_amount) == Decimal("1000.00")


class TestBr006StampDutyBoundary:
    def test_standard_case(self):
        assert compute_stamp_duty(Decimal("41900.00")) == Decimal("42.00")

    def test_exact_thousand_boundary(self):
        assert compute_stamp_duty(Decimal("3000.00")) == Decimal("3.00")

    def test_minimum_applied_below_one_thousand(self):
        assert compute_stamp_duty(Decimal("500.00")) == Decimal("1.00")


class TestEc002ZeroBrokerage:
    def test_zero_rate_custom_broker_is_valid(self):
        broker = _percentage_broker("0", "0")
        fees = calculate_lot_fees(1000, Decimal("1.00"), broker)
        assert fees.brokerage_fee == Decimal("0.00")
        assert fees.all_in_cost == Decimal("1000.00") + fees.clearing_fee + fees.stamp_duty


class TestBr025RoundingBoundary:
    """Worked rounding-boundary examples from BR-025."""

    def test_clearing_fee_rounds_down_at_exact_half(self):
        assert compute_clearing_fee(Decimal("41666.67")) == Decimal("12.50")

    def test_clearing_fee_stored_as_is(self):
        assert compute_clearing_fee(Decimal("41833.33")) == Decimal("12.55")

    def test_clearing_fee_rounds_up_half_away_from_zero(self):
        assert compute_clearing_fee(Decimal("41916.67")) == Decimal("12.58")

    def test_round_myr_half_away_from_zero(self):
        assert round_myr(Decimal("12.575")) == Decimal("12.58")
        assert round_myr(Decimal("12.565")) == Decimal("12.57")
        assert round_myr(Decimal("12.564")) == Decimal("12.56")


class TestEc004NonTradingDay:
    def test_saturday_is_non_trading_day(self):
        assert is_non_trading_day(date(2026, 1, 17)) is True  # a Saturday

    def test_weekday_is_trading_day(self):
        assert is_non_trading_day(date(2026, 1, 15)) is False  # a Thursday
