export interface DivergenceSignal {
  ticker: string;
  name: string;
  market: string;
  category: string;
  signal_type: string;
  signal_label: string;
  detected_at: string;
  price_at_signal: number;
  rsi_at_signal: number;
  current_price: number;
  price_change_pct: number;
}

export interface ScanResult {
  scanned_at: string;
  total_stocks: number;
  signals_found: number;
  scan_duration_sec: number;
  signals: DivergenceSignal[];
}

export interface ScanStatus {
  last_scan: string | null;
  next_scan: string | null;
  is_scanning: boolean;
}

export interface StockEntry {
  ticker: string;
  name: string;
  market: string;
  category: string;
  pool_type: string;
}

export interface StockPoolResponse {
  total: number;
  stocks: StockEntry[];
}
