"use client";

import { use } from "react";
import TradingChart from "@/components/chart/TradingChart";
import ChartToolbar from "@/components/chart/ChartToolbar";

export default function ChartPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = use(params);

  return (
    <div className="flex flex-col h-screen">
      <ChartToolbar symbol={symbol} />
      <div className="flex-1 min-h-0">
        <TradingChart symbol={symbol} />
      </div>
    </div>
  );
}
