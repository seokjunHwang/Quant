"use client";

import useSWR from "swr";
import { getTsrData } from "@/lib/api";
import type { TsrData, TsrParams } from "@/lib/chart-types";

export function useTsrData(
  ticker: string | null,
  enabled: boolean,
  params?: TsrParams,
) {
  const key =
    ticker && enabled
      ? ["tsr", ticker, JSON.stringify(params ?? {})].join("-")
      : null;

  const { data, error, isLoading, mutate } = useSWR<TsrData>(
    key,
    () => (ticker ? getTsrData(ticker, params) : Promise.reject()),
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );

  return { data, error, isLoading, refresh: mutate };
}
