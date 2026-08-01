import useSWR from "swr";

import { apiFetch } from "@/lib/api";
import type { DividendCalendarResponse } from "@/lib/types";

const fetcher = (path: string) => apiFetch<DividendCalendarResponse>(path);

/** GET /api/v1/portfolio/dividends?year= (BE-3.3) — year-scoped (defaults to
 * the current year), not a rolling "future dates plus trailing 30 days"
 * window; see that endpoint's own docstring for why. */
export function useDividendCalendar(year: number) {
  const { data, error, isLoading, mutate } = useSWR<DividendCalendarResponse>(
    `/api/v1/portfolio/dividends?year=${year}`,
    fetcher
  );

  return {
    tranches: data?.tranches ?? [],
    isLoading,
    error,
    mutate,
  };
}
