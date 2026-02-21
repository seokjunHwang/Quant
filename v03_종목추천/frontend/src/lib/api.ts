import type { ScanResult, ScanStatus, StockPoolResponse } from "./types";

const API_BASE = "/api/v1";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
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

export async function triggerScan(market?: string): Promise<ScanResult> {
  const query = market ? `?market=${market}` : "";
  return fetchJSON<ScanResult>(`${API_BASE}/scan/trigger${query}`, {
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
