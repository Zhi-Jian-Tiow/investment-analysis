import useSWR from "swr";

import { apiFetch } from "@/lib/api";
import type { PortfolioResponse } from "@/lib/types";

const fetcher = (path: string) => apiFetch<PortfolioResponse>(path);

/** GET /api/v1/portfolio/dashboard — see backend's docstring on that route
 * for why a minimal slice of the Epic 4 dashboard endpoint exists already.
 */
export function useDashboard() {
  const { data, error, isLoading, mutate } = useSWR<PortfolioResponse>("/api/v1/portfolio/dashboard", fetcher);

  return {
    portfolio: data,
    positions: data?.positions ?? [],
    isLoading,
    error,
    mutate,
  };
}
