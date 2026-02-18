export interface StrategyComponent {
  indicator_id: string;
  params: Record<string, number | string>;
}

export interface Strategy {
  strategy_id: string;
  primary: StrategyComponent;
  confirmation: StrategyComponent[];
  filter: StrategyComponent | null;
  exit: StrategyComponent | null;
  description: string;
  composite_score: number;
  created_at: string;
}

export interface BacktestResult {
  strategy_id: string;
  asset: string;
  period: string;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  total_trades: number;
  composite_score: number;
}
