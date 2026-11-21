// @vitest-environment node
// 실제로 빌드해 dist에 manifest·sw.js·아이콘이 들어가고 미리 캐시 목록에 /api/가 없는지 본다
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { build } from "vite";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const root = resolve(__dirname, "../..");
let outDir = "";

beforeAll(async () => {
  outDir = mkdtempSync(join(tmpdir(), "taxsplit-pwa-"));
  await build({
    root,
    configFile: resolve(root, "vite.config.ts"),
    logLevel: "silent",
    build: { outDir, emptyOutDir: true },
  });
}, 120_000);

afterAll(() => {
  if (outDir) rmSync(outDir, { recursive: true, force: true });
});

describe("빌드 결과", () => {
  it("manifest·sw.js·아이콘이 들어간다", () => {
    for (const file of [
      "manifest.webmanifest",
      "sw.js",
      "registerSW.js",
      "icons/icon-192.png",
      "icons/icon-512.png",
      "icons/icon-maskable-512.png",
      "icons/apple-touch-icon.png",
    ]) {
      expect(existsSync(join(outDir, file)), file).toBe(true);
    }
  });

  it("index.html이 manifest와 등록 스크립트를 부른다", () => {
    const html = readFileSync(join(outDir, "index.html"), "utf-8");
    expect(html).toContain("manifest.webmanifest");
    expect(html).toContain("registerSW.js");
    expect(html).toContain('name="theme-color"');
  });

  it("manifest에 이름과 아이콘이 있다", () => {
    const manifest = JSON.parse(readFileSync(join(outDir, "manifest.webmanifest"), "utf-8"));
    expect(manifest.name).toBe("원투원");
    expect(manifest.display).toBe("standalone");
    expect(manifest.icons.length).toBeGreaterThanOrEqual(3);
  });

  it("sw.js의 미리 캐시 목록에 /api/가 없고 화면 파일만 있다", () => {
    const sw = readFileSync(join(outDir, "sw.js"), "utf-8");
    const urls = [...sw.matchAll(/["']?url["']?\s*:\s*["']([^"']+)["']/g)].map((m) => m[1]);
    expect(urls).toContain("index.html");
    expect(urls).toContain("manifest.webmanifest");
    for (const url of urls) {
      expect(url).not.toMatch(/(^|\/)api(\/|$)/);
      expect(url).toMatch(/\.(html|js|css|png|svg|webmanifest)$/);
    }
    // /api/ 요청은 캐시 없이 네트워크로만 보낸다
    expect(sw).toContain("NetworkOnly");
  });
});
