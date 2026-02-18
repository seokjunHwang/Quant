import Link from "next/link";

const NAV_ITEMS = [
  { href: "/chart/BTCUSDT", label: "Chart" },
  { href: "/signals", label: "Signals" },
  { href: "/strategies", label: "Strategies" },
  { href: "/trading", label: "Trading" },
  { href: "/settings", label: "Settings" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <nav className="w-16 bg-gray-900 border-r border-gray-800 flex flex-col items-center py-4 gap-4">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="w-10 h-10 rounded-lg flex items-center justify-center text-xs text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
            title={item.label}
          >
            {item.label.slice(0, 2).toUpperCase()}
          </Link>
        ))}
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
