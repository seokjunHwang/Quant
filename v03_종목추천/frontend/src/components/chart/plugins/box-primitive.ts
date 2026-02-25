/**
 * BoxPrimitive for TradingView Lightweight Charts v5.
 * Draws a semi-transparent rectangular zone between two {time, price} corners.
 * Used for rendering Support/Resistance zones from TSR indicator.
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

interface BoxOptions {
  fillColor: string;
  borderColor: string;
  borderWidth: number;
}

class BoxRenderer implements IPrimitivePaneRenderer {
  _x1: Coordinate | null = null;
  _y1: Coordinate | null = null;
  _x2: Coordinate | null = null;
  _y2: Coordinate | null = null;
  _options: BoxOptions;

  constructor(options: BoxOptions) {
    this._options = options;
  }

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
      ctx.fillStyle = this._options.fillColor;
      ctx.fillRect(x, y, w, h);

      // Border
      if (this._options.borderWidth > 0) {
        ctx.strokeStyle = this._options.borderColor;
        ctx.lineWidth = this._options.borderWidth * hpr;
        ctx.strokeRect(x, y, w, h);
      }
    });
  }
}

class BoxPaneView implements IPrimitivePaneView {
  _source: BoxPrimitive;
  _renderer: BoxRenderer;

  constructor(source: BoxPrimitive) {
    this._source = source;
    this._renderer = new BoxRenderer(source._options);
  }

  update(): void {
    if (!this._source._chart || !this._source._series) return;

    const timeScale = this._source._chart.timeScale();

    this._renderer._x1 = timeScale.timeToCoordinate(this._source._time1);
    this._renderer._x2 = timeScale.timeToCoordinate(this._source._time2);
    this._renderer._y1 = this._source._series.priceToCoordinate(this._source._priceTop);
    this._renderer._y2 = this._source._series.priceToCoordinate(this._source._priceBottom);
    this._renderer._options = this._source._options;
  }

  renderer(): IPrimitivePaneRenderer {
    return this._renderer;
  }
}

export class BoxPrimitive implements ISeriesPrimitive<Time> {
  _chart: IChartApiBase<Time> | null = null;
  _series: ISeriesApi<SeriesType, Time> | null = null;
  _time1: Time;
  _time2: Time;
  _priceTop: number;
  _priceBottom: number;
  _options: BoxOptions;
  _paneViews: BoxPaneView[];

  constructor(
    time1: Time,
    time2: Time,
    priceTop: number,
    priceBottom: number,
    options?: Partial<BoxOptions>,
  ) {
    this._time1 = time1;
    this._time2 = time2;
    this._priceTop = priceTop;
    this._priceBottom = priceBottom;
    this._options = {
      fillColor: options?.fillColor ?? "rgba(255,255,255,0.1)",
      borderColor: options?.borderColor ?? "rgba(255,255,255,0.3)",
      borderWidth: options?.borderWidth ?? 1,
    };
    this._paneViews = [new BoxPaneView(this)];
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
