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
import { BoxPrimitive } from "./plugins/box-primitive";
import { FibonacciPrimitive } from "./plugins/fibonacci-primitive";
import { PriceRangePrimitive } from "./plugins/price-range-primitive";
import type { ChartData, TsrData, Timezone } from "@/lib/chart-types";
import type { IndicatorId, IndicatorState } from "@/lib/indicator-types";
import type { Drawing, DrawingToolId } from "@/lib/drawing-types";
import { shiftChartData, shiftTsrData, applyTzOffset, reverseTzOffset } from "@/lib/tz-utils";

const COLORS: Record<string, string> = {
  regular_bullish: "#26a69a",
  hidden_bullish: "#4dd0e1",
  regular_bearish: "#ef5350",
  hidden_bearish: "#ff8a65",
};

const TSR_COLORS = {
  uptrend: "#2962ff",
  uptrend_violated: "rgba(41, 98, 255, 0.3)",
  downtrend: "#ef5350",
  downtrend_violated: "rgba(239, 83, 80, 0.3)",
  support_fill: "rgba(38, 166, 154, 0.15)",
  support_border: "rgba(38, 166, 154, 0.5)",
  resistance_fill: "rgba(239, 83, 80, 0.15)",
  resistance_border: "rgba(239, 83, 80, 0.5)",
};

interface TvChartProps {
  data: ChartData;
  tsrData?: TsrData | null;
  indicators: Record<IndicatorId, IndicatorState>;
  timezone: Timezone;
  drawings: Drawing[];
  activeTool: DrawingToolId;
  onChartClick?: (point: { time: number; price: number }) => void;
}

/** Deduplicate and ensure ascending time order (keep last for duplicate times). */
function dedup<T extends { time: number }>(arr: T[]): T[] {
  const sorted = [...arr].sort((a, b) => a.time - b.time);
  return sorted.filter((item, i) => i === 0 || item.time !== sorted[i - 1].time);
}

