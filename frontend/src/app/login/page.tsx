import Link from "next/link";

import { AuthCard } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Visual placeholder only — matches the BursaTrack Design's login screen so
 * the "Log in instead?" / "Log in" links from FE-1.1 don't land on a broken
 * page. Real submit wiring (BE-1.2 integration, lockout countdown, session
 * bootstrap) is FE-1.2's scope, not implemented here.
 */
export default function LoginPage() {
  return (
    <AuthCard
      width={400}
      footer={
        <>
          Don&apos;t have an account? <Link href="/register">Start your free trial</Link>
        </>
      }
    >
      <h1 className="mb-1 text-xl font-bold tracking-tight text-foreground">Welcome back</h1>
      <p className="mb-5 text-[13.5px] text-muted-foreground">Log in to see your portfolio.</p>

      <div className="mb-4">
        <Label htmlFor="email" className="mb-1.5 text-[13px] font-semibold">
          Email address
        </Label>
        <Input id="email" type="email" autoComplete="email" placeholder="you@example.com" />
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
        <Input id="password" type="password" autoComplete="current-password" />
      </div>

      <Button type="button" className="w-full" size="lg" disabled title="Login is implemented in FE-1.2">
        Log in
      </Button>
      <p className="mt-3 text-center text-xs text-muted-foreground">Login isn&apos;t wired up yet (FE-1.2).</p>
    </AuthCard>
  );
}
