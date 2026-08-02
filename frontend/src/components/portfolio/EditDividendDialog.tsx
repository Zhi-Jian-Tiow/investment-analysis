"use client";

import { useEffect, useMemo, useState } from "react";
import Decimal from "decimal.js";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiFetch } from "@/lib/api";
import { computeDividendTotal, computeYieldPercent, formatPercent, sharesEligibleAsOf } from "@/lib/dividend-calculator";
import {
  validateDividendPaymentDate,
  validateExDividendDate,
  validatePerShareAmount,
  validateQualifyingShares,
} from "@/lib/dividend-validation";
import { formatMyr } from "@/lib/fee-calculator";
import type { DividendTrancheResponse, PositionResponse } from "@/lib/types";

// Same conflict copy as EditLotDialog (FE-2.3's AC) — not the backend's own
// generic 409 message, which BE-2.3/BE-3.2 both use identically.
const CONFLICT_MESSAGE =
  "This record was updated by another session. Please refresh the page to see the latest values before making changes.";

interface FieldErrors {
  perShareAmount?: string;
  qualifyingShares?: string;
  paymentDate?: string;
  exDividendDate?: string;
}

interface EditDividendDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  position: PositionResponse;
  tranche: DividendTrancheResponse;
  revalidatePosition: () => Promise<PositionResponse | undefined>;
  revalidateDashboard: () => Promise<unknown>;
  onSaved: (notice: string) => void;
}

