"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import type { AuthResponse, UserResponse } from "@/lib/types";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  user: UserResponse | null;
  status: AuthStatus;
  register: (email: string, password: string, brokerId: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// Matches architecture §14.1's silent-refresh design: proactively refresh
// once the session is within this window of expiring.
const REFRESH_THRESHOLD_MS = 24 * 60 * 60 * 1000;
// How often to check while the tab is open — well inside the 24h buffer, so
// there's no realistic risk of missing the window between checks.
const CHECK_INTERVAL_MS = 15 * 60 * 1000;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const expiresAtRef = useRef<number | null>(null);

  const applyAuthResponse = useCallback((res: AuthResponse) => {
    setUser(res.user);
    setStatus("authenticated");
    expiresAtRef.current = new Date(res.expires_at).getTime();
  }, []);

  const silentRefresh = useCallback(async () => {
    try {
      const res = await apiFetch<AuthResponse>("/auth/refresh", { method: "POST" });
      applyAuthResponse(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        setStatus("unauthenticated");
        expiresAtRef.current = null;
      }
      // Other errors (a network blip) are left alone — the next scheduled
      // check will simply try again.
    }
  }, [applyAuthResponse]);

  useEffect(() => {
    let cancelled = false;
    apiFetch<AuthResponse>("/auth/refresh", { method: "POST", suppressAuthRedirect: true })
      .then((res) => {
        if (!cancelled) applyAuthResponse(res);
      })
      .catch(() => {
        if (!cancelled) setStatus("unauthenticated");
      });
    return () => {
      cancelled = true;
    };
  }, [applyAuthResponse]);

  useEffect(() => {
    function maybeRefresh() {
      if (status !== "authenticated" || expiresAtRef.current === null) return;
      if (expiresAtRef.current - Date.now() < REFRESH_THRESHOLD_MS) {
        void silentRefresh();
      }
    }

    const interval = setInterval(maybeRefresh, CHECK_INTERVAL_MS);
    window.addEventListener("focus", maybeRefresh);
    return () => {
      clearInterval(interval);
      window.removeEventListener("focus", maybeRefresh);
    };
  }, [status, silentRefresh]);

  const register = useCallback(
    async (email: string, password: string, brokerId: string) => {
      const res = await apiFetch<AuthResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, broker_id: brokerId }),
      });
      applyAuthResponse(res);
    },
    [applyAuthResponse]
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await apiFetch<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      applyAuthResponse(res);
    },
    [applyAuthResponse]
  );

  const logout = useCallback(async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST", suppressAuthRedirect: true });
    } finally {
      setUser(null);
      setStatus("unauthenticated");
      expiresAtRef.current = null;
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, status, register, login, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
