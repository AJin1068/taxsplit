// 원투원 화면: 첫 화면 설정(UI-00)·자료 올리기(UI-03) → 스트리밍 채팅(UI-04)
// → 빈 곳 알림 카드(FR-11)·배분안 비교 카드(UI-01)와 근거 칩(UI-02).
import { useEffect, useMemo, useRef, useState } from "react";
import type { ExtractedDoc, SetupChoice } from "./api/types";
import { useChat } from "./chat/useChat";
import { AllocationCard } from "./components/AllocationCard";
import { Bubble } from "./components/Bubble";
import { Composer } from "./components/Composer";
import { GapCard } from "./components/GapCard";
import { Setup } from "./components/Setup";
import { FOOTER_DISCLAIMER } from "./labels";
import { sampleDocuments } from "./samples";

export default function App() {
  const [sampleId, setSampleId] = useState("");
  const [uploaded, setUploaded] = useState<ExtractedDoc[]>([]);
  const [setup, setSetup] = useState<SetupChoice>({ self_role: null, child_count: null });
  // 올려서 고친 자료가 있으면 그것을, 없으면 고른 견본을 보낸다
  const documents = useMemo(
    () => (uploaded.length > 0 ? uploaded : sampleDocuments(sampleId)),
    [uploaded, sampleId],
  );
  const { state, send, retry, started } = useChat(documents, setup);
  const bottom = useRef<HTMLDivElement>(null);

  // 새 글이 오면 아래로 내린다(jsdom에는 scrollIntoView가 없다)
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [state.messages, state.allocation, state.progress, state.gaps]);

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col bg-brand-bg font-sans text-brand-text">
      <header className="px-5 pb-3 pt-6">
        <h1 className="text-2xl font-extrabold text-brand-navy">원투원</h1>
        <p className="mt-1 text-sm text-brand-subtext">맞벌이 연말정산, 누구에게 넣을지 같이 계산해요</p>
      </header>

      <main className="flex-1 space-y-3 px-4 pb-44">
        <Setup
          setup={setup}
          onSetup={setSetup}
          sampleId={sampleId}
          onSample={setSampleId}
          uploaded={uploaded}
          onUploaded={setUploaded}
          disabled={started}
        />
        {state.messages.length === 0 && (
          <div className="rounded-3xl bg-brand-card px-5 py-6 text-[15px] leading-relaxed text-brand-subtext shadow-sm">
            남편·아내 연봉과 부양가족(부모님, 자녀)을 알려 주시면 세금을 가장 아끼는 방법을 찾아 드려요.
          </div>
        )}
        {state.messages.map((m, i) => (
          <Bubble key={i} message={m} onRetry={retry} busy={state.busy} />
        ))}
        {state.progress && (
          <p role="status" className="animate-pulse px-2 text-sm text-brand-muted">
            {state.progress}
          </p>
        )}
        {state.gaps.map((card) => (
          <GapCard key={`${card.id}/${card.person ?? ""}`} card={card} busy={state.busy} onAnswer={send} />
        ))}
        {state.allocation && (
          <AllocationCard data={state.allocation} evidence={state.evidence} selfRole={setup.self_role} />
        )}
        <div ref={bottom} />
      </main>

      <div className="fixed inset-x-0 bottom-0 mx-auto max-w-md bg-brand-bg/95 px-4 pb-3 pt-2 backdrop-blur">
        <Composer onSend={send} busy={state.busy} />
        <footer className="mt-2 text-center text-[11px] text-brand-muted">{FOOTER_DISCLAIMER}</footer>
      </div>
    </div>
  );
}