export function EditDividendDialog({
  open,
  onOpenChange,
  position,
  tranche,
  revalidatePosition,
  revalidateDashboard,
  onSaved,
}: EditDividendDialogProps) {
  const [perShareAmount, setPerShareAmount] = useState(tranche.per_share_amount);
  const [qualifyingShares, setQualifyingShares] = useState(String(tranche.qualifying_shares));
  const [paymentDate, setPaymentDate] = useState(tranche.payment_date);
  const [exDividendDate, setExDividendDate] = useState(tranche.ex_dividend_date ?? "");
  const [version, setVersion] = useState(tranche.version);

  const [errors, setErrors] = useState<FieldErrors>({});
  const [genericError, setGenericError] = useState<string | null>(null);
  const [versionConflict, setVersionConflict] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // `version` is tracked in state but never rendered as an input — travels
  // transparently with every PATCH, same contract as EditLotDialog.
  useEffect(() => {
    if (!open) return;
    setPerShareAmount(tranche.per_share_amount);
    setQualifyingShares(String(tranche.qualifying_shares));
    setPaymentDate(tranche.payment_date);
    setExDividendDate(tranche.ex_dividend_date ?? "");
    setVersion(tranche.version);
    setErrors({});
    setGenericError(null);
    setVersionConflict(false);
  }, [open, tranche]);

  const preview = useMemo(() => {
    const shares = parseInt(qualifyingShares, 10);
    if (!perShareAmount || !shares || shares <= 0) return null;
    try {
      return computeDividendTotal(perShareAmount, shares);
    } catch {
      return null;
    }
  }, [perShareAmount, qualifyingShares]);

  const qualifyingSharesDiffers =
    qualifyingShares !== "" && parseInt(qualifyingShares, 10) !== position.total_shares;

  // BR-027: bounded by shares owned as of the ex-date (falling back to
  // payment date) — not the position's live total.
  const referenceDate = exDividendDate || paymentDate;
  const eligibleShares = sharesEligibleAsOf(position.lots, referenceDate);

  function validate(): boolean {
    const next: FieldErrors = {
      perShareAmount: validatePerShareAmount(perShareAmount) ?? undefined,
      qualifyingShares:
        validateQualifyingShares(qualifyingShares, eligibleShares, position.total_shares, referenceDate) ?? undefined,
      paymentDate: validateDividendPaymentDate(paymentDate) ?? undefined,
      exDividendDate: validateExDividendDate(exDividendDate, paymentDate) ?? undefined,
    };
    setErrors(next);
    return !Object.values(next).some(Boolean);
  }

  async function handleSave() {
    setGenericError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      const updated = await apiFetch<DividendTrancheResponse>(`/api/v1/portfolio/dividends/${tranche.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          per_share_amount: perShareAmount,
          qualifying_shares: parseInt(qualifyingShares, 10),
          payment_date: paymentDate,
          ex_dividend_date: exDividendDate || null,
          version,
        }),
      });

      onOpenChange(false);

      const freshPosition = await revalidatePosition();
      await revalidateDashboard();

      const yieldPercent = freshPosition
        ? formatPercent(computeYieldPercent(freshPosition.total_dividend_income_ytd, freshPosition.total_all_in_cost))
        : "—";
      onSaved(
        `${updated.tranche_label} dividend updated — now ${formatMyr(new Decimal(updated.total_amount))}. ` +
          `Position yield is now ${yieldPercent}.`
      );
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setVersionConflict(true);
        } else if (err.fields?.length) {
          setErrors({
            perShareAmount: err.fieldError("per_share_amount"),
            qualifyingShares: err.fieldError("qualifying_shares"),
            paymentDate: err.fieldError("payment_date"),
            exDividendDate: err.fieldError("ex_dividend_date"),
          });
        } else {
          setGenericError(err.message);
        }
      } else {
        setGenericError("Something went wrong. Please check your connection and try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const fresh = await revalidatePosition();
      const freshTranche = fresh?.dividend_tranches.find((t) => t.id === tranche.id);
      if (freshTranche) {
        setPerShareAmount(freshTranche.per_share_amount);
        setQualifyingShares(String(freshTranche.qualifying_shares));
        setPaymentDate(freshTranche.payment_date);
        setExDividendDate(freshTranche.ex_dividend_date ?? "");
        setVersion(freshTranche.version);
      }
      setVersionConflict(false);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[480px] p-0 sm:max-w-[480px]">
        <div className="flex items-center justify-between border-b border-border px-6 py-5">
          <DialogTitle className="text-[17px] font-bold">
            Edit Dividend — {tranche.tranche_label} tranche
          </DialogTitle>
        </div>

        {versionConflict && (
          <div className="mx-6 mt-4 flex items-start gap-2.5 rounded-lg border border-[#F0D9A6] bg-[#FFF6E3] px-3.5 py-3 text-[13px] text-[#8A5A00]">
            <span>⚠</span>
            <div className="flex-1">
              <div>{CONFLICT_MESSAGE}</div>
              <button
                type="button"
                onClick={handleRefresh}
                disabled={refreshing}
                className="mt-1.5 cursor-pointer font-semibold underline underline-offset-2 disabled:cursor-not-allowed"
              >
                {refreshing ? "Refreshing…" : "Refresh"}
              </button>
            </div>
          </div>
        )}

        {genericError && (
          <div className="mx-6 mt-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-[13px] text-destructive">
            {genericError}
          </div>
        )}

        <div className="px-6 py-5.5">
          <Label htmlFor="ed-per-share" className="mb-1.5 text-[13px] font-semibold">
            Per share (RM) <span className="text-destructive">*</span>
          </Label>
          <Input
            id="ed-per-share"
            inputMode="decimal"
            value={perShareAmount}
            onChange={(e) => setPerShareAmount(e.target.value)}
            disabled={versionConflict}
            aria-invalid={Boolean(errors.perShareAmount)}
          />
          {errors.perShareAmount && <p className="mt-1 text-xs text-destructive">{errors.perShareAmount}</p>}

          <div className="h-4" />

          <Label htmlFor="ed-qualifying-shares" className="mb-1.5 text-[13px] font-semibold">
            Qualifying shares
          </Label>
          <Input
            id="ed-qualifying-shares"
            inputMode="numeric"
            value={qualifyingShares}
            onChange={(e) => setQualifyingShares(e.target.value)}
            disabled={versionConflict}
            aria-invalid={Boolean(errors.qualifyingShares)}
          />
          <p className="mt-1.5 text-xs text-tertiary">
            This is the number of shares you held before the ex-dividend date. Change this if you held fewer shares
            than your current total.
          </p>
          {errors.qualifyingShares && <p className="mt-1.5 text-xs text-destructive">{errors.qualifyingShares}</p>}
          {qualifyingSharesDiffers && !errors.qualifyingShares && (
            <div className="mt-2 rounded-[7px] border border-[#F0D9A6] bg-[#FFF6E3] px-2.5 py-[7px] text-xs text-[#8A5A00]">
              Using {parseInt(qualifyingShares, 10).toLocaleString("en-MY")} qualifying shares (not your current
              total of {position.total_shares.toLocaleString("en-MY")})
            </div>
          )}

          <div className="h-4" />

          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="ed-payment-date" className="mb-1.5 text-[13px] font-semibold">
                Payment date <span className="text-destructive">*</span>
              </Label>
              <Input
                id="ed-payment-date"
                type="date"
                value={paymentDate}
                onChange={(e) => setPaymentDate(e.target.value)}
                disabled={versionConflict}
                aria-invalid={Boolean(errors.paymentDate)}
              />
              {errors.paymentDate && <p className="mt-1 text-xs text-destructive">{errors.paymentDate}</p>}
            </div>
            <div className="flex-1">
              <Label htmlFor="ed-ex-date" className="mb-1.5 text-[13px] font-semibold">
                Ex-date <span className="font-normal text-tertiary">(optional)</span>
              </Label>
              <Input
                id="ed-ex-date"
                type="date"
                value={exDividendDate}
                onChange={(e) => setExDividendDate(e.target.value)}
                disabled={versionConflict}
                aria-invalid={Boolean(errors.exDividendDate)}
              />
              {errors.exDividendDate && <p className="mt-1 text-xs text-destructive">{errors.exDividendDate}</p>}
            </div>
          </div>

          <div className="mt-4.5 rounded-[10px] border border-[#D5DEFC] bg-accent px-4 py-3.5" aria-live="polite">
            <div className="text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
              Total received this tranche
            </div>
            <div className="mt-0.5 text-xl font-bold text-secondary-foreground">
              {preview ? formatMyr(preview) : "—"}
            </div>
            <div className="mt-0.5 font-mono text-xs text-muted-foreground">
              {perShareAmount || "0.00"} × {qualifyingShares || "0"} shares
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2.5 border-t border-border px-6 py-4">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" onClick={handleSave} disabled={submitting || versionConflict}>
            {submitting ? "Saving…" : "Save Changes"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
