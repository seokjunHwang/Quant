"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useSignals } from "@/hooks/useSignals";
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

export default function Home() {
  const [market, setMarket] = useState<string | undefined>(undefined);
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [signalType, setSignalType] = useState<string | undefined>(undefined);

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
            4H timeframe | 140 stocks (US 70 + KR 70)
            <Link
              href="/chart"
              className="ml-3 text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Chart View &rarr;
            </Link>
          </p>
        </div>
        <ScanButton
          onClick={() => trigger(market)}
          isLoading={isTriggering}
        />
      </div>

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