export default function TvChart({
  data,
  tsrData,
  indicators,
  timezone,
  drawings,
  activeTool,
  onChartClick,
}: TvChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const rsiVisible = indicators["rsi-divergence"]?.visible ?? true;
  const tsrVisible = indicators["tsr"]?.visible ?? true;

  useEffect(() => {
    if (!containerRef.current) return;

    // Apply timezone shift to data
    const chartData = shiftChartData(data, timezone);
    const tsrShifted = tsrData ? shiftTsrData(tsrData, timezone) : null;

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
      dedup(chartData.candles)
        .filter((c) => c.open != null && c.high != null && c.low != null && c.close != null)
        .map((c) => ({
          time: c.time as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })),
    );

    // ─── Candle markers (merge RSI signals + TSR pivots) ───
    const candleMarkers: SeriesMarker<Time>[] = [];

    // RSI divergence signal markers
    if (rsiVisible) {
      for (const s of chartData.signals) {
        candleMarkers.push({
          time: s.time as UTCTimestamp as Time,
          position: s.position as "belowBar" | "aboveBar",
          color: s.color,
          shape: s.shape as "arrowUp" | "arrowDown",
          text: s.text,
        });
      }
    }

    // TSR pivot markers on candle pane
    if (tsrVisible && tsrShifted) {
      for (const p of tsrShifted.pivot_markers) {
        candleMarkers.push({
          time: p.time as UTCTimestamp as Time,
          position: p.pivot_type === "high" ? "aboveBar" : "belowBar",
          color: p.pivot_type === "high" ? "rgba(239, 83, 80, 0.5)" : "rgba(38, 166, 154, 0.5)",
          shape: "circle" as const,
          text: "",
        });
      }
    }

    if (candleMarkers.length > 0) {
      candleMarkers.sort((a, b) => (a.time as number) - (b.time as number));
      createSeriesMarkers(candleSeries, candleMarkers);
    }

    // ─── TSR: Trend Lines + S/R Zones (overlay on price pane) ───
    if (tsrVisible && tsrShifted) {
      // Trend lines
      for (const tl of tsrShifted.trend_lines) {
        const isUp = tl.direction === "up";
        const baseColor = isUp
          ? (tl.is_violated ? TSR_COLORS.uptrend_violated : TSR_COLORS.uptrend)
          : (tl.is_violated ? TSR_COLORS.downtrend_violated : TSR_COLORS.downtrend);

        // Main segment: start → end
        const mainLine = new TrendLinePrimitive(
          { time: tl.start_time as UTCTimestamp as Time, value: tl.start_price },
          { time: tl.end_time as UTCTimestamp as Time, value: tl.end_price },
          { lineColor: baseColor, lineWidth: 2, lineStyle: "solid" },
        );
        candleSeries.attachPrimitive(mainLine);

        // Extension segment: end → ext (dashed, dimmer)
        if (tl.ext_time != null && tl.ext_price != null) {
          const extLine = new TrendLinePrimitive(
            { time: tl.end_time as UTCTimestamp as Time, value: tl.end_price },
            { time: tl.ext_time as UTCTimestamp as Time, value: tl.ext_price },
            { lineColor: baseColor, lineWidth: 1, lineStyle: "dashed" },
          );
          candleSeries.attachPrimitive(extLine);
        }
      }

      // S/R zones
      for (const zone of tsrShifted.sr_zones) {
        const isSupport = zone.zone_type === "support";
        const box = new BoxPrimitive(
          zone.start_time as UTCTimestamp as Time,
          zone.end_time as UTCTimestamp as Time,
          zone.top,
          zone.bottom,
          {
            fillColor: isSupport ? TSR_COLORS.support_fill : TSR_COLORS.resistance_fill,
            borderColor: isSupport ? TSR_COLORS.support_border : TSR_COLORS.resistance_border,
            borderWidth: 1,
          },
        );
        candleSeries.attachPrimitive(box);
      }
    }

    // ─── RSI Divergence: lines on price pane ───
    if (rsiVisible) {
      for (const line of chartData.divergence_lines) {
        const isRegular = line.signal_type.includes("regular");
        const color = COLORS[line.signal_type] ?? "#ffffff";
        const style = isRegular ? "solid" : ("dashed" as const);

        const priceLine = new TrendLinePrimitive(
          { time: line.prev_time as UTCTimestamp as Time, value: line.prev_price },
          { time: line.curr_time as UTCTimestamp as Time, value: line.curr_price },
          { lineColor: color, lineWidth: 2, lineStyle: style },
        );
        candleSeries.attachPrimitive(priceLine);
      }
    }

    // ─── User Drawings ───
    for (const d of drawings) {
      switch (d.tool) {
        case "hline": {
          candleSeries.createPriceLine({
            price: d.price,
            color: "#fbbf24",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "",
          });
          break;
        }
        case "trendline": {
          const tl = new TrendLinePrimitive(
            { time: applyTzOffset(d.p1.time, timezone) as UTCTimestamp as Time, value: d.p1.price },
            { time: applyTzOffset(d.p2.time, timezone) as UTCTimestamp as Time, value: d.p2.price },
            { lineColor: "#fbbf24", lineWidth: 2, lineStyle: "solid" },
          );
          candleSeries.attachPrimitive(tl);
          break;
        }
        case "fibonacci": {
          const fib = new FibonacciPrimitive(
            { time: applyTzOffset(d.p1.time, timezone) as UTCTimestamp as Time, value: d.p1.price },
            { time: applyTzOffset(d.p2.time, timezone) as UTCTimestamp as Time, value: d.p2.price },
          );
          candleSeries.attachPrimitive(fib);
          break;
        }
        case "price-range": {
          const pr = new PriceRangePrimitive(
            { time: applyTzOffset(d.p1.time, timezone) as UTCTimestamp as Time, value: d.p1.price },
            { time: applyTzOffset(d.p2.time, timezone) as UTCTimestamp as Time, value: d.p2.price },
          );
          candleSeries.attachPrimitive(pr);
          break;
        }
      }
    }

    // ─── Pane 1: RSI (only when RSI indicator is visible) ───
    if (rsiVisible) {
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
        dedup(chartData.rsi).map((r) => ({
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

      // Pane sizing
      const panes = chart.panes();
      if (panes.length > 1) {
        panes[0].setHeight(480);
        panes[1].setHeight(180);
      }

      // Pivot markers on RSI
      const pivotMarkers: SeriesMarker<Time>[] = [
        ...chartData.pivot_lows.map((p) => ({
          time: p.time as UTCTimestamp as Time,
          position: "belowBar" as const,
          color: "rgba(38, 166, 154, 0.4)",
          shape: "circle" as const,
          text: "",
        })),
        ...chartData.pivot_highs.map((p) => ({
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

      // Divergence lines on RSI pane
      for (const line of chartData.divergence_lines) {
        const isRegular = line.signal_type.includes("regular");
        const color = COLORS[line.signal_type] ?? "#ffffff";
        const style = isRegular ? "solid" : ("dashed" as const);

        const rsiLine = new TrendLinePrimitive(
          { time: line.prev_time as UTCTimestamp as Time, value: line.prev_rsi },
          { time: line.curr_time as UTCTimestamp as Time, value: line.curr_rsi },
          { lineColor: color, lineWidth: 2, lineStyle: style },
        );
        rsiSeries.attachPrimitive(rsiLine);
      }
    }

    // Fit content
    chart.timeScale().fitContent();

    // ─── Click handler for drawings ───
    const clickHandler = (param: { time?: Time; point?: { x: number; y: number } }) => {
      if (!onChartClick || activeTool === "cursor") return;
      if (!param.time || !param.point) return;

      const price = candleSeries.coordinateToPrice(param.point.y as number);
      if (price === null) return;

      // Convert shifted time back to raw epoch
      const shiftedTime = param.time as number;
      const rawTime = reverseTzOffset(shiftedTime, timezone);

      onChartClick({ time: rawTime, price });
    };
    chart.subscribeClick(clickHandler);

    // Resize observer
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        chart.applyOptions({ width });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      chart.unsubscribeClick(clickHandler);
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [data, tsrData, rsiVisible, tsrVisible, timezone, drawings, activeTool, onChartClick]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden"
      style={{
        height: rsiVisible ? "700px" : "520px",
        cursor: activeTool !== "cursor" ? "crosshair" : undefined,
      }}
    />
  );
}
