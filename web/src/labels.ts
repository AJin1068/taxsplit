// 화면에 보이는 쉬운 말. 도구 이름·상태 코드·규칙 ID는 화면에 보이지 않게 여기서 바꾼다.
import type { Relation, StatusEvent, Who } from "./api/types";

// 도구 이름 → 진행 한 줄
const TOOL_LABELS: Record<string, string> = {
  check_eligibility: "가족 공제 요건을 확인하고 있어요",
  compare_allocations: "나누는 방법을 모두 계산하고 있어요",
};
const THINKING_LABEL = "답을 준비하고 있어요";
const TOOL_FALLBACK = "계산하고 있어요";

/** status 이벤트를 쉬운 말 한 줄로. 모르는 도구도 이름을 드러내지 않는다. */
export function statusLabel(status: StatusEvent): string {
  if (status.stage === "tool") return TOOL_LABELS[status.tool ?? ""] ?? TOOL_FALLBACK;
  return THINKING_LABEL;
}

export const WHO_LABELS: Record<Who, string> = { husband: "남편", wife: "아내" };

export const RELATION_LABELS: Record<Relation, string> = {
  child: "자녀",
  lineal_ascendant: "부모님",
  sibling: "형제자매",
  spouse: "배우자",
};

export const ERROR_TEXT = "잠시 뒤 다시 시도해 주세요.";
export const RESULT_DISCLAIMER =
  "참고용 계산이며 신고 대리나 세무 자문이 아닙니다. 신고는 홈택스에서 직접 해 주세요.";
export const FOOTER_DISCLAIMER = "참고용 계산 · 최종 판단은 본인 또는 세무사와";
