/** Drawing tool types for interactive chart annotations. */

export type DrawingToolId = "cursor" | "hline" | "trendline" | "fibonacci" | "price-range";

export interface DrawingPoint {
  time: number;  // raw epoch (no tz offset)
  price: number;
}

export interface HLineDrawing {
  id: string;
  tool: "hline";
  price: number;
}

export interface TrendLineDrawing {
  id: string;
  tool: "trendline";
  p1: DrawingPoint;
  p2: DrawingPoint;
}

export interface FibonacciDrawing {
  id: string;
  tool: "fibonacci";
  p1: DrawingPoint;
  p2: DrawingPoint;
}

export interface PriceRangeDrawing {
  id: string;
  tool: "price-range";
  p1: DrawingPoint;
  p2: DrawingPoint;
}

export type Drawing = HLineDrawing | TrendLineDrawing | FibonacciDrawing | PriceRangeDrawing;

let _nextId = 0;
export function generateDrawingId(): string {
  return `d${Date.now()}_${_nextId++}`;
}
