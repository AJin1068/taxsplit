// 개발용 간소화 자료 예시(PR 12 추출 결과 형식, 가상 인물). 실제 사람·평가 시나리오와 무관하다.
import couple from "./documents.json";

export interface Sample {
  id: string;
  label: string;
  documents: unknown[];
}

export const SAMPLES: Sample[] = [{ id: "couple-2024", label: "맞벌이 부부 작년 자료(가상)", documents: couple }];

export function sampleDocuments(id: string): unknown[] {
  return SAMPLES.find((s) => s.id === id)?.documents ?? [];
}
