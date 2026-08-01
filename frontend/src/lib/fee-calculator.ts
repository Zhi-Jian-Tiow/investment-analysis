/**
 * Client-side fee preview mirroring backend/app/portfolio/calculator.py
 * exactly (BR-001-BR-007, BR-025 rounding). decimal.js only — never native
 * floating point (FE-2.1 AC) — since this preview must never diverge from
 * what the server actually computes and persists. Display-only: the form
 * never submits these computed values, only the raw inputs (P-003).
 */

import Decimal from "decimal.js";

import type { BrokerConfigResponse } from "@/lib/types";

export interface FeeBreakdown {
  initialAmount: Decimal;
  brokerageFee: Decimal;
  clearingFee: Decimal;
  stampDuty: Decimal;
  allInCost: Decimal;
}

const CLEARING_FEE_RATE = new Decimal("0.0003"); // BR-005: 0.03%
const CLEARING_FEE_CAP = new Decimal("1000.00"); // BR-005: regulatory cap
const STAMP_DUTY_MINIMUM = new Decimal("1.00"); // BR-006

function roundMyr(value: Decimal): Decimal {
  // BR-025: round half away from zero to 2dp.
  return value.toDecimalPlaces(2, Decimal.ROUND_HALF_UP);
}

export function computeInitialAmount(shares: number, purchasePrice: string): Decimal {
  return roundMyr(new Decimal(shares).times(new Decimal(purchasePrice)));
}

export function computeBrokerageFee(initialAmount: Decimal, broker: BrokerConfigResponse): Decimal {
  // BR-001 (percentage, with minimum) / BR-002 (flat) / BR-003 (per lot,
  // enforced by callers invoking this once per lot).
  if (broker.fee_type === "percentage") {
    const rate = new Decimal(broker.rate ?? "0");
    const minimum = new Decimal(broker.minimum_fee ?? "0");
    const fee = roundMyr(initialAmount.times(rate));
    return Decimal.max(fee, minimum);
  }
  return roundMyr(new Decimal(broker.flat_fee ?? "0"));
}

export function computeClearingFee(initialAmount: Decimal): Decimal {
  // BR-005: 0.03%, capped at RM1,000 per contract.
  const fee = roundMyr(initialAmount.times(CLEARING_FEE_RATE));
  return Decimal.min(fee, CLEARING_FEE_CAP);
}

export function computeStampDuty(initialAmount: Decimal): Decimal {
  // BR-006: ROUNDUP(initial_amount / 1000, 0) x RM1, RM1 minimum.
  const blocks = initialAmount.dividedBy(1000).ceil();
  const duty = roundMyr(blocks);
  return Decimal.max(duty, STAMP_DUTY_MINIMUM);
}

export function calculateLotFees(
  shares: number,
  purchasePrice: string,
  broker: BrokerConfigResponse
): FeeBreakdown {
  // BR-007: all-in cost = sum of the four components, each individually
  // rounded before summing.
  const initialAmount = computeInitialAmount(shares, purchasePrice);
  const brokerageFee = computeBrokerageFee(initialAmount, broker);
  const clearingFee = computeClearingFee(initialAmount);
  const stampDuty = computeStampDuty(initialAmount);
  const allInCost = roundMyr(initialAmount.plus(brokerageFee).plus(clearingFee).plus(stampDuty));
  return { initialAmount, brokerageFee, clearingFee, stampDuty, allInCost };
}

export function formatMyr(value: Decimal): string {
  return (
    "RM " +
    value.toNumber().toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  );
}

export function brokerNote(broker: BrokerConfigResponse, initialAmount: Decimal): string {
  if (broker.fee_type === "flat") {
    return `${broker.name}: ${formatMyr(new Decimal(broker.flat_fee ?? "0"))} flat per trade`;
  }
  const rate = new Decimal(broker.rate ?? "0");
  const minimum = new Decimal(broker.minimum_fee ?? "0");
  const raw = roundMyr(initialAmount.times(rate));
  const ratePct = rate.times(100).toFixed(2);
  const minNote = raw.lessThan(minimum) ? ` → minimum ${formatMyr(minimum)} applied` : "";
  return `${broker.name}: ${ratePct}% of ${formatMyr(initialAmount)}${minNote}`;
}
