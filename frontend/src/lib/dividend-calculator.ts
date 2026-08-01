/**
 * Client-side dividend total/yield preview. decimal.js only, mirroring
 * backend/app/portfolio/service.py's create_dividend_tranche exactly
 * (BR-025 rounding). Display-only (P-003): the form never submits this
 * computed total — only the raw per_share_amount/qualifying_shares inputs
 * the server uses to compute and store the authoritative total_amount.
 *
 * Yield is never returned by the server as a percentage at all (architecture
 * P0-API-001/FC-002 — see backend/app/portfolio/schemas.py::PortfolioResponse's
 * docstring) — it's always computed here, client-side, from the response's
 * total_dividend_income_ytd / total_all_in_cost fields.
 */

import Decimal from "decimal.js";

function roundMyr(value: Decimal): Decimal {
  // BR-025: round half away from zero to 2dp.
  return value.toDecimalPlaces(2, Decimal.ROUND_HALF_UP);
}

export function computeDividendTotal(perShareAmount: string, qualifyingShares: number): Decimal {
  return roundMyr(new Decimal(perShareAmount || "0").times(qualifyingShares || 0));
}

export function computeYieldPercent(incomeYtd: string, totalAllInCost: string): Decimal | null {
  const cost = new Decimal(totalAllInCost);
  if (cost.isZero()) return null;
  return new Decimal(incomeYtd).dividedBy(cost).times(100);
}

export function formatPercent(value: Decimal | null): string {
  if (value === null) return "—";
  return value.toDecimalPlaces(2, Decimal.ROUND_HALF_UP).toString() + "%";
}
