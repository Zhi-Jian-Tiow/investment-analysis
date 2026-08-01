"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthGate } from "@/components/auth/AuthGate";
import { VerifyBanner } from "@/components/dashboard/VerifyBanner";
import { AddPositionDialog } from "@/components/portfolio/AddPositionDialog";
import { Button } from "@/components/ui/button";
import { useDashboard } from "@/hooks/useDashboard";
import { useAuth } from "@/lib/auth-context";
import { CATEGORY_TAG_STYLES } from "@/lib/category-tags";

function formatMoney(value: string): string {
  return "RM " + parseFloat(value).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatShares(value: number): string {
  return value.toLocaleString("en-MY");
}

function DashboardContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const { portfolio, positions, isLoading } = useDashboard();
  const [addPositionOpen, setAddPositionOpen] = useState(false);

  if (!user) return null; // AuthGate guarantees this, but keeps TS happy

  async function handleLogout() {
    await logout();
    router.push("/");
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-card">
        <div className="mx-auto flex h-[58px] max-w-[1200px] items-center gap-4 px-6">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
              B
            </div>
            <div className="text-[16.5px] font-bold tracking-tight text-foreground">BursaTrack</div>
          </div>
          <div className="flex-1" />
          <button type="button" onClick={handleLogout} className="cursor-pointer text-xs text-muted-foreground">
            Log out
          </button>
          <div className="flex h-[34px] w-[34px] items-center justify-center rounded-full border border-[#D5DEFC] bg-secondary text-xs font-bold text-secondary-foreground">
            {user.email.slice(0, 2).toUpperCase()}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1200px] px-6 py-6">
        {!user.email_verified && <VerifyBanner />}

        <div className="mb-4.5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="m-0 text-[22px] font-bold tracking-tight text-foreground">Portfolio</h1>
            <div className="mt-1 text-[13px] text-muted-foreground">
              {portfolio ? `${positions.length} position${positions.length === 1 ? "" : "s"}` : "Loading…"}
            </div>
          </div>
          <Button onClick={() => setAddPositionOpen(true)}>+ Add Position</Button>
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
              <div className="mt-1 text-xs text-tertiary">Dividend tracking arrives in a later epic</div>
            </div>
            <div className="rounded-xl border border-border bg-card px-5 py-4.5">
              <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">Blended Yield</div>
              <div className="mt-1.5 text-2xl font-bold tracking-tight text-muted-foreground">—</div>
              <div className="mt-1 text-xs text-tertiary">Income ÷ all-in cost — needs dividend tracking</div>
            </div>
            <div className="rounded-xl border border-border bg-card px-5 py-4.5">
              <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">Next Dividend</div>
              <div className="mt-1.5 text-[16.5px] font-bold text-muted-foreground">—</div>
              <div className="mt-1 text-xs text-tertiary">Dividend calendar arrives in a later epic</div>
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
              <table className="w-full min-w-[860px] border-collapse text-[13.5px]">
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-3.5 py-3 text-left text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                      Stock
                    </th>
                    <th className="px-3.5 py-3 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                      Shares
                    </th>
                    <th className="px-3.5 py-3 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                      Blended Price
                    </th>
                    <th className="px-3.5 py-3 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                      All-In Cost
                    </th>
                    <th className="px-3.5 py-3 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                      Current Price
                    </th>
                    <th className="px-3.5 py-3 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                      Income YTD
                    </th>
                    <th className="px-3.5 py-3 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                      Yield
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((position) => (
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
                      <td className="px-3.5 py-3 text-right text-muted-foreground">—</td>
                      <td className="px-3.5 py-3 text-right text-muted-foreground">—</td>
                      <td className="px-3.5 py-3 text-right text-muted-foreground">—</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="border-t border-[#F0F0ED] bg-[#FAFAF8] px-3.5 py-2.5 font-mono text-xs text-tertiary">
              Current price, income, and yield require the price-feed and dividend features (later epics).
            </div>
          </div>
        )}
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
