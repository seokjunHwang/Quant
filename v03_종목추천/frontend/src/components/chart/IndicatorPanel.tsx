"use client";

import { useState } from "react";
import type {
  IndicatorId,
  IndicatorState,
  IndicatorMeta,
} from "@/lib/indicator-types";
import {
  INDICATOR_REGISTRY,
  ALL_INDICATOR_IDS,
} from "@/lib/indicator-types";

interface IndicatorPanelProps {
  indicators: Record<IndicatorId, IndicatorState>;
  onChange: (id: IndicatorId, state: IndicatorState) => void;
}

export default function IndicatorPanel({
  indicators,
  onChange,
}: IndicatorPanelProps) {
  const [editingId, setEditingId] = useState<IndicatorId | null>(null);
  const [draft, setDraft] = useState<Record<string, number>>({});

  const openSettings = (id: IndicatorId) => {
    const meta = INDICATOR_REGISTRY[id];
    const current = indicators[id];
    const merged: Record<string, number> = {};
    for (const p of meta.paramInfo) {
      merged[p.key] = current.params[p.key] ?? meta.defaultParams[p.key];
    }
    setDraft(merged);
    setEditingId(id);
  };

  const applySettings = () => {
    if (!editingId) return;
    const meta = INDICATOR_REGISTRY[editingId];
    const customParams: Record<string, number> = {};
    for (const p of meta.paramInfo) {
      if (draft[p.key] !== meta.defaultParams[p.key]) {
        customParams[p.key] = draft[p.key];
      }
    }
    onChange(editingId, { ...indicators[editingId], params: customParams });
    setEditingId(null);
  };

  const resetDraft = () => {
    if (!editingId) return;
    const meta = INDICATOR_REGISTRY[editingId];
    const defaults: Record<string, number> = {};
    for (const p of meta.paramInfo) {
      defaults[p.key] = meta.defaultParams[p.key];
    }
    setDraft(defaults);
  };

  const toggleVisibility = (id: IndicatorId) => {
    onChange(id, { ...indicators[id], visible: !indicators[id].visible });
  };

  return (
    <div className="w-52 shrink-0 bg-zinc-900 border border-zinc-800 rounded-xl p-3 flex flex-col gap-1">
      <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1">
        Indicators
      </h3>

      {ALL_INDICATOR_IDS.map((id) => {
        const meta: IndicatorMeta = INDICATOR_REGISTRY[id];
        const state = indicators[id];
        const hasCustom = Object.keys(state.params).length > 0;

        return (
          <div key={id}>
            <div className="flex items-center justify-between py-1.5 px-1 rounded hover:bg-zinc-800/50 group">
              <span
                className={`text-sm font-medium truncate ${
                  state.visible ? "text-zinc-200" : "text-zinc-600"
                }`}
              >
                {meta.shortName}
                {hasCustom && (
                  <span className="ml-1 text-[9px] text-yellow-500">*</span>
                )}
              </span>

              <div className="flex items-center gap-1 opacity-70 group-hover:opacity-100">
                {/* Settings button */}
                <button
                  onClick={() => openSettings(id)}
                  className="p-1 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
                  title="Settings"
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                </button>

                {/* Visibility toggle */}
                <button
                  onClick={() => toggleVisibility(id)}
                  className={`p-1 rounded hover:bg-zinc-700 transition-colors ${
                    state.visible
                      ? "text-zinc-300 hover:text-zinc-100"
                      : "text-zinc-600 hover:text-zinc-400"
                  }`}
                  title={state.visible ? "Hide" : "Show"}
                >
                  {state.visible ? (
                    <svg
                      className="w-3.5 h-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                      />
                    </svg>
                  ) : (
                    <svg
                      className="w-3.5 h-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21"
                      />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Inline settings panel */}
            {editingId === id && (
              <div className="mt-1 mb-2 p-2 bg-zinc-800/80 rounded-lg border border-zinc-700">
                <div className="space-y-2.5">
                  {INDICATOR_REGISTRY[id].paramInfo.map((p) => (
                    <div key={p.key}>
                      <div className="flex items-center justify-between mb-0.5">
                        <label className="text-[11px] font-medium text-zinc-400">
                          {p.label}
                          <span className="ml-1 text-zinc-200 font-bold text-xs">
                            {draft[p.key]}
                          </span>
                        </label>
                        {draft[p.key] !== INDICATOR_REGISTRY[id].defaultParams[p.key] && (
                          <span className="text-[9px] text-yellow-500">
                            def: {INDICATOR_REGISTRY[id].defaultParams[p.key]}
                          </span>
                        )}
                      </div>
                      <input
                        type="range"
                        min={p.min}
                        max={p.max}
                        value={draft[p.key]}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            [p.key]: Number(e.target.value),
                          }))
                        }
                        className="w-full accent-purple-500 h-1"
                      />
                      <p className="text-[9px] text-zinc-600 mt-0.5">{p.desc}</p>
                    </div>
                  ))}
                </div>

                <div className="flex gap-1 mt-3">
                  <button
                    onClick={applySettings}
                    className="flex-1 bg-purple-600 hover:bg-purple-500 text-white py-1 rounded text-[11px] font-medium transition-colors"
                  >
                    Apply
                  </button>
                  <button
                    onClick={resetDraft}
                    className="bg-zinc-700 hover:bg-zinc-600 text-zinc-300 px-2 py-1 rounded text-[11px] transition-colors"
                  >
                    Reset
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="bg-zinc-700 hover:bg-zinc-600 text-zinc-400 px-2 py-1 rounded text-[11px] transition-colors"
                  >
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
