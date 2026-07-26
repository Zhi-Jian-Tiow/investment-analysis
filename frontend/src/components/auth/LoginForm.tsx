"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const LOCKOUT_CODES = new Set(["account_locked", "rate_limit_exceeded"]);

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lockedUntil, setLockedUntil] = useState<number | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState(0);
  const [showResetBanner, setShowResetBanner] = useState(searchParams.get("reset") === "success");

  const sessionExpired = searchParams.get("reason") === "session_expired";
  const locked = lockedUntil !== null && secondsRemaining > 0;

  useEffect(() => {
    if (lockedUntil === null) return;

    function tick() {
      const remaining = Math.max(0, Math.ceil(((lockedUntil ?? 0) - Date.now()) / 1000));
      setSecondsRemaining(remaining);
      if (remaining <= 0) setLockedUntil(null);
    }

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [lockedUntil]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!email || !password) {
      setError("Please enter your email and password.");
      return;
    }

    setSubmitting(true);
    try {
      await login(email, password);
      const redirect = searchParams.get("redirect");
      router.push(redirect && redirect.startsWith("/") ? redirect : "/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        if (LOCKOUT_CODES.has(err.code) && err.retryAfterSeconds) {
          setLockedUntil(Date.now() + err.retryAfterSeconds * 1000);
        }
        setError(err.message);
      } else {
        setError("Something went wrong. Please check your connection and try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <h1 className="mb-1 text-xl font-bold tracking-tight text-foreground">Welcome back</h1>
      <p className="mb-5 text-[13.5px] text-muted-foreground">Log in to see your portfolio.</p>

      {showResetBanner && (
        <div
          role="status"
          className="mb-4 flex items-start gap-2.5 rounded-[10px] border border-[#B7E2CC] bg-[#E7F5EE] px-3.5 py-3"
        >
          <span className="mt-px flex h-[19px] w-[19px] shrink-0 items-center justify-center rounded-full bg-emerald-600 text-[12px] text-white">
            ✓
          </span>
          <div className="flex-1">
            <div className="text-[13.5px] font-bold text-foreground">Password updated successfully.</div>
            <div className="mt-0.5 text-[12.5px] text-emerald-800">Please log in with your new password.</div>
          </div>
          <button
            type="button"
            aria-label="Dismiss"
            onClick={() => setShowResetBanner(false)}
            className="cursor-pointer rounded p-0.5 text-base leading-none text-emerald-800 hover:no-underline"
          >
            ×
          </button>
        </div>
      )}

      {sessionExpired && !error && (
        <div className="mb-4 rounded-lg border border-secondary bg-secondary px-3.5 py-3 text-[13px] text-secondary-foreground">
          Your session has expired. Please log in again.
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-[13px] text-destructive">
          {error}
          {locked && <span className="mt-1 block font-semibold">Try again in {secondsRemaining}s.</span>}
        </div>
      )}

      <div className="mb-4">
        <Label htmlFor="email" className="mb-1.5 text-[13px] font-semibold">
          Email address
        </Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={locked}
        />
      </div>

      <div className="mb-5">
        <div className="mb-1.5 flex items-baseline justify-between">
          <Label htmlFor="password" className="text-[13px] font-semibold">
            Password
          </Label>
          <Link href="/forgot-password" className="text-xs">
            Forgot password?
          </Link>
        </div>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={locked}
        />
      </div>

      <Button type="submit" className="w-full" size="lg" disabled={submitting || locked}>
        {locked ? `Try again in ${secondsRemaining}s` : submitting ? "Logging in…" : "Log in"}
      </Button>
    </form>
  );
}
