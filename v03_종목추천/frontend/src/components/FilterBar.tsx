"use client";

interface FilterBarProps {
  categories: string[];
  selectedCategory: string | undefined;
  onCategoryChange: (cat: string | undefined) => void;
  selectedSignalType: string | undefined;
  onSignalTypeChange: (type: string | undefined) => void;
}

export default function FilterBar({
  categories,
  selectedCategory,
  onCategoryChange,
  selectedSignalType,
  onSignalTypeChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap gap-3 items-center">
      <div className="flex items-center gap-2">
        <label className="text-sm text-zinc-400">Category</label>
        <select
          value={selectedCategory ?? ""}
          onChange={(e) =>
            onCategoryChange(e.target.value || undefined)
          }
          className="bg-zinc-800 border border-zinc-700 rounded-md px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-2">
        <label className="text-sm text-zinc-400">Signal</label>
        <select
          value={selectedSignalType ?? ""}
          onChange={(e) =>
            onSignalTypeChange(e.target.value || undefined)
          }
          className="bg-zinc-800 border border-zinc-700 rounded-md px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All</option>
          <option value="bullish">Bullish</option>
          <option value="bearish">Bearish</option>
        </select>
      </div>
    </div>
  );
}
