// 채팅 API(PR 10, Issue #19 "API 모양")가 SSE로 보내는 이벤트의 모양.
// 화면은 이 값을 보여 주기만 한다. 금액을 새로 만들지 않는다(설계 원칙 1).

export type Who = "husband" | "wife";
export type Relation = "child" | "lineal_ascendant" | "sibling" | "spouse";

// 배분안 = 부양가족 이름 → 기본공제 받는 쪽
export type Assignment = Record<string, Who>;

export interface PlanResult {
  assignment: Assignment;
  husband_tax: number;
  wife_tax: number;
  total: number;
}

export interface CommonPlan {
  name: "A" | "B";
  description: string;
  plan: PlanResult;
  saving: number;
}

export interface AllocationMember {
  name: string;
  relation: Relation;
  birth_year: number;
}

export interface AllocationEvent {
  plan_count: number;
  best: PlanResult;
  best_assignments: Assignment[];
  common: CommonPlan[];
  headline_saving: number;
  members: AllocationMember[];
}

export type Ended = "answered" | "guard_stop" | "sensor_stop" | "error";

export interface StatusEvent {
  stage: "thinking" | "tool";
  tool?: string;
  status?: string;
}

export interface DoneEvent {
  message_id: number | null;
  turn: number;
  ended: Ended;
}

// SSE 한 덩어리를 이름과 JSON 값으로 읽은 것
export type ChatEvent =
  | { name: "status"; data: StatusEvent }
  | { name: "delta"; data: { text: string } }
  | { name: "allocation"; data: AllocationEvent }
  | { name: "evidence"; data: unknown }
  | { name: "error"; data: { message: string } }
  | { name: "done"; data: DoneEvent };
