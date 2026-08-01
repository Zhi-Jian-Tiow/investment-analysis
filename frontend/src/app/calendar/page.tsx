"use client";

import Link from "next/link";
import { Suspense } from "react";

import { AuthGate } from "@/components/auth/AuthGate";
import { AppHeader } from "@/components/layout/AppHeader";
import { useDividendCalendar } from "@/hooks/useDividendCalendar";
import type { DividendCalendarEntry } from "@/lib/types";

function formatMoney(value: string): string {
  return "RM " + parseFloat(value).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(value: string): string {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const [y, m, d] = value.split("-").map((part) => parseInt(part, 10));
  return `${d} ${months[m - 1]} ${y}`;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function CalendarContent() {
  const year = new Date().getFullYear();
  const { tranches, isLoading } = useDividendCalendar(year);

  const dueSoon = tranches.filter((t) => t.is_upcoming);
  const upcoming = tranches.filter((t) => !t.is_paid && !t.is_upcoming);
  const recentlyPaid = tranches
    .filter((t) => t.is_paid)
    .slice()
    .sort((a, b) => (a.payment_date < b.payment_date ? 1 : -1));

  const isEmpty = tranches.length === 0;

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />

      <main className="mx-auto max-w-[1200px] px-6 py-6">
        <h1 className="m-0 mb-1 text-[22px] font-bold tracking-tight text-foreground">Dividend Calendar</h1>
        <div className="mb-5 text-[13.5px] text-muted-foreground">
          Ex-dates and payment dates from your logged dividends. Today is {formatDate(todayIso())}.
        </div>

        {isLoading && (
          <div className="rounded-xl border border-border bg-card p-10 text-center text-sm text-muted-foreground">
            Loading calendar…
          </div>
        )}

        {!isLoading && isEmpty && (
          <div className="rounded-xl border border-border bg-card p-10 text-center">
            <p className="mx-auto max-w-md text-sm text-muted-foreground">
              Add ex-dates when logging dividends to see your payment schedule here.
            </p>
          </div>
        )}

        {!isLoading && !isEmpty && (
          <>
            {dueSoon.length > 0 && (
              <div className="mb-7">
                <div className="mb-2.5 text-[13px] font-bold tracking-wide text-[#8A5A00] uppercase">
                  Due in the next 7 days
                </div>
                <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
                  {dueSoon.map((entry) => (
                    <Link
                      key={entry.id}
                      href={`/positions/${entry.position_id}`}
                      className="block rounded-xl border border-[#F0D9A6] bg-[#FFFBF0] px-4.5 py-4 hover:no-underline"
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <div className="text-[15px] font-bold text-foreground">{entry.stock_name}</div>
                        {entry.ex_dividend_date && (
                          <span className="shrink-0 rounded-full bg-[#FFF1D0] px-2.5 py-0.5 text-[11px] font-bold text-[#8A5A00]">
                            Ex {formatDate(entry.ex_dividend_date)}
                          </span>
                        )}
                      </div>
                      <div className="mt-1.5 text-[12.5px] text-muted-foreground">
                        {entry.tranche_label} · RM {parseFloat(entry.per_share_amount).toFixed(4)}/share
                      </div>
                      <div className="mt-1.5 text-base font-bold text-[#177A4E]">{formatMoney(entry.total_amount)}</div>
                      <div className="mt-0.5 text-xs text-tertiary">Payment {formatDate(entry.payment_date)}</div>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              <CalendarList title="Upcoming" entries={upcoming} emptyText="No other upcoming dividends this year." />
              <CalendarList
                title="Recently paid"
                entries={recentlyPaid}
                emptyText="No dividends paid yet this year."
                paid
              />
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function CalendarList({
  title,
  entries,
  emptyText,
  paid = false,
}: {
  title: string;
  entries: DividendCalendarEntry[];
  emptyText: string;
  paid?: boolean;
}) {
  return (
    <div className="min-w-0">
      <div className="mb-2.5 text-[13px] font-bold tracking-wide text-muted-foreground uppercase">{title}</div>
      <div className="rounded-xl border border-border bg-card">
        {entries.length === 0 ? (
          <div className="px-4 py-5 text-[13px] text-muted-foreground">{emptyText}</div>
        ) : (
          entries.map((entry) => (
            <Link
              key={entry.id}
              href={`/positions/${entry.position_id}`}
              className="flex items-center justify-between gap-2.5 border-b border-[#F0F0ED] px-4 py-3.5 last:border-0 hover:bg-[#FAFAF8] hover:no-underline"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-foreground">
                  {entry.stock_name} <span className="font-normal text-tertiary">{entry.tranche_label}</span>
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {paid
                    ? `Paid ${formatDate(entry.payment_date)}`
                    : `Ex ${entry.ex_dividend_date ? formatDate(entry.ex_dividend_date) : "—"} · Pays ${formatDate(entry.payment_date)}`}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2.5">
                <div className="text-right">
                  <div className="font-bold text-[#177A4E]">{formatMoney(entry.total_amount)}</div>
                  {!paid && (
                    <div className="text-[11.5px] text-tertiary">RM {parseFloat(entry.per_share_amount).toFixed(4)}/share</div>
                  )}
                </div>
                {paid && (
                  <span className="shrink-0 rounded-full bg-[#E7F5EE] px-2.5 py-0.5 text-[11px] font-bold text-[#177A4E]">
                    Paid
                  </span>
                )}
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}

export default function CalendarPage() {
  return (
    <Suspense fallback={null}>
      <AuthGate>
        <CalendarContent />
      </AuthGate>
    </Suspense>
  );
}
