"use client";

import { useChartStore } from "@/store/chartStore";

const INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"];

const PINE_INDICATORS = [
  { id: "SR_BREAKS", label: "S/R" },
];

const BUILTIN_INDICATORS = [
  { id: "RSI_14", label: "RSI" },
  { id: "MACD", label: "MACD" },
  { id: "BB_20", label: "BB" },
  { id: "EMA_20", label: "EMA20" },
  { id: "EMA_50", label: "EMA50" },
  { id: "ADX", label: "ADX" },
  { id: "ATR_14", label: "ATR" },
  { id: "OBV", label: "OBV" },
];

const btnBase: React.CSSProperties = {
  padding: "4px 8px", fontSize: 12, borderRadius: 4,
  border: "none", cursor: "pointer",
};

interface ChartToolbarProps {
  symbol: string;
}

export default function ChartToolbar({ symbol }: ChartToolbarProps) {
  const { interval, setInterval, activeIndicators, toggleIndicator } =
    useChartStore();

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 16,
      padding: "8px 16px", background: "#111827",
      borderBottom: "1px solid #1f2937", height: 50,
    }}>
      <span style={{ fontWeight: 700, fontSize: 16, color: "#f9fafb" }}>{symbol}</span>

      {/* Intervals */}
      <div style={{ display: "flex", gap: 4 }}>
        {INTERVALS.map((tf) => (
          <button
            key={tf}
            onClick={() => setInterval(tf)}
            style={{
              ...btnBase,
              background: interval === tf ? "#2563eb" : "transparent",
              color: interval === tf ? "#fff" : "#9ca3af",
            }}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* Pine indicators */}
      <div style={{ display: "flex", gap: 4, marginLeft: 16, paddingLeft: 16, borderLeft: "1px solid #374151" }}>
        <span style={{ color: "#6b7280", fontSize: 11, alignSelf: "center", marginRight: 4 }}>Pine:</span>
        {PINE_INDICATORS.map((ind) => (
          <button
            key={ind.id}
            onClick={() => toggleIndicator(ind.id)}
            style={{
              ...btnBase,
              background: activeIndicators.includes(ind.id) ? "#16a34a" : "transparent",
              color: activeIndicators.includes(ind.id) ? "#fff" : "#9ca3af",
            }}
          >
            {ind.label}
          </button>
        ))}
      </div>

      {/* Built-in indicators */}
      <div style={{ display: "flex", gap: 4 }}>
        {BUILTIN_INDICATORS.map((ind) => (
          <button
            key={ind.id}
            onClick={() => toggleIndicator(ind.id)}
            style={{
              ...btnBase,
              background: activeIndicators.includes(ind.id) ? "#7c3aed" : "transparent",
              color: activeIndicators.includes(ind.id) ? "#fff" : "#9ca3af",
            }}
          >
            {ind.label}
          </button>
        ))}
      </div>
    </div>
  );
}
