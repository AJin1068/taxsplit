"""배분 비교: 모든 배분안을 PR 4·5 엔진으로 계산하고 최적안과 흔한 방식 A·B를 고른다.

금액은 모두 엔진이 낸다. 이 모듈은 엔진을 부르고 합계를 비교하기만 한다(ADR-0003).
"""

from taxsplit.allocation.assign import to_workers
from taxsplit.allocation.candidates import (
    all_assignments,
    candidates,
    common_a,
    common_b,
    larger_earner,
)
from taxsplit.allocation.checks import Claim, check_claims, scope_warnings
from taxsplit.allocation.models import (
    AllocationResult,
    Assignment,
    CommonPlan,
    Household,
    PlanResult,
)
from taxsplit.engine import Rulebook, compute_tax
from taxsplit.rules.loader import Rule


def evaluate(household: Household, plan: Assignment, rules: dict[str, Rule]) -> PlanResult:
    """배분안 하나: 부부 각자 엔진을 한 번씩 부르고 결정세액을 더한다."""
    book = Rulebook(rules)
    workers, dropped = to_workers(household, plan, book)
    husband = compute_tax(workers["husband"], rules)
    wife = compute_tax(workers["wife"], rules)
    ids = {i for r in (husband, wife) for stage in r.rules_used.values() for i in stage}
    ids |= {i for stage in book.rules_used().values() for i in stage}
    return PlanResult(
        assignment=dict(plan),
        husband_tax=husband.determined_tax,
        wife_tax=wife.determined_tax,
        total=husband.determined_tax + wife.determined_tax,
        husband=husband,
        wife=wife,
        dropped=tuple(dropped),
        rule_ids=tuple(sorted(ids)),
    )


def compare_allocations(
    household: Household,
    rules: dict[str, Rule],
    claims: tuple[Claim, ...] = (),
) -> AllocationResult:
    """모든 안을 계산해 최적안·흔한 방식 A·B 대비 차이·경고를 돌려준다.

    claims를 주면(부부가 각자 신청하려는 것) 중복공제 검사도 한다.
    """
    book = Rulebook(rules)
    cands = candidates(household, book)
    plans = tuple(evaluate(household, a, rules) for a in all_assignments(cands))

    # "총급여가 큰 쪽"이 같을 때 쓰는 과세표준: 부양가족 없이 각자 계산한 값
    alone = evaluate(household, {}, rules)
    taxable = {"husband": alone.husband.taxable_income, "wife": alone.wife.taxable_income}
    larger, equal = larger_earner(household, taxable)

    a_plan = _find(plans, common_a(cands, larger))
    b_plan = _find(plans, common_b(household, cands, larger))
    low = min(p.total for p in plans)
    ties = tuple(p for p in plans if p.total == low)
    # 같은 금액이면 흔한 방식 A와 같은 안을 먼저(바꿀 것이 적은 쪽, Issue #15 정해진 결정)
    best = a_plan if a_plan in ties else ties[0]
    common = (
        CommonPlan(
            name="A",
            description="부양가족 전부 총급여가 큰 쪽",
            plan=a_plan,
            saving=a_plan.total - best.total,
        ),
        CommonPlan(
            name="B",
            description="각자 자기 부모는 자기가, 자녀는 총급여가 큰 쪽",
            plan=b_plan,
            saving=b_plan.total - best.total,
        ),
    )
    warnings = scope_warnings(household, book)
    if claims:
        warnings += check_claims(household, claims, rules)
    return AllocationResult(
        plans=plans,
        plan_count=len(plans),
        best=best,
        best_plans=ties,
        common=common,
        headline_saving=min(c.saving for c in common),
        larger_earner=larger,
        equal_gross=equal,
        warnings=warnings,
    )


def _find(plans: tuple[PlanResult, ...], assignment: Assignment) -> PlanResult:
    return next(p for p in plans if p.assignment == assignment)
