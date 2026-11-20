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

// 근거 한 줄(PR 13 evidence 이벤트): 규칙 ID → 원문 조각 목록. 규칙 ID는 화면에 보이지 않는다
export interface EvidenceItem {
  rule_id: string;
  source: string;
  page: string;
  print_page: number | null;
  pdf_page: number | null;
  snippet: string;
}
export type EvidenceMap = Record<string, EvidenceItem[]>;

// 빈 곳 알림 카드(PR 24 gaps 이벤트). 모르는 칸은 무시한다(PR 11c가 칸을 더할 수 있다)
export interface GapOption {
  label: string;
  amount?: number | null;
}
export interface GapCardData {
  id: string;
  kind: string;
  person: string | null;
  title: string;
  why: string;
  todo: string;
  source_pages: string[];
  question?: { text: string; options: GapOption[] } | null;
  estimate?: { message: string } | null;
  consent_message?: string | null;
}

// 질문 카드 선택지를 눌렀을 때 메시지와 함께 보내는 답(POST /conversations/{id}/messages의 answer)
export interface CardAnswer {
  gap_id: string;
  person: string | null;
  choice: string;
  amount?: number | null;
}

// 첫 화면 설정(UI-00). 고르지 않으면 null
export interface SetupChoice {
  self_role: Who | null;
  child_count: number | null;
}

// 간소화 PDF 추출 결과(PR 12 형식). 화면은 금액·가족 칸만 고친다
export interface ExtractedItem {
  group: string;
  kind: string;
  person_name: string;
  amount: number;
  [other: string]: unknown;
}
export interface ExtractedDoc {
  tax_year: number;
  worker_name: string;
  items: ExtractedItem[];
  totals?: { group: string; amount: number }[];
  notes?: string[];
  [other: string]: unknown;
}
export interface ExtractionResponse {
  ok: boolean;
  doc: ExtractedDoc | null;
  errors: string[];
  fallback: "json_upload" | null;
  filename: string | null;
}

// SSE 한 덩어리를 이름과 JSON 값으로 읽은 것
export type ChatEvent =
  | { name: "status"; data: StatusEvent }
  | { name: "delta"; data: { text: string } }
  | { name: "allocation"; data: AllocationEvent }
  | { name: "evidence"; data: unknown }
  | { name: "gaps"; data: { cards?: unknown } }
  | { name: "error"; data: { message: string } }
  | { name: "done"; data: DoneEvent };
