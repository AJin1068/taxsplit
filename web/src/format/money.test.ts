import { describe, expect, it } from "vitest";
import { formatBigMoney, formatWon } from "./money";

describe("금액 표시", () => {
  it("만 원 단위로 버림해 큰 글씨, 원 단위는 작은 글씨", () => {
    expect(formatBigMoney(472_150)).toEqual({ big: "47만 원", exact: "472,150원" });
    expect(formatBigMoney(479_999)).toEqual({ big: "47만 원", exact: "479,999원" });
    expect(formatBigMoney(12_340_000)).toEqual({ big: "1,234만 원", exact: "12,340,000원" });
  });

  it("딱 만 원이면 1만 원", () => {
    expect(formatBigMoney(10_000)).toEqual({ big: "1만 원", exact: "10,000원" });
  });

  it("만 원 미만이면 원 단위만", () => {
    expect(formatBigMoney(9_990)).toEqual({ big: "9,990원", exact: null });
  });

  it("0원", () => {
    expect(formatBigMoney(0)).toEqual({ big: "0원", exact: null });
    expect(formatWon(0)).toBe("0원");
  });
});
