import useSWR from "swr";

import { apiFetch } from "@/lib/api";
import type { PositionResponse } from "@/lib/types";

const fetcher = (path: string) => apiFetch<PositionResponse>(path);

/** GET /api/v1/portfolio/positions/{id} (added in BE-2.3 to unblock this). */
export function usePosition(positionId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<PositionResponse>(
    positionId ? `/api/v1/portfolio/positions/${positionId}` : null,
    fetcher
  );

  return {
    position: data,
    isLoading,
    error,
    mutate,
  };
}
