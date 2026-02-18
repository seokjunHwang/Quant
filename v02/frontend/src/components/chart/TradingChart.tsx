"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  ColorType,
} from "lightweight-charts";
import { useChartData } from "./hooks/useChartData";
import { useIndicatorData } from "./hooks/useIndicatorData";
import { useChartStore } from "@/store/chartStore";

interface TradingChartProps {
  symbol: string;
}

interface SRLevels {
  support: number | null;
  support_bottom: number | null;
  resistance: number | null;
  resistance_top: number | null;
}

interface BoxData {
  type: string;
  start_time: number;
  end_time: number;
  top: number;
  bottom: number;
  active: boolean;
}

type DrawingTool = "cursor" | "hline" | "trendline";

export default function TradingChart({ symbol }: TradingChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const boxOverlayRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const boxSeriesRefs = useRef<any[]>([]);

  const { interval, activeIndicators } = useChartStore();
  const { data, isLoading } = useChartData(symbol, interval);
  const { data: indicatorData } = useIndicatorData(symbol, interval, activeIndicators);

  const [srLevels, setSrLevels] = useState<SRLevels>({
    support: null, support_bottom: null,
    resistance: null, resistance_top: null,
  });
  const [boxes, setBoxes] = useState<BoxData[]>([]);
  const [drawTool, setDrawTool] = useState<DrawingTool>("cursor");
  const [hLines, setHLines] = useState<{ price: number; id: string }[]>([]);
  const [trendLines, setTrendLines] = useState<{ p1: { time: number; price: number }; p2: { time: number; price: number }; id: string }[]>([]);
  const trendStartRef = useRef<{ time: number; price: number } | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const priceLineRefs = useRef<any[]>([]);

  // Create chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a0a" },
        textColor: "#d1d5db",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: "#374151" },
      timeScale: { borderColor: "#374151", timeVisible: true },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener("resize", handleResize);
    handleResize();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      boxSeriesRefs.current = [];
      priceLineRefs.current = [];
    };
  }, []);

  // Update candle data
  useEffect(() => {
    if (data && candleSeriesRef.current) {
      candleSeriesRef.current.setData(data);
      chartRef.current?.timeScale().fitContent();
    }
  }, [data]);

  // Handle chart click for drawing tools
  useEffect(() => {
    const chart = chartRef.current;
    const series = candleSeriesRef.current;
    if (!chart || !series) return;

    const handler = (param: { time?: unknown; point?: { x: number; y: number } }) => {
      if (drawTool === "cursor" || !param.time || !param.point) return;

      const price = series.coordinateToPrice(param.point.y);
      if (price === null) return;
      const time = param.time as number;

      if (drawTool === "hline") {
        const id = `hl_${Date.now()}`;
        const pl = series.createPriceLine({
          price: price,
          color: "#fbbf24",
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: `${price.toFixed(0)}`,
        });
        priceLineRefs.current.push(pl);
        setHLines((prev) => [...prev, { price, id }]);
        setDrawTool("cursor");
      }

      if (drawTool === "trendline") {
        if (!trendStartRef.current) {
          trendStartRef.current = { time, price };
        } else {
          const p1 = trendStartRef.current;
          const p2 = { time, price };
          const id = `tl_${Date.now()}`;
          // Draw trend line as a line series with 2 points
          const ls = chart.addLineSeries({
            color: "#fbbf24",
            lineWidth: 1,
            lineStyle: 0,
            priceLineVisible: false,
            lastValueVisible: false,
          });
          ls.setData([
            { time: p1.time as never, value: p1.price },
            { time: p2.time as never, value: p2.price },
          ]);
          boxSeriesRefs.current.push(ls);
          setTrendLines((prev) => [...prev, { p1, p2, id }]);
          trendStartRef.current = null;
          setDrawTool("cursor");
        }
      }
    };

    chart.subscribeClick(handler);
    return () => chart.unsubscribeClick(handler);
  }, [drawTool]);

  // Render S/R indicator overlays
  useEffect(() => {
    if (!chartRef.current || !candleSeriesRef.current) return;
    const chart = chartRef.current;
    const srData = indicatorData?.["SR_BREAKS"];

    // Clear previous box series
    for (const s of boxSeriesRefs.current) {
      try { chart.removeSeries(s); } catch { /* already removed */ }
    }
    boxSeriesRefs.current = [];

    if (!srData || srData.error || !activeIndicators.includes("SR_BREAKS")) {
      candleSeriesRef.current.setMarkers([]);
      setSrLevels({ support: null, support_bottom: null, resistance: null, resistance_top: null });
      setBoxes([]);
      return;
    }

    // ── Render boxes as pairs of horizontal line series ──
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const boxData: BoxData[] = (srData.boxes || []).filter((b: any) => b.start_time != null);
    for (const box of boxData) {
      const borderColor = box.type === "support" ? "#20ca26" : "#e92929";

      // Top boundary line
      const topLine = chart.addLineSeries({
        color: borderColor,
        lineWidth: 1,
        lineStyle: box.active ? 0 : 2, // solid for active, dashed for old
        priceLineVisible: false,
        lastValueVisible: false,
      });
      topLine.setData([
        { time: box.start_time as never, value: box.top },
        { time: box.end_time as never, value: box.top },
      ]);
      boxSeriesRefs.current.push(topLine);

      // Bottom boundary line
      const bottomLine = chart.addLineSeries({
        color: borderColor,
        lineWidth: 1,
        lineStyle: box.active ? 0 : 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      bottomLine.setData([
        { time: box.start_time as never, value: box.bottom },
        { time: box.end_time as never, value: box.bottom },
      ]);
      boxSeriesRefs.current.push(bottomLine);
    }
    setBoxes(boxData);

    // ── Markers ──
    if (srData.markers?.length > 0) {
      const sorted = [...srData.markers].sort(
        (a: { time: number }, b: { time: number }) => a.time - b.time
      );
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      candleSeriesRef.current.setMarkers(sorted as any);
    } else {
      candleSeriesRef.current.setMarkers([]);
    }

    // ── S/R levels ──
    if (srData.levels) {
      setSrLevels(srData.levels);
    }
  }, [indicatorData, activeIndicators]);

  // Render box fills using HTML overlay (positioned via chart coordinates)
  const renderBoxOverlays = useCallback(() => {
    if (!boxOverlayRef.current || !chartRef.current || !candleSeriesRef.current) return;
    const chart = chartRef.current;
    const series = candleSeriesRef.current;
    const container = boxOverlayRef.current;
    container.innerHTML = "";

    if (!activeIndicators.includes("SR_BREAKS")) return;

    for (const box of boxes) {
      const ts = chart.timeScale();
      const x1 = ts.timeToCoordinate(box.start_time as never);
      const x2 = ts.timeToCoordinate(box.end_time as never);
      const y1 = series.priceToCoordinate(box.top);
      const y2 = series.priceToCoordinate(box.bottom);

      if (x1 === null || x2 === null || y1 === null || y2 === null) continue;

      const left = Math.min(x1, x2);
      const width = Math.abs(x2 - x1);
      const top = Math.min(y1, y2);
      const height = Math.abs(y2 - y1);

      if (width < 1 || height < 1) continue;

      const div = document.createElement("div");
      div.style.position = "absolute";
      div.style.left = `${left}px`;
      div.style.top = `${top}px`;
      div.style.width = `${width}px`;
      div.style.height = `${height}px`;
      div.style.pointerEvents = "none";

      const alpha = box.active ? 0.15 : 0.07;
      div.style.background = box.type === "support"
        ? `rgba(32,202,38,${alpha})`
        : `rgba(233,41,41,${alpha})`;

      container.appendChild(div);
    }
  }, [boxes, activeIndicators]);

  // Re-render box overlays on scroll/zoom
  useEffect(() => {
    if (!chartRef.current) return;
    const chart = chartRef.current;

    renderBoxOverlays();
    const sub = chart.timeScale().subscribeVisibleTimeRangeChange(() => renderBoxOverlays());

    return () => {
      try { chart.timeScale().unsubscribeVisibleTimeRangeChange(sub as unknown as () => void); } catch { /* ok */ }
    };
  }, [renderBoxOverlays]);

  const showSRPanel = activeIndicators.includes("SR_BREAKS") && (srLevels.support || srLevels.resistance);

  const toolBtnStyle = (active: boolean): React.CSSProperties => ({
    padding: "4px 8px", fontSize: 11, borderRadius: 4, cursor: "pointer",
    border: active ? "1px solid #fbbf24" : "1px solid #374151",
    background: active ? "#78350f" : "#111827",
    color: active ? "#fbbf24" : "#9ca3af",
  });

  return (
    <div style={{ position: "relative", width: "100%", height: "calc(100vh - 50px)", background: "#0a0a0a" }}>
      {isLoading && (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(3,7,18,0.5)", zIndex: 10 }}>
          <span style={{ color: "#9ca3af" }}>Loading chart...</span>
        </div>
      )}

      {/* Drawing Toolbar (left side, like TradingView) */}
      <div style={{
        position: "absolute", top: 12, right: 12, zIndex: 20,
        display: "flex", flexDirection: "column", gap: 4,
      }}>
        <button
          style={toolBtnStyle(drawTool === "cursor")}
          onClick={() => { setDrawTool("cursor"); trendStartRef.current = null; }}
          title="Cursor"
        >+</button>
        <button
          style={toolBtnStyle(drawTool === "hline")}
          onClick={() => { setDrawTool("hline"); trendStartRef.current = null; }}
          title="Horizontal Line (Alert)"
        >―</button>
        <button
          style={toolBtnStyle(drawTool === "trendline")}
          onClick={() => { setDrawTool("trendline"); trendStartRef.current = null; }}
          title="Trend Line"
        >╲</button>
      </div>

      {/* S/R Info Panel */}
      {showSRPanel && (
        <div style={{
          position: "absolute", top: 12, left: 12, zIndex: 20,
          background: "rgba(17,24,39,0.95)", border: "1px solid #374151",
          borderRadius: 8, padding: "8px 12px", fontSize: 12, color: "#d1d5db",
        }}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: "#9ca3af" }}>S/R Levels</div>
          {srLevels.resistance_top && (
            <div style={{ display: "flex", justifyContent: "space-between", gap: 16, marginBottom: 2 }}>
              <span style={{ color: "#f87171" }}>Res Top</span>
              <span style={{ color: "#fff", fontFamily: "monospace" }}>{srLevels.resistance_top.toLocaleString()}</span>
            </div>
          )}
          {srLevels.resistance && (
            <div style={{ display: "flex", justifyContent: "space-between", gap: 16, marginBottom: 2 }}>
              <span style={{ color: "#ef4444" }}>Resistance</span>
              <span style={{ color: "#fff", fontFamily: "monospace" }}>{srLevels.resistance.toLocaleString()}</span>
            </div>
          )}
          {srLevels.support && (
            <div style={{ display: "flex", justifyContent: "space-between", gap: 16, marginBottom: 2 }}>
              <span style={{ color: "#22c55e" }}>Support</span>
              <span style={{ color: "#fff", fontFamily: "monospace" }}>{srLevels.support.toLocaleString()}</span>
            </div>
          )}
          {srLevels.support_bottom && (
            <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
              <span style={{ color: "#4ade80" }}>Sup Bottom</span>
              <span style={{ color: "#fff", fontFamily: "monospace" }}>{srLevels.support_bottom.toLocaleString()}</span>
            </div>
          )}
        </div>
      )}

      {/* Drawing mode indicator */}
      {drawTool !== "cursor" && (
        <div style={{
          position: "absolute", bottom: 12, left: "50%", transform: "translateX(-50%)", zIndex: 20,
          background: "#78350f", border: "1px solid #fbbf24", borderRadius: 6,
          padding: "4px 12px", fontSize: 12, color: "#fbbf24",
        }}>
          {drawTool === "hline" ? "Click chart to place horizontal line" :
           trendStartRef.current ? "Click second point for trend line" : "Click first point for trend line"}
        </div>
      )}

      {/* Box fill overlays */}
      <div ref={boxOverlayRef} style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 1 }} />

      <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
}
