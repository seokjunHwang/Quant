export type OrderSide = "BUY" | "SELL";
export type OrderType = "MARKET" | "LIMIT";

export interface Order {
  order_id: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  quantity: number;
  price: number;
  status: string;
}

export interface Position {
  symbol: string;
  positionAmt: number;
  entryPrice: number;
  markPrice: number;
  unrealizedPnl: number;
  leverage: number;
  side: "LONG" | "SHORT";
}

export interface Account {
  totalBalance: number;
  availableBalance: number;
  totalUnrealizedProfit: number;
}
