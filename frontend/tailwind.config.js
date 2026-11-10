/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#FBF4F5",
          100: "#F5E4E7",
          200: "#E8C7CF",
          300: "#D69BA8",
          400: "#B05A6E",
          500: "#95394F",
          600: "#791D32",
          700: "#67182B",
          800: "#531423",
          900: "#3F0F1B",
        },
        cream: "#FFF9F0",
        ink: "#292329",
      },
      fontFamily: {
        sans: ["Segoe UI", "Inter", "system-ui", "-apple-system", "Arial", "sans-serif"],
        serif: ["'Times New Roman'", "Georgia", "serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(41,35,41,0.06), 0 4px 14px rgba(41,35,41,0.05)",
      },
    },
  },
  plugins: [],
};
