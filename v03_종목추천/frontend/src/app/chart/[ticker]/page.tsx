"use client";

import { useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useChartData } from "@/hooks/useChartData";
import { useTsrData } from "@/hooks/useTsrData";
import { validateTicker } from "@/lib/api";
import type { ChartParams, Interval, TsrParams } from "@/lib/chart-types";
import type { IndicatorId, IndicatorState } from "@/lib/indicator-types";
import { INDICATOR_REGISTRY, getDefaultIndicatorStates } from "@/lib/indicator-types";

// Dynamic imports to avoid SSR issues with canvas/DOM
const TvChart = dynamic(() => import("@/components/chart/TvChart"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[700px] text-zinc-500">
      Loading chart...
    </div>
  ),
});

const IndicatorPanel = dynamic(
  () => import("@/components/chart/IndicatorPanel"),
  { ssr: false },
);

const LEGEND = [
  { label: "Regular Bull", color: "#26a69a", dashed: false },
  { label: "Hidden Bull", color: "#4dd0e1", dashed: true },
  { label: "Regular Bear", color: "#ef5350", dashed: false },
  { label: "Hidden Bear", color: "#ff8a65", dashed: true },
] as const;

const INTERVALS: { value: Interval; label: string }[] = [
  { value: "1h", label: "1H" },
  { value: "4h", label: "4H" },
  { value: "1d", label: "1D" },
];

const INTERVAL_LABELS: Record<Interval, string> = {
  "1h": "1H",
  "4h": "4H",
  "1d": "1D",
};

export default function ChartPage() {
  const params = useParams<{ ticker: string }>();
  const router = useRouter();
  const ticker = decodeURIComponent(params.ticker ?? "").toUpperCase();

  const [inputTicker, setInputTicker] = useState(ticker);
  const [validating, setValidating] = useState(false);
  const [tickerError, setTickerError] = useState<string | null>(null);

  // Interval
  const [interval, setInterval] = useState<Interval>("4h");

  // Multi-indicator state
  const [indicators, setIndicators] = useState<Record<IndicatorId, IndicatorState>>(
    getDefaultIndicatorStates,
  );

  const handleIndicatorChange = useCallback(
    (id: IndicatorId, state: IndicatorState) => {
      setIndicators((prev) => ({ ...prev, [id]: state }));
    },
    [],
  );

  // Build RSI divergence params from indicator state
  const rsiMeta = INDICATOR_REGISTRY["rsi-divergence"];
  const rsiCustom = indicators["rsi-divergence"].params;
  const rsiParams: ChartParams = {
    ...(interval !== "4h" ? { interval } : {}),
    ...Object.fromEntries(
      rsiMeta.paramInfo
        .filter((p) => rsiCustom[p.key] !== undefined)
        .map((p) => [p.key, rsiCustom[p.key]]),
    ),
  };

  // Build TSR params from indicator state
  const tsrMeta = INDICATOR_REGISTRY["tsr"];
  const tsrCustom = indicators["tsr"].params;
  const tsrParams: TsrParams = {
    ...(interval !== "4h" ? { interval } : {}),
    ...Object.fromEntries(
      tsrMeta.paramInfo
        .filter((p) => tsrCustom[p.key] !== undefined)
        .map((p) => [p.key, tsrCustom[p.key]]),
    ),
  };

  // Data hooks
  const { data, isLoading, error, clearAndRefresh } = useChartData(
    ticker || null,
    rsiParams,
  );
  const { data: tsrData } = useTsrData(
    ticker || null,
    indicators["tsr"].visible,
    tsrParams,
  );

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
            {ticker} — {INTERVAL_LABELS[interval]}
          </h1>

          {/* Timeframe buttons */}
          <div className="flex bg-zinc-800 rounded-lg p-0.5 border border-zinc-700">
            {INTERVALS.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setInterval(tf.value)}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                  interval === tf.value
                    ? "bg-purple-600 text-white"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={clearAndRefresh}
            className="bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 px-3 py-1.5 rounded-lg text-sm transition-colors"
            title="Clear cache &amp; reload data"
          >
            Refresh
          </button>
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

      {/* Main content: indicator panel + chart */}
      <div className="flex gap-3">
        <IndicatorPanel indicators={indicators} onChange={handleIndicatorChange} />

        <div className="flex-1 min-w-0">
          <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-2">
            {isLoading && (
              <div className="flex items-center justify-center h-[700px] text-zinc-500">
                Loading {INTERVAL_LABELS[interval]} chart data for {ticker}...
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
            {data && (
              <TvChart
                data={data}
                tsrData={indicators["tsr"].visible ? tsrData ?? null : null}
                indicators={indicators}
              />
            )}
          </div>

          {/* Legend & stats */}
          {data && (
            <div className="flex flex-wrap items-center gap-5 mt-3 text-xs text-zinc-400">
              {indicators["rsi-divergence"].visible && (
                <>
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
                </>
              )}
              {indicators["tsr"].visible && tsrData && (
                <>
                  <span className="text-zinc-600">|</span>
                  <span>
                    TL:{" "}
                    <strong className="text-zinc-200">
                      {tsrData.trend_lines.length}
                    </strong>
                  </span>
                  <span>
                    S/R:{" "}
                    <strong className="text-zinc-200">
                      {tsrData.sr_zones.length}
                    </strong>
                  </span>
                </>
              )}
              <span className="text-zinc-600">|</span>
              <span>
                Candles:{" "}
                <strong className="text-zinc-200">{data.candles.length}</strong>
              </span>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
