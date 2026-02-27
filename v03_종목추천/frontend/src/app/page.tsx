"use client";

import { useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useSignals } from "@/hooks/useSignals";
import type { ScanParams } from "@/lib/api";
import MarketTabs from "@/components/MarketTabs";
import FilterBar from "@/components/FilterBar";
import ScanButton from "@/components/ScanButton";
import SignalTable from "@/components/SignalTable";

const US_CATEGORIES = [
  "AI / 반도체",
  "클라우드 / SaaS",
  "바이오 / 헬스케어",
  "소비재 / 이커머스",
  "에너지 / 인프라",
  "산업재 / 방산",
];

const KR_CATEGORIES = [
  "반도체 / 전자",
  "2차전지 / 소재",
  "바이오 / 제약",
  "방산 / 조선",
  "엔터 / 플랫폼",
  "로봇 / AI",
];

const SCAN_DEFAULTS: Required<ScanParams> = {
  rsi_period: 14,
  lb_left: 5,
  lb_right: 3,
  range_lower: 5,
  range_upper: 50,
};

const SCAN_PARAM_INFO: {
  key: keyof ScanParams;
  label: string;
  desc: string;
  min: number;
  max: number;
}[] = [
  { key: "rsi_period", label: "RSI Period", desc: "RSI 계산 기간", min: 2, max: 50 },
  { key: "lb_left", label: "Pivot Left", desc: "피봇 왼쪽 확인 봉 수", min: 1, max: 20 },
  { key: "lb_right", label: "Pivot Right", desc: "피봇 오른쪽 확인 봉 수", min: 1, max: 20 },
  { key: "range_lower", label: "Range Min", desc: "두 피봇 사이 최소 봉 간격", min: 1, max: 50 },
  { key: "range_upper", label: "Range Max", desc: "두 피봇 사이 최대 봉 간격", min: 10, max: 200 },
];

const SCAN_INTERVALS = [
  { value: "15m", label: "15M" },
  { value: "1h", label: "1H" },
  { value: "4h", label: "4H" },
  { value: "1d", label: "1D" },
  { value: "1w", label: "1W" },
] as const;

type ScanInterval = (typeof SCAN_INTERVALS)[number]["value"];

