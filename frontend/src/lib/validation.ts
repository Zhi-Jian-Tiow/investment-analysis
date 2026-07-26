/**
 * Client-side mirrors of BAS VR-001 (email) and VR-002 (password). Copy
 * matches the BAS spec verbatim so inline errors are correct before a
 * request ever reaches the backend (FE-1.1 AC: "Inline field validation
 * matches VR-001/VR-002 error copy exactly").
 */

export function validateEmail(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return "Email address is required";
  if (trimmed.length > 254) return "Email address must be under 254 characters";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) return "Please enter a valid email address";
  return null;
}

export function validatePassword(value: string): string | null {
  if (!value) return "Password is required";
  if (value.length < 8) return "Password must be at least 8 characters";
  if (value.length > 128) return "Password must be under 128 characters";
  if (!/[A-Z]/.test(value)) return "Password must contain at least one uppercase letter";
  if (!/[0-9]/.test(value)) return "Password must contain at least one digit";
  return null;
}

export function validatePasswordConfirmation(password: string, confirmation: string): string | null {
  if (!confirmation) return "Please confirm your password";
  if (password !== confirmation) return "Passwords do not match";
  return null;
}

export interface PasswordStrength {
  /** 0-3: how many of {length>=8, has uppercase, has digit} are satisfied. */
  score: 0 | 1 | 2 | 3;
  label: "Too weak" | "Weak" | "Good" | "Strong";
}

/** Purely a visual aid (matches the meter shown in the BursaTrack Design) —
 * validatePassword above is the actual source of truth for whether a
 * password is accepted. */
export function passwordStrength(value: string): PasswordStrength {
  const score = [(value.length >= 8), /[A-Z]/.test(value), /[0-9]/.test(value)].filter(Boolean)
    .length as PasswordStrength["score"];
  const labels: PasswordStrength["label"][] = ["Too weak", "Weak", "Good", "Strong"];
  return { score, label: labels[score] };
}

export interface PasswordRuleCheck {
  label: string;
  ok: boolean;
}

/** Live checklist rows for the reset-password screen. Deliberately mirrors
 * VR-002 exactly — the BursaTrack Design's equivalent checklist uses
 * different rules ("upper and lower case", "a number or symbol") that don't
 * match what the backend actually enforces; showing those would be
 * inaccurate, so this uses our real three checks instead. */
export function passwordRuleChecks(value: string): PasswordRuleCheck[] {
  return [
    { label: "At least 8 characters", ok: value.length >= 8 },
    { label: "One uppercase letter", ok: /[A-Z]/.test(value) },
    { label: "One digit", ok: /[0-9]/.test(value) },
  ];
}
