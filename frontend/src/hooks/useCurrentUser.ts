"use client";

import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import type { AuthResponse, UserResponse } from "@/lib/types";

/**
 * Bootstraps "who is currently logged in" by calling POST /auth/refresh —
 * there's no dedicated GET /auth/me endpoint yet. This doubles as the
 * silent-refresh call FE-1.2 will eventually gate on the JWT's exp claim;
 * here it's called unconditionally on mount, which is correct for a stub
 * dashboard page but should be revisited (checked against exp first) once
 * FE-1.2 formalizes session handling.
 */
export function useCurrentUser() {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "authenticated" | "unauthenticated">("loading");

  useEffect(() => {
    let cancelled = false;

    apiFetch<AuthResponse>("/auth/refresh", { method: "POST" })
      .then((res) => {
        if (cancelled) return;
        setUser(res.user);
        setStatus("authenticated");
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          setStatus("unauthenticated");
        } else {
          // Non-auth failure (network, 5xx) — treat conservatively as
          // unauthenticated rather than showing a broken dashboard.
          setStatus("unauthenticated");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { user, status, setUser };
}
