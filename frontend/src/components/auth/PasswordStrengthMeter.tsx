import { passwordStrength } from "@/lib/validation";

const SEGMENT_COLOR = ["bg-border", "bg-destructive", "bg-amber-500", "bg-emerald-600"];
const LABEL_COLOR = ["text-muted-foreground", "text-destructive", "text-amber-700", "text-emerald-700"];

/** Visual-only aid matching the meter in the BursaTrack Design — not the
 * source of truth for whether a password is accepted (see lib/validation.ts). */
export function PasswordStrengthMeter({ password }: { password: string }) {
  if (!password) return null;

  const { score, label } = passwordStrength(password);

  return (
    <div className="mt-2 flex items-center gap-2">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className={`h-1 flex-1 rounded-full ${i < score ? SEGMENT_COLOR[score] : "bg-border"}`}
        />
      ))}
      <span className={`text-xs font-semibold ${LABEL_COLOR[score]}`}>{label}</span>
    </div>
  );
}
