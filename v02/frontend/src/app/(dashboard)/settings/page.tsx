"use client";

export default function SettingsPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 max-w-md">
        <h2 className="text-lg font-semibold mb-4">Binance API Keys</h2>
        {/* TODO: API key form with encryption */}
        <p className="text-gray-400">API key management will be implemented here.</p>
      </div>
    </div>
  );
}
