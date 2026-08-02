"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";

import { AuthGate } from "@/components/auth/AuthGate";
import { VerifyBanner } from "@/components/dashboard/VerifyBanner";
import { AppHeader } from "@/components/layout/AppHeader";
import { AddPositionDialog } from "@/components/portfolio/AddPositionDialog";
import { Button } from "@/components/ui/button";
import { useDashboard } from "@/hooks/useDashboard";
import { useDividendCalendar } from "@/hooks/useDividendCalendar";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { CATEGORY_TAG_STYLES } from "@/lib/category-tags";
import { STALE_THRESHOLD_MS } from "@/lib/constants";
import { computeYieldPercent, formatPercent } from "@/lib/dividend-calculator";
import type { PositionSummaryResponse } from "@/lib/types";

const SORT_STORAGE_KEY = "bursatrack:dashboard:sort";

type SortKey = "name" | "shares" | "avg" | "cost" | "price" | "value" | "pl" | "income" | "yield";

interface SortState {
  key: SortKey;
  dir: 1 | -1;
}

// BAS US-014: default sort is yield descending.
const DEFAULT_SORT: SortState = { key: "yield", dir: -1 };

const HEADERS: { key: SortKey; label: string; align: "left" | "right" }[] = [
  { key: "name", label: "Stock", align: "left" },
  { key: "shares", label: "Shares", align: "right" },
  { key: "avg", label: "Avg Price", align: "right" },
  { key: "cost", label: "All-In Cost", align: "right" },
  { key: "price", label: "Price", align: "right" },
  { key: "value", label: "Mkt Value", align: "right" },
  { key: "pl", label: "P / L", align: "right" },
  { key: "income", label: "Income YTD", align: "right" },
  { key: "yield", label: "Yield", align: "right" },
];

