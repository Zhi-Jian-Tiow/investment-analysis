"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiFetch } from "@/lib/api";
import { validatePassword, validatePasswordConfirmation } from "@/lib/validation";

import { PasswordRulesChecklist } from "./PasswordRulesChecklist";
import { PasswordStrengthMeter } from "./PasswordStrengthMeter";

type Stage = "form" | "error" | "done";

/**
 * There is no endpoint to check a reset token's validity ahead of time —
 * the only way to find out is to actually submit a new password and see
 * what comes back. So unlike the BursaTrack Design's mockup (which shows a
 * dedicated "expired" screen state independent of submission), this always
 * renders the form first and only shows an error card after a real 400
 * from POST /auth/password-reset.
 */
export function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [stage, setStage] = useState<Stage>(token ? "form" : "error");
  const [errorMessage, setErrorMessage] = useState<string>(
    token ? "" : "This reset link is invalid. Please request a new one."
  );

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [confirmTouched, setConfirmTouched] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ password?: string; confirm?: string }>({});
  const [submitting, setSubmitting] = useState(false);

  const passwordsMatch = confirmPassword.length > 0 && confirmPassword === password;
  const passwordsMismatch = confirmTouched && confirmPassword.length > 0 && confirmPassword !== password;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;

    const passwordError = validatePassword(password);
    const confirmError = validatePasswordConfirmation(password, confirmPassword);
    setFieldErrors({ password: passwordError ?? undefined, confirm: confirmError ?? undefined });
    if (passwordError || confirmError) return;

    setSubmitting(true);
    try {
      await apiFetch("/auth/password-reset", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      });
      setStage("done");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        // The backend's message text is already the distinct, actionable
        // copy (invalid / expired / already used) — just surface it.
        setErrorMessage(err.message);
        setStage("error");
      } else if (err instanceof ApiError && err.fields?.length) {
        setFieldErrors({
          password: err.fieldError("new_password"),
        });
      } else {
        setFieldErrors({});
        setErrorMessage(
          err instanceof ApiError ? err.message : "Something went wrong. Please check your connection and try again."
        );
        setStage("error");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (stage === "error") {
    return (
      <div>
        <div
          role="alert"
          className="mb-5 flex items-start gap-2.5 rounded-[10px] border border-[#F0C9C9] bg-[#FBEEEE] px-[15px] py-[13px]"
        >
          <span className="mt-px flex h-[19px] w-[19px] shrink-0 items-center justify-center rounded-full bg-destructive text-xs text-white">
            !
          </span>
          <div className="text-[13.5px] text-[#A33232]">
            <strong>{errorMessage}</strong>
          </div>
        </div>
        <p className="mb-5 text-[13.5px] text-muted-foreground">
          Request a new link and we&apos;ll email it to you right away. Your existing password is unchanged.
        </p>
        <Button type="button" className="w-full" size="lg" onClick={() => router.push("/forgot-password")}>
          Request a new link
        </Button>
      </div>
    );
  }

  if (stage === "done") {
    return (
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-[46px] w-[46px] items-center justify-center rounded-full border border-[#B7E2CC] bg-[#E7F5EE] text-xl text-emerald-600">
          ✓
        </div>
        <h1 className="mb-1.5 text-xl font-bold tracking-tight text-foreground">Password updated successfully</h1>
        <p className="text-[13.5px] text-muted-foreground">
          Your new password is now active. Please log in to continue.
        </p>

        <div className="mt-4 rounded-[10px] border border-[#F0F0ED] bg-[#FAFAF8] px-4 py-3.5 text-left text-[13px] text-foreground/80">
          Didn&apos;t do this?{" "}
          <a href="mailto:support@bursatrack.com" className="font-semibold">
            Contact support immediately
          </a>
          .
        </div>

        <div className="h-5" />
        <Button type="button" className="w-full" size="lg" onClick={() => router.push("/login?reset=success")}>
          Continue to log in →
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <h1 className="mb-1 text-xl font-bold tracking-tight text-foreground">Choose a new password</h1>
      <p className="mb-4 text-[13.5px] text-muted-foreground">Choose a strong new password for your account.</p>

      <div className="mb-5 flex items-center gap-2 rounded-[9px] border border-[#D5DEFC] bg-accent px-[13px] py-[9px] text-[12.5px] text-accent-foreground">
        <span>🔒</span>
        <span>
          This link is valid for up to 1 hour and can only be used once. Resetting your password signs you out
          of all other sessions.
        </span>
      </div>

      <div className="mb-4">
        <Label htmlFor="new-password" className="mb-1.5 text-[13px] font-semibold">
          New password
        </Label>
        <Input
          id="new-password"
          type="password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onBlur={() => setFieldErrors((prev) => ({ ...prev, password: validatePassword(password) ?? undefined }))}
          aria-invalid={Boolean(fieldErrors.password)}
        />
        <PasswordStrengthMeter password={password} />
        <PasswordRulesChecklist password={password} />
        {fieldErrors.password && <p className="mt-1.5 text-xs text-destructive">{fieldErrors.password}</p>}
      </div>

      <div className="mb-1">
        <Label htmlFor="confirm-password" className="mb-1.5 text-[13px] font-semibold">
          Confirm new password
        </Label>
        <Input
          id="confirm-password"
          type="password"
          autoComplete="new-password"
          placeholder="Re-enter your new password"
          value={confirmPassword}
          onChange={(e) => {
            setConfirmPassword(e.target.value);
            setConfirmTouched(true);
          }}
          aria-invalid={passwordsMismatch}
        />
        {passwordsMismatch && <p className="mt-1.5 text-xs text-destructive">Passwords don&apos;t match.</p>}
        {passwordsMatch && !passwordsMismatch && (
          <p className="mt-1.5 text-xs text-emerald-700">✓ Passwords match.</p>
        )}
      </div>

      <div className="h-[22px]" />
      <Button type="submit" className="w-full" size="lg" disabled={submitting}>
        {submitting ? "Updating password…" : "Update password"}
      </Button>
      <p className="mt-3.5 text-center text-xs text-muted-foreground">
        Your portfolio data is untouched by a password reset.
      </p>
    </form>
  );
}
