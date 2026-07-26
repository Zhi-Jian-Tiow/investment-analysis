import useSWR from "swr";

import { apiFetch } from "@/lib/api";
import type { BrokerListResponse } from "@/lib/types";

const fetcher = (path: string) => apiFetch<BrokerListResponse>(path);

/**
 * GET /api/v1/brokers (architecture §12.4: SWR, 60-minute-ish staleness is
 * fine — broker fee structures change rarely). Public/no-auth-required —
 * see app.auth.dependencies.get_current_user_optional on the backend for
 * why: this must work on the registration page, before any session exists.
 */
export function useBrokers() {
  const { data, error, isLoading } = useSWR<BrokerListResponse>("/api/v1/brokers", fetcher, {
    revalidateOnFocus: false,
  });

  return {
    brokers: data?.brokers.filter((b) => b.is_system) ?? [],
    isLoading,
    error,
  };
}
