import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RSI Divergence Screener",
  description: "v03 - RSI Divergence Stock Screener",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="bg-zinc-950 text-zinc-100 min-h-screen antialiased">
        <div className="max-w-7xl mx-auto px-4 py-6">{children}</div>
      </body>
    </html>
  );
}
