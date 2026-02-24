"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { validateTicker } from "@/lib/api";

export default function ChartIndexPage() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const input = ticker.trim().toUpperCase();
    if (!input) return;

    setValidating(true);
    setError(null);

    try {
      const result = await validateTicker(input);
      if (result.valid) {
        // Use the resolved ticker (e.g. NQ1! → NQ=F)
        router.push(`/chart/${encodeURIComponent(result.ticker)}`);
      } else {
        setError(`"${input}" — ticker not found`);
      }
    } catch {
      setError("Validation failed. Check backend connection.");
    } finally {
      setValidating(false);
    }
  };

  return (
    <main className="flex flex-col items-center justify-center min-h-[60vh]">
      <Link
        href="/"
        className="text-sm text-zinc-500 hover:text-zinc-300 mb-8 transition-colors"
      >
        &larr; Back to Screener
      </Link>
      <h1 className="text-2xl font-bold text-zinc-100 mb-4">
        RSI Divergence Chart
      </h1>
      <p className="text-sm text-zinc-500 mb-6">
        4H session-based candles with RSI divergence signals
      </p>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={ticker}
          onChange={(e) => {
            setTicker(e.target.value.toUpperCase());
            setError(null);
          }}
          placeholder="e.g. AAPL, NQ1!, ^NDX"
          className={`bg-zinc-800 border rounded-lg px-4 py-2 text-zinc-100 placeholder-zinc-500 w-64 focus:outline-none ${
            error ? "border-red-500" : "border-zinc-700 focus:border-zinc-500"
          }`}
          autoFocus
          disabled={validating}
        />
        <button
          type="submit"
          disabled={validating || !ticker.trim()}
          className="bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 text-zinc-200 px-6 py-2 rounded-lg transition-colors"
        >
          {validating ? "Checking..." : "View Chart"}
        </button>
      </form>
      {error && (
        <p className="mt-3 text-sm text-red-400">{error}</p>
      )}
      <p className="mt-6 text-xs text-zinc-600">
        TradingView tickers supported: NQ1!, ES1!, GC1!, CL1!, BTC1! etc.
      </p>
    </main>
  );
}
