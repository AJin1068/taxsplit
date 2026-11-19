import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { allocationFixture } from "../test/fixtures";
import { AllocationCard } from "./AllocationCard";

// 부양가족 한 줄(이름이 있는 li)
const rowOf = (name: string) => screen.getByText(name, { exact: false }).closest("li");

describe("배분안 카드", () => {
  it("큰 숫자와 흔한 방식 A·B 차이는 allocation 이벤트 값 그대로다", () => {
    render(<AllocationCard data={allocationFixture()} />);
    expect(screen.getByTestId("headline-big")).toHaveTextContent("47만 원");
    // headline 원 단위(472,150원)는 큰 숫자 아래와 A 줄에 모두 나온다
    expect(screen.getAllByText("472,150원")).toHaveLength(2);
    expect(screen.getByText("613,400원")).toBeInTheDocument();
    expect(screen.getByText("61만 원")).toBeInTheDocument();
    expect(screen.getByText("소득이 많은 쪽에 부양가족을 모두 넣는 방식")).toBeInTheDocument();
  });

  it("최선 안에서 부양가족마다 누구 쪽인지 보여 준다", () => {
    render(<AllocationCard data={allocationFixture()} />);
    expect(rowOf("가상어머니")).toHaveTextContent("부모님→ 아내");
    expect(rowOf("가상자녀")).toHaveTextContent("자녀→ 남편");
  });

  it("배분안에 없는 부양가족은 공제 대상 아님", () => {
    const data = allocationFixture({ best_assignments: [{ 가상어머니: "wife" }] });
    render(<AllocationCard data={data} />);
    expect(screen.getByText("공제 대상 아님")).toBeInTheDocument();
  });

  it("부양가족 수와 계산한 경우의 수 한 줄", () => {
    render(<AllocationCard data={allocationFixture({ plan_count: 128 })} />);
    expect(screen.getByText("부양가족 2명, 128가지 경우를 모두 계산했어요")).toBeInTheDocument();
  });

  it("최선 안이 여럿이면 첫 번째를 보여 주고 나머지 수를 한 줄로", () => {
    const data = allocationFixture({
      best_assignments: [
        { 가상어머니: "husband", 가상자녀: "husband" },
        { 가상어머니: "wife", 가상자녀: "husband" },
        { 가상어머니: "wife", 가상자녀: "wife" },
      ],
    });
    render(<AllocationCard data={data} />);
    expect(rowOf("가상어머니")).toHaveTextContent("→ 남편");
    expect(screen.getByText("같은 금액인 방법이 2가지 더 있어요")).toBeInTheDocument();
  });

  it("최선 안이 하나면 '더 있어요' 줄이 없다", () => {
    render(<AllocationCard data={allocationFixture()} />);
    expect(screen.queryByText(/더 있어요/)).not.toBeInTheDocument();
  });

  it("차이가 0원이면 큰 숫자 대신 '어떻게 나눠도 세금이 같아요'", () => {
    const zero = allocationFixture({
      headline_saving: 0,
      common: allocationFixture().common.map((c) => ({ ...c, saving: 0 })),
    });
    render(<AllocationCard data={zero} />);
    expect(screen.getByText("어떻게 나눠도 세금이 같아요")).toBeInTheDocument();
    expect(screen.queryByTestId("headline-big")).not.toBeInTheDocument();
  });

  it("결과 카드 아래 고지 문구가 있다", () => {
    render(<AllocationCard data={allocationFixture()} />);
    expect(screen.getByText(/신고 대리나 세무 자문이 아닙니다/)).toBeInTheDocument();
  });
});
