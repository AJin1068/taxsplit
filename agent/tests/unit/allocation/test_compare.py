"""배분 비교: 안 개수, 최적안, 같은 금액 처리, 흔한 방식 A·B, 지출이 따라가는 곳."""

import pytest

from allocation.households import (
    CARD_NEAR_THRESHOLD,
    HOUSEHOLDS,
    SIMILAR_WITH_KIDS,
    WIDE_GAP_PARENTS,
    child,
    earner,
    parent,
)
from taxsplit.allocation import (
    EducationSpend,
    Household,
    MedicalSpend,
    compare_allocations,
    evaluate,
)
from taxsplit.allocation.assign import to_workers
from taxsplit.engine import Rulebook

PLAN_COUNTS = {
    "1 소득 비슷+자녀": 4,
    "2 소득 차이+양가 부모": 4,
    "3 의료비 문턱 근처": 4,
    "4 카드 문턱 근처": 2,
    "5 부양가족 없음": 1,
}


@pytest.mark.parametrize("name", HOUSEHOLDS)
def test_plan_count_is_two_to_the_n(name, rules):
    assert compare_allocations(HOUSEHOLDS[name], rules).plan_count == PLAN_COUNTS[name]


@pytest.mark.parametrize("name", HOUSEHOLDS)
def test_best_total_not_above_any_plan(name, rules):
    r = compare_allocations(HOUSEHOLDS[name], rules)
    assert all(r.best.total <= p.total for p in r.plans)
    assert r.best in r.best_plans
    assert all(p.total == r.best.total for p in r.best_plans)


@pytest.mark.parametrize("name", HOUSEHOLDS)
def test_plan_total_is_sum_of_engine_results(name, rules):
    for p in compare_allocations(HOUSEHOLDS[name], rules).plans:
        assert p.total == p.husband.determined_tax + p.wife.determined_tax


@pytest.mark.parametrize("name", HOUSEHOLDS)
def test_saving_is_total_difference_and_headline_is_smaller(name, rules):
    r = compare_allocations(HOUSEHOLDS[name], rules)
    for c in r.common:
        assert c.saving == c.plan.total - r.best.total >= 0
    assert r.headline_saving == min(c.saving for c in r.common)


def test_common_a_and_b_assignments(rules):
    r = compare_allocations(WIDE_GAP_PARENTS, rules)
    a, b = r.common
    assert r.larger_earner == "husband" and not r.equal_gross
    assert a.plan.assignment == {"남편아버지": "husband", "아내어머니": "husband"}
    assert b.plan.assignment == {"남편아버지": "husband", "아내어머니": "wife"}
    # 아내가 낸 아내 어머니 의료비는 B에서만 공제된다. 그래서 B가 A보다 싸다
    assert b.plan.total < a.plan.total


def test_equal_totals_return_all_and_pick_common_a(rules):
    # 두 사람이 똑같으면 자녀를 누가 받아도 합계가 같다
    twin = Household(
        husband=earner(50_000_000, "male"),
        wife=earner(50_000_000, "male"),
        members=(child("아이", 2014),),
    )
    r = compare_allocations(twin, rules)
    assert len(r.best_plans) == 2
    # 총급여가 같으면 과세표준, 그것도 같으면 남편을 "큰 쪽"으로 본다
    assert r.equal_gross and r.larger_earner == "husband"
    assert r.best.assignment == r.common[0].plan.assignment == {"아이": "husband"}


def test_medical_paid_by_non_claimant_is_not_deducted(rules):
    # 작은아이를 남편이 기본공제하면 아내가 낸 작은아이 의료비는 공제 0
    p = evaluate(SIMILAR_WITH_KIDS, {"큰아이": "husband", "작은아이": "husband"}, rules)
    assert p.wife.medical.amount == 0 and p.husband.medical.amount == 0
    (d,) = p.dropped
    assert (d.kind, d.for_whom, d.payer, d.rule_id) == (
        "medical",
        "작은아이",
        "wife",
        "2025.medical.couple_rule",
    )
    q = evaluate(SIMILAR_WITH_KIDS, {"큰아이": "husband", "작은아이": "wife"}, rules)
    assert q.wife.medical.amount > 0 and not q.dropped


def test_child_credit_follows_claimant_and_education_needs_claimant_payer(rules):
    p = evaluate(SIMILAR_WITH_KIDS, {"큰아이": "wife", "작은아이": "wife"}, rules)
    # 큰아이(10세) 자녀세액공제는 기본공제 받은 아내 쪽에 붙는다
    assert p.wife.child_credit.age8plus_count == 1 and p.husband.child_credit.total == 0
    # 교육비는 기본공제 받은 쪽이 낸 것만 공제(PR 6 [기획 확인] 2번, p389·p181).
    # 남편이 낸 큰아이 교육비는 아내가 기본공제 받으면 아무도 공제받지 못한다
    assert p.wife.education.amount == 0 and p.husband.education.amount == 0
    assert [(d.kind, d.payer, d.rule_id) for d in p.dropped] == [
        ("education", "husband", "2025.education.couple_rule")
    ]
    q = evaluate(SIMILAR_WITH_KIDS, {"큰아이": "husband", "작은아이": "wife"}, rules)
    assert q.husband.education.base_children == 600_000 and not q.dropped


def test_cards_follow_user_not_payer(rules):
    book = Rulebook(rules)
    workers, dropped = to_workers(CARD_NEAR_THRESHOLD, {"중학생": "wife"}, book)
    wife = [(c.user, c.credit, c.cash_debit) for c in workers["wife"].card_usage]
    # 남편 명의 가족카드를 아내가 쓴 200만원은 아내, 자녀 카드는 자녀를 공제받는 아내
    assert ("self", 2_000_000, 0) in wife and ("child", 0, 3_000_000) in wife
    assert [c.credit for c in workers["husband"].card_usage] == [15_500_000]
    assert not dropped


def test_spouse_expenses_with_income(rules):
    house = SIMILAR_WITH_KIDS.model_copy(
        update={
            "medical": (MedicalSpend(payer="husband", for_whom="wife", amount=3_000_000),),
            "education": (EducationSpend(payer="husband", for_whom="wife", amount=1_000_000),),
        }
    )
    p = evaluate(house, {"큰아이": "husband", "작은아이": "husband"}, rules)
    # 소득이 있는 배우자 의료비는 낸 사람(남편)이 공제, 교육비는 공제 안 됨
    assert p.husband.medical.amount > 0
    assert [(d.kind, d.rule_id) for d in p.dropped] == [
        ("education", "2025.education.excluded_persons")
    ]
    # 배우자 줄은 소득요건을 넘어 인적공제가 없다
    assert p.husband.personal.basic_count == 3


def test_not_dual_income_is_warned(rules):
    house = Household(husband=earner(50_000_000, "male"), wife=earner(4_000_000, "female"))
    r = compare_allocations(house, rules)
    assert [w.code for w in r.warnings] == ["not_dual_income"]
    assert r.warnings[0].rule_ids == ("2025.dependent.basic",)
    assert r.plan_count == 1


def test_ineligible_member_is_not_a_candidate(rules):
    # 소득요건을 넘는 부모는 고르는 대상이 아니다
    working = parent("일하는아버지", 1955, "wife", income=5_000_000)
    house = WIDE_GAP_PARENTS.model_copy(update={"members": (*WIDE_GAP_PARENTS.members, working)})
    r = compare_allocations(house, rules)
    assert r.plan_count == 4
    assert all("일하는아버지" not in p.assignment for p in r.plans)
