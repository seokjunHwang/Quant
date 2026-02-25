export interface CandleData {
  time: number; // UNIX epoch seconds
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface RsiPoint {
  time: number;
  value: number;
}

export interface PivotPoint {
  time: number;
  value: number; // RSI value
  price: number; // price at pivot
}

export interface DivergenceLine {
  signal_type: string;
  signal_label: string;
  curr_time: number;
  curr_price: number;
  curr_rsi: number;
  prev_time: number;
  prev_price: number;
  prev_rsi: number;
}

export interface SignalMarker {
  time: number;
  position: "belowBar" | "aboveBar";
  color: string;
  shape: "arrowUp" | "arrowDown";
  text: string;
}

export interface ChartData {
  ticker: string;
  candles: CandleData[];
  rsi: RsiPoint[];
  pivot_lows: PivotPoint[];
  pivot_highs: PivotPoint[];
  signals: SignalMarker[];
  divergence_lines: DivergenceLine[];
}

export type Interval = "1h" | "4h" | "1d";

export interface ChartParams {
  interval?: Interval;
  days?: number;
  rsi_period?: number;
  lb_left?: number;
  lb_right?: number;
  range_lower?: number;
  range_upper?: number;
  lookback?: number;
}

// ─── TSR types ───

export interface TsrTrendLine {
  start_time: number;
  start_price: number;
  end_time: number;
  end_price: number;
  direction: "up" | "down";
  is_violated: boolean;
  ext_time: number | null;
  ext_price: number | null;
}

export interface TsrSrZone {
  zone_type: "support" | "resistance";
  start_time: number;
  end_time: number;
  top: number;
  bottom: number;
  price: number;
}

export interface TsrPivotMarker {
  time: number;
  price: number;
  pivot_type: "high" | "low";
}

export interface TsrData {
  ticker: string;
  candles: CandleData[];
  trend_lines: TsrTrendLine[];
  sr_zones: TsrSrZone[];
  pivot_markers: TsrPivotMarker[];
}

export interface TsrParams {
  interval?: Interval;
  days?: number;
  pvt_length?: number;
  tl_points_to_check?: number;
  tl_max_violation?: number;
  tl_except_bars?: number;
  sr_points_to_check?: number;
  sr_max_violation?: number;
  sr_except_bars?: number;
}
