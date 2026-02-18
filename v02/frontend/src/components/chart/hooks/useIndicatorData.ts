import useSWR from "swr";
import { fetchAPI } from "@/lib/api";

const fetcher = async (url: string) => {
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

  const { data, error, isLoading, mutate } = useSWR(key, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 30000,
  });

  return { data, error, isLoading, mutate };
}
