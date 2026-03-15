import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#DC2626",
          light: "#FEF2F2",
        },
        secondary: "#1E293B",
        neutral: {
          50: "#F8FAFC",
          400: "#94A3B8",
          500: "#64748B",
          900: "#0F172A",
        },
        border: "#E2E8F0",
        success: {
          DEFAULT: "#16A34A",
          light: "#F0FDF4",
        },
        info: {
          DEFAULT: "#2563EB",
          light: "#EFF6FF",
        },
        accent: {
          DEFAULT: "#F97316",
          light: "#FFF7ED",
        },
        domain: {
          cybersecurity: "#6366F1",
          "ai-ml": "#059669",
          cloud: "#0EA5E9",
          devops: "#D946EF",
          default: "#64748B",
        },
        steady: {
          DEFAULT: "#64748B",
          light: "#F1F5F9",
        },
      },
      fontFamily: {
        heading: ["var(--font-space-grotesk)", "sans-serif"],
        body: ["var(--font-inter)", "sans-serif"],
      },
      borderRadius: {
        sm: "4px",
        md: "8px",
        lg: "12px",
        pill: "9999px",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(0,0,0,0.05)",
        md: "0 4px 6px -1px rgba(0,0,0,0.07)",
      },
    },
  },
  plugins: [],
};

export default config;
