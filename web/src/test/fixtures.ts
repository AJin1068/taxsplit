// 테스트용 allocation 이벤트(가상 가족). 금액은 아무 값이며 세법과 무관하다.
import type { AllocationEvent, PlanResult } from "../api/types";

const plan = (total: number, assignment: PlanResult["assignment"]): PlanResult => ({
  assignment,
  husband_tax: 0,
  wife_tax: total,
  total,
});

export function allocationFixture(over: Partial<AllocationEvent> = {}): AllocationEvent {
  return {
    plan_count: 4,
    best: plan(1_000_000, { 가상어머니: "wife", 가상자녀: "husband" }),
    best_assignments: [{ 가상어머니: "wife", 가상자녀: "husband" }],
    common: [
      { name: "A", description: "소득이 많은 쪽에 부양가족을 모두 넣는 방식", plan: plan(1_472_150, {}), saving: 472_150 },
      { name: "B", description: "각자 자기 부모님을 넣는 방식", plan: plan(1_613_400, {}), saving: 613_400 },
    ],
    headline_saving: 472_150,
    members: [
      { name: "가상어머니", relation: "lineal_ascendant", birth_year: 1955 },
      { name: "가상자녀", relation: "child", birth_year: 2019 },
    ],
    ...over,
  };
}

/** SSE 글을 주어진 조각대로 흘려보내는 응답 본문 */
export function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
}

export function sse(name: string, data: unknown): string {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
}
