"use client";

export default function TradingPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Trading</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h2 className="text-lg font-semibold mb-4">Order Form</h2>
          {/* TODO: OrderForm component */}
        </div>
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h2 className="text-lg font-semibold mb-4">Positions</h2>
          {/* TODO: PositionTable component */}
        </div>
      </div>
    </div>
  );
}
