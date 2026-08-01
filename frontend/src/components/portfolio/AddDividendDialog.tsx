"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiFetch } from "@/lib/api";
import { computeDividendTotal, computeYieldPercent, formatPercent } from "@/lib/dividend-calculator";
import {
  validateDividendPaymentDate,
  validateExDividendDate,
  validatePerShareAmount,
  validateQualifyingShares,
} from "@/lib/dividend-validation";
import { formatMyr } from "@/lib/fee-calculator";
import type { CreateDividendRequest, DividendTrancheLabel, DividendTrancheResponse, PositionResponse } from "@/lib/types";
import Decimal from "decimal.js";

const ALL_LABELS: DividendTrancheLabel[] = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

interface FieldErrors {
  perShareAmount?: string;
  qualifyingShares?: string;
  paymentDate?: string;
  exDividendDate?: string;
}

interface AddDividendDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  position: PositionResponse;
  /** Re-fetches the position (BE-3.1's GET /positions/{id}) and returns the
   * fresh data — used to compute the post-submission yield from the
   * authoritative response, per this story's AC ("computed from the
   * response, not client-recomputed"). */
  revalidatePosition: () => Promise<PositionResponse | undefined>;
  revalidateDashboard: () => Promise<unknown>;
  onLogged: (notice: string) => void;
}

