// 근거 칩(UI-02): 판정 옆 칩, 올리거나 누르면 원문 조각과 쪽. 근거 없는 판정엔 칩 없음.
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { EvidenceItem } from "../api/types";
import { readEvidence } from "../chat/events";
import { allocationFixture } from "../test/fixtures";
import { AllocationCard } from "./AllocationCard";

// 가상 원문 조각(쪽 번호는 아무 값)
const item = (rule_id: string, snippet: string, print_page: number | null = 10): EvidenceItem => ({
  rule_id,
  source: "가상 신고안내",
  page: "p.10",
  print_page,
  pdf_page: print_page === null ? null : print_page + 18,
  snippet,
});

describe("근거 칩", () => {
  it("가족 판정 옆에 칩을 그리고, 마우스를 올리면 원문 조각과 인쇄·PDF 쪽을 보여 준다", () => {
    const evidence = { "2025.dependent.basic": [item("2025.dependent.basic", "기본공제 원문 조각")] };
    render(<AllocationCard data={allocationFixture()} evidence={evidence} />);
    const chips = within(screen.getByTestId("evidence-가상어머니")).getAllByRole("button");
    expect(chips).toHaveLength(1);
    expect(chips[0]).toHaveTextContent("근거 · 기본공제 10쪽");
    // 규칙 ID는 화면에 보이지 않는다
    expect(document.body.textContent).not.toMatch(/2025\.dependent/);
    fireEvent.mouseEnter(chips[0].parentElement!);
    const tip = screen.getByRole("tooltip");
    expect(tip).toHaveTextContent("기본공제 원문 조각");
    expect(tip).toHaveTextContent("가상 신고안내 · 인쇄 10쪽 (PDF 28쪽)");
    fireEvent.mouseLeave(chips[0].parentElement!);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("휴대폰처럼 누르면 열리고 다시 누르면 닫힌다", () => {
    const evidence = { "2025.child.credit.base": [item("2025.child.credit.base", "자녀 원문")] };
    render(<AllocationCard data={allocationFixture()} evidence={evidence} />);
    const chip = within(screen.getByTestId("evidence-가상자녀")).getByRole("button");
    fireEvent.click(chip);
    expect(screen.getByRole("tooltip")).toHaveTextContent("자녀 원문");
    fireEvent.click(chip);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("근거가 없는 판정에는 칩을 그리지 않는다", () => {
    // 자녀 규칙 근거만 있으면 부모님 줄에는 칩이 없다. 가족 판정이 아닌 규칙(카드)도 줄에 붙지 않는다
    const evidence = {
      "2025.child.credit.base": [item("2025.child.credit.base", "자녀 원문")],
      "2025.card.rate": [item("2025.card.rate", "카드 원문")],
    };
    render(<AllocationCard data={allocationFixture()} evidence={evidence} />);
    expect(screen.queryByTestId("evidence-가상어머니")).not.toBeInTheDocument();
    expect(within(screen.getByTestId("evidence-가상자녀")).getAllByRole("button")).toHaveLength(1);
  });

  it("evidence가 없거나 모양이 다르면 칩이 하나도 없다", () => {
    const evidence = readEvidence({ "2025.dependent.basic": { title: "x" }, "2025.dependent.age": [] });
    expect(evidence).toEqual({});
    render(<AllocationCard data={allocationFixture()} evidence={evidence} />);
    expect(screen.queryAllByText(/^근거 ·/)).toHaveLength(0);
  });

  it("본인 입장을 골랐으면 그쪽을 '나'로 부른다", () => {
    render(<AllocationCard data={allocationFixture()} selfRole="wife" />);
    expect(screen.getByText("가상어머니", { exact: false }).closest("li")).toHaveTextContent("→ 나");
    expect(screen.getByText("가상자녀", { exact: false }).closest("li")).toHaveTextContent("→ 남편");
  });
});
