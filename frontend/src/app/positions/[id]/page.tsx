"use client";

import Decimal from "decimal.js";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthGate } from "@/components/auth/AuthGate";
import { AddLotDialog } from "@/components/portfolio/AddLotDialog";
import { EditLotDialog } from "@/components/portfolio/EditLotDialog";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { useBrokers } from "@/hooks/useBrokers";
import { useDashboard } from "@/hooks/useDashboard";
import { usePosition } from "@/hooks/usePosition";
import { apiFetch } from "@/lib/api";
import { brokerNote } from "@/lib/fee-calculator";
import { CATEGORY_TAG_STYLES } from "@/lib/category-tags";
import type { BrokerConfigResponse } from "@/lib/types";

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

function PositionDetailContent() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { position, isLoading, error, mutate: revalidatePosition } = usePosition(params.id);
  const { brokers } = useBrokers();
  const { mutate: revalidateDashboard } = useDashboard();
  const [addLotOpen, setAddLotOpen] = useState(false);
  const [editingLotId, setEditingLotId] = useState<string | null>(null);
  const [deletingLotId, setDeletingLotId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const [notice, setNotice] = useState<string | null>(searchParams.get("notice"));

  function findBroker(brokerId: string): BrokerConfigResponse | undefined {
    return brokers.find((b) => b.id === brokerId);
  }

  async function handleLotAdded(lotNotice: string) {
    await revalidatePosition();
    await revalidateDashboard();
    setNotice(lotNotice);
  }

  async function handleLotEdited(lotNotice: string) {
    await revalidatePosition();
    await revalidateDashboard();
    setNotice(lotNotice);
  }

  const editingLot = position?.lots.find((l) => l.id === editingLotId) ?? null;
  const deletingLot = position?.lots.find((l) => l.id === deletingLotId) ?? null;

  async function handleDeletePosition() {
    if (!position) return;
    await apiFetch(`/api/v1/portfolio/positions/${position.id}`, { method: "DELETE" });
    await revalidateDashboard();
    router.push("/dashboard");
  }

  async function handleDeleteLot() {
    if (!position || !deletingLot) return;
    await apiFetch(`/api/v1/portfolio/positions/${position.id}/lots/${deletingLot.id}`, { method: "DELETE" });
    await revalidatePosition();
    await revalidateDashboard();
    setNotice("Lot deleted.");
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
            {notice && (
              <div className="mb-4.5 flex items-start justify-between gap-3 rounded-lg border border-secondary bg-secondary px-3.5 py-3 text-[13px] text-secondary-foreground">
                <span>{notice}</span>
                <button
                  type="button"
                  onClick={() => setNotice(null)}
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
                    <span className="font-mono text-[13px] text-tertiary">{position.stock_code}</span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ${CATEGORY_TAG_STYLES[position.category_tag] ?? CATEGORY_TAG_STYLES.Dividend}`}
                    >
                      {position.category_tag}
                    </span>
                  </div>
                  {position.notes && <div className="mt-1 text-[13px] text-muted-foreground">{position.notes}</div>}
                </div>
                <Button variant="destructive" size="sm" onClick={() => setDeleteDialogOpen(true)}>
                  Delete Position
                </Button>
              </div>
              <div className="mt-4.5 flex flex-wrap gap-7 text-[13.5px]">
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                    Total shares
                  </div>
                  <div className="mt-0.5 font-semibold">{formatShares(position.total_shares)}</div>
                </div>
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                    Blended price
                  </div>
                  <div className="mt-0.5 font-semibold">{formatMoney(position.blended_purchase_price)}</div>
                </div>
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                    All-in cost
                  </div>
                  <div className="mt-0.5 font-semibold">{formatMoney(position.total_all_in_cost)}</div>
                </div>
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                    Current price
                  </div>
                  <div className="mt-0.5 font-semibold text-muted-foreground">—</div>
                </div>
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                    Income YTD
                  </div>
                  <div className="mt-0.5 font-semibold text-muted-foreground">—</div>
                </div>
                <div>
                  <div className="text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                    Unrealised P/L
                  </div>
                  <div className="mt-0.5 font-semibold text-muted-foreground">—</div>
                </div>
              </div>
            </div>

            <div className="mb-3 flex items-center justify-between">
              <div className="text-[15px] font-bold">Lots ({position.lots.length})</div>
              <button
                type="button"
                onClick={() => setAddLotOpen(true)}
                className="rounded-lg border border-[#C9D4FA] bg-card px-3.5 py-2 text-[13.5px] font-semibold text-primary hover:bg-accent focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2"
              >
                + Add Lot
              </button>
            </div>
            <div className="rounded-xl border border-border bg-card">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1060px] border-collapse text-[13.5px]">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="px-3.5 py-2.5 text-left text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        Lot
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        Shares
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        Price
                      </th>
                      <th className="px-3.5 py-2.5 text-left text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        Date
                      </th>
                      <th className="px-3.5 py-2.5 text-left text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        Broker
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        Initial
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        Brokerage
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        Clearing
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        Stamp
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        All-In Cost
                      </th>
                      <th className="px-3.5 py-2.5 text-right text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {position.lots.map((lot, index) => {
                      const broker = findBroker(lot.broker_id);
                      const brokerageTitle = broker
                        ? brokerNote(broker, new Decimal(lot.initial_amount))
                        : undefined;
                      return (
                        <tr key={lot.id} className="border-b border-[#F0F0ED] last:border-0 hover:bg-[#FAFAF8]">
                          <td className="px-3.5 py-3 font-semibold">{index + 1}</td>
                          <td className="px-3.5 py-3 text-right">{formatShares(lot.shares)}</td>
                          <td className="px-3.5 py-3 text-right">{formatMoney(lot.purchase_price)}</td>
                          <td className="px-3.5 py-3">{formatDate(lot.purchase_date)}</td>
                          <td className="px-3.5 py-3">{broker?.name ?? lot.broker_id}</td>
                          <td className="px-3.5 py-3 text-right">{formatMoney(lot.initial_amount)}</td>
                          <td className="px-3.5 py-3 text-right" title={brokerageTitle}>
                            {formatMoney(lot.brokerage_fee)}
                          </td>
                          <td className="px-3.5 py-3 text-right" title="0.03% of initial amount">
                            {formatMoney(lot.clearing_fee)}
                          </td>
                          <td className="px-3.5 py-3 text-right" title="RM1 per RM1,000 (rounded up)">
                            {formatMoney(lot.stamp_duty)}
                          </td>
                          <td className="px-3.5 py-3 text-right font-bold">{formatMoney(lot.all_in_cost)}</td>
                          <td className="px-3.5 py-3 text-right whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => setEditingLotId(lot.id)}
                              className="cursor-pointer rounded-[5px] px-1.5 py-1 text-[12.5px] font-semibold text-primary hover:bg-accent"
                            >
                              Edit
                            </button>
                            {position.lots.length > 1 && (
                              <button
                                type="button"
                                onClick={() => setDeletingLotId(lot.id)}
                                className="cursor-pointer rounded-[5px] px-1.5 py-1 text-[12.5px] font-semibold text-destructive hover:bg-destructive/10"
                              >
                                Delete
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="border-t border-[#F0F0ED] bg-[#FAFAF8] px-3.5 py-2.5 font-mono text-xs text-tertiary">
                brokerage per broker rule · clearing 0.03% · stamp duty RM1/RM1,000 (ROUNDUP) — hover a fee for its
                formula
              </div>
            </div>
          </>
        )}
      </main>

      {position && (
        <AddLotDialog open={addLotOpen} onOpenChange={setAddLotOpen} position={position} onLotAdded={handleLotAdded} />
      )}
      {position && editingLot && (
        <EditLotDialog
          open={Boolean(editingLotId)}
          onOpenChange={(next) => {
            if (!next) setEditingLotId(null);
          }}
          position={position}
          lot={editingLot}
          revalidatePosition={revalidatePosition}
          onSaved={handleLotEdited}
        />
      )}
      {position && (
        <ConfirmDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          title="Delete position?"
          description={`This will delete ${position.stock_name} and all ${position.lots.length} lot${position.lots.length === 1 ? "" : "s"} and ${position.dividend_tranches.length} dividend record${position.dividend_tranches.length === 1 ? "" : "s"}. This cannot be undone.`}
          confirmLabel="Delete Position"
          onConfirm={handleDeletePosition}
        />
      )}
      {position && deletingLot && (
        <ConfirmDialog
          open={Boolean(deletingLotId)}
          onOpenChange={(next) => {
            if (!next) setDeletingLotId(null);
          }}
          title="Delete this lot?"
          description={`This will delete the ${deletingLot.shares.toLocaleString("en-MY")}-share lot purchased on ${formatDate(deletingLot.purchase_date)}. This cannot be undone.`}
          confirmLabel="Delete Lot"
          onConfirm={handleDeleteLot}
        />
      )}
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
