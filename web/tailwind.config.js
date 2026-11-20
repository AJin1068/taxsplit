/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // 발표 데모 시안의 색(Issue #23 "모양")
      colors: {
        brand: {
          bg: "#F8FAFC",
          card: "#FFFFFF",
          text: "#16202E",
          subtext: "#465263",
          muted: "#5F6B7A",
          line: "#E6EAF0",
          navy: "#1B365D",
          navyDark: "#132844",
          navyBg: "#E8EEF6",
          mint: "#00B894",
          mintText: "#007D63",
          mintBg: "#E6F7F2",
          wife: "#7A4E9E",
          wifeBg: "#F1EAF7",
          amber: "#B45309",
          amberBg: "#FFF6E5",
        },
      },
      // 글꼴 파일은 레포에 넣지 않는다. 깔려 있으면 쓰고 없으면 시스템 글꼴
      fontFamily: {
        sans: [
          "Pretendard",
          '"Gothic A1"',
          "-apple-system",
          "BlinkMacSystemFont",
          "system-ui",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
