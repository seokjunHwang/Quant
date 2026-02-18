export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Ticker {
  symbol: string;
  lastPrice: number;
  priceChange24h: number;
  volume24h: number;
}

export interface OrderBookEntry {
  price: number;
  quantity: number;
}

export interface OrderBook {
  symbol: string;
  bids: OrderBookEntry[];
  asks: OrderBookEntry[];
}
