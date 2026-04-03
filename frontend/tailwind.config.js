/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          950: "#0c1222",
          900: "#111827",
          700: "#1f3c5c",
          500: "#3b82f6",
          400: "#60a5fa",
        },
      },
    },
  },
  plugins: [],
};
