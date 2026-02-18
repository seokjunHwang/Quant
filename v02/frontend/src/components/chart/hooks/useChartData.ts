import useSWR from "swr";
import { fetchAPI } from "@/lib/api";

interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

const fetcher = async (url: string): Promise<CandleData[]> => {
  const res = await fetchAPI(url);
  return res.data || [];
};

export function useChartData(symbol: string, interval: string, limit = 500) {
  const { data, error, isLoading, mutate } = useSWR<CandleData[]>(
    `/market/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  return { data, error, isLoading, mutate };
}
