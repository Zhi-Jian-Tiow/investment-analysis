/**
 * Shared fetch wrapper (architecture §7.2 lib/api.ts). Every call includes
 * credentials so the HTTP-only session cookie set by the backend
 * (BE-1.1/1.2) is sent automatically — the frontend never reads or writes
 * that cookie directly.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ValidationFieldError {
  field: string;
  constraint: string;
  received: string | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields?: ValidationFieldError[];
  readonly retryAfterSeconds?: number;

  constructor(
    status: number,
    code: string,
    message: string,
    fields?: ValidationFieldError[],
    retryAfterSeconds?: number
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.retryAfterSeconds = retryAfterSeconds;
  }

  /** Convenience accessor: the constraint message for a specific field, if
   * the backend's 422 validation_failed response included one. */
  fieldError(field: string): string | undefined {
    return this.fields?.find((f) => f.field === field)?.constraint;
  }
}

// 401 codes meaning the session itself is dead — as opposed to
// invalid_credentials, which is a normal login-form error and must never
// trigger a redirect away from the login page.
const SESSION_INVALID_CODES = new Set(["invalid_token", "token_expired", "token_revoked"]);

interface ApiFetchOptions extends RequestInit {
  /** Skip the global session-expired redirect for this call. Used for the
   * initial auth bootstrap check (lib/auth-context.tsx), where a 401 just
   * means "not logged in yet" — not "was logged in, now isn't" (EX-010). */
  suppressAuthRedirect?: boolean;
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { suppressAuthRedirect, ...init } = options;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    let body: { error?: string; message?: string; fields?: ValidationFieldError[] } = {};
    try {
      body = await response.json();
    } catch {
      // Non-JSON error body (e.g. a network gateway page) — fall through to
      // the generic message below.
    }
    const retryAfterHeader = response.headers.get("Retry-After");
    const error = new ApiError(
      response.status,
      body.error ?? "unknown_error",
      body.message ?? "Something went wrong. Please try again.",
      body.fields,
      retryAfterHeader ? Number(retryAfterHeader) : undefined
    );

    if (
      !suppressAuthRedirect &&
      error.status === 401 &&
      SESSION_INVALID_CODES.has(error.code) &&
      typeof window !== "undefined" &&
      window.location.pathname !== "/login"
    ) {
      const redirectTo = `${window.location.pathname}${window.location.search}`;
      window.location.href = `/login?redirect=${encodeURIComponent(redirectTo)}&reason=session_expired`;
    }

    throw error;
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
