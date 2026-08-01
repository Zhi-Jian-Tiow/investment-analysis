"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => Promise<void>;
}

/** Reusable delete/destructive-action confirmation modal (architecture
 * §7.2's components/shared/ConfirmDialog.tsx) — first used by FE-2.4's
 * Delete Position flow, intended for every other destructive action
 * (dividend delete, account delete) to reuse rather than re-implement.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  destructive = true,
  onConfirm,
}: ConfirmDialogProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    setError(null);
    setSubmitting(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } catch {
      setError("Something went wrong. Please check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!submitting) onOpenChange(next);
      }}
    >
      <DialogContent className="max-w-[440px]">
        <DialogTitle className="text-[17px] font-bold">{title}</DialogTitle>
        <p className="text-[13.5px] text-muted-foreground">{description}</p>

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-[13px] text-destructive">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2.5 pt-1">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={destructive ? "destructive" : "default"}
            onClick={handleConfirm}
            disabled={submitting}
          >
            {submitting ? "Deleting…" : confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
