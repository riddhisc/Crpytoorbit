/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        raised: "var(--surface-raised)",
        line: "var(--border)",
        ink: "var(--text)",
        muted: "var(--text-muted)",
        accent: "var(--accent)",
        "accent-ink": "var(--accent-contrast)",
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
        info: "var(--info)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        xs: ["12px", "16px"],
        sm: ["14px", "20px"],
        base: ["16px", "24px"],
        lg: ["20px", "28px"],
        xl: ["24px", "32px"],
        "2xl": ["32px", "40px"],
      },
      borderRadius: { md: "8px", lg: "12px" },
      boxShadow: { soft: "var(--shadow)" },
    },
  },
  plugins: [],
};
