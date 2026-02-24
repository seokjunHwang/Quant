"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useChartData } from "@/hooks/useChartData";
import { validateTicker } from "@/lib/api";

// Dynamic import to avoid SSR issues with canvas/DOM
const TvChart = dynamic(() => import("@/components/chart/TvChart"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[700px] text-zinc-500">
      Loading chart...
    </div>
  ),
});

const LEGEND = [
  { label: "Regular Bull", color: "#26a69a", dashed: false },
  { label: "Hidden Bull", color: "#4dd0e1", dashed: true },
  { label: "Regular Bear", color: "#ef5350", dashed: false },
  { label: "Hidden Bear", color: "#ff8a65", dashed: true },
] as const;

export default function ChartPage() {
  const params = useParams<{ ticker: string }>();
  const router = useRouter();
  const ticker = decodeURIComponent(params.ticker ?? "").toUpperCase();

  const [inputTicker, setInputTicker] = useState(ticker);
  const [validating, setValidating] = useState(false);
  const [tickerError, setTickerError] = useState<string | null>(null);
  const { data, isLoading, error } = useChartData(ticker || null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const input = inputTicker.trim().toUpperCase();
    if (!input || input === ticker) return;

    setValidating(true);
    setTickerError(null);

    try {
      const result = await validateTicker(input);
      if (result.valid) {
        router.push(`/chart/${encodeURIComponent(result.ticker)}`);
      } else {
        setTickerError(`"${input}" not found`);
      }
    } catch {
      setTickerError("Check failed");
    } finally {
      setValidating(false);
    }
  };

  return (
    <main>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            &larr; Screener
          </Link>
          <h1 className="text-xl font-bold text-zinc-100">
            {ticker} — 4H RSI Divergence
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={inputTicker}
              onChange={(e) => {
                setInputTicker(e.target.value.toUpperCase());
                setTickerError(null);
              }}
              placeholder="TICKER"
              className={`bg-zinc-800 border rounded-lg px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-500 w-28 focus:outline-none ${
                tickerError
                  ? "border-red-500"
                  : "border-zinc-700 focus:border-zinc-500"
              }`}
              disabled={validating}
            />
            <button
              type="submit"
              disabled={validating || !inputTicker.trim()}
              className="bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 text-zinc-200 px-4 py-1.5 rounded-lg text-sm transition-colors"
            >
              {validating ? "..." : "Go"}
            </button>
          </form>
          {tickerError && (
            <span className="text-xs text-red-400">{tickerError}</span>
          )}
        </div>
      </div>

      {/* Chart */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-2">
        {isLoading && (
          <div className="flex items-center justify-center h-[700px] text-zinc-500">
            Loading chart data for {ticker}...
          </div>
        )}
        {error && (
          <div className="flex flex-col items-center justify-center h-[700px] text-red-400 gap-2">
            <span>Failed to load data for {ticker}</span>
            <span className="text-xs text-zinc-500">
              Check if the ticker is valid or try: AAPL, MSFT, ^NDX, NQ1!
            </span>
          </div>
        )}
        {data && <TvChart data={data} />}
      </div>

      {/* Legend & stats */}
      {data && (
        <div className="flex flex-wrap items-center gap-5 mt-3 text-xs text-zinc-400">
          {LEGEND.map((l) => (
            <span key={l.label} className="flex items-center gap-1.5">
              <span
                className="inline-block w-5 h-0.5"
                style={{
                  backgroundColor: l.color,
                  borderTop: l.dashed ? `2px dashed ${l.color}` : undefined,
                  background: l.dashed ? "transparent" : l.color,
                }}
              />
              {l.label}
            </span>
          ))}
          <span className="text-zinc-600">|</span>
          <span>
            Divergences:{" "}
            <strong className="text-zinc-200">
              {data.divergence_lines.length}
            </strong>
          </span>
          <span>
            Candles:{" "}
            <strong className="text-zinc-200">{data.candles.length}</strong>
          </span>
        </div>
      )}
    </main>
  );
}
