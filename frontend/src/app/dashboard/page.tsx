"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { VerifyBanner } from "@/components/dashboard/VerifyBanner";
import { useCurrentUser } from "@/hooks/useCurrentUser";

/**
 * Minimal stub — the real portfolio dashboard is Epic 4 (BE-4.1/FE-4.1).
 * This page exists so FE-1.1's "redirected to the dashboard with a
 * persistent banner" AC has somewhere real to land: it bootstraps the
 * current user (POST /auth/refresh — no GET /auth/me exists yet, see
 * hooks/useCurrentUser.ts), shows the email-verification banner when
 * appropriate, and redirects to /login if there's no valid session.
 */
export default function DashboardPage() {
  const router = useRouter();
  const { user, status } = useCurrentUser();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status === "loading" || (status === "unauthenticated") || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        {status === "loading" ? "Loading…" : null}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-card">
        <div className="mx-auto flex h-[58px] max-w-[1200px] items-center gap-4 px-6">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
              B
            </div>
            <div className="text-[16.5px] font-bold tracking-tight text-foreground">BursaTrack</div>
          </div>
          <div className="flex-1" />
          <div className="flex h-[34px] w-[34px] items-center justify-center rounded-full border border-[#D5DEFC] bg-secondary text-xs font-bold text-secondary-foreground">
            {user.email.slice(0, 2).toUpperCase()}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1200px] px-6 py-6">
        {!user.email_verified && <VerifyBanner />}

        <div className="rounded-xl border border-border bg-card p-10 text-center">
          <h1 className="mb-2 text-xl font-bold tracking-tight text-foreground">Welcome to BursaTrack</h1>
          <p className="mx-auto max-w-md text-sm text-muted-foreground">
            You&apos;re signed in as <span className="font-medium text-foreground">{user.email}</span>. The
            portfolio dashboard — adding positions, tracking dividends, yield — is built in Epic 2 through 4.
            This page confirms registration and email verification are fully working end to end.
          </p>
        </div>
      </main>
    </div>
  );
}
