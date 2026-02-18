import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        long: "#26a69a",
        short: "#ef5350",
        hold: "#78909c",
      },
    },
  },
  plugins: [],
};

export default config;
