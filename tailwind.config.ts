import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        border: "hsl(var(--border))",
        muted: "hsl(var(--muted))",
        panel: "hsl(var(--panel))",
        accent: "hsl(var(--accent))",
        signal: "hsl(var(--signal))",
        warning: "hsl(var(--warning))",
        danger: "hsl(var(--danger))"
      },
      boxShadow: {
        panel: "0 18px 60px rgba(19, 27, 31, 0.08)"
      },
      borderRadius: {
        md: "8px"
      }
    }
  },
  plugins: []
} satisfies Config;
