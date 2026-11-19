// 말풍선 하나. 정상 답이 아니면 다시 보내기 버튼을 단다.
import type { ChatMessage } from "../chat/reducer";

export function Bubble({ message, onRetry, busy }: { message: ChatMessage; onRetry: () => void; busy: boolean }) {
  const mine = message.role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-3xl px-4 py-3 text-[15px] leading-relaxed ${
          mine ? "rounded-br-md bg-brand-navy text-white" : "rounded-bl-md bg-brand-card text-brand-text shadow-sm"
        }`}
      >
        {message.text}
        {message.retry && (
          <button
            type="button"
            onClick={onRetry}
            disabled={busy}
            className="mt-3 block rounded-full bg-brand-amberBg px-4 py-2 text-sm font-semibold text-brand-amber disabled:opacity-50"
          >
            다시 보내기
          </button>
        )}
      </div>
    </div>
  );
}
