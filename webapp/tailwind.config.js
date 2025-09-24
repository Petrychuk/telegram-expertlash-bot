/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/app/**/*.{js,jsx}",
    "./src/components/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        roseSoft: {
          50:  "#fff1f5",
          100: "#ffe4ec",
          200: "#fecdd8",
          300: "#fda4b8",
          400: "#fb7194",
          500: "#f43f5e", // основной розовый
          600: "#e11d48",
        },
      },
      boxShadow: {
        soft: "0 8px 24px rgba(244, 63, 94, 0.12)", // нежная тень
        card: "0 6px 18px rgba(0,0,0,0.06)",
      },
    },
  },
  plugins: [],
};
