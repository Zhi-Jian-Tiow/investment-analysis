"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { brokerNote, calculateLotFees, formatMyr } from "@/lib/fee-calculator";
import { useDashboard } from "@/hooks/useDashboard";
import { useBrokers } from "@/hooks/useBrokers";
import { ApiError, apiFetch } from "@/lib/api";
import {
  validateBrokerId,
  validatePurchaseDate,
  validatePurchasePrice,
  validateShares,
  validateStockCode,
  validateStockName,
} from "@/lib/position-validation";
import type { CategoryTag, CreatePositionRequest, PositionResponse } from "@/lib/types";

const CATEGORY_TAGS: CategoryTag[] = ["Dividend", "Volatile", "Growth"];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

interface FieldErrors {
  stockCode?: string;
  stockName?: string;
  shares?: string;
  price?: string;
  purchaseDate?: string;
  brokerId?: string;
}

interface AddPositionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddPositionDialog({ open, onOpenChange }: AddPositionDialogProps) {
  const router = useRouter();
  const { brokers, isLoading: brokersLoading } = useBrokers();
  const { mutate: revalidateDashboard } = useDashboard();

  const [stockCode, setStockCode] = useState("");
  const [stockName, setStockName] = useState("");
  const [shares, setShares] = useState("");
  const [price, setPrice] = useState("");
  const [purchaseDate, setPurchaseDate] = useState(todayIso);
  const [brokerId, setBrokerId] = useState("");
  const [categoryTag, setCategoryTag] = useState<CategoryTag>("Dividend");

