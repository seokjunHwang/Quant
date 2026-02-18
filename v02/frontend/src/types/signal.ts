export type SignalType = "LONG" | "HOLD" | "SHORT";

export interface Signal {
  symbol: string;
  signal_type: SignalType;
  confidence: number;
  price: number;
  timestamp: string;
  strategy_name: string;
}
