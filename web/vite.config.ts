/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 에이전트 API 주소. 다른 포트로 띄웠으면 AGENT_API_URL로 바꾼다
const agentApi = process.env.AGENT_API_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    // /api로 시작하는 요청을 에이전트 API로 넘긴다(그래서 CORS 설정이 필요 없다)
    proxy: {
      "/api": {
        target: agentApi,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
