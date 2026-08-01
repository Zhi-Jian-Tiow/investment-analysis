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

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

interface FieldErrors {
  shares?: string;
  price?: string;
  purchaseDate?: string;
  brokerId?: string;
}

interface AddLotDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  position: PositionResponse;
  onLotAdded: (notice: string) => void;
}

export function AddLotDialog({ open, onOpenChange, position, onLotAdded }: AddLotDialogProps) {
  const { brokers, isLoading: brokersLoading } = useBrokers();

  const [shares, setShares] = useState("");
  const [price, setPrice] = useState("");
  const [purchaseDate, setPurchaseDate] = useState(todayIso);
  const [brokerId, setBrokerId] = useState("");

  const [errors, setErrors] = useState<FieldErrors>({});
  const [genericError, setGenericError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // BR-003 — brokerage is per-transaction, so a per-lot broker override is a
  // valid scenario. Pre-fills to the position's first lot's broker (there is
  // no backend notion of a position-level "default broker" — see BE-2.2's
  // Implementation Record) but is fully editable.
  useEffect(() => {
    if (open) setBrokerId(position.lots[0]?.broker_id ?? "");
  }, [open, position.lots]);

  const selectedBroker = useMemo(() => brokers.find((b) => b.id === brokerId), [brokers, brokerId]);
  const preview = useFeePreview(selectedBroker, shares, price);

  function resetForm() {
    setShares("");
    setPrice("");
    setPurchaseDate(todayIso());
    setErrors({});
    setGenericError(null);
  }

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
      const lot = await apiFetch<LotResponse>(`/api/v1/portfolio/positions/${position.id}/lots`, {
        method: "POST",
        body: JSON.stringify({
          shares: parseInt(shares, 10),
          purchase_price: price,
          broker_id: brokerId,
          purchase_date: purchaseDate,
        }),
      });

      onOpenChange(false);
      resetForm();

      // BR-009: historical dividend records are never touched by adding a
      // lot — true regardless of whether the server sent an EC-004 warning,
      // so this reassurance is always appended (matches the design's intent
      // that Add Lot explicitly confirms the invariant to the user).
      const notices = [...lot.warnings, "Lot added. Historical dividend records are unaffected."];
      onLotAdded(notices.join(" "));
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.fields?.length) {
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

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) resetForm();
        onOpenChange(next);
      }}
    >
      <DialogContent className="max-w-[640px] p-0 sm:max-w-[640px]">
        <div className="flex items-center justify-between border-b border-border px-6 py-5">
          <DialogTitle className="text-[17px] font-bold">Add Lot — {position.stock_name}</DialogTitle>
        </div>

        {genericError && (
          <div className="mx-6 mt-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-[13px] text-destructive">
            {genericError}
          </div>
        )}

        <div className="flex flex-wrap">
          <div className="min-w-[280px] flex-[1.15] px-6 py-5">
            <Label className="mb-1.5 text-[13px] font-semibold">Stock</Label>
            <Input
              readOnly
              value={`${position.stock_name} — ${position.stock_code}`}
              className="bg-[#FAFAF8] text-muted-foreground"
            />
            <div className="h-4" />

            <div className="mb-4 flex gap-3">
              <div className="flex-1">
                <Label htmlFor="lot-shares" className="mb-1.5 text-[13px] font-semibold">
                  Shares <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="lot-shares"
                  inputMode="numeric"
                  value={shares}
                  onChange={(e) => setShares(e.target.value)}
                  placeholder="2000"
                  aria-invalid={Boolean(errors.shares)}
                />
                {errors.shares && <p className="mt-1 text-xs text-destructive">{errors.shares}</p>}
              </div>
              <div className="flex-1">
                <Label htmlFor="lot-price" className="mb-1.5 text-[13px] font-semibold">
                  Price / share (RM) <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="lot-price"
                  inputMode="decimal"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="9.00"
                  aria-invalid={Boolean(errors.price)}
                />
                {errors.price && <p className="mt-1 text-xs text-destructive">{errors.price}</p>}
              </div>
            </div>

            <div className="flex gap-3">
              <div className="flex-1">
                <Label htmlFor="lot-purchase-date" className="mb-1.5 text-[13px] font-semibold">
                  Purchase date <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="lot-purchase-date"
                  type="date"
                  value={purchaseDate}
                  onChange={(e) => setPurchaseDate(e.target.value)}
                  aria-invalid={Boolean(errors.purchaseDate)}
                />
                {errors.purchaseDate && <p className="mt-1 text-xs text-destructive">{errors.purchaseDate}</p>}
              </div>
              <div className="flex-1">
                <Label htmlFor="lot-broker" className="mb-1.5 text-[13px] font-semibold">
                  Broker
                </Label>
                <Select value={brokerId} onValueChange={(value) => setBrokerId(value ?? "")}>
                  <SelectTrigger id="lot-broker" className="w-full" aria-invalid={Boolean(errors.brokerId)}>
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
            <p className="mt-2.5 text-xs text-muted-foreground">
              Brokerage is charged per lot — you can use a different broker than your other lots.
            </p>
          </div>

          <FeePreviewPanel preview={preview} />
        </div>

        <div className="flex justify-end gap-2.5 border-t border-border px-6 py-4">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" onClick={handleSave} disabled={submitting}>
            {submitting ? "Saving…" : "Save Lot"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
