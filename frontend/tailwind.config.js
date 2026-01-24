/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#09090B",
        foreground: "#FAFAFA",
        card: {
          DEFAULT: "#18181B",
          foreground: "#FAFAFA"
        },
        popover: {
          DEFAULT: "#09090B",
          foreground: "#FAFAFA"
        },
        primary: {
          DEFAULT: "#22C55E",
          foreground: "#052e16"
        },
        secondary: {
          DEFAULT: "#27272A",
          foreground: "#FAFAFA"
        },
        muted: {
          DEFAULT: "#27272A",
          foreground: "#A1A1AA"
        },
        accent: {
          DEFAULT: "#27272A",
          foreground: "#FAFAFA"
        },
        destructive: {
          DEFAULT: "#EF4444",
          foreground: "#FAFAFA"
        },
        border: "#27272A",
        input: "#27272A",
        ring: "#22C55E",
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
        sans: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        lg: "0.5rem",
        md: "calc(0.5rem - 2px)",
        sm: "calc(0.5rem - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
