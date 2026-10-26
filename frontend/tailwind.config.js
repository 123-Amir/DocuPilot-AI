/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#05080f",
          900: "#080d17",
          850: "#0b1220",
          800: "#101a2b",
          700: "#1a2740",
        },
        signal: "#c8f56a",
        ember: "#ff8a5c",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "SFMono-Regular",
          "ui-monospace",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        panel: "0 20px 60px -30px rgba(0, 0, 0, 0.9)",
        signal: "0 0 0 1px rgba(200, 245, 106, 0.35), 0 12px 40px -20px rgba(200, 245, 106, 0.4)",
      },
      keyframes: {
        pulseSoft: {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        rise: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        pulseSoft: "pulseSoft 1.8s ease-in-out infinite",
        rise: "rise 220ms ease-out both",
      },
    },
  },
  plugins: [],
};