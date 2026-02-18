"use client";

import { useChartStore } from "@/store/chartStore";

const INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"];

const INDICATORS = [
  { id: "RSI_14", label: "RSI" },
  { id: "MACD", label: "MACD" },
  { id: "BB_20", label: "BB" },
  { id: "EMA_20", label: "EMA20" },
  { id: "EMA_50", label: "EMA50" },
  { id: "ADX", label: "ADX" },
  { id: "ATR_14", label: "ATR" },
  { id: "OBV", label: "OBV" },
];

interface ChartToolbarProps {
  symbol: string;
}

export default function ChartToolbar({ symbol }: ChartToolbarProps) {
  const { interval, setInterval, activeIndicators, toggleIndicator } =
    useChartStore();

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-gray-900 border-b border-gray-800">
      {/* Symbol */}
      <span className="font-bold text-lg">{symbol}</span>

      {/* Interval selector */}
      <div className="flex gap-1">
        {INTERVALS.map((tf) => (
          <button
            key={tf}
            onClick={() => setInterval(tf)}
            className={`px-2 py-1 text-xs rounded ${
              interval === tf
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:bg-gray-800"
            }`}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* Indicator toggles */}
      <div className="flex gap-1 ml-4">
        {INDICATORS.map((ind) => (
          <button
            key={ind.id}
            onClick={() => toggleIndicator(ind.id)}
            className={`px-2 py-1 text-xs rounded ${
              activeIndicators.includes(ind.id)
                ? "bg-purple-600 text-white"
                : "text-gray-400 hover:bg-gray-800"
            }`}
          >
            {ind.label}
          </button>
        ))}
      </div>
    </div>
  );
}
