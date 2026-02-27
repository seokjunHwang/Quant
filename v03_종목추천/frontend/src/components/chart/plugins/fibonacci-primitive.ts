/**
 * Fibonacci Retracement primitive for Lightweight Charts v5.
 * Draws horizontal levels (0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%)
 * between two price points with labels and semi-transparent fills.
 */

import type {
  ISeriesPrimitive,
  SeriesAttachedParameter,
  IPrimitivePaneView,
  IPrimitivePaneRenderer,
  Coordinate,
  Time,
  ISeriesApi,
  SeriesType,
  IChartApiBase,
} from "lightweight-charts";
import { CanvasRenderingTarget2D } from "fancy-canvas";

const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1] as const;
const FIB_COLORS = [
  "rgba(239, 83, 80, 0.8)",   // 0%
  "rgba(255, 152, 0, 0.8)",   // 23.6%
  "rgba(255, 235, 59, 0.8)",  // 38.2%
  "rgba(76, 175, 80, 0.8)",   // 50%
  "rgba(0, 188, 212, 0.8)",   // 61.8%
  "rgba(33, 150, 243, 0.8)",  // 78.6%
  "rgba(156, 39, 176, 0.8)",  // 100%
];
const FIB_FILL = "rgba(251, 191, 36, 0.04)";

interface FibPoint {
  time: Time;
  value: number;
}

class FibRenderer implements IPrimitivePaneRenderer {
  _levels: { y: Coordinate | null; price: number; pct: number }[] = [];
  _x1: Coordinate | null = null;
  _x2: Coordinate | null = null;
  _canvasWidth = 0;

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const hpr = scope.horizontalPixelRatio;
      const vpr = scope.verticalPixelRatio;
      const w = scope.bitmapSize.width;

      // Draw fills between levels
      for (let i = 0; i < this._levels.length - 1; i++) {
        const top = this._levels[i];
        const bot = this._levels[i + 1];
        if (top.y === null || bot.y === null) continue;

        ctx.fillStyle = FIB_FILL;
        const y1 = Math.min(top.y, bot.y) * vpr;
        const y2 = Math.max(top.y, bot.y) * vpr;
        ctx.fillRect(0, y1, w, y2 - y1);
      }

      // Draw level lines and labels
      for (let i = 0; i < this._levels.length; i++) {
        const lvl = this._levels[i];
        if (lvl.y === null) continue;

        const y = lvl.y * vpr;
        const color = FIB_COLORS[i] ?? "rgba(255,255,255,0.5)";

        // Dashed line
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1 * hpr;
        ctx.setLineDash([4 * hpr, 3 * hpr]);
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label on right side
        const pctStr = `${(lvl.pct * 100).toFixed(1)}%`;
        const priceStr = lvl.price.toFixed(2);
        const label = `${pctStr}  (${priceStr})`;

        ctx.font = `${11 * hpr}px monospace`;
        ctx.fillStyle = color;
        ctx.textAlign = "right";
        ctx.textBaseline = "bottom";
        ctx.fillText(label, w - 6 * hpr, y - 3 * vpr);
      }
    });
  }
}

class FibPaneView implements IPrimitivePaneView {
  _source: FibonacciPrimitive;
  _renderer: FibRenderer;

  constructor(source: FibonacciPrimitive) {
    this._source = source;
    this._renderer = new FibRenderer();
  }

  update(): void {
    if (!this._source._chart || !this._source._series) return;

    const ts = this._source._chart.timeScale();
    this._renderer._x1 = ts.timeToCoordinate(this._source._p1.time);
    this._renderer._x2 = ts.timeToCoordinate(this._source._p2.time);

    const low = Math.min(this._source._p1.value, this._source._p2.value);
    const high = Math.max(this._source._p1.value, this._source._p2.value);

    this._renderer._levels = FIB_LEVELS.map((pct) => {
      const price = high - (high - low) * pct;
      return {
        y: this._source._series!.priceToCoordinate(price),
        price,
        pct,
      };
    });
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

export class FibonacciPrimitive implements ISeriesPrimitive<Time> {
  _chart: IChartApiBase<Time> | null = null;
  _series: ISeriesApi<SeriesType, Time> | null = null;
  _p1: FibPoint;
  _p2: FibPoint;
  _paneViews: FibPaneView[];

  constructor(p1: FibPoint, p2: FibPoint) {
    this._p1 = p1;
    this._p2 = p2;
    this._paneViews = [new FibPaneView(this)];
  }

  attached(param: SeriesAttachedParameter<Time, SeriesType>): void {
    this._chart = param.chart;
    this._series = param.series;
  }

  detached(): void {
    this._chart = null;
    this._series = null;
  }

  updateAllViews(): void {
    this._paneViews.forEach((v) => v.update());
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews;
  }
}
