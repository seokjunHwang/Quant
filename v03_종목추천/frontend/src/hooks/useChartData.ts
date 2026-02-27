"use client";

import useSWR, { useSWRConfig } from "swr";
import { getChartData } from "@/lib/api";
import type { ChartData, ChartParams } from "@/lib/chart-types";

export function useChartData(ticker: string | null, params?: ChartParams) {
  const key = ticker
    ? ["chart", ticker, JSON.stringify(params ?? {})].join("-")
    : null;

  const { cache } = useSWRConfig();

  const { data, error, isLoading, mutate } = useSWR<ChartData>(
    key,
    () => (ticker ? getChartData(ticker, params) : Promise.reject()),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30_000,
      refreshInterval: 5 * 60 * 1000, // auto-refresh every 5 minutes
      errorRetryCount: 2,
      errorRetryInterval: 3000,
      shouldRetryOnError: (err) => {
        // Don't retry on 400 (bad request), only retry on 404/5xx (may be transient)
        if (err?.message?.includes("400")) return false;
        return true;
      },
    },
  );

  /** Clear all SWR cache entries and re-fetch current key. */
  const clearAndRefresh = async () => {
    if (cache instanceof Map) {
      cache.clear();
    }
    await mutate();
  };

  return { data, error, isLoading, refresh: mutate, clearAndRefresh };
}