  const [errors, setErrors] = useState<FieldErrors>({});
  const [genericError, setGenericError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const selectedBroker = useMemo(() => brokers.find((b) => b.id === brokerId), [brokers, brokerId]);

  const preview = useMemo(() => {
    const sharesNum = parseInt(shares, 10);
    if (!selectedBroker || !sharesNum || sharesNum <= 0 || !price || parseFloat(price) <= 0) {
      return null;
    }
    try {
      const fees = calculateLotFees(sharesNum, price, selectedBroker);
      return {
        initialAmount: formatMyr(fees.initialAmount),
        brokerageFee: formatMyr(fees.brokerageFee),
        clearingFee: formatMyr(fees.clearingFee),
        stampDuty: formatMyr(fees.stampDuty),
        allInCost: formatMyr(fees.allInCost),
        note: brokerNote(selectedBroker, fees.initialAmount),
      };
    } catch {
      return null;
    }
  }, [selectedBroker, shares, price]);

  function resetForm() {
    setStockCode("");
    setStockName("");
    setShares("");
    setPrice("");
    setPurchaseDate(todayIso());
    setBrokerId("");
    setCategoryTag("Dividend");
    setErrors({});
    setGenericError(null);
  }

  function validate(): boolean {
    const next: FieldErrors = {
      stockCode: validateStockCode(stockCode) ?? undefined,
      stockName: validateStockName(stockName) ?? undefined,
      shares: validateShares(shares) ?? undefined,
      price: validatePurchasePrice(price) ?? undefined,
      purchaseDate: validatePurchaseDate(purchaseDate) ?? undefined,
      brokerId: validateBrokerId(brokerId) ?? undefined,
    };
    setErrors(next);
    return !Object.values(next).some(Boolean);
  }

  async function handleSave() {
    setGenericError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      const body: CreatePositionRequest = {
        stock_code: stockCode.trim(),
        stock_name: stockName.trim(),
        shares: parseInt(shares, 10),
        purchase_price: price,
        broker_id: brokerId,
        purchase_date: purchaseDate,
        category_tag: categoryTag,
      };
      const position = await apiFetch<PositionResponse>("/api/v1/portfolio/positions", {
        method: "POST",
        body: JSON.stringify(body),
      });

      await revalidateDashboard();
      onOpenChange(false);
      resetForm();

      const notice = position.warnings.length > 0 ? encodeURIComponent(position.warnings.join(" ")) : null;
      router.push(notice ? `/positions/${position.id}?notice=${notice}` : `/positions/${position.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.fields?.length) {
          setErrors({
            stockCode: err.fieldError("stock_code"),
            stockName: err.fieldError("stock_name"),
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
          <DialogTitle className="text-[17px] font-bold">Add Position</DialogTitle>
        </div>

        {genericError && (
          <div className="mx-6 mt-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-[13px] text-destructive">
            {genericError}
          </div>
        )}

        <div className="flex flex-wrap">
          <div className="min-w-[280px] flex-[1.15] px-6 py-5">
            <div className="mb-1.5 flex gap-3">
              <div className="flex-1">
                <Label htmlFor="stock-code" className="mb-1.5 text-[13px] font-semibold">
                  Stock code <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="stock-code"
                  value={stockCode}
                  onChange={(e) => setStockCode(e.target.value)}
                  placeholder="1023"
                  aria-invalid={Boolean(errors.stockCode)}
                />
                {errors.stockCode && <p className="mt-1 text-xs text-destructive">{errors.stockCode}</p>}
              </div>
              <div className="flex-[1.5]">
                <Label htmlFor="stock-name" className="mb-1.5 text-[13px] font-semibold">
                  Stock name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="stock-name"
                  value={stockName}
                  onChange={(e) => setStockName(e.target.value)}
                  placeholder="CIMB Group Holdings Berhad"
                  aria-invalid={Boolean(errors.stockName)}
                />
                {errors.stockName && <p className="mt-1 text-xs text-destructive">{errors.stockName}</p>}
              </div>
            </div>
            <p className="mb-4 text-xs text-muted-foreground">
              Stock lookup isn&apos;t available yet — enter the Bursa code and name directly.
            </p>

            <div className="mb-4 flex gap-3">
              <div className="flex-1">
                <Label htmlFor="shares" className="mb-1.5 text-[13px] font-semibold">
                  Shares <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="shares"
                  inputMode="numeric"
                  value={shares}
                  onChange={(e) => setShares(e.target.value)}
                  placeholder="5000"
                  aria-invalid={Boolean(errors.shares)}
                />
                {errors.shares && <p className="mt-1 text-xs text-destructive">{errors.shares}</p>}
              </div>
              <div className="flex-1">
                <Label htmlFor="price" className="mb-1.5 text-[13px] font-semibold">
                  Price / share (RM) <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="price"
                  inputMode="decimal"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="8.38"
                  aria-invalid={Boolean(errors.price)}
                />
                {errors.price && <p className="mt-1 text-xs text-destructive">{errors.price}</p>}
              </div>
            </div>

            <div className="mb-4 flex gap-3">
              <div className="flex-1">
                <Label htmlFor="purchase-date" className="mb-1.5 text-[13px] font-semibold">
                  Purchase date <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="purchase-date"
                  type="date"
                  value={purchaseDate}
                  onChange={(e) => setPurchaseDate(e.target.value)}
                  aria-invalid={Boolean(errors.purchaseDate)}
                />
                {errors.purchaseDate && <p className="mt-1 text-xs text-destructive">{errors.purchaseDate}</p>}
              </div>
              <div className="flex-1">
                <Label htmlFor="broker" className="mb-1.5 text-[13px] font-semibold">
                  Broker
                </Label>
                <Select value={brokerId} onValueChange={(value) => setBrokerId(value ?? "")}>
                  <SelectTrigger id="broker" className="w-full" aria-invalid={Boolean(errors.brokerId)}>
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

            <Label className="mb-1.5 text-[13px] font-semibold">Category tag</Label>
            <div className="flex gap-2">
              {CATEGORY_TAGS.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => setCategoryTag(tag)}
                  className={
                    tag === categoryTag
                      ? "rounded-full border-[1.5px] border-[#17A05E] bg-[#E7F5EE] px-3.5 py-1.5 text-[12.5px] font-semibold text-[#177A4E]"
                      : "rounded-full border-[1.5px] border-input px-3.5 py-1.5 text-[12.5px] font-semibold text-muted-foreground hover:border-muted-foreground"
                  }
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          <div className="min-w-[250px] flex-1 border-l border-border bg-[#FAFAF8] px-6 py-5" aria-live="polite">
            <div className="mb-3.5 text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
              Live fee calculation
            </div>
            <div className="flex flex-col gap-2.5 text-[13.5px]">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Initial amount</span>
                <span className="font-semibold">{preview?.initialAmount ?? "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Brokerage fee</span>
                <span className="font-semibold">{preview?.brokerageFee ?? "—"}</span>
              </div>
              <div className="-mt-1.5 font-mono text-[11.5px] text-muted-foreground">
                {preview?.note ?? "Enter shares and price to preview fees"}
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Clearing fee</span>
                <span className="font-semibold">{preview?.clearingFee ?? "—"}</span>
              </div>
              <div className="-mt-1.5 font-mono text-[11.5px] text-muted-foreground">0.03% of initial amount</div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Stamp duty</span>
                <span className="font-semibold">{preview?.stampDuty ?? "—"}</span>
              </div>
              <div className="-mt-1.5 font-mono text-[11.5px] text-muted-foreground">
                RM1 per RM1,000 (rounded up)
              </div>
              <div className="flex items-baseline justify-between border-t border-border pt-2.5">
                <span className="font-bold">All-in cost</span>
                <span className="text-[17px] font-bold">{preview?.allInCost ?? "—"}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2.5 border-t border-border px-6 py-4">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" onClick={handleSave} disabled={submitting}>
            {submitting ? "Saving…" : "Save Position"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
