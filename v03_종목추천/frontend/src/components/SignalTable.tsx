"use client";

import { useState, useMemo } from "react";
import type { DivergenceSignal } from "@/lib/types";
import StatusBadge from "./StatusBadge";

interface SignalTableProps {
  signals: DivergenceSignal[];
}

type SortKey =
  | "detected_at"
  | "ticker"
  | "rsi_at_signal"
  | "price_change_pct";

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function formatPrice(price: number, market: string): string {
  if (market === "KR") {
    return price >= 1000
      ? `${Math.round(price).toLocaleString()}`
      : price.toFixed(0);
  }
  return `$${price.toFixed(2)}`;
}

export default function SignalTable({ signals }: SignalTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("detected_at");
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = useMemo(() => {
    return [...signals].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "detected_at":
          cmp =
            new Date(a.detected_at).getTime() -
            new Date(b.detected_at).getTime();
          break;
        case "ticker":
          cmp = a.ticker.localeCompare(b.ticker);
          break;
        case "rsi_at_signal":
          cmp = a.rsi_at_signal - b.rsi_at_signal;
          break;
        case "price_change_pct":
          cmp = a.price_change_pct - b.price_change_pct;
          break;
      }
      return sortAsc ? cmp : -cmp;
    });
  }, [signals, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const SortHeader = ({
    label,
    sortField,
    className,
  }: {
    label: string;
    sortField: SortKey;
    className?: string;
  }) => (
    <th
      onClick={() => toggleSort(sortField)}
      className={`px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider cursor-pointer hover:text-zinc-200 select-none ${className ?? ""}`}
    >
      {label}
      {sortKey === sortField && (
        <span className="ml-1">{sortAsc ? "\u25B2" : "\u25BC"}</span>
      )}
    </th>
  );

  if (signals.length === 0) {
    return (
      <div className="text-center py-12 text-zinc-500">
        No signals found. Try running a scan.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="border-b border-zinc-700">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider w-10">
              #
            </th>
            <SortHeader label="Ticker" sortField="ticker" />
            <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
              Name
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
              Signal
            </th>
            <SortHeader label="RSI" sortField="rsi_at_signal" />
            <SortHeader label="Time" sortField="detected_at" />
            <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
              Price
            </th>
            <SortHeader
              label="Change"
              sortField="price_change_pct"
            />
            <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
              Category
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800">
          {sorted.map((signal, idx) => (
            <tr
              key={`${signal.ticker}-${signal.detected_at}-${signal.signal_type}`}
              className="hover:bg-zinc-800/50 transition-colors"
            >
              <td className="px-4 py-3 text-sm text-zinc-500">
                {idx + 1}
              </td>
              <td className="px-4 py-3 text-sm font-mono font-semibold text-zinc-200">
                {signal.ticker}
              </td>
              <td className="px-4 py-3 text-sm text-zinc-300 max-w-[160px] truncate">
                {signal.name}
              </td>
              <td className="px-4 py-3">
                <StatusBadge
                  signalType={signal.signal_type}
                  label={signal.signal_label}
                />
              </td>
              <td className="px-4 py-3 text-sm font-mono text-zinc-300">
                {signal.rsi_at_signal.toFixed(1)}
              </td>
              <td className="px-4 py-3 text-sm text-zinc-400">
                {timeAgo(signal.detected_at)}
              </td>
              <td className="px-4 py-3 text-sm font-mono text-zinc-300">
                {formatPrice(signal.current_price, signal.market)}
              </td>
              <td className="px-4 py-3 text-sm font-mono">
                <span
                  className={
                    signal.price_change_pct >= 0
                      ? "text-emerald-400"
                      : "text-red-400"
                  }
                >
                  {signal.price_change_pct >= 0 ? "+" : ""}
                  {signal.price_change_pct.toFixed(2)}%
                </span>
              </td>
              <td className="px-4 py-3 text-xs text-zinc-500">
                {signal.category}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
