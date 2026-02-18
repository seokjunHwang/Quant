import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trading Pipeline",
  description: "Crypto trading strategy pipeline dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="bg-gray-950 text-gray-100 antialiased">{children}</body>
    </html>
  );
}
