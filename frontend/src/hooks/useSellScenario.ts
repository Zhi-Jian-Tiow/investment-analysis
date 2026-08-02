import useSWR from "swr";

import { apiFetch } from "@/lib/api";
import type { SellScenarioResponse } from "@/lib/types";

const fetcher = (path: string) => apiFetch<SellScenarioResponse>(path);

interface SellScenarioParams {
  shares: number;
  /** 4dp-formatted string, or omitted to use only the default ladder. */
  customPrice?: string;
  /** Omitted to let the backend resolve A-006's default (most recently
   * created active lot's broker). */
  brokerId?: string;
}

/** GET /api/v1/portfolio/positions/{id}/sell-scenario (BE-4.2) — stateless,
 * nothing persisted. SWR's own key-based caching means identical
 * shares/price/broker combinations don't re-fetch. */
export function useSellScenario(positionId: string, { shares, customPrice, brokerId }: SellScenarioParams) {
  const query = new URLSearchParams();
  query.set("shares", String(shares));
  if (customPrice) query.set("price", customPrice);
  if (brokerId) query.set("broker_id", brokerId);

  const key = `/api/v1/portfolio/positions/${positionId}/sell-scenario?${query.toString()}`;
  const { data, error, isLoading } = useSWR<SellScenarioResponse>(key, fetcher);

  return { scenario: data, isLoading, error };
}
