interface StatusBadgeProps {
  signalType: string;
  label: string;
}

export default function StatusBadge({ signalType, label }: StatusBadgeProps) {
  const isBullish = signalType.includes("bullish");
  const isHidden = signalType.includes("hidden");

  const base = isBullish
    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
    : "bg-red-500/20 text-red-400 border-red-500/30";

  const opacity = isHidden ? "opacity-70" : "";

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${base} ${opacity}`}
    >
      {label}
    </span>
  );
}
