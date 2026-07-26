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

  constructor(status: number, code: string, message: string, fields?: ValidationFieldError[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }

  /** Convenience accessor: the constraint message for a specific field, if
   * the backend's 422 validation_failed response included one. */
  fieldError(field: string): string | undefined {
    return this.fields?.find((f) => f.field === field)?.constraint;
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
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
    throw new ApiError(
      response.status,
      body.error ?? "unknown_error",
      body.message ?? "Something went wrong. Please try again.",
      body.fields
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
