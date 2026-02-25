/** Indicator registry and shared types for multi-indicator panel. */

export type IndicatorId = "rsi-divergence" | "tsr";

export interface ParamInfo {
  key: string;
  label: string;
  desc: string;
  min: number;
  max: number;
}

export interface IndicatorMeta {
  name: string;
  shortName: string;
  pane: "overlay" | "separate";
  defaultParams: Record<string, number>;
  paramInfo: ParamInfo[];
}

export interface IndicatorState {
  visible: boolean;
  params: Record<string, number>;
}

export const INDICATOR_REGISTRY: Record<IndicatorId, IndicatorMeta> = {
  "rsi-divergence": {
    name: "RSI Divergence",
    shortName: "RSI Div",
    pane: "separate",
    defaultParams: {
      rsi_period: 14,
      lb_left: 5,
      lb_right: 5,
      range_lower: 5,
      range_upper: 60,
      lookback: 1,
      days: 730,
    },
    paramInfo: [
      { key: "rsi_period", label: "RSI Period", desc: "RSI 계산 기간", min: 2, max: 50 },
      { key: "lb_left", label: "Pivot Left", desc: "피봇 왼쪽 확인 봉 수", min: 1, max: 20 },
      { key: "lb_right", label: "Pivot Right", desc: "피봇 오른쪽 확인 봉 수", min: 1, max: 20 },
      { key: "range_lower", label: "Range Min", desc: "두 피봇 사이 최소 봉 간격", min: 1, max: 50 },
      { key: "range_upper", label: "Range Max", desc: "두 피봇 사이 최대 봉 간격", min: 10, max: 200 },
      { key: "lookback", label: "Lookback", desc: "이전 N개 피봇과 비교", min: 1, max: 10 },
      { key: "days", label: "Days", desc: "데이터 조회 기간 (일)", min: 30, max: 730 },
    ],
  },
  tsr: {
    name: "TSR (Trend Lines, S/R)",
    shortName: "TSR",
    pane: "overlay",
    defaultParams: {
      pvt_length: 5,
      tl_points_to_check: 3,
      tl_max_violation: 0,
      tl_except_bars: 3,
      sr_points_to_check: 3,
      sr_max_violation: 0,
      sr_except_bars: 3,
    },
    paramInfo: [
      { key: "pvt_length", label: "Pivot Length", desc: "피봇 감지 길이", min: 1, max: 50 },
      { key: "tl_points_to_check", label: "TL Points", desc: "트렌드 라인 피봇 수", min: 2, max: 20 },
      { key: "tl_max_violation", label: "TL Max Violation", desc: "트렌드 라인 최대 위반 허용", min: 0, max: 10 },
      { key: "tl_except_bars", label: "TL Except Bars", desc: "트렌드 라인 예외 봉 수", min: 0, max: 20 },
      { key: "sr_points_to_check", label: "SR Points", desc: "지지/저항 피봇 수", min: 1, max: 20 },
      { key: "sr_max_violation", label: "SR Max Violation", desc: "지지/저항 최대 위반 허용", min: 0, max: 10 },
      { key: "sr_except_bars", label: "SR Except Bars", desc: "지지/저항 예외 봉 수", min: 0, max: 20 },
    ],
  },
};

export const ALL_INDICATOR_IDS = Object.keys(INDICATOR_REGISTRY) as IndicatorId[];

export function getDefaultIndicatorStates(): Record<IndicatorId, IndicatorState> {
  const states = {} as Record<IndicatorId, IndicatorState>;
  for (const id of ALL_INDICATOR_IDS) {
    states[id] = { visible: true, params: {} };
  }
  return states;
}
