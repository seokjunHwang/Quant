"use client";

import type { DrawingToolId, DrawingPoint } from "@/lib/drawing-types";

interface DrawingToolbarProps {
  activeTool: DrawingToolId;
  onToolChange: (tool: DrawingToolId) => void;
  pendingPoint: DrawingPoint | null;
  hasDrawings: boolean;
  onClearAll: () => void;
}

const TOOLS: { id: DrawingToolId; label: string; title: string }[] = [
  { id: "cursor", label: "↖", title: "Select (Esc)" },
  { id: "hline", label: "─", title: "Horizontal Line (1 click)" },
  { id: "trendline", label: "╱", title: "Trend Line (2 clicks)" },
  { id: "fibonacci", label: "Fib", title: "Fibonacci Retracement (2 clicks)" },
  { id: "price-range", label: "%", title: "Price Range / Profit (2 clicks)" },
];

export default function DrawingToolbar({
  activeTool,
  onToolChange,
  pendingPoint,
  hasDrawings,
  onClearAll,
}: DrawingToolbarProps) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 bg-zinc-900 border-b border-zinc-800 text-xs">
      {TOOLS.map((t) => (
        <button
          key={t.id}
          onClick={() => onToolChange(t.id)}
          title={t.title}
          className={`px-2 py-1 rounded transition-colors font-mono ${
            activeTool === t.id
              ? "bg-zinc-700 text-zinc-100"
              : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
          }`}
        >
          {t.label}
        </button>
      ))}

      {pendingPoint && (
        <span className="ml-2 text-amber-400 animate-pulse">
          Click second point... (Esc to cancel)
        </span>
      )}

      {hasDrawings && (
        <button
          onClick={onClearAll}
          className="ml-auto text-zinc-500 hover:text-red-400 transition-colors px-2 py-1"
          title="Clear all drawings"
        >
          Clear All
        </button>
      )}
    </div>
  );
}
