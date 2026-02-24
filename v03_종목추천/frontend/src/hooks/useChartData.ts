"use client";

import useSWR from "swr";
import { getChartData } from "@/lib/api";
import type { ChartData, ChartParams } from "@/lib/chart-types";

export function useChartData(ticker: string | null, params?: ChartParams) {
  const key = ticker
    ? ["chart", ticker, JSON.stringify(params ?? {})].join("-")
    : null;

  const { data, error, isLoading, mutate } = useSWR<ChartData>(
    key,
    () => (ticker ? getChartData(ticker, params) : Promise.reject()),
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );

  return { data, error, isLoading, refresh: mutate };
}
