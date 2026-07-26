"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";

const COOLDOWN_SECONDS = 60;

/** FE-1.1 AC: "'Resend verification email' control visible on the banner;
 * disabled with a cooldown after use." Calls the real POST
 * /auth/resend-verification endpoint (added alongside this component —
 * previously this control had nothing to call). */
export function VerifyBanner() {
  const [sending, setSending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  async function handleResend() {
    setSending(true);
    setError(null);
    try {
      await apiFetch("/auth/resend-verification", { method: "POST" });
      setCooldown(COOLDOWN_SECONDS);
    } catch {
      setError("Couldn't resend right now. Please try again in a moment.");
    } finally {
      setSending(false);
    }
  }

  const label = cooldown > 0 ? `Resend in ${cooldown}s` : sending ? "Sending…" : "Resend verification email";

  return (
    <div className="mb-[18px] rounded-[10px] border border-[#C9D4FA] bg-secondary px-4 py-[11px] text-[13.5px] text-secondary-foreground">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span>Please verify your email when you have a moment. You have full access now.</span>
        <button
          type="button"
          onClick={handleResend}
          disabled={sending || cooldown > 0}
          className="shrink-0 whitespace-nowrap text-[13px] font-semibold underline disabled:cursor-not-allowed disabled:opacity-60"
        >
          {label}
        </button>
      </div>
      {error && <p className="mt-1.5 text-xs text-destructive">{error}</p>}
    </div>
  );
}
