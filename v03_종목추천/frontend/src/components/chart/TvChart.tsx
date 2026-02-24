"use client";

import { useRef, useEffect } from "react";
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  LineSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type UTCTimestamp,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { TrendLinePrimitive } from "./plugins/trend-line";
import type { ChartData } from "@/lib/chart-types";

const COLORS: Record<string, string> = {
  regular_bullish: "#26a69a",
  hidden_bullish: "#4dd0e1",
  regular_bearish: "#ef5350",
  hidden_bearish: "#ff8a65",
};

interface TvChartProps {
  data: ChartData;
}

export default function TvChart({ data }: TvChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create chart
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#131722" },
        textColor: "#787b86",
      },
      grid: {
        vertLines: { color: "#1e222d" },
        horzLines: { color: "#1e222d" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: {
        borderColor: "#1e222d",
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: { borderColor: "#1e222d" },
    });
    chartRef.current = chart;

    // ─── Pane 0: Candlestick ───
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });

    candleSeries.setData(
      data.candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );

    // Signal markers on candles
    const candleMarkers: SeriesMarker<Time>[] = data.signals
      .map((s) => ({
        time: s.time as UTCTimestamp as Time,
        position: s.position as "belowBar" | "aboveBar",
        color: s.color,
        shape: s.shape as "arrowUp" | "arrowDown",
        text: s.text,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));

    if (candleMarkers.length > 0) {
      createSeriesMarkers(candleSeries, candleMarkers);
    }

    // ─── Pane 1: RSI ───
    const rsiSeries = chart.addSeries(
      LineSeries,
      {
        color: "#bb86fc",
        lineWidth: 2,
        lastValueVisible: true,
        priceFormat: {
          type: "custom",
          formatter: (v: number) => v.toFixed(1),
        },
      },
      1,
    );

    rsiSeries.setData(
      data.rsi.map((r) => ({
        time: r.time as UTCTimestamp,
        value: r.value,
      })),
    );

    // RSI 30/70 level lines
    rsiSeries.createPriceLine({
      price: 70,
      color: "rgba(239, 83, 80, 0.5)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
    });
    rsiSeries.createPriceLine({
      price: 30,
      color: "rgba(38, 166, 154, 0.5)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
    });

    // RSI pane height
    const panes = chart.panes();
    if (panes.length > 1) {
      panes[0].setHeight(480);
      panes[1].setHeight(180);
    }

    // Pivot markers on RSI
    const pivotMarkers: SeriesMarker<Time>[] = [
      ...data.pivot_lows.map((p) => ({
        time: p.time as UTCTimestamp as Time,
        position: "belowBar" as const,
        color: "rgba(38, 166, 154, 0.4)",
        shape: "circle" as const,
        text: "",
      })),
      ...data.pivot_highs.map((p) => ({
        time: p.time as UTCTimestamp as Time,
        position: "aboveBar" as const,
        color: "rgba(239, 83, 80, 0.4)",
        shape: "circle" as const,
        text: "",
      })),
    ].sort((a, b) => (a.time as number) - (b.time as number));

    if (pivotMarkers.length > 0) {
      createSeriesMarkers(rsiSeries, pivotMarkers);
    }

    // ─── Divergence lines on both panes ───
    for (const line of data.divergence_lines) {
      const isRegular = line.signal_type.includes("regular");
      const color = COLORS[line.signal_type] ?? "#ffffff";
      const style = isRegular ? "solid" : ("dashed" as const);

      // Price pane divergence line
      const priceLine = new TrendLinePrimitive(
        { time: line.prev_time as UTCTimestamp as Time, value: line.prev_price },
        { time: line.curr_time as UTCTimestamp as Time, value: line.curr_price },
        { lineColor: color, lineWidth: 2, lineStyle: style },
      );
      candleSeries.attachPrimitive(priceLine);

      // RSI pane divergence line
      const rsiLine = new TrendLinePrimitive(
        { time: line.prev_time as UTCTimestamp as Time, value: line.prev_rsi },
        { time: line.curr_time as UTCTimestamp as Time, value: line.curr_rsi },
        { lineColor: color, lineWidth: 2, lineStyle: style },
      );
      rsiSeries.attachPrimitive(rsiLine);
    }

    // Fit content
    chart.timeScale().fitContent();

    // Resize observer
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        chart.applyOptions({ width });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [data]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden"
      style={{ height: "700px" }}
    />
  );
}
