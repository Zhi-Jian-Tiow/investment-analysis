"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthGate } from "@/components/auth/AuthGate";
import { useBrokers } from "@/hooks/useBrokers";
import { usePosition } from "@/hooks/usePosition";

function formatMoney(value: string): string {
  return "RM " + parseFloat(value).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatShares(value: number): string {
  return value.toLocaleString("en-MY");
}

function formatDate(value: string): string {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const [y, m, d] = value.split("-").map((part) => parseInt(part, 10));
  return `${d} ${months[m - 1]} ${y}`;
}

const TAG_STYLES: Record<string, string> = {
  Dividend: "bg-[#E7F5EE] text-[#177A4E]",
  Volatile: "bg-secondary text-secondary-foreground",
  Growth: "bg-accent text-accent-foreground",
};

function PositionDetailContent() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const { position, isLoading, error } = usePosition(params.id);
  const { brokers } = useBrokers();
  const [noticeVisible, setNoticeVisible] = useState(Boolean(searchParams.get("notice")));
  const notice = searchParams.get("notice");

  function brokerName(brokerId: string): string {
    return brokers.find((b) => b.id === brokerId)?.name ?? brokerId;
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-card">
        <div className="mx-auto flex h-[58px] max-w-[1200px] items-center gap-4 px-6">
          <Link href="/dashboard" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
              B
            </div>
            <div className="text-[16.5px] font-bold tracking-tight text-foreground">BursaTrack</div>
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1200px] px-6 py-6">
        <Link href="/dashboard" className="mb-3.5 inline-block text-[13.5px]">
          ← Back to Portfolio
        </Link>

        {error && error.status === 404 && (
          <div className="rounded-xl border border-border bg-card p-10 text-center">
            <h1 className="mb-2 text-lg font-bold text-foreground">Position not found</h1>
            <p className="text-sm text-muted-foreground">
              This position doesn&apos;t exist or you don&apos;t have access to it.
            </p>
          </div>
        )}

        {isLoading && (
          <div className="rounded-xl border border-border bg-card p-10 text-center text-sm text-muted-foreground">
            Loading position…
          </div>
        )}

        {position && (
          <>
            {notice && noticeVisible && (
              <div className="mb-4.5 flex items-start justify-between gap-3 rounded-lg border border-secondary bg-secondary px-3.5 py-3 text-[13px] text-secondary-foreground">
                <span>{notice}</span>
                <button
                  type="button"
                  onClick={() => setNoticeVisible(false)}
                  className="cursor-pointer font-semibold hover:no-underline"
                >
                  Dismiss
                </button>
              </div>
            )}

            <div className="mb-4.5 rounded-xl border border-border bg-card px-6 py-5.5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2.5">
                    <h1 className="m-0 text-2xl font-bold tracking-tight text-foreground">
                      {position.stock_name}
                    </h1>
                    <span className="font-mono text-[13px] text-muted-foreground">{position.stock_code}</span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ${TAG_STYLES[position.category_tag] ?? TAG_STYLES.Dividend}`}
                    >
                      {position.category_tag}
                    </span>
                  </div>
                  {position.notes && <div className="mt-1 text-[13px] text-muted-foreground">{position.notes}</div>}
                </div>
              </div>
              <div className="mt-4.5 flex flex-wrap gap-7 text-[13.5px]">
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                    Total shares
                  </div>
                  <div className="mt-0.5 font-semibold">{formatShares(position.total_shares)}</div>
                </div>
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                    Blended price
                  </div>
                  <div className="mt-0.5 font-semibold">{formatMoney(position.blended_purchase_price)}</div>
                </div>
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                    All-in cost
                  </div>
                  <div className="mt-0.5 font-semibold">{formatMoney(position.total_all_in_cost)}</div>
                </div>
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                    Current price
                  </div>
                  <div className="mt-0.5 font-semibold text-muted-foreground">—</div>
                </div>
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                    Income YTD
                  </div>
                  <div className="mt-0.5 font-semibold text-muted-foreground">—</div>
                </div>
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                    Unrealised P/L
                  </div>
                  <div className="mt-0.5 font-semibold text-muted-foreground">—</div>
                </div>
              </div>
            </div>

            <div className="mb-3 text-[15px] font-bold">Lots ({position.lots.length})</div>
            <div className="rounded-xl border border-border bg-card">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[920px] border-collapse text-[13.5px]">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="px-3.5 py-2.5 text-left text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                        Shares
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                        Price
                      </th>
                      <th className="px-3.5 py-2.5 text-left text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                        Date
                      </th>
                      <th className="px-3.5 py-2.5 text-left text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                        Broker
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                        Initial
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                        Brokerage
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                        Clearing
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                        Stamp
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
                        All-In Cost
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {position.lots.map((lot) => (
                      <tr key={lot.id} className="border-b border-[#F0F0ED] last:border-0">
                        <td className="px-3.5 py-3 text-right">{formatShares(lot.shares)}</td>
                        <td className="px-3.5 py-3 text-right">{formatMoney(lot.purchase_price)}</td>
                        <td className="px-3.5 py-3">{formatDate(lot.purchase_date)}</td>
                        <td className="px-3.5 py-3">{brokerName(lot.broker_id)}</td>
                        <td className="px-3.5 py-3 text-right">{formatMoney(lot.initial_amount)}</td>
                        <td className="px-3.5 py-3 text-right">{formatMoney(lot.brokerage_fee)}</td>
                        <td className="px-3.5 py-3 text-right">{formatMoney(lot.clearing_fee)}</td>
                        <td className="px-3.5 py-3 text-right">{formatMoney(lot.stamp_duty)}</td>
                        <td className="px-3.5 py-3 text-right font-bold">{formatMoney(lot.all_in_cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="border-t border-[#F0F0ED] bg-[#FAFAF8] px-3.5 py-2.5 font-mono text-xs text-muted-foreground">
                brokerage per broker rule · clearing 0.03% · stamp duty RM1/RM1,000 (ROUNDUP)
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default function PositionDetailPage() {
  return (
    <Suspense fallback={null}>
      <AuthGate>
        <PositionDetailContent />
      </AuthGate>
    </Suspense>
  );
}
