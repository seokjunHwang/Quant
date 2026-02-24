/**
 * TrendLine primitive for TradingView Lightweight Charts v5.
 * Draws a straight line between two {time, value} points on a series.
 * Used for rendering RSI divergence lines on both price and RSI panes.
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

interface TrendLinePoint {
  time: Time;
  value: number;
}

interface TrendLineOptions {
  lineColor: string;
  lineWidth: number;
  lineStyle: "solid" | "dashed";
}

class TrendLineRenderer implements IPrimitivePaneRenderer {
  _p1x: Coordinate | null = null;
  _p1y: Coordinate | null = null;
  _p2x: Coordinate | null = null;
  _p2y: Coordinate | null = null;
  _options: TrendLineOptions;

  constructor(options: TrendLineOptions) {
    this._options = options;
  }

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      if (
        this._p1x === null ||
        this._p1y === null ||
        this._p2x === null ||
        this._p2y === null
      )
        return;

      const ctx = scope.context;
      const hpr = scope.horizontalPixelRatio;
      const vpr = scope.verticalPixelRatio;

      ctx.beginPath();
      ctx.lineWidth = this._options.lineWidth * hpr;
      ctx.strokeStyle = this._options.lineColor;

      if (this._options.lineStyle === "dashed") {
        ctx.setLineDash([6 * hpr, 4 * hpr]);
      } else {
        ctx.setLineDash([]);
      }

      ctx.moveTo(this._p1x * hpr, this._p1y * vpr);
      ctx.lineTo(this._p2x * hpr, this._p2y * vpr);
      ctx.stroke();
    });
  }
}

class TrendLinePaneView implements IPrimitivePaneView {
  _source: TrendLinePrimitive;
  _renderer: TrendLineRenderer;

  constructor(source: TrendLinePrimitive) {
    this._source = source;
    this._renderer = new TrendLineRenderer(source._options);
  }

  update(): void {
    if (!this._source._chart || !this._source._series) return;

    const timeScale = this._source._chart.timeScale();

    this._renderer._p1x = timeScale.timeToCoordinate(this._source._p1.time);
    this._renderer._p1y = this._source._series.priceToCoordinate(
      this._source._p1.value,
    );
    this._renderer._p2x = timeScale.timeToCoordinate(this._source._p2.time);
    this._renderer._p2y = this._source._series.priceToCoordinate(
      this._source._p2.value,
    );
    this._renderer._options = this._source._options;
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

export class TrendLinePrimitive implements ISeriesPrimitive<Time> {
  _chart: IChartApiBase<Time> | null = null;
  _series: ISeriesApi<SeriesType, Time> | null = null;
  _p1: TrendLinePoint;
  _p2: TrendLinePoint;
  _options: TrendLineOptions;
  _paneViews: TrendLinePaneView[];

  constructor(
    p1: TrendLinePoint,
    p2: TrendLinePoint,
    options?: Partial<TrendLineOptions>,
  ) {
    this._p1 = p1;
    this._p2 = p2;
    this._options = {
      lineColor: options?.lineColor ?? "#ffffff",
      lineWidth: options?.lineWidth ?? 2,
      lineStyle: options?.lineStyle ?? "solid",
    };
    this._paneViews = [new TrendLinePaneView(this)];
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
    this._paneViews.forEach((view) => view.update());
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews;
  }
}
