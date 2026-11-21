/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA, type VitePWAOptions } from "vite-plugin-pwa";

// 에이전트 API 주소. 다른 포트로 띄웠으면 AGENT_API_URL로 바꾼다
const agentApi = process.env.AGENT_API_URL ?? "http://localhost:8000";

// 설치되는 웹앱(PWA) 설정. 테스트(web/tests/pwa/)가 이 값을 그대로 검사한다
export const pwaOptions: Partial<VitePWAOptions> = {
  registerType: "autoUpdate",
  // 등록 스크립트를 빌드가 index.html에 넣는다(web/src/를 건드리지 않음)
  injectRegister: "script",
  // 아이콘은 아래 globPatterns(png)로 이미 미리 캐시되므로 두 번 넣지 않는다
  includeManifestIcons: false,
  manifest: {
    name: "원투원",
    short_name: "원투원",
    description: "맞벌이 부부의 연말정산 공제를 누구에게 넣을지 계산하고 근거와 함께 설명해요",
    lang: "ko",
    start_url: "/",
    scope: "/",
    display: "standalone",
    // web/tailwind.config.js의 brand.navy, brand.bg
    theme_color: "#1B365D",
    background_color: "#F8FAFC",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  },
  workbox: {
    // 빌드된 화면 파일만 미리 캐시한다
    globPatterns: ["**/*.{html,js,css,png,svg,webmanifest}"],
    // /api/로 가는 화면 이동 요청은 index.html로 바꿔 주지 않는다
    navigateFallbackDenylist: [/^\/api(\/|$)/],
    // 에이전트 API(/api/) 요청은 소득·공제 금액, 대화, 업로드를 주고받는다.
    // 기기에 개인 자료를 남기지 않도록 캐시 없이 늘 네트워크로만 보낸다.
    // 이 함수는 본문이 문자열로 sw.js에 들어가므로 바깥 변수를 쓰면 안 된다
    runtimeCaching: [
      {
        urlPattern: ({ url }) => url.pathname === "/api" || url.pathname.startsWith("/api/"),
        handler: "NetworkOnly",
      },
    ],
  },
};

export default defineConfig({
  plugins: [react(), VitePWA(pwaOptions)],
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
