"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiFetch } from "@/lib/api";
import { validateEmail } from "@/lib/validation";

const RESEND_COOLDOWN_SECONDS = 30;

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [rateLimitedUntil, setRateLimitedUntil] = useState<number | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState(0);

  const rateLimited = rateLimitedUntil !== null && secondsRemaining > 0;

  useEffect(() => {
    if (rateLimitedUntil === null) return;
    function tick() {
      const remaining = Math.max(0, Math.ceil(((rateLimitedUntil ?? 0) - Date.now()) / 1000));
      setSecondsRemaining(remaining);
      if (remaining <= 0) setRateLimitedUntil(null);
    }
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [rateLimitedUntil]);

  async function submitRequest(targetEmail: string) {
    setSubmitting(true);
    try {
      await apiFetch("/auth/password-reset-request", {
        method: "POST",
        body: JSON.stringify({ email: targetEmail }),
      });
      setSentTo(targetEmail);
      setRateLimitedUntil(Date.now() + RESEND_COOLDOWN_SECONDS * 1000);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setRateLimitedUntil(Date.now() + (err.retryAfterSeconds ?? 60) * 1000);
      }
      // Any other error (network, 5xx) — the backend's contract never
      // returns a "this email doesn't exist" error, so there is nothing
      // else meaningful to distinguish here; the form just stays put.
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const validationError = validateEmail(email);
    setEmailError(validationError);
    if (validationError || rateLimited) return;
    await submitRequest(email);
  }

  if (sentTo) {
    return (
      <div>
        <div
          role="status"
          className="mb-5 flex items-start gap-2.5 rounded-[10px] border border-[#C9D4FA] bg-secondary px-[15px] py-[13px]"
        >
          <span className="mt-px flex h-[19px] w-[19px] shrink-0 items-center justify-center rounded-full bg-primary text-[11px] text-white">
            ✓
          </span>
          <div className="text-[13.5px] text-secondary-foreground">
            <strong>Check your inbox.</strong> If an account exists for that address, a reset link is on its
            way.
          </div>
        </div>

        <h1 className="mb-1.5 text-xl font-bold tracking-tight text-foreground">Reset link sent</h1>
        <p className="text-[13.5px] text-muted-foreground">
          We sent instructions to <strong className="text-foreground">{sentTo}</strong>. The link expires in{" "}
          <strong className="text-foreground">60 minutes</strong> and can be used once.
        </p>

        <div className="mt-[18px] rounded-[10px] border border-[#F0F0ED] bg-[#FAFAF8] px-4 py-3.5">
          <div className="mb-2 text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">
            Didn&apos;t get it?
          </div>
          <div className="flex flex-col gap-1 text-[13px] text-foreground/80">
            <div>· Check your spam or promotions folder</div>
            <div>· Confirm you typed the address correctly</div>
            <div>· Delivery can take up to 5 minutes</div>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-between gap-2.5">
          <button
            type="button"
            onClick={() => setSentTo(null)}
            className="cursor-pointer p-0 text-[13px] font-semibold text-muted-foreground hover:text-foreground hover:no-underline"
          >
            Use a different email
          </button>
          <button
            type="button"
            disabled={rateLimited || submitting}
            onClick={() => submitRequest(sentTo)}
            className="cursor-pointer p-0 text-[13px] font-semibold text-primary hover:no-underline disabled:cursor-not-allowed disabled:text-muted-foreground"
          >
            {rateLimited ? `Resend in ${secondsRemaining}s` : "Resend email"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <h1 className="mb-1 text-xl font-bold tracking-tight text-foreground">Reset your password</h1>
      <p className="mb-[22px] text-[13.5px] text-muted-foreground">
        Enter the email address on your account and we&apos;ll send you a reset link.
      </p>

      {rateLimited && (
        <div className="mb-4 flex items-start gap-2.5 rounded-[10px] border border-[#F0D9A6] bg-[#FFF6E3] px-3.5 py-[11px] text-[13px] text-[#8A5A00]">
          <span>⚠</span>
          <div>
            Too many requests. You can request another reset link in <strong>{secondsRemaining}s</strong>.
          </div>
        </div>
      )}

      <Label htmlFor="email" className="mb-1.5 text-[13px] font-semibold">
        Email address
      </Label>
      <Input
        id="email"
        type="email"
        autoComplete="email"
        placeholder="you@example.com"
        value={email}
        onChange={(e) => {
          setEmail(e.target.value);
          setEmailError(null);
        }}
        onBlur={() => setEmailError(validateEmail(email))}
        aria-invalid={Boolean(emailError)}
        disabled={rateLimited}
      />
      {emailError && <p className="mt-1.5 text-xs text-destructive">{emailError}</p>}

      <div className="h-[22px]" />
      <Button type="submit" className="w-full" size="lg" disabled={submitting || rateLimited}>
        {submitting ? "Sending…" : "Send reset link"}
      </Button>
    </form>
  );
}
