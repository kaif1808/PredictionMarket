/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        slatebg: "#f3f4f6",
        ink: "#111827",
        accent: "#0e7490",
        warn: "#b45309"
      }
    }
  },
  plugins: []
};
