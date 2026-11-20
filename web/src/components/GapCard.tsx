// FR-11 빈 곳 알림 카드(gaps 이벤트). 질문 카드는 선택지 버튼, 동의 안내 카드는 "문구 복사" 버튼.
// 카드 글과 금액은 이벤트 값 그대로 보여 준다(화면이 만들지 않는다).
import { useState } from "react";
import type { CardAnswer, GapCardData, GapOption } from "../api/types";

/** 선택지 하나 → 메시지와 함께 보낼 구조화된 답 */
export function answerOf(card: GapCardData, option: GapOption): CardAnswer {
  const answer: CardAnswer = { gap_id: card.id, person: card.person, choice: option.label };
  if (typeof option.amount === "number") answer.amount = option.amount;
  return answer;
}

function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "done" | "failed">("idle");
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("done");
    } catch {
      // 브라우저가 클립보드를 막으면 글을 직접 골라 복사하게 안내한다
      setState("failed");
    }
  }
  const label = { idle: "문구 복사", done: "복사했어요", failed: "글을 길게 눌러 복사해 주세요" }[state];
  return (
    <button
      type="button"
      onClick={copy}
      className="mt-2 rounded-full bg-brand-navy px-4 py-2 text-xs font-semibold text-white hover:bg-brand-navyDark"
    >
      {label}
    </button>
  );
}

interface Props {
  card: GapCardData;
  busy: boolean;
  onAnswer: (text: string, answer: CardAnswer) => void;
}

export function GapCard({ card, busy, onAnswer }: Props) {
  const question = card.question;
  return (
    <article data-testid="gap-card" className="rounded-3xl border border-brand-amberBg bg-brand-card px-5 py-4 shadow-sm">
      <p className="text-xs font-semibold text-brand-amber">놓칠 수 있는 공제{card.person ? ` · ${card.person}` : ""}</p>
      <h3 className="mt-1 text-[15px] font-bold text-brand-text">{card.title}</h3>
      <p className="mt-2 text-sm text-brand-subtext">{card.why}</p>
      <p className="mt-1 text-sm text-brand-text">{card.todo}</p>
      {card.estimate?.message && (
        <p className="mt-2 rounded-2xl bg-brand-mintBg px-3 py-2 text-sm text-brand-mintText">{card.estimate.message}</p>
      )}
      {question && question.options.length > 0 && (
        <div className="mt-3">
          <p className="text-sm font-semibold text-brand-text">{question.text}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {question.options.map((o) => (
              <button
                key={o.label}
                type="button"
                disabled={busy}
                onClick={() => onAnswer(o.label, answerOf(card, o))}
                className="rounded-full border border-brand-navy px-3 py-1.5 text-sm text-brand-navy hover:bg-brand-navyBg disabled:opacity-40"
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {card.consent_message && (
        <div className="mt-3 rounded-2xl bg-brand-bg px-3 py-3">
          <p className="text-xs text-brand-muted">카카오톡으로 그대로 보낼 글</p>
          <p className="mt-1 whitespace-pre-line text-sm text-brand-text" data-testid="consent-message">
            {card.consent_message}
          </p>
          <CopyButton text={card.consent_message} />
        </div>
      )}
      {card.source_pages.length > 0 && (
        <p className="mt-2 text-[11px] text-brand-muted">
          근거: 국세청 「2025년 원천징수의무자를 위한 연말정산 신고안내」 인쇄{" "}
          {card.source_pages.join("·")}쪽
        </p>
      )}
    </article>
  );
}
