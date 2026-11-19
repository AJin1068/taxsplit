"""배분 비교: 모든 배분안을 PR 4·5 엔진으로 계산하고 최적안과 흔한 방식 A·B를 고른다.

금액은 모두 엔진이 낸다. 이 모듈은 엔진을 부르고 합계를 비교하기만 한다(ADR-0003).
"""

from itertools import product

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
    WHO,
    AllocationResult,
    AllocWarning,
    Assignment,
    CommonPlan,
    Household,
    PlanResult,
    Who,
)
from taxsplit.allocation.unclaimed import CARD_FAMILY, CARD_NOTE, unclaimed_card_users
from taxsplit.engine import Rulebook, compute_tax
from taxsplit.rules.loader import Rule

_NAMES = {"husband": "남편", "wife": "아내"}


def evaluate(household: Household, plan: Assignment, rules: dict[str, Rule]) -> PlanResult:
    """배분안 하나: 부부 각자 엔진을 한 번씩 부르고 결정세액을 더한다.

    아무도 기본공제 받지 않는 가족의 카드 사용액은 문서가 누구에게 넣을지 정하지 않는다
    (인쇄 134쪽 "포함할 수 있음"). 사람 결정(2026-11-19, Issue #15)대로 남편 쪽·아내 쪽을
    모두 계산해 부부 결정세액 합이 작은 쪽을 고른다. 같으면 남편 쪽(입력의 첫 사람).
    """
    users = unclaimed_card_users(household, plan, Rulebook(rules))
    options = [dict(zip(users, pick, strict=True)) for pick in product(WHO, repeat=len(users))]
    # min은 같은 값이면 앞의 것을 돌려준다(product의 첫 줄 = 모두 남편 쪽)
    return min((_evaluate(household, plan, sides, rules) for sides in options), key=_total)


def _total(p: PlanResult) -> int:
    return p.total


def _evaluate(
    household: Household, plan: Assignment, card_sides: dict[str, Who], rules: dict[str, Rule]
) -> PlanResult:
    book = Rulebook(rules)
    workers, dropped = to_workers(household, plan, book, card_sides)
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
        card_sides=dict(card_sides),
        notes=tuple(_card_note(household, name, who, book) for name, who in card_sides.items()),
    )


def _card_note(household: Household, name: str, who: Who, book: Rulebook) -> AllocWarning:
    amount = sum(
        sum(c.model_dump(exclude={"user", "payer"}).values())
        for c in household.cards
        if c.user == name
    )
    msg = (
        f"{name} 카드 사용액 {amount:,}원: 부부 누구도 기본공제 받지 않는 가족이라"
        f" 남편 쪽·아내 쪽을 모두 계산해 부부 결정세액 합이 작은 {_NAMES[who]} 쪽에 넣음."
        f" {CARD_NOTE}"
    )
    return AllocWarning(
        code="card_unclaimed_family", message=msg, rule_ids=(book.full_id(CARD_FAMILY),)
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

    # "총급여가 큰 쪽"이 같을 때 쓰는 과세표준: 부양가족 없이 각자 계산한 값.
    # 가족 지출은 빼야 한다(아무도 기본공제 받지 않는 가족 지출도 이제 공제되므로)
    alone = evaluate(_without_family(household), {}, rules)
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
    warnings = scope_warnings(household, book) + best.notes
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


def _without_family(household: Household) -> Household:
    """부양가족과 가족 지출을 뺀 가구(부부 본인·배우자 지출만 남김)."""
    return household.model_copy(
        update={
            "members": (),
            "medical": tuple(s for s in household.medical if s.for_whom in WHO),
            "education": tuple(e for e in household.education if e.for_whom in WHO),
            "cards": tuple(c for c in household.cards if c.user in WHO),
        }
    )
