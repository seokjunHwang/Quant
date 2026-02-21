"use client";

interface MarketTabsProps {
  selected: string | undefined;
  onChange: (market: string | undefined) => void;
}

const tabs = [
  { key: undefined, label: "All" },
  { key: "US", label: "US" },
  { key: "KR", label: "KR" },
] as const;

export default function MarketTabs({ selected, onChange }: MarketTabsProps) {
  return (
    <div className="flex gap-1 bg-zinc-800 rounded-lg p-1">
      {tabs.map((tab) => {
        const active = selected === tab.key;
        return (
          <button
            key={tab.label}
            onClick={() => onChange(tab.key)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              active
                ? "bg-zinc-600 text-white"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