export function AddDividendDialog({
  open,
  onOpenChange,
  position,
  revalidatePosition,
  revalidateDashboard,
  onLogged,
}: AddDividendDialogProps) {
  const [perShareAmount, setPerShareAmount] = useState("");
  const [qualifyingShares, setQualifyingShares] = useState(String(position.total_shares));
  const [paymentDate, setPaymentDate] = useState(todayIso);
  const [exDividendDate, setExDividendDate] = useState("");

  const [errors, setErrors] = useState<FieldErrors>({});
  const [genericError, setGenericError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const year = paymentDate ? new Date(paymentDate).getFullYear() : new Date().getFullYear();
  const tranchesForYear = useMemo(
    () => position.dividend_tranches.filter((t) => t.year === year),
    [position.dividend_tranches, year]
  );
  const usedLabels = new Set(tranchesForYear.map((t) => t.tranche_label));
  const nextLabel = ALL_LABELS.find((label) => !usedLabels.has(label));
  const capReached = nextLabel === undefined;

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

  function resetForm() {
    setPerShareAmount("");
    setQualifyingShares(String(position.total_shares));
    setPaymentDate(todayIso());
    setExDividendDate("");
    setErrors({});
    setGenericError(null);
  }

  function validate(): boolean {
    const next: FieldErrors = {
      perShareAmount: validatePerShareAmount(perShareAmount) ?? undefined,
      qualifyingShares: validateQualifyingShares(qualifyingShares, position.total_shares) ?? undefined,
      paymentDate: validateDividendPaymentDate(paymentDate) ?? undefined,
      exDividendDate: validateExDividendDate(exDividendDate, paymentDate) ?? undefined,
    };
    setErrors(next);
    return !Object.values(next).some(Boolean);
  }

  async function handleSave() {
    setGenericError(null);
    if (capReached) {
      setGenericError(`Maximum of 8 dividend tranches per year reached for ${position.stock_name} (${year}).`);
      return;
    }
    if (!validate()) return;

    setSubmitting(true);
    try {
      const body: CreateDividendRequest = {
        position_id: position.id,
        tranche_label: nextLabel,
        per_share_amount: perShareAmount,
        qualifying_shares: parseInt(qualifyingShares, 10),
        payment_date: paymentDate,
        ex_dividend_date: exDividendDate || null,
      };
      const tranche = await apiFetch<DividendTrancheResponse>("/api/v1/portfolio/dividends", {
        method: "POST",
        body: JSON.stringify(body),
      });

      onOpenChange(false);
      resetForm();

      const freshPosition = await revalidatePosition();
      await revalidateDashboard();

      const yieldPercent = freshPosition
        ? formatPercent(computeYieldPercent(freshPosition.total_dividend_income_ytd, freshPosition.total_all_in_cost))
        : "—";
      onLogged(
        `${tranche.tranche_label} dividend logged — ${formatMyr(new Decimal(tranche.total_amount))}. ` +
          `Position yield is now ${yieldPercent}.`
      );
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.fields?.length) {
          setErrors({
            perShareAmount: err.fieldError("per_share_amount"),
            qualifyingShares: err.fieldError("qualifying_shares"),
            paymentDate: err.fieldError("payment_date"),
            exDividendDate: err.fieldError("ex_dividend_date"),
          });
          if (!err.fields.some((f) => ["per_share_amount", "qualifying_shares", "payment_date", "ex_dividend_date"].includes(f.field))) {
            setGenericError(err.message);
          }
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

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) resetForm();
        onOpenChange(next);
      }}
    >
      <DialogContent className="max-w-[480px] p-0 sm:max-w-[480px]">
        <div className="flex items-center justify-between border-b border-border px-6 py-5">
          <DialogTitle className="text-[17px] font-bold">Add Dividend — {position.stock_name}</DialogTitle>
        </div>

        {genericError && (
          <div className="mx-6 mt-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-[13px] text-destructive">
            {genericError}
          </div>
        )}

        <div className="px-6 py-5.5">
          <div className="flex gap-3">
            <div className="flex-1">
              <Label className="mb-1.5 text-[13px] font-semibold">Tranche</Label>
              <Input readOnly value={capReached ? "—" : `${nextLabel} tranche`} className="bg-[#FAFAF8] text-muted-foreground" />
              <div className="mt-1 text-[11.5px] text-tertiary">Next available label</div>
            </div>
            <div className="flex-1">
              <Label htmlFor="ad-per-share" className="mb-1.5 text-[13px] font-semibold">
                Per share (RM) <span className="text-destructive">*</span>
              </Label>
              <Input
                id="ad-per-share"
                inputMode="decimal"
                value={perShareAmount}
                onChange={(e) => setPerShareAmount(e.target.value)}
                placeholder="0.20"
                disabled={capReached}
                aria-invalid={Boolean(errors.perShareAmount)}
              />
              {errors.perShareAmount && <p className="mt-1 text-xs text-destructive">{errors.perShareAmount}</p>}
            </div>
          </div>

          <div className="h-4" />

          <Label htmlFor="ad-qualifying-shares" className="mb-1.5 text-[13px] font-semibold">
            Qualifying shares
          </Label>
          <Input
            id="ad-qualifying-shares"
            inputMode="numeric"
            value={qualifyingShares}
            onChange={(e) => setQualifyingShares(e.target.value)}
            disabled={capReached}
            aria-invalid={Boolean(errors.qualifyingShares)}
          />
          {/* BAS Enhanced Part2's exact guidance text (verbatim, per this
              story's AC) — the design's own wording differs slightly and is
              deliberately not used here, since this field is the UI's
              primary defense against the BR-009 class of user error. */}
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
              <Label htmlFor="ad-payment-date" className="mb-1.5 text-[13px] font-semibold">
                Payment date <span className="text-destructive">*</span>
              </Label>
              <Input
                id="ad-payment-date"
                type="date"
                value={paymentDate}
                onChange={(e) => setPaymentDate(e.target.value)}
                disabled={capReached}
                aria-invalid={Boolean(errors.paymentDate)}
              />
              {errors.paymentDate && <p className="mt-1 text-xs text-destructive">{errors.paymentDate}</p>}
            </div>
            <div className="flex-1">
              <Label htmlFor="ad-ex-date" className="mb-1.5 text-[13px] font-semibold">
                Ex-date <span className="font-normal text-tertiary">(optional)</span>
              </Label>
              <Input
                id="ad-ex-date"
                type="date"
                value={exDividendDate}
                onChange={(e) => setExDividendDate(e.target.value)}
                disabled={capReached}
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
          <Button type="button" onClick={handleSave} disabled={submitting || capReached}>
            {submitting ? "Saving…" : "Save Dividend"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
