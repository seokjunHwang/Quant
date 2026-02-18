import { create } from "zustand";

interface ChartState {
  interval: string;
  activeIndicators: string[];
  setInterval: (interval: string) => void;
  toggleIndicator: (id: string) => void;
}

export const useChartStore = create<ChartState>((set) => ({
  interval: "1d",
  activeIndicators: [],

  setInterval: (interval) => set({ interval }),

  toggleIndicator: (id) =>
    set((state) => ({
      activeIndicators: state.activeIndicators.includes(id)
        ? state.activeIndicators.filter((i) => i !== id)
        : [...state.activeIndicators, id],
    })),
}));