export default function Home() {
  const [market, setMarket] = useState<string | undefined>(undefined);
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [signalType, setSignalType] = useState<string | undefined>(undefined);
  const [interval, setInterval] = useState<ScanInterval>("4h");

  // Scan settings
  const [showSettings, setShowSettings] = useState(false);
  const [scanParams, setScanParams] = useState<ScanParams>({});
  const [draft, setDraft] = useState<Required<ScanParams>>({ ...SCAN_DEFAULTS });

  const { data, isLoading, isTriggering, trigger } = useSignals({
    market,
    category,
    signal_type: signalType,
  });

  const categories = useMemo(() => {
    if (market === "US") return US_CATEGORIES;
    if (market === "KR") return KR_CATEGORIES;
    return [...US_CATEGORIES, ...KR_CATEGORIES];
  }, [market]);

  const handleMarketChange = (m: string | undefined) => {
    setMarket(m);
    setCategory(undefined);
  };

  const handleScan = useCallback(() => {
    // Only send non-default params
    const params: ScanParams = {};
    for (const { key } of SCAN_PARAM_INFO) {
      if (scanParams[key] !== undefined) {
        params[key] = scanParams[key];
      }
    }
    trigger(
      market,
      interval !== "4h" ? interval : undefined,
      Object.keys(params).length > 0 ? params : undefined,
    );
  }, [market, interval, scanParams, trigger]);

  const openSettings = useCallback(() => {
    const merged = { ...SCAN_DEFAULTS };
    for (const { key } of SCAN_PARAM_INFO) {
      if (scanParams[key] !== undefined) {
        merged[key] = scanParams[key]!;
      }
    }
    setDraft(merged);
    setShowSettings(true);
  }, [scanParams]);

  const applySettings = useCallback(() => {
    const next: ScanParams = {};
    for (const { key } of SCAN_PARAM_INFO) {
      if (draft[key] !== SCAN_DEFAULTS[key]) {
        next[key] = draft[key];
      }
    }
    setScanParams(next);
    setShowSettings(false);
  }, [draft]);

  const hasCustomParams = Object.keys(scanParams).length > 0;

  const lastScan = data?.scanned_at
    ? new Date(data.scanned_at).toLocaleString("ko-KR")
    : null;

  return (
    <main>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">
            RSI Divergence Screener
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            {SCAN_INTERVALS.find((i) => i.value === interval)?.label ?? "4H"} timeframe | 140 stocks (US 70 + KR 70)
            <Link
              href="/chart"
              className="ml-3 text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Chart View &rarr;
            </Link>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Interval selector */}
          <div className="flex bg-zinc-800 rounded-lg p-0.5 border border-zinc-700">
            {SCAN_INTERVALS.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setInterval(tf.value)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  interval === tf.value
                    ? "bg-purple-600 text-white"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {tf.label}
              </button>
            ))}
          </div>
          <button
            onClick={openSettings}
            className={`bg-zinc-800 hover:bg-zinc-700 border text-zinc-300 px-3 py-1.5 rounded-lg text-sm transition-colors flex items-center gap-1.5 ${
              hasCustomParams ? "border-yellow-500/50" : "border-zinc-700"
            }`}
            title="RSI Divergence Settings"
          >
            RSI Divergence
            {hasCustomParams && (
              <span className="text-yellow-500 text-[10px]">*</span>
            )}
            <svg className="w-3 h-3 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <ScanButton
            onClick={handleScan}
            isLoading={isTriggering}
          />
        </div>
      </div>

      {/* Settings Popup */}
      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 w-[420px] max-h-[80vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-zinc-100">
                RSI Divergence Settings
              </h2>
              <button
                onClick={() => setShowSettings(false)}
                className="text-zinc-500 hover:text-zinc-300 text-xl leading-none"
              >
                &times;
              </button>
            </div>

            <div className="space-y-4">
              {SCAN_PARAM_INFO.map(({ key, label, desc, min, max }) => (
                <div key={key}>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-sm font-medium text-zinc-300">
                      {label}
                      <span className="ml-2 text-zinc-100 font-bold">
                        {draft[key]}
                      </span>
                    </label>
                    {draft[key] !== SCAN_DEFAULTS[key] && (
                      <span className="text-[10px] text-yellow-500">
                        default: {SCAN_DEFAULTS[key]}
                      </span>
                    )}
                  </div>
                  <input
                    type="range"
                    min={min}
                    max={max}
                    value={draft[key]}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        [key]: Number(e.target.value),
                      }))
                    }
                    className="w-full accent-purple-500"
                  />
                  <p className="text-[11px] text-zinc-500 mt-0.5">{desc}</p>
                </div>
              ))}
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={applySettings}
                className="flex-1 bg-purple-600 hover:bg-purple-500 text-white py-2 rounded-lg text-sm font-medium transition-colors"
              >
                Apply
              </button>
              <button
                onClick={() => setDraft({ ...SCAN_DEFAULTS })}
                className="bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 px-4 py-2 rounded-lg text-sm transition-colors"
              >
                Reset
              </button>
              <button
                onClick={() => setShowSettings(false)}
                className="bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-400 px-4 py-2 rounded-lg text-sm transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <MarketTabs selected={market} onChange={handleMarketChange} />
        <FilterBar
          categories={categories}
          selectedCategory={category}
          onCategoryChange={setCategory}
          selectedSignalType={signalType}
          onSignalTypeChange={setSignalType}
        />
      </div>

      {/* Stats Bar */}
      {data && (
        <div className="flex flex-wrap gap-6 mb-4 text-sm text-zinc-400">
          <span>
            Scanned: <strong className="text-zinc-200">{data.total_stocks}</strong> stocks
          </span>
          <span>
            Signals: <strong className="text-zinc-200">{data.signals_found}</strong>
          </span>
          <span>
            Duration: <strong className="text-zinc-200">{data.scan_duration_sec.toFixed(1)}s</strong>
          </span>
          {lastScan && (
            <span>
              Last scan: <strong className="text-zinc-200">{lastScan}</strong>
            </span>
          )}
          {hasCustomParams && (
            <>
              <span className="text-zinc-600">|</span>
              <span className="text-yellow-500">Custom params active</span>
            </>
          )}
        </div>
      )}

      {/* Table */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden">
        {isLoading ? (
          <div className="text-center py-12 text-zinc-500">Loading...</div>
        ) : data ? (
          <SignalTable signals={data.signals} />
        ) : (
          <div className="text-center py-12 text-zinc-500">
            No scan results yet. Click &quot;Scan Now&quot; to start.
          </div>
        )}
      </div>
    </main>
  );
}
