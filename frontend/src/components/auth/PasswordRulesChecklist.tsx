import { passwordRuleChecks } from "@/lib/validation";

export function PasswordRulesChecklist({ password }: { password: string }) {
  return (
    <div className="mt-3 flex flex-col gap-1.5">
      {passwordRuleChecks(password).map((rule) => (
        <div
          key={rule.label}
          className={`flex items-center gap-2 text-[12.5px] ${rule.ok ? "text-emerald-700" : "text-muted-foreground"}`}
        >
          <span
            className={`flex h-[15px] w-[15px] shrink-0 items-center justify-center rounded-full border text-[9px] text-white ${
              rule.ok ? "border-emerald-600 bg-emerald-600" : "border-input bg-transparent"
            }`}
          >
            {rule.ok ? "✓" : ""}
          </span>
          <span>{rule.label}</span>
        </div>
      ))}
    </div>
  );
}
