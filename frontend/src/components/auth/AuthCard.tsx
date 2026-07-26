import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Shared visual shell for auth screens (register/login), matching the
 * BursaTrack Design (BursaTrack.dc.html): centered logo lockup above a
 * white, rounded, bordered card.
 */
export function AuthCard({
  children,
  footer,
  width = 440,
}: {
  children: ReactNode;
  /** Rendered below the card, outside its border (e.g. "Already have an
   * account? Log in"), matching the BursaTrack Design layout. */
  footer?: ReactNode;
  width?: number;
}) {
  return (
    <div className="flex min-h-screen items-start justify-center bg-background px-5 py-16">
      <div className="w-full animate-in fade-in slide-in-from-bottom-1 duration-300" style={{ maxWidth: width }}>
        <Link href="/" className="mb-7 flex items-center justify-center gap-2.5 hover:no-underline">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-[15px] font-bold text-primary-foreground">
            B
          </div>
          <div className="text-[19px] font-bold tracking-tight text-foreground">BursaTrack</div>
        </Link>
        <div className="rounded-[14px] border border-border bg-card p-7 shadow-[0_1px_2px_rgba(20,20,20,0.04)]">
          {children}
        </div>
        {footer && <div className="mt-[18px] text-center text-[13.5px] text-muted-foreground">{footer}</div>}
      </div>
    </div>
  );
}
