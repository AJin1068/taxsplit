// UI-03 PDF 올리기와 추출 확인 표. 부부 각자 간소화 PDF(또는 JSON) 0~2개를 올리면 읽은 값을
// 표로 보여 주고, 사용자가 금액·가족 칸을 고친다. 고친 값은 대화를 만들 때 documents로 간다.
import { useState, type ChangeEvent } from "react";
import { extractFile } from "../api/client";
import type { ExtractedDoc, ExtractedItem } from "../api/types";

export const MAX_DOCS = 2;
const GROUP_LABELS: Record<string, string> = {
  medical: "의료비",
  education: "교육비",
  card: "카드 등",
  insurance: "보험료",
  other: "그 밖",
};

/**
 * 한 줄을 고친 문서. 사용자가 고치면 PDF에 적힌 그룹 합계(totals)와 더는 맞지 않으므로
 * 합계 대조를 빼고 사용자가 고친 값을 믿는다. 가정: PR 14b "개발이 정한 것" (종류: 개발, 확신: 분명)
 */
export function editItem(doc: ExtractedDoc, index: number, patch: Partial<ExtractedItem>): ExtractedDoc {
  const items = doc.items.map((item, i) => (i === index ? { ...item, ...patch } : item));
  const { totals: _dropped, ...rest } = doc;
  return { ...rest, items };
}

function DocTable({ doc, onChange, onRemove }: { doc: ExtractedDoc; onChange: (d: ExtractedDoc) => void; onRemove: () => void }) {
  return (
    <div className="mt-2 rounded-2xl bg-brand-bg p-3" data-testid="extract-table">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-brand-text">
          {doc.worker_name} 님 자료 <span className="text-xs text-brand-muted">{doc.tax_year}년 귀속</span>
        </p>
        <button type="button" onClick={onRemove} className="text-xs text-brand-muted underline">
          빼기
        </button>
      </div>
      {(doc.notes ?? []).map((n) => (
        <p key={n} className="mt-1 text-xs text-brand-amber">
          {n}
        </p>
      ))}
      <table className="mt-2 w-full text-left text-xs">
        <thead className="text-brand-muted">
          <tr>
            <th className="py-1 font-normal">항목</th>
            <th className="py-1 font-normal">가족</th>
            <th className="py-1 text-right font-normal">금액(원)</th>
          </tr>
        </thead>
        <tbody>
          {doc.items.map((item, i) => (
            <tr key={i} className="border-t border-brand-line">
              <td className="py-1 pr-1 text-brand-subtext">
                {GROUP_LABELS[item.group] ?? item.group} · {item.kind}
              </td>
              <td className="py-1 pr-1">
                <input
                  aria-label={`${i + 1}번째 줄 가족`}
                  value={item.person_name}
                  onChange={(e) => onChange(editItem(doc, i, { person_name: e.target.value }))}
                  className="w-20 rounded border border-brand-line bg-white px-1 py-0.5"
                />
              </td>
              <td className="py-1 text-right">
                <input
                  aria-label={`${i + 1}번째 줄 금액`}
                  inputMode="numeric"
                  value={String(item.amount)}
                  onChange={(e) => onChange(editItem(doc, i, { amount: Number(e.target.value.replace(/[^0-9]/g, "")) }))}
                  className="w-24 rounded border border-brand-line bg-white px-1 py-0.5 text-right"
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface Props {
  docs: ExtractedDoc[];
  onChange: (docs: ExtractedDoc[]) => void;
  disabled: boolean;
}

export function ExtractReview({ docs, onChange, disabled }: Props) {
  const [reading, setReading] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []).slice(0, MAX_DOCS - docs.length);
    e.target.value = "";
    if (files.length === 0) return;
    setReading(true);
    setProblems([]);
    const added: ExtractedDoc[] = [];
    const errors: string[] = [];
    for (const file of files) {
      try {
        const result = await extractFile(file);
        if (result.ok && result.doc) added.push(result.doc);
        // 읽지 못하면 이유와 함께 JSON으로 올리는 길을 알려 준다
        else errors.push(`${file.name}: ${result.errors.join(" / ")} → JSON 파일로 올려 주세요`);
      } catch (err) {
        errors.push(`${file.name}: ${err instanceof Error ? err.message : "파일을 읽지 못했어요"}`);
      }
    }
    setReading(false);
    setProblems(errors);
    if (added.length) onChange([...docs, ...added]);
  }

  return (
    <section>
      <label className="flex items-center justify-between rounded-2xl border border-dashed border-brand-navy px-4 py-3 text-sm text-brand-navy">
        <span className="font-semibold">PDF 올리기</span>
        <span className="text-xs text-brand-muted">{reading ? "읽고 있어요…" : `부부 각자 1개씩, 최대 ${MAX_DOCS}개`}</span>
        <input
          type="file"
          accept=".pdf,.json,application/pdf,application/json"
          multiple
          aria-label="간소화 PDF 올리기"
          disabled={disabled || reading || docs.length >= MAX_DOCS}
          onChange={upload}
          className="sr-only"
        />
      </label>
      {problems.map((p) => (
        <p key={p} role="alert" className="mt-1 text-xs text-brand-amber">
          {p}
        </p>
      ))}
      {docs.map((doc, i) => (
        <DocTable
          key={i}
          doc={doc}
          onChange={(d) => onChange(docs.map((old, j) => (j === i ? d : old)))}
          onRemove={() => onChange(docs.filter((_, j) => j !== i))}
        />
      ))}
    </section>
  );
}
