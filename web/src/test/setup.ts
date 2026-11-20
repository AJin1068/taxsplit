import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// vitest 전역 모드를 쓰지 않아서, 테스트마다 그린 화면을 직접 지운다
afterEach(() => cleanup());
