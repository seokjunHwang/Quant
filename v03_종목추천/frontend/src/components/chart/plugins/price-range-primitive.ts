/**
 * PriceRange (profit bar) primitive for Lightweight Charts v5.
 * Draws a semi-transparent box between two points with % change label.
 * Green for positive, red for negative.
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

interface PRPoint {
  time: Time;
  value: number;
}

class PriceRangeRenderer implements IPrimitivePaneRenderer {
  _x1: Coordinate | null = null;
  _y1: Coordinate | null = null;
  _x2: Coordinate | null = null;
  _y2: Coordinate | null = null;
  _pctChange = 0;
  _priceChange = 0;
  _isPositive = true;

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      if (
        this._x1 === null ||
        this._y1 === null ||
        this._x2 === null ||
        this._y2 === null
      )
        return;

      const ctx = scope.context;
      const hpr = scope.horizontalPixelRatio;
      const vpr = scope.verticalPixelRatio;

      const x = Math.min(this._x1, this._x2) * hpr;
      const y = Math.min(this._y1, this._y2) * vpr;
      const w = Math.abs(this._x2 - this._x1) * hpr;
      const h = Math.abs(this._y2 - this._y1) * vpr;

      // Fill
      ctx.fillStyle = this._isPositive
        ? "rgba(38, 166, 154, 0.15)"
        : "rgba(239, 83, 80, 0.15)";
      ctx.fillRect(x, y, w, h);

      // Border
      ctx.strokeStyle = this._isPositive
        ? "rgba(38, 166, 154, 0.6)"
        : "rgba(239, 83, 80, 0.6)";
      ctx.lineWidth = 1.5 * hpr;
      ctx.strokeRect(x, y, w, h);

      // Center label
      const sign = this._isPositive ? "+" : "";
      const pctStr = `${sign}${this._pctChange.toFixed(2)}%`;
      const priceStr = `${sign}${this._priceChange.toFixed(2)}`;
      const label = `${pctStr}  (${priceStr})`;

      const cx = x + w / 2;
      const cy = y + h / 2;

      ctx.font = `bold ${12 * hpr}px monospace`;
      ctx.fillStyle = this._isPositive
        ? "rgba(38, 166, 154, 0.9)"
        : "rgba(239, 83, 80, 0.9)";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      // Background for readability
      const metrics = ctx.measureText(label);
      const pad = 4 * hpr;
      ctx.fillStyle = "rgba(19, 23, 34, 0.8)";
      ctx.fillRect(
        cx - metrics.width / 2 - pad,
        cy - 8 * vpr,
        metrics.width + pad * 2,
        16 * vpr,
      );

      ctx.fillStyle = this._isPositive
        ? "rgba(38, 166, 154, 0.9)"
        : "rgba(239, 83, 80, 0.9)";
      ctx.fillText(label, cx, cy);
    });
  }
}

class PriceRangePaneView implements IPrimitivePaneView {
  _source: PriceRangePrimitive;
  _renderer: PriceRangeRenderer;

  constructor(source: PriceRangePrimitive) {
    this._source = source;
    this._renderer = new PriceRangeRenderer();
  }

  update(): void {
    if (!this._source._chart || !this._source._series) return;

    const ts = this._source._chart.timeScale();
    this._renderer._x1 = ts.timeToCoordinate(this._source._p1.time);
    this._renderer._x2 = ts.timeToCoordinate(this._source._p2.time);
    this._renderer._y1 = this._source._series.priceToCoordinate(this._source._p1.value);
    this._renderer._y2 = this._source._series.priceToCoordinate(this._source._p2.value);

    const diff = this._source._p2.value - this._source._p1.value;
    this._renderer._priceChange = diff;
    this._renderer._pctChange = this._source._p1.value !== 0
      ? (diff / this._source._p1.value) * 100
      : 0;
    this._renderer._isPositive = diff >= 0;
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

export class PriceRangePrimitive implements ISeriesPrimitive<Time> {
  _chart: IChartApiBase<Time> | null = null;
  _series: ISeriesApi<SeriesType, Time> | null = null;
  _p1: PRPoint;
  _p2: PRPoint;
  _paneViews: PriceRangePaneView[];

  constructor(p1: PRPoint, p2: PRPoint) {
    this._p1 = p1;
    this._p2 = p2;
    this._paneViews = [new PriceRangePaneView(this)];
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
