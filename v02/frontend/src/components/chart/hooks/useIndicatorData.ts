import useSWR from "swr";
import { fetchAPI } from "@/lib/api";

export interface IndicatorMarker {
  time: number;
  position: "belowBar" | "aboveBar";
  color: string;
  shape: "circle" | "arrowUp" | "arrowDown";
  text: string;
}

export interface SRData {
  markers: IndicatorMarker[];
  levels: {
    support: number | null;
    support_bottom: number | null;
    resistance: number | null;
    resistance_top: number | null;
  };
  boxes: {
    type: string;
    start_time: number;
    end_time: number;
    top: number;
    bottom: number;
    vol: number;
    active: boolean;
  }[];
  error?: string;
}

export type IndicatorResult = Record<string, SRData>;

const fetcher = async (url: string): Promise<IndicatorResult> => {
  return fetchAPI(url);
};

export function useIndicatorData(
  symbol: string,
  interval: string,
  indicators: string[]
) {
  const enabled = indicators.length > 0;
  const key = enabled
    ? `/indicators?symbol=${symbol}&interval=${interval}&indicators=${indicators.join(",")}`
    : null;

  const { data, error, isLoading, mutate } = useSWR<IndicatorResult>(key, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 30000,
  });

  return { data, error, isLoading, mutate };
}
