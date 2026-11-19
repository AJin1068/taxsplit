// 원투원 첫 화면: 스트리밍 채팅(UI-04) + 배분안 비교 카드(UI-01).
import { useEffect, useMemo, useRef, useState } from "react";
import { useChat } from "./chat/useChat";
import { AllocationCard } from "./components/AllocationCard";
import { Bubble } from "./components/Bubble";
import { Composer } from "./components/Composer";
import { SamplePicker } from "./components/SamplePicker";
import { FOOTER_DISCLAIMER } from "./labels";
import { sampleDocuments } from "./samples";

export default function App() {
  const [sampleId, setSampleId] = useState("");
  const documents = useMemo(() => sampleDocuments(sampleId), [sampleId]);
  const { state, send, retry, started } = useChat(documents);
  const bottom = useRef<HTMLDivElement>(null);

  // 새 글이 오면 아래로 내린다(jsdom에는 scrollIntoView가 없다)
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [state.messages, state.allocation, state.progress]);

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col bg-brand-bg font-sans text-brand-text">
      <header className="px-5 pb-3 pt-6">
        <h1 className="text-2xl font-extrabold text-brand-navy">원투원</h1>
        <p className="mt-1 text-sm text-brand-subtext">맞벌이 연말정산, 누구에게 넣을지 같이 계산해요</p>
      </header>

      <main className="flex-1 space-y-3 px-4 pb-44">
        <SamplePicker value={sampleId} onChange={setSampleId} disabled={started} />
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
        {state.allocation && <AllocationCard data={state.allocation} />}
        <div ref={bottom} />
      </main>

      <div className="fixed inset-x-0 bottom-0 mx-auto max-w-md bg-brand-bg/95 px-4 pb-3 pt-2 backdrop-blur">
        <Composer onSend={send} busy={state.busy} />
        <footer className="mt-2 text-center text-[11px] text-brand-muted">{FOOTER_DISCLAIMER}</footer>
      </div>
    </div>
  );
}
