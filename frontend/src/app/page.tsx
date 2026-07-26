import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

/**
 * Minimal marketing landing page — just enough to give the FE-1.1 Gherkin's
 * "Given a visitor is on the marketing site / When they click 'Create
 * Account'" a real starting point. A full marketing site is out of scope
 * for this story.
 */
export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-6 text-center">
      <div className="flex items-center gap-2.5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-base font-bold text-primary-foreground">
          B
        </div>
        <div className="text-xl font-bold tracking-tight text-foreground">BursaTrack</div>
      </div>

      <h1 className="max-w-lg text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
        The dividend investor&apos;s source of truth for Bursa Malaysia
      </h1>
      <p className="max-w-md text-[15px] text-muted-foreground">
        True yield, per-tranche dividend logging, and your broker&apos;s actual fees — accurate to the ringgit.
      </p>

      <div className="flex gap-3">
        <Link href="/register" className={buttonVariants({ size: "lg" })}>
          Create Account
        </Link>
        <Link href="/login" className={buttonVariants({ size: "lg", variant: "outline" })}>
          Log in
        </Link>
      </div>
    </div>
  );
}
