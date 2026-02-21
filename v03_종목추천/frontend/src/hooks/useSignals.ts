"use client";

import useSWR from "swr";
import { getScanResults, triggerScan } from "@/lib/api";
import type { ScanResult } from "@/lib/types";
import { useCallback, useState } from "react";

export function useSignals(params?: {
  market?: string;
  category?: string;
  signal_type?: string;
}) {
  const key = ["scan", params?.market, params?.category, params?.signal_type]
    .filter(Boolean)
    .join("-");

  const { data, error, isLoading, mutate } = useSWR<ScanResult | null>(
    key,
    () => getScanResults(params),
    { refreshInterval: 60_000 }
  );

  const [isTriggering, setIsTriggering] = useState(false);

  const trigger = useCallback(
    async (market?: string) => {
      setIsTriggering(true);
      try {
        const result = await triggerScan(market);
        mutate(result, false);
        return result;
      } finally {
        setIsTriggering(false);
      }
    },
    [mutate]
  );

  return { data, error, isLoading, isTriggering, trigger, refresh: mutate };
}
