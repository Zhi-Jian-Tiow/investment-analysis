"use client";

import { useEffect, useMemo, useState } from "react";

import { FeePreviewPanel } from "@/components/portfolio/FeePreviewPanel";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useBrokers } from "@/hooks/useBrokers";
import { useFeePreview } from "@/hooks/useFeePreview";
import { ApiError, apiFetch } from "@/lib/api";
import { validatePurchaseDate, validatePurchasePrice, validateShares } from "@/lib/position-validation";
import type { LotResponse, PositionResponse } from "@/lib/types";

// Exact copy required by FE-2.3's AC — deliberately not the backend's own
// generic 409 message ("This record was modified by another session. Please
// refresh and try again.", app/errors.py::version_conflict), which the story
// specifies different, more actionable wording for.
const CONFLICT_MESSAGE =
  "This record was updated by another session. Please refresh the page to see the latest values before making changes.";

interface FieldErrors {
  shares?: string;
  price?: string;
  purchaseDate?: string;
  brokerId?: string;
}

interface EditLotDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  position: PositionResponse;
  lot: LotResponse;
  /** Re-fetches the position (BE-2.3's GET /positions/{id}) and returns the
   * fresh data — used both for normal post-save revalidation and to reload
   * current values after a 409 version conflict. */
  revalidatePosition: () => Promise<PositionResponse | undefined>;
  onSaved: (notice: string) => void;
}

export function EditLotDialog({ open, onOpenChange, position, lot, revalidatePosition, onSaved }: EditLotDialogProps) {
  const { brokers, isLoading: brokersLoading } = useBrokers();

  const [shares, setShares] = useState(String(lot.shares));
  const [price, setPrice] = useState(lot.purchase_price);
  const [purchaseDate, setPurchaseDate] = useState(lot.purchase_date);
  const [brokerId, setBrokerId] = useState(lot.broker_id);
  const [version, setVersion] = useState(lot.version);

  const [errors, setErrors] = useState<FieldErrors>({});
  const [genericError, setGenericError] = useState<string | null>(null);
  const [versionConflict, setVersionConflict] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // `version` is tracked in state but never rendered as an input — the AC
  // requires it travel with every PATCH transparently, not be user-editable.
  useEffect(() => {
    if (!open) return;
    setShares(String(lot.shares));
    setPrice(lot.purchase_price);
    setPurchaseDate(lot.purchase_date);
    setBrokerId(lot.broker_id);
    setVersion(lot.version);
    setErrors({});
    setGenericError(null);
    setVersionConflict(false);
  }, [open, lot]);

  const selectedBroker = useMemo(() => brokers.find((b) => b.id === brokerId), [brokers, brokerId]);
  const preview = useFeePreview(selectedBroker, shares, price);

  function validate(): boolean {
    const next: FieldErrors = {
      shares: validateShares(shares) ?? undefined,
      price: validatePurchasePrice(price) ?? undefined,
      purchaseDate: validatePurchaseDate(purchaseDate) ?? undefined,
      brokerId: brokerId ? undefined : "Please select a broker",
    };
    setErrors(next);
    return !Object.values(next).some(Boolean);
  }

  async function handleSave() {
    setGenericError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      const updated = await apiFetch<LotResponse>(`/api/v1/portfolio/positions/${position.id}/lots/${lot.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          shares: parseInt(shares, 10),
          purchase_price: price,
          broker_id: brokerId,
          purchase_date: purchaseDate,
          version,
        }),
      });

      onOpenChange(false);
      // EC-015's "Position updated. Dividend records were not changed."
      // notice arrives via `warnings` only when the share count changed;
      // fall back to a plain confirmation so every successful save gives
      // some feedback.
      const notices = updated.warnings.length > 0 ? updated.warnings : ["Lot updated."];
      onSaved(notices.join(" "));
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setVersionConflict(true);
        } else if (err.fields?.length) {
          setErrors({
            shares: err.fieldError("shares"),
            price: err.fieldError("purchase_price"),
            purchaseDate: err.fieldError("purchase_date"),
            brokerId: err.fieldError("broker_id"),
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
      const freshLot = fresh?.lots.find((l) => l.id === lot.id);
      if (freshLot) {
        setShares(String(freshLot.shares));
        setPrice(freshLot.purchase_price);
        setPurchaseDate(freshLot.purchase_date);
        setBrokerId(freshLot.broker_id);
        setVersion(freshLot.version);
      }
      setVersionConflict(false);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[640px] p-0 sm:max-w-[640px]">
        <div className="flex items-center justify-between border-b border-border px-6 py-5">
          <DialogTitle className="text-[17px] font-bold">Edit Lot — {position.stock_name}</DialogTitle>
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

        <div className="flex flex-wrap">
          <div className="min-w-[280px] flex-[1.15] px-6 py-5">
            <div className="mb-4 flex gap-3">
              <div className="flex-1">
                <Label htmlFor="edit-lot-shares" className="mb-1.5 text-[13px] font-semibold">
                  Shares <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="edit-lot-shares"
                  inputMode="numeric"
                  value={shares}
                  onChange={(e) => setShares(e.target.value)}
                  disabled={versionConflict}
                  aria-invalid={Boolean(errors.shares)}
                />
                {errors.shares && <p className="mt-1 text-xs text-destructive">{errors.shares}</p>}
              </div>
              <div className="flex-1">
                <Label htmlFor="edit-lot-price" className="mb-1.5 text-[13px] font-semibold">
                  Price / share (RM) <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="edit-lot-price"
                  inputMode="decimal"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  disabled={versionConflict}
                  aria-invalid={Boolean(errors.price)}
                />
                {errors.price && <p className="mt-1 text-xs text-destructive">{errors.price}</p>}
              </div>
            </div>

            <div className="flex gap-3">
              <div className="flex-1">
                <Label htmlFor="edit-lot-purchase-date" className="mb-1.5 text-[13px] font-semibold">
                  Purchase date <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="edit-lot-purchase-date"
                  type="date"
                  value={purchaseDate}
                  onChange={(e) => setPurchaseDate(e.target.value)}
                  disabled={versionConflict}
                  aria-invalid={Boolean(errors.purchaseDate)}
                />
                {errors.purchaseDate && <p className="mt-1 text-xs text-destructive">{errors.purchaseDate}</p>}
              </div>
              <div className="flex-1">
                <Label htmlFor="edit-lot-broker" className="mb-1.5 text-[13px] font-semibold">
                  Broker
                </Label>
                <Select value={brokerId} onValueChange={(value) => setBrokerId(value ?? "")} disabled={versionConflict}>
                  <SelectTrigger id="edit-lot-broker" className="w-full" aria-invalid={Boolean(errors.brokerId)}>
                    <SelectValue>
                      {(value: string | null) =>
                        brokers.find((b) => b.id === value)?.name ?? (brokersLoading ? "Loading…" : "Select broker")
                      }
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {brokers.map((broker) => (
                      <SelectItem key={broker.id} value={broker.id}>
                        {broker.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.brokerId && <p className="mt-1 text-xs text-destructive">{errors.brokerId}</p>}
              </div>
            </div>
            {shares !== String(lot.shares) && (
              <p className="mt-2.5 text-xs text-muted-foreground">
                Changing the share count does not affect any dividend records already logged for this position.
              </p>
            )}
          </div>

          <FeePreviewPanel preview={preview} />
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
