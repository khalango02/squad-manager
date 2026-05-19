import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0f1117",
        card: "#1a1d27",
        border: "#2a2d3e",
        accent: "#6c63ff",
        "accent-hover": "#574fd6",
      },
    },
  },
  plugins: [],
};

export default config;
