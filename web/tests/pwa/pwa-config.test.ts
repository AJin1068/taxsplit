// 설치되는 웹앱(PWA) 설정 검사: manifest 필수 칸과 "/api/는 캐시하지 않는다" 규칙
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import type { RouteMatchCallbackOptions } from "workbox-core";
import { describe, expect, it } from "vitest";
import { pwaOptions } from "../../vite.config";

const publicDir = resolve(__dirname, "../../public");

describe("manifest", () => {
  const manifest = pwaOptions.manifest;
  if (!manifest) throw new Error("manifest 설정이 없다");

  it("앱 이름·시작 주소·표시 방식이 있다", () => {
    expect(manifest.name).toBe("원투원");
    expect(manifest.short_name).toBeTruthy();
    expect(manifest.start_url).toBe("/");
    expect(manifest.display).toBe("standalone");
    expect(manifest.theme_color).toMatch(/^#[0-9A-Fa-f]{6}$/);
    expect(manifest.background_color).toMatch(/^#[0-9A-Fa-f]{6}$/);
  });

  it("아이콘 192·512px와 maskable 아이콘이 있고 파일도 있다", () => {
    const icons = manifest.icons ?? [];
    const has = (size: string, purpose: string) =>
      icons.some((i) => i.sizes === size && (i.purpose ?? "any").split(" ").includes(purpose));
    expect(has("192x192", "any")).toBe(true);
    expect(has("512x512", "any")).toBe(true);
    expect(has("512x512", "maskable")).toBe(true);
    for (const icon of icons) {
      expect(existsSync(resolve(publicDir, icon.src.replace(/^\//, "")))).toBe(true);
    }
  });

  it("서비스 워커를 플러그인이 자동 등록한다", () => {
    expect(pwaOptions.injectRegister).toBe("script");
  });
});

describe("/api/는 캐시하지 않는다", () => {
  const workbox = pwaOptions.workbox;
  if (!workbox) throw new Error("workbox 설정이 없다");

  const matches = (pattern: unknown, href: string): boolean => {
    const url = new URL(href);
    if (pattern instanceof RegExp) return pattern.test(url.href);
    if (typeof pattern === "function") {
      return Boolean(pattern({ url, sameOrigin: true } as RouteMatchCallbackOptions));
    }
    return false;
  };

  it("/api/ 요청은 NetworkOnly 규칙에 걸린다", () => {
    const rules = workbox.runtimeCaching ?? [];
    for (const href of [
      "https://example.test/api/chat",
      "https://example.test/api/households/1",
      "https://example.test/api/upload",
    ]) {
      const hit = rules.filter((r) => matches(r.urlPattern, href));
      expect(hit.length).toBeGreaterThan(0);
      expect(hit.every((r) => r.handler === "NetworkOnly")).toBe(true);
    }
  });

  it("/api/가 아닌 화면 주소는 /api/ 규칙에 걸리지 않는다", () => {
    const rules = workbox.runtimeCaching ?? [];
    for (const href of ["https://example.test/", "https://example.test/apiary"]) {
      expect(rules.some((r) => matches(r.urlPattern, href))).toBe(false);
    }
  });

  it("어떤 캐시 규칙도 /api/에 캐시 전략을 쓰지 않는다", () => {
    const rules = workbox.runtimeCaching ?? [];
    const cached = rules.filter(
      (r) => r.handler !== "NetworkOnly" && matches(r.urlPattern, "https://example.test/api/chat"),
    );
    expect(cached).toEqual([]);
  });

  it("/api/ 화면 이동은 index.html로 바꿔 주지 않는다", () => {
    const deny = workbox.navigateFallbackDenylist ?? [];
    expect(deny.some((re) => re.test("/api/chat"))).toBe(true);
    expect(deny.some((re) => re.test("/"))).toBe(false);
  });

  it("미리 캐시하는 파일은 화면 파일 종류뿐이다", () => {
    for (const pattern of workbox.globPatterns ?? []) {
      expect(pattern).not.toMatch(/api/);
      expect(pattern).not.toMatch(/json/);
    }
  });
});
