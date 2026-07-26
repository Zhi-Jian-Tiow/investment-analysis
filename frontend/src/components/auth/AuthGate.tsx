"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth-context";

/**
 * Auth-only route guard. Epic 7's SubscriptionGate extends this with
 * trial/subscription-status checks — this is just the "must be logged in"
 * half (FE-1.2 scope).
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (status !== "unauthenticated") return;
    const query = searchParams.toString();
    const currentUrl = query ? `${pathname}?${query}` : pathname;
    router.replace(`/login?redirect=${encodeURIComponent(currentUrl)}`);
  }, [status, pathname, searchParams, router]);

  if (status !== "authenticated") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        {status === "loading" ? "Loading…" : null}
      </div>
    );
  }

  return <>{children}</>;
}
