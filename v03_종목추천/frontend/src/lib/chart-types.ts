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

export interface ChartParams {
  days?: number;
  rsi_period?: number;
  lb_left?: number;
  lb_right?: number;
  range_lower?: number;
  range_upper?: number;
  lookback?: number;
}
