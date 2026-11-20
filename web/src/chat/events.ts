// SSE evidence·gaps 이벤트 값을 화면이 쓰는 모양으로 읽는다.
// 모양이 다른 값은 버리고, 모르는 칸은 무시한다(서버가 칸을 더해도 화면이 깨지지 않게).
import type { AllocationMember, EvidenceItem, EvidenceMap, GapCardData } from "../api/types";

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

function isEvidence(v: unknown): v is EvidenceItem {
  return isObject(v) && typeof v.snippet === "string" && typeof v.source === "string";
}

/** evidence 이벤트: 규칙 ID → 근거 목록. 목록이 아니거나 비면 그 규칙은 근거 없음으로 본다. */
export function readEvidence(data: unknown): EvidenceMap {
  if (!isObject(data)) return {};
  const out: EvidenceMap = {};
  for (const [ruleId, items] of Object.entries(data)) {
    if (!Array.isArray(items)) continue;
    const good = items.filter(isEvidence);
    if (good.length > 0) out[ruleId] = good;
  }
  return out;
}

function isGapCard(v: unknown): v is GapCardData {
  return isObject(v) && typeof v.id === "string" && typeof v.title === "string";
}

/** gaps 이벤트: {cards: [...]}에서 id·title이 있는 카드만. */
export function readGapCards(data: unknown): GapCardData[] {
  if (!isObject(data) || !Array.isArray(data.cards)) return [];
  return data.cards.filter(isGapCard);
}

// 규칙 ID 모양: "2025.dependent.basic". 연도 뒤 첫 칸이 주제다
function topicOf(ruleId: string): string[] {
  return ruleId.split(".").slice(1);
}

/**
 * 배분안 카드의 가족 한 줄(판정) 옆에 붙일 근거. 규칙마다 첫 번째(점수가 가장 높은) 조각 하나.
 * - 부양가족 규칙(dependent.*): 모든 가족 줄
 * - 자녀 규칙(child.*): 자녀 줄에만
 * 그 밖의 규칙(의료비·카드 등)은 가족 판정이 아니라서 줄에 붙이지 않는다.
 * 가정: PR 14b "개발이 정한 것" (종류: 개발, 확신: 애매)
 */
export function evidenceForMember(member: AllocationMember, evidence: EvidenceMap): EvidenceItem[] {
  const out: EvidenceItem[] = [];
  for (const [ruleId, items] of Object.entries(evidence)) {
    const [topic] = topicOf(ruleId);
    const fits = topic === "dependent" || (topic === "child" && member.relation === "child");
    if (fits && items[0]) out.push(items[0]);
  }
  return out;
}

/** 칩에 쓰는 쉬운 이름(규칙 ID는 화면에 보이지 않는다). */
export function chipLabel(ruleId: string): string {
  const [topic, sub] = topicOf(ruleId);
  if (topic === "child") return "자녀세액공제";
  if (topic === "dependent" && sub === "basic") return "기본공제";
  if (topic === "dependent" && sub === "additional") return "추가공제";
  return "부양가족 공제";
}
