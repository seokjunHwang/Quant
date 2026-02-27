/**
 * Timezone offset utilities for Lightweight Charts.
 *
 * LWC v5 displays UTCTimestamp values in UTC.
 * To show KST, we add +9h to every epoch before passing to the chart.
 * UTC mode = no shift (raw epoch as-is).
 */

import type { ChartData, TsrData, Timezone } from "./chart-types";

const TZ_OFFSETS: Record<Timezone, number> = {
  UTC: 0,
  KST: 9 * 3600,
};

export function applyTzOffset(epoch: number, tz: Timezone): number {
  return epoch + TZ_OFFSETS[tz];
}

export function reverseTzOffset(shifted: number, tz: Timezone): number {
  return shifted - TZ_OFFSETS[tz];
}

export function shiftChartData(data: ChartData, tz: Timezone): ChartData {
  const off = TZ_OFFSETS[tz];
  if (off === 0) return data;

  return {
    ...data,
    candles: data.candles.map((c) => ({ ...c, time: c.time + off })),
    rsi: data.rsi.map((r) => ({ ...r, time: r.time + off })),
    pivot_lows: data.pivot_lows.map((p) => ({ ...p, time: p.time + off })),
    pivot_highs: data.pivot_highs.map((p) => ({ ...p, time: p.time + off })),
    signals: data.signals.map((s) => ({ ...s, time: s.time + off })),
    divergence_lines: data.divergence_lines.map((d) => ({
      ...d,
      curr_time: d.curr_time + off,
      prev_time: d.prev_time + off,
    })),
  };
}

export function shiftTsrData(data: TsrData, tz: Timezone): TsrData {
  const off = TZ_OFFSETS[tz];
  if (off === 0) return data;

  return {
    ...data,
    candles: data.candles.map((c) => ({ ...c, time: c.time + off })),
    trend_lines: data.trend_lines.map((tl) => ({
      ...tl,
      start_time: tl.start_time + off,
      end_time: tl.end_time + off,
      ext_time: tl.ext_time != null ? tl.ext_time + off : null,
    })),
    sr_zones: data.sr_zones.map((z) => ({
      ...z,
      start_time: z.start_time + off,
      end_time: z.end_time + off,
    })),
    pivot_markers: data.pivot_markers.map((p) => ({ ...p, time: p.time + off })),
  };
}
