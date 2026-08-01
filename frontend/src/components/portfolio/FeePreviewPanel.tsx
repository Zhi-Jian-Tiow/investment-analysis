"use client";

export interface FeePreviewValues {
  initialAmount: string;
  brokerageFee: string;
  clearingFee: string;
  stampDuty: string;
  allInCost: string;
  note: string;
}

interface FeePreviewPanelProps {
  preview: FeePreviewValues | null;
}

/** Shared live fee-breakdown panel (FE-2.1's AddPositionDialog, FE-2.2's
 * AddLotDialog) — display-only, values always come from lib/fee-calculator.ts.
 */
export function FeePreviewPanel({ preview }: FeePreviewPanelProps) {
  return (
    <div className="min-w-[250px] flex-1 border-l border-border bg-[#FAFAF8] px-6 py-5" aria-live="polite">
      <div className="mb-3.5 text-[11.5px] font-semibold tracking-wide text-tertiary uppercase">
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
        <div className="-mt-1.5 font-mono text-[11.5px] text-tertiary">
          {preview?.note ?? "Enter shares and price to preview fees"}
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Clearing fee</span>
          <span className="font-semibold">{preview?.clearingFee ?? "—"}</span>
        </div>
        <div className="-mt-1.5 font-mono text-[11.5px] text-tertiary">0.03% of initial amount</div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Stamp duty</span>
          <span className="font-semibold">{preview?.stampDuty ?? "—"}</span>
        </div>
        <div className="-mt-1.5 font-mono text-[11.5px] text-tertiary">RM1 per RM1,000 (rounded up)</div>
        <div className="flex items-baseline justify-between border-t border-border pt-2.5">
          <span className="font-bold">All-in cost</span>
          <span className="text-[17px] font-bold">{preview?.allInCost ?? "—"}</span>
        </div>
      </div>
    </div>
  );
}
