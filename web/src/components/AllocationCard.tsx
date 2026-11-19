// UI-01 배분안 비교 카드. allocation 이벤트 값만 보여 준다(금액을 더하거나 빼지 않는다).
// 보여 줄 것은 3가지: 최선 안, 흔한 방식 A·B와의 차이, "n명, m가지 경우를 모두 계산" 한 줄.
import type { AllocationEvent, Assignment, CommonPlan } from "../api/types";
import { formatBigMoney } from "../format/money";
import { RELATION_LABELS, RESULT_DISCLAIMER, WHO_LABELS } from "../labels";

function Headline({ saving }: { saving: number }) {
  // 차이가 0원이면 큰 숫자 대신 한 줄
  if (saving === 0) {
    return <p className="text-xl font-bold text-white">어떻게 나눠도 세금이 같아요</p>;
  }
  const money = formatBigMoney(saving);
  return (
    <div>
      <p className="text-sm text-brand-navyBg">흔한 방식보다 세금</p>
      <p className="mt-1 text-4xl font-extrabold text-brand-mint" data-testid="headline-big">
        {money.big}
      </p>
      {money.exact && <p className="mt-1 text-xs text-brand-navyBg">{money.exact}</p>}
      <p className="mt-2 text-base font-semibold text-white">아낄 수 있어요</p>
    </div>
  );
}

function BestPlan({ data, assignment }: { data: AllocationEvent; assignment: Assignment }) {
  const more = data.best_assignments.length - 1;
  return (
    <section className="mt-5">
      <h3 className="text-sm font-semibold text-brand-subtext">이렇게 나누면 가장 좋아요</h3>
      <ul className="mt-2 space-y-2">
        {data.members.map((m) => {
          const who = assignment[m.name];
          return (
            <li key={m.name} className="flex items-center justify-between rounded-2xl bg-brand-bg px-4 py-3">
              <span className="text-brand-text">
                {m.name} <span className="text-xs text-brand-muted">{RELATION_LABELS[m.relation] ?? ""}</span>
              </span>
              {who ? (
                <span
                  className={`rounded-full px-3 py-1 text-sm font-semibold ${
                    who === "husband" ? "bg-brand-navyBg text-brand-navy" : "bg-brand-wifeBg text-brand-wife"
                  }`}
                >
                  → {WHO_LABELS[who]}
                </span>
              ) : (
                <span className="text-sm text-brand-muted">공제 대상 아님</span>
              )}
            </li>
          );
        })}
      </ul>
      {more > 0 && <p className="mt-2 text-xs text-brand-muted">같은 금액인 방법이 {more}가지 더 있어요</p>}
    </section>
  );
}

function CommonRow({ plan }: { plan: CommonPlan }) {
  const money = formatBigMoney(plan.saving);
  return (
    <li className="rounded-2xl border border-brand-line px-4 py-3">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold text-brand-text">흔한 방식 {plan.name}보다</span>
        <span className="text-lg font-bold text-brand-mintText">{money.big}</span>
      </div>
      {money.exact && <p className="text-right text-xs text-brand-muted">{money.exact}</p>}
      <p className="mt-1 text-xs text-brand-subtext">{plan.description}</p>
    </li>
  );
}

export function AllocationCard({ data }: { data: AllocationEvent }) {
  // 최선 안이 여럿이면 첫 번째를 보여 준다
  const assignment = data.best_assignments[0] ?? data.best.assignment;
  return (
    <div data-testid="allocation-card">
      <article className="overflow-hidden rounded-3xl bg-brand-card shadow-sm">
        <div className="bg-brand-navy px-5 py-6">
          <Headline saving={data.headline_saving} />
        </div>
        <div className="px-5 pb-5">
          <BestPlan data={data} assignment={assignment} />
          <section className="mt-5">
            <h3 className="text-sm font-semibold text-brand-subtext">흔한 방식과 비교하면</h3>
            <ul className="mt-2 space-y-2">
              {data.common.map((c) => (
                <CommonRow key={c.name} plan={c} />
              ))}
            </ul>
          </section>
          <p className="mt-5 rounded-2xl bg-brand-mintBg px-4 py-3 text-sm text-brand-mintText">
            부양가족 {data.members.length}명, {data.plan_count.toLocaleString("ko-KR")}가지 경우를 모두 계산했어요
          </p>
        </div>
      </article>
      <p className="mt-2 px-2 text-xs text-brand-muted">{RESULT_DISCLAIMER}</p>
    </div>
  );
}