function formatMoney(value: string): string {
  return "RM " + parseFloat(value).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatMoneyOrDash(value: string | null): string {
  return value === null ? "—" : formatMoney(value);
}

function formatShares(value: number): string {
  return value.toLocaleString("en-MY");
}

function formatDate(value: string): string {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const [y, m, d] = value.split("-").map((part) => parseInt(part, 10));
  return `${d} ${months[m - 1]} ${y}`;
}

// EX-001's "[last successful refresh timestamp]" — date + time, in the
// viewer's local timezone (unlike formatDate, which works off a plain
// YYYY-MM-DD calendar date with no timezone to resolve).
function formatDateTime(value: string): string {
  const d = new Date(value);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const datePart = `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
  const timePart = d.toLocaleTimeString("en-MY", { hour: "numeric", minute: "2-digit" });
  return `${datePart}, ${timePart}`;
}

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formatManualBadgeTime(value: string): string {
  return new Date(value).toLocaleTimeString("en-MY", { hour: "numeric", minute: "2-digit" });
}

function positionYieldPercent(position: PositionSummaryResponse) {
  return computeYieldPercent(position.total_dividend_income_ytd, position.total_all_in_cost);
}

function isStale(position: PositionSummaryResponse): boolean {
  // EC-005: no price ever retrieved is a different state from a stale one —
  // only flag staleness when a refresh actually happened.
  if (!position.price_last_refreshed_at) return false;
  return Date.now() - new Date(position.price_last_refreshed_at).getTime() > STALE_THRESHOLD_MS;
}

function sortValue(position: PositionSummaryResponse, key: SortKey): number | string | null {
  switch (key) {
    case "name":
      return position.stock_name;
    case "shares":
      return position.total_shares;
    case "avg":
      return parseFloat(position.blended_purchase_price);
    case "cost":
      return parseFloat(position.total_all_in_cost);
    case "price":
      return position.current_price === null ? null : parseFloat(position.current_price);
    case "value":
      return position.current_market_value === null ? null : parseFloat(position.current_market_value);
    case "pl":
      return position.unrealised_pnl === null ? null : parseFloat(position.unrealised_pnl);
    case "income":
      return parseFloat(position.total_dividend_income_ytd);
    case "yield": {
      const y = positionYieldPercent(position);
      return y === null ? null : y.toNumber();
    }
  }
}

function compareRows(a: PositionSummaryResponse, b: PositionSummaryResponse, sort: SortState): number {
  const va = sortValue(a, sort.key);
  const vb = sortValue(b, sort.key);
  // Nulls (no data yet) always sort last, regardless of direction — avoids
  // "—" rows jumping to the top just because a direction toggle flipped.
  if (va === null && vb === null) return 0;
  if (va === null) return 1;
  if (vb === null) return -1;
  if (va < vb) return -1 * sort.dir;
  if (va > vb) return 1 * sort.dir;
  return 0;
}

function DashboardContent() {
  const { user } = useAuth();
  const { portfolio, positions, isLoading, mutate } = useDashboard();
  const [addPositionOpen, setAddPositionOpen] = useState(false);
  const [sort, setSort] = useState<SortState>(DEFAULT_SORT);
  const [overrideCode, setOverrideCode] = useState<string | null>(null);
  const [overrideValue, setOverrideValue] = useState("");
  const [overrideError, setOverrideError] = useState<string | null>(null);
  const [overrideSaving, setOverrideSaving] = useState(false);

  const currentYear = new Date().getFullYear();
  const { tranches } = useDividendCalendar(currentYear);

  // BAS US-014: "Sort preference persists across the session" — sessionStorage
  // (not localStorage), so it resets with a fresh browser tab, not forever.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(SORT_STORAGE_KEY);
      if (raw) setSort(JSON.parse(raw) as SortState);
    } catch {
      // Corrupt/blocked storage — fall back to the default sort silently.
    }
  }, []);

  function handleSort(key: SortKey) {
    setSort((prev) => {
      const next: SortState = prev.key === key ? { key, dir: (prev.dir * -1) as 1 | -1 } : { key, dir: key === "name" ? 1 : -1 };
      try {
        sessionStorage.setItem(SORT_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Ignore storage failures — sort still works for this render.
      }
      return next;
    });
  }

  function openOverride(position: PositionSummaryResponse) {
    setOverrideCode(position.stock_code);
    setOverrideValue("");
    setOverrideError(null);
  }

  function closeOverride() {
    setOverrideCode(null);
    setOverrideValue("");
    setOverrideError(null);
  }

  async function saveOverride(position: PositionSummaryResponse) {
    const trimmed = overrideValue.trim();
    const parsed = parseFloat(trimmed);
    if (!trimmed || !(parsed > 0)) {
      setOverrideError("Price must be greater than zero");
      return;
    }
    setOverrideSaving(true);
    setOverrideError(null);
    try {
      await apiFetch("/api/v1/pricing/manual-override", {
        method: "POST",
        body: JSON.stringify({
          stock_code: position.stock_code,
          price: trimmed,
          trading_date: todayIso(),
        }),
      });
      closeOverride();
      await mutate();
    } catch (err) {
      setOverrideError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setOverrideSaving(false);
    }
  }

  if (!user) return null; // AuthGate guarantees this, but keeps TS happy

  const isReadOnly = user.account_status === "trial_expired";
  const staleList = positions.filter(isStale);
  const isCompleteOutage = positions.length > 0 && staleList.length === positions.length;
  const sortedPositions = positions.slice().sort((a, b) => compareRows(a, b, sort));
  const blendedYield = portfolio ? computeYieldPercent(portfolio.total_dividend_income_ytd, portfolio.total_all_in_cost) : null;
  const trancheCount = tranches.length;
  const upcomingDividend = tranches
    .filter((t) => !t.is_paid)
    .slice()
    .sort((a, b) => (a.payment_date < b.payment_date ? -1 : 1))[0];

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />

      <main className="mx-auto max-w-[1200px] px-6 py-6">
        {!user.email_verified && <VerifyBanner />}

        {isReadOnly && (
          <div className="mb-4.5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#C9D4FA] bg-secondary px-4 py-3 text-[13.5px] text-secondary-foreground">
            <span>Your free trial has ended. Subscribe to continue adding positions and logging dividends. Your data is read-only until then.</span>
          </div>
        )}

        {staleList.length > 0 && (
          <div className="mb-4.5 flex items-center gap-2.5 rounded-lg border border-[#F0D9A6] bg-[#FFF6E3] px-4 py-3 text-[13.5px] text-[#8A5A00]">
            <span>⚠</span>
            {isCompleteOutage ? (
              // EX-001: complete outage — no stocks priced at all.
              <span>
                Price data unavailable — showing prices as of{" "}
                {portfolio?.last_price_refresh_at ? formatDateTime(portfolio.last_price_refresh_at) : "the last refresh"}.
                Update prices manually below.
              </span>
            ) : (
              // EX-002: partial failure — some but not all stocks affected.
              <span>
                Price data unavailable for {staleList.length} stock{staleList.length === 1 ? "" : "s"} —{" "}
                {staleList.map((p) => p.stock_name).join(", ")}. Showing last known prices.
              </span>
            )}
          </div>
        )}

        <div className="mb-4.5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="m-0 text-[22px] font-bold tracking-tight text-foreground">Portfolio</h1>
            <div className="mt-1 flex items-center gap-1.5 text-[13px] text-muted-foreground">
              {portfolio?.last_price_refresh_at ? (
                <>
                  <span className={`inline-block h-2 w-2 rounded-full ${staleList.length > 0 ? "bg-[#E0A526]" : "bg-[#17A05E]"}`} />
                  <span>Last refreshed: {formatDateTime(portfolio.last_price_refresh_at)}</span>
                </>
              ) : (
                <span>{portfolio ? `${positions.length} position${positions.length === 1 ? "" : "s"} · prices not yet refreshed` : "Loading…"}</span>
              )}
            </div>
          </div>
          {!isReadOnly && <Button onClick={() => setAddPositionOpen(true)}>+ Add Position</Button>}
        </div>

        {portfolio && (
          <div className="mb-5.5 grid grid-cols-[repeat(auto-fit,minmax(215px,1fr))] gap-3.5">
            <div className="rounded-xl border border-border bg-card px-5 py-4.5">
              <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                Total All-In Cost
              </div>
              <div className="mt-1.5 text-2xl font-bold tracking-tight">
                {formatMoney(portfolio.total_all_in_cost)}
              </div>
              <div className="mt-1 text-xs text-tertiary">
                {positions.length} position{positions.length === 1 ? "" : "s"}
              </div>
            </div>
            <div className="rounded-xl border border-border bg-card px-5 py-4.5">
              <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                Dividend Income YTD
              </div>
              <div className="mt-1.5 text-2xl font-bold tracking-tight text-[#177A4E]">
                {formatMoney(portfolio.total_dividend_income_ytd)}
              </div>
              <div className="mt-1 text-xs text-tertiary">
                {trancheCount} tranche{trancheCount === 1 ? "" : "s"} logged in {currentYear}
              </div>
            </div>
            <div className="rounded-xl border border-border bg-card px-5 py-4.5">
              <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">Blended Yield</div>
              <div className="mt-1.5 text-2xl font-bold tracking-tight text-primary">{formatPercent(blendedYield)}</div>
              <div className="mt-1 text-xs text-tertiary">Income ÷ all-in cost</div>
            </div>
            <div className="rounded-xl border border-border bg-card px-5 py-4.5">
              <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">Next Dividend</div>
              {upcomingDividend ? (
                <>
                  <div className="mt-1.5 text-[16.5px] font-bold text-foreground">
                    {upcomingDividend.stock_name} · {formatMoney(upcomingDividend.total_amount)}
                  </div>
                  <div className="mt-1 text-xs text-tertiary">
                    {upcomingDividend.ex_dividend_date ? `Ex ${formatDate(upcomingDividend.ex_dividend_date)} · ` : ""}
                    Pays {formatDate(upcomingDividend.payment_date)}
                  </div>
                </>
              ) : (
                <>
                  <div className="mt-1.5 text-[16.5px] font-bold text-muted-foreground">—</div>
                  <div className="mt-1 text-xs text-tertiary">No upcoming payments logged</div>
                </>
              )}
            </div>
          </div>
        )}

        {isLoading && (
          <div className="rounded-xl border border-border bg-card p-10 text-center text-sm text-muted-foreground">
            Loading portfolio…
          </div>
        )}

        {!isLoading && positions.length === 0 && (
          <div className="rounded-xl border border-border bg-card p-10 text-center">
            <h2 className="mb-2 text-lg font-bold tracking-tight text-foreground">No positions yet</h2>
            <p className="mx-auto max-w-md text-sm text-muted-foreground">
              Add your first position to start tracking your true all-in cost and dividend income.
            </p>
          </div>
        )}

        {!isLoading && positions.length > 0 && (
          <div className="rounded-xl border border-border bg-card">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1040px] border-collapse text-[13.5px]">
                <thead>
                  <tr className="border-b border-border">
                    {HEADERS.map((h) => {
                      const active = sort.key === h.key;
                      return (
                        <th
                          key={h.key}
                          scope="col"
                          onClick={() => handleSort(h.key)}
                          className={`cursor-pointer px-3.5 py-3 text-[11.5px] font-semibold tracking-wide uppercase select-none hover:text-foreground ${
                            h.align === "left" ? "text-left" : "text-right"
                          } ${active ? "text-primary" : "text-tertiary"}`}
                        >
                          {h.label}
                          {active ? (sort.dir === -1 ? " ↓" : " ↑") : ""}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {sortedPositions.map((position) => {
                    const yieldPercent = positionYieldPercent(position);
                    const stale = isStale(position);
                    const pl = position.unrealised_pnl;
                    return (
                      <tr key={position.id} className="border-b border-[#F0F0ED] last:border-0 hover:bg-[#FAFAF8]">
                        <td className="px-3.5 py-3">
                          <Link
                            href={`/positions/${position.id}`}
                            className="flex items-center gap-2.5 text-foreground hover:no-underline"
                          >
                            <div>
                              <div className="font-semibold text-foreground">{position.stock_name}</div>
                              <div className="font-mono text-[11.5px] text-tertiary">{position.stock_code}</div>
                            </div>
                            <span
                              className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${CATEGORY_TAG_STYLES[position.category_tag] ?? CATEGORY_TAG_STYLES.Dividend}`}
                            >
                              {position.category_tag}
                            </span>
                          </Link>
                        </td>
                        <td className="px-3.5 py-3 text-right">{formatShares(position.total_shares)}</td>
                        <td className="px-3.5 py-3 text-right">{formatMoney(position.blended_purchase_price)}</td>
                        <td className="px-3.5 py-3 text-right">{formatMoney(position.total_all_in_cost)}</td>
                        <td className="px-3.5 py-3 text-right whitespace-nowrap">
                          {overrideCode === position.stock_code ? (
                            isReadOnly ? (
                              // EC-020: trial-expired accounts get a paywall
                              // prompt in place of the override input.
                              <span className="inline-flex items-center gap-2 text-[12px] text-[#8A5A00]">
                                Subscribe to override prices manually.
                                <button
                                  onClick={closeOverride}
                                  className="text-tertiary underline hover:text-foreground"
                                >
                                  Dismiss
                                </button>
                              </span>
                            ) : (
                              <span className="inline-flex flex-col items-end gap-1">
                                <span className="inline-flex items-center gap-1.5">
                                  <input
                                    autoFocus
                                    value={overrideValue}
                                    onChange={(e) => setOverrideValue(e.target.value)}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter") saveOverride(position);
                                      if (e.key === "Escape") closeOverride();
                                    }}
                                    inputMode="decimal"
                                    placeholder={position.current_price ?? "0.00"}
                                    disabled={overrideSaving}
                                    className="w-[74px] rounded-md border border-primary px-2 py-1 text-[13px] focus:ring-3 focus:ring-primary/15 focus:outline-none"
                                  />
                                  <button
                                    onClick={() => saveOverride(position)}
                                    disabled={overrideSaving}
                                    className="rounded-md bg-primary px-2.5 py-1 text-[12px] font-semibold text-primary-foreground hover:bg-[#2F41C4] disabled:opacity-60"
                                  >
                                    Save
                                  </button>
                                </span>
                                {overrideError && <span className="text-[11px] text-destructive">{overrideError}</span>}
                              </span>
                            )
                          ) : (
                            <>
                              <span className={position.current_price === null ? "text-muted-foreground" : ""}>
                                {formatMoneyOrDash(position.current_price)}
                              </span>
                              {stale && (
                                <button
                                  onClick={() => openOverride(position)}
                                  aria-label="Stale price. Click to enter price manually."
                                  className="ml-1.5 rounded-full border border-[#F0D9A6] bg-[#FFF6E3] px-2 py-0.5 text-[11px] font-semibold text-[#8A5A00] hover:bg-[#FBEBC7]"
                                >
                                  ⚠ Stale
                                </button>
                              )}
                              {!stale && position.price_source === "manual" && position.price_last_refreshed_at && (
                                <span className="ml-1.5 rounded-full border border-[#C9D4FA] bg-[#EBF0FF] px-2 py-0.5 text-[11px] font-semibold text-[#2B3EB8]">
                                  Manual · {formatManualBadgeTime(position.price_last_refreshed_at)}
                                </span>
                              )}
                            </>
                          )}
                        </td>
                        <td className="px-3.5 py-3 text-right">
                          <span className={position.current_market_value === null ? "text-muted-foreground" : ""}>
                            {formatMoneyOrDash(position.current_market_value)}
                          </span>
                        </td>
                        <td
                          className={`px-3.5 py-3 text-right font-semibold ${
                            pl === null ? "text-muted-foreground" : parseFloat(pl) >= 0 ? "text-[#177A4E]" : "text-destructive"
                          }`}
                        >
                          {formatMoneyOrDash(pl)}
                        </td>
                        <td className="px-3.5 py-3 text-right text-[#177A4E]">{formatMoney(position.total_dividend_income_ytd)}</td>
                        <td className="px-3.5 py-3 text-right font-bold">{formatPercent(yieldPercent)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="mt-3.5 text-center text-xs text-tertiary">
          BursaTrack is a portfolio tracking tool and does not provide financial advice. All calculations are informational only.
        </div>
      </main>

      <AddPositionDialog open={addPositionOpen} onOpenChange={setAddPositionOpen} />
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={null}>
      <AuthGate>
        <DashboardContent />
      </AuthGate>
    </Suspense>
  );
}
