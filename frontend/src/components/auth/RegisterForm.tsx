"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useBrokers } from "@/hooks/useBrokers";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { validateEmail, validatePassword, validatePasswordConfirmation } from "@/lib/validation";

import { PasswordRulesChecklist } from "./PasswordRulesChecklist";
import { PasswordStrengthMeter } from "./PasswordStrengthMeter";

interface FieldErrors {
  email?: string;
  password?: string;
  passwordConfirm?: string;
  brokerId?: string;
}

export function RegisterForm() {
  const router = useRouter();
  const { register } = useAuth();
  const { brokers, isLoading: brokersLoading } = useBrokers();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [brokerId, setBrokerId] = useState("");

  const [errors, setErrors] = useState<FieldErrors>({});
  const [duplicateEmail, setDuplicateEmail] = useState(false);
  const [genericError, setGenericError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    const next: FieldErrors = {
      email: validateEmail(email) ?? undefined,
      password: validatePassword(password) ?? undefined,
      passwordConfirm: validatePasswordConfirmation(password, passwordConfirm) ?? undefined,
      brokerId: brokerId ? undefined : "Please select a broker",
    };
    setErrors(next);
    return !Object.values(next).some(Boolean);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setGenericError(null);
    setDuplicateEmail(false);

    if (!validate()) return;

    setSubmitting(true);
    try {
      await register(email, password, brokerId);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.fieldError("email") === "already registered") {
          // PRD-specified copy (FE-1.1 AC) — distinct from a plain inline
          // field error because it includes a link to /login.
          setDuplicateEmail(true);
        } else if (err.fields?.length) {
          setErrors({
            email: err.fieldError("email"),
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
    <form onSubmit={handleSubmit} noValidate>
      <h1 className="mb-1 text-xl font-bold tracking-tight text-foreground">Start your 14-day free trial</h1>
      <p className="mb-5 text-[13.5px] text-muted-foreground">
        Three fields. Under a minute. No card required.
      </p>

      {duplicateEmail && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-[13px] text-destructive">
          An account with this email already exists.{" "}
          <Link href="/login" className="font-semibold">
            Log in instead?
          </Link>
        </div>
      )}

      {genericError && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-[13px] text-destructive">
          {genericError}
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
          onBlur={() => setErrors((prev) => ({ ...prev, email: validateEmail(email) ?? undefined }))}
          aria-invalid={Boolean(errors.email)}
        />
        {errors.email && <p className="mt-1.5 text-xs text-destructive">{errors.email}</p>}
      </div>

      <div className="mb-4">
        <Label htmlFor="password" className="mb-1.5 text-[13px] font-semibold">
          Password
        </Label>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onBlur={() => setErrors((prev) => ({ ...prev, password: validatePassword(password) ?? undefined }))}
          aria-invalid={Boolean(errors.password)}
        />
        <PasswordStrengthMeter password={password} />
        <PasswordRulesChecklist password={password} />
        {errors.password && <p className="mt-1.5 text-xs text-destructive">{errors.password}</p>}
      </div>

      <div className="mb-4">
        <Label htmlFor="password-confirm" className="mb-1.5 text-[13px] font-semibold">
          Confirm password
        </Label>
        <Input
          id="password-confirm"
          type="password"
          autoComplete="new-password"
          value={passwordConfirm}
          onChange={(e) => setPasswordConfirm(e.target.value)}
          onBlur={() =>
            setErrors((prev) => ({
              ...prev,
              passwordConfirm: validatePasswordConfirmation(password, passwordConfirm) ?? undefined,
            }))
          }
          aria-invalid={Boolean(errors.passwordConfirm)}
        />
        {errors.passwordConfirm && <p className="mt-1.5 text-xs text-destructive">{errors.passwordConfirm}</p>}
      </div>

      <div className="mb-1">
        <Label htmlFor="broker" className="mb-1.5 text-[13px] font-semibold">
          Default broker
        </Label>
        <Select value={brokerId} onValueChange={(value) => setBrokerId(value ?? "")}>
          <SelectTrigger id="broker" className="w-full" aria-invalid={Boolean(errors.brokerId)}>
            {/* Base UI's Select.Value, unlike Radix's, does not auto-derive
                the label from the matching SelectItem's children — it shows
                the raw value unless given an explicit render function. */}
            <SelectValue>
              {(value: string | null) =>
                brokers.find((b) => b.id === value)?.name ??
                (brokersLoading ? "Loading brokers…" : "Select your broker")
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
        {errors.brokerId && <p className="mt-1.5 text-xs text-destructive">{errors.brokerId}</p>}
      </div>
      <p className="mb-5 text-xs text-muted-foreground">
        Used to pre-fill brokerage fees on every purchase. You can override per lot.
      </p>

      <Button type="submit" className="w-full" size="lg" disabled={submitting}>
        {submitting ? "Creating account…" : "Create account"}
      </Button>

      <p className="mt-3.5 text-center text-xs text-muted-foreground">
        Your data is stored securely. Cancel anytime during your 14-day free trial.
      </p>
    </form>
  );
}
