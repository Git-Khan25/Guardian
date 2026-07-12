/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0b0e11",
          900: "#12161b",
          800: "#1a1f26",
          700: "#242b34",
          600: "#333c47",
        },
        paper: "#f2ede1",
        amber: {
          accent: "#e0a336",
        },
        verdict: {
          confirmed: "#4f9d69",
          contradicted: "#c65a4a",
          unverifiable: "#8a8578",
        },
      },
      fontFamily: {
        display: ["'Source Serif 4'", "Georgia", "serif"],
        body: ["'Inter'", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      backgroundImage: {
        grain: "radial-gradient(circle at 1px 1px, rgba(242,237,225,0.04) 1px, transparent 0)",
      },
    },
  },
  plugins: [],
};
