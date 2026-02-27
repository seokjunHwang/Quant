import type { ScanResult, ScanStatus, StockPoolResponse } from "./types";
import type { ChartData, ChartParams, TsrData, TsrParams } from "./chart-types";

const API_BASE = "/api/v1";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getScanResults(params?: {
  market?: string;
  category?: string;
  signal_type?: string;
}): Promise<ScanResult | null> {
  const query = new URLSearchParams();
  if (params?.market) query.set("market", params.market);
  if (params?.category) query.set("category", params.category);
  if (params?.signal_type) query.set("signal_type", params.signal_type);

  const qs = query.toString();
  return fetchJSON<ScanResult | null>(
    `${API_BASE}/scan${qs ? `?${qs}` : ""}`
  );
}

export interface ScanParams {
  rsi_period?: number;
  lb_left?: number;
  lb_right?: number;
  range_lower?: number;
  range_upper?: number;
}

export async function triggerScan(
  market?: string,
  interval?: string,
  scanParams?: ScanParams,
): Promise<ScanResult> {
  const query = new URLSearchParams();
  if (market) query.set("market", market);
  if (interval) query.set("interval", interval);
  if (scanParams?.rsi_period) query.set("rsi_period", String(scanParams.rsi_period));
  if (scanParams?.lb_left) query.set("lb_left", String(scanParams.lb_left));
  if (scanParams?.lb_right) query.set("lb_right", String(scanParams.lb_right));
  if (scanParams?.range_lower) query.set("range_lower", String(scanParams.range_lower));
  if (scanParams?.range_upper) query.set("range_upper", String(scanParams.range_upper));

  const qs = query.toString();
  return fetchJSON<ScanResult>(`${API_BASE}/scan/trigger${qs ? `?${qs}` : ""}`, {
    method: "POST",
  });
}

export async function getScanStatus(): Promise<ScanStatus> {
  return fetchJSON<ScanStatus>(`${API_BASE}/scan/status`);
}

export async function getStocks(params?: {
  market?: string;
  category?: string;
}): Promise<StockPoolResponse> {
  const query = new URLSearchParams();
  if (params?.market) query.set("market", params.market);
  if (params?.category) query.set("category", params.category);
  return fetchJSON<StockPoolResponse>(
    `${API_BASE}/stocks?${query.toString()}`
  );
}

export interface TickerValidation {
  valid: boolean;
  ticker: string;    // resolved yfinance ticker
  original: string;  // user input
  name: string | null;
}

export async function validateTicker(
  ticker: string,
): Promise<TickerValidation> {
  return fetchJSON<TickerValidation>(
    `${API_BASE}/chart/validate/${encodeURIComponent(ticker)}`,
  );
}

export async function getChartData(
  ticker: string,
  params?: ChartParams,
): Promise<ChartData> {
  const query = new URLSearchParams();
  if (params?.interval) query.set("interval", params.interval);
  if (params?.days) query.set("days", String(params.days));
  if (params?.rsi_period) query.set("rsi_period", String(params.rsi_period));
  if (params?.lb_left) query.set("lb_left", String(params.lb_left));
  if (params?.lb_right) query.set("lb_right", String(params.lb_right));
  if (params?.range_lower) query.set("range_lower", String(params.range_lower));
  if (params?.range_upper) query.set("range_upper", String(params.range_upper));
  if (params?.lookback) query.set("lookback", String(params.lookback));

  const qs = query.toString();
  return fetchJSON<ChartData>(
    `${API_BASE}/chart/${encodeURIComponent(ticker)}${qs ? `?${qs}` : ""}`,
  );
}

export async function getTsrData(
  ticker: string,
  params?: TsrParams,
): Promise<TsrData> {
  const query = new URLSearchParams();
  if (params?.interval) query.set("interval", params.interval);
  if (params?.days) query.set("days", String(params.days));
  if (params?.pvt_length) query.set("pvt_length", String(params.pvt_length));
  if (params?.tl_points_to_check) query.set("tl_points_to_check", String(params.tl_points_to_check));
  if (params?.tl_max_violation !== undefined) query.set("tl_max_violation", String(params.tl_max_violation));
  if (params?.tl_except_bars) query.set("tl_except_bars", String(params.tl_except_bars));
  if (params?.sr_points_to_check) query.set("sr_points_to_check", String(params.sr_points_to_check));
  if (params?.sr_max_violation !== undefined) query.set("sr_max_violation", String(params.sr_max_violation));
  if (params?.sr_except_bars) query.set("sr_except_bars", String(params.sr_except_bars));

  const qs = query.toString();
  return fetchJSON<TsrData>(
    `${API_BASE}/chart/${encodeURIComponent(ticker)}/tsr${qs ? `?${qs}` : ""}`,
  );
}
