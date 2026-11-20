// 글 입력 칸과 보내기 버튼.
import { useState, type FormEvent } from "react";

export function Composer({ onSend, busy }: { onSend: (text: string) => void; busy: boolean }) {
  const [text, setText] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || !text.trim()) return;
    onSend(text);
    setText("");
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="가족 정보나 궁금한 것을 적어 주세요"
        aria-label="메시지"
        className="min-w-0 flex-1 rounded-full border border-brand-line bg-brand-card px-4 py-3 text-[15px] text-brand-text outline-none focus:border-brand-navy"
      />
      <button
        type="submit"
        disabled={busy || !text.trim()}
        className="rounded-full bg-brand-navy px-5 py-3 font-semibold text-white hover:bg-brand-navyDark disabled:opacity-40"
      >
        보내기
      </button>
    </form>
  );
}
