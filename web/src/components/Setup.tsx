// UI-00 첫 화면 설정(FR-09·FR-10)과 간소화 자료 고르기(UI-03).
// "저는 남편 / 저는 아내", 공제 대상 자녀 수(0~5명), 자료(견본 또는 PDF 올리기)를 고른 뒤 첫 메시지로 시작한다.
// 아무것도 고르지 않고 시작해도 된다. 첫 메시지를 보낸 뒤에는 바꿀 수 없다.
import type { ExtractedDoc, SetupChoice, Who } from "../api/types";
import { ExtractReview } from "./ExtractReview";
import { SamplePicker } from "./SamplePicker";

export const CHILD_COUNTS = [0, 1, 2, 3, 4, 5];
const ROLES: { value: Who; label: string }[] = [
  { value: "husband", label: "저는 남편" },
  { value: "wife", label: "저는 아내" },
];

interface Props {
  setup: SetupChoice;
  onSetup: (s: SetupChoice) => void;
  sampleId: string;
  onSample: (id: string) => void;
  uploaded: ExtractedDoc[];
  onUploaded: (docs: ExtractedDoc[]) => void;
  disabled: boolean;
}

export function Setup({ setup, onSetup, sampleId, onSample, uploaded, onUploaded, disabled }: Props) {
  return (
    <section aria-label="첫 화면 설정" className="space-y-3 rounded-3xl bg-brand-card px-5 py-5 shadow-sm">
      <div role="group" aria-label="본인 입장" className="grid grid-cols-2 gap-2">
        {ROLES.map((r) => {
          const on = setup.self_role === r.value;
          return (
            <button
              key={r.value}
              type="button"
              aria-pressed={on}
              disabled={disabled}
              // 한 번 더 누르면 고르지 않음으로 돌아간다
              onClick={() => onSetup({ ...setup, self_role: on ? null : r.value })}
              className={`rounded-2xl px-3 py-3 text-[15px] font-semibold disabled:opacity-60 ${
                on ? "bg-brand-navy text-white" : "border border-brand-line text-brand-text"
              }`}
            >
              {r.label}
            </button>
          );
        })}
      </div>
      <label className="flex items-center justify-between text-sm text-brand-text">
        <span className="font-semibold">공제 대상 자녀 수</span>
        <select
          aria-label="공제 대상 자녀 수"
          disabled={disabled}
          value={setup.child_count === null ? "" : String(setup.child_count)}
          onChange={(e) => onSetup({ ...setup, child_count: e.target.value === "" ? null : Number(e.target.value) })}
          className="rounded-lg border border-brand-line bg-white px-2 py-1 disabled:opacity-60"
        >
          <option value="">고르지 않음</option>
          {CHILD_COUNTS.map((n) => (
            <option key={n} value={n}>
              {n}명
            </option>
          ))}
        </select>
      </label>
      <ExtractReview docs={uploaded} onChange={onUploaded} disabled={disabled} />
      {/* 올린 자료가 있으면 견본은 쓰지 않는다 */}
      <SamplePicker value={sampleId} onChange={onSample} disabled={disabled || uploaded.length > 0} />
    </section>
  );
}
