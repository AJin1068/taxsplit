// "견본으로 해 보기": PDF 없이 가상 간소화 자료 예시로 대화를 시작한다(PDF 올리기는 ExtractReview).
import { SAMPLES } from "../samples";

export function SamplePicker({ value, onChange, disabled }: { value: string; onChange: (id: string) => void; disabled: boolean }) {
  return (
    <label className="flex items-center gap-2 rounded-2xl bg-brand-amberBg px-4 py-2 text-xs text-brand-amber">
      <span className="font-semibold">견본으로 해 보기</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        aria-label="개발용 간소화 자료"
        className="flex-1 rounded-lg bg-white px-2 py-1 text-brand-text disabled:opacity-60"
      >
        <option value="">보내지 않음</option>
        {SAMPLES.map((s) => (
          <option key={s.id} value={s.id}>
            {s.label}
          </option>
        ))}
      </select>
    </label>
  );
}
