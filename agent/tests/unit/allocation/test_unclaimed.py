"""아무도 기본공제 받지 않는 가족의 지출.

PR 6 [기획 확인] 1번·덧붙임, Issue #15 정해진 결정(2026-11-19).

- 의료비·교육비는 버리지 않고 낸 사람이 공제한다(교육비는 대상 관계·소득요건을 본다).
- 카드는 소득요건 안의 배우자·직계존비속이면 남편 쪽·아내 쪽을 모두 계산해 합계가 작은 쪽.
"""

import pytest

from allocation.households import NOBODY_CLAIMS, child, parent
from taxsplit.allocation import (
    CardSpend,
    EducationSpend,
    MedicalSpend,
    compare_allocations,
    evaluate,
)
from taxsplit.allocation.assign import to_workers
from taxsplit.allocation.compare import _evaluate
from taxsplit.allocation.models import Member
from taxsplit.engine import Dependent, Rulebook

NOTE = "문서가 정하지 않은 해석(인쇄 134쪽 '포함할 수 있음')"


def _with(**update):
    return NOBODY_CLAIMS.model_copy(update=update)


def test_nobody_can_claim_so_one_plan(rules):
    assert compare_allocations(NOBODY_CLAIMS, rules).plan_count == 1


def test_payer_gets_medical_and_education_of_unclaimed_family(rules):
    p = evaluate(NOBODY_CLAIMS, {}, rules)
    assert not p.dropped
    # 의료비: 500만원 − 남편 총급여 3%(180만원) = 320만원 × 15%
    assert (p.husband.medical.base, p.husband.medical.amount) == (3_200_000, 480_000)
    # 교육비: 대학 등록금 800만원(대학 한도 900만원 안) × 15%
    assert (p.husband.education.base_children, p.husband.education.amount) == (8_000_000, 1_200_000)
    # 인적공제·자녀세액공제는 없다(요건이 안 되는 부양가족 줄)
    assert p.husband.personal.basic_count == 1 and p.husband.child_credit.total == 0
    assert {"2025.medical.no_claimant_payer"} <= set(p.rule_ids)
    # 같은 가구에서 두 지출을 빼면 남편 결정세액이 두 세액공제만큼 크다
    bare = evaluate(_with(medical=(), education=()), {}, rules)
    assert bare.husband_tax - p.husband_tax == 480_000 + 1_200_000


def test_parent_with_income_medical_is_still_deducted_by_payer(rules):
    # 의료비는 소득 제한도 없다: 소득이 있는 아버지 의료비를 낸 아내가 공제
    father = parent("일하는아버지", 1955, "wife", income=5_000_000)
    house = _with(
        members=(*NOBODY_CLAIMS.members, father),
        medical=(MedicalSpend(payer="wife", for_whom="일하는아버지", amount=3_000_000),),
    )
    p = evaluate(house, {}, rules)
    assert p.wife.medical.amount > 0 and not p.dropped


@pytest.mark.parametrize(
    ("member", "reason"),
    [
        (parent("어머니", 1968, "husband"), "직계존속 교육비"),
        (
            Member(
                dependent=Dependent(
                    name="대학생", relation="child", birth_year=2003, income_amount=2_000_000
                )
            ),
            "소득요건 초과",
        ),
    ],
    ids=lambda x: x if isinstance(x, str) else "",
)
def test_education_needs_relation_and_income(member, reason, rules):
    edu = EducationSpend(payer="husband", for_whom=member.name, level="university", amount=1_000)
    others = tuple(m for m in NOBODY_CLAIMS.members if m.name != member.name)
    house = _with(members=(*others, member), medical=(), education=(edu,))
    (d,) = evaluate(house, {}, rules).dropped
    assert (d.kind, d.rule_id) == ("education", "2025.education.no_claimant_payer"), reason


def test_unclaimed_family_card_goes_to_cheaper_side_with_note(rules):
    card = CardSpend(user="대학생", payer="husband", credit=6_000_000)
    house = _with(cards=(*NOBODY_CLAIMS.cards, card))
    both = {who: _evaluate(house, {}, {"대학생": who}, rules) for who in ("husband", "wife")}
    p = evaluate(house, {}, rules)
    # 두 쪽을 모두 계산해 부부 결정세액 합이 작은 쪽(같으면 남편)
    cheaper = min(("husband", "wife"), key=lambda w: both[w].total)
    assert p.card_sides == {"대학생": cheaper} and p.total == both[cheaper].total
    assert all(p.total <= q.total for q in both.values())
    (note,) = p.notes
    assert note.code == "card_unclaimed_family" and NOTE in note.message
    assert note.rule_ids == ("2025.card.no_claimant_family",)
    r = compare_allocations(house, rules)
    assert note in r.warnings


def test_card_of_sibling_or_over_income_family_is_dropped(rules):
    sibling = Member(dependent=Dependent(name="동생", relation="sibling", birth_year=1990))
    rich = parent("부자아버지", 1950, "wife", income=5_000_000)
    house = _with(
        members=(*NOBODY_CLAIMS.members, sibling, rich),
        cards=(
            CardSpend(user="동생", credit=1_000_000),
            CardSpend(user="부자아버지", credit=2_000_000),
        ),
    )
    p = evaluate(house, {}, rules)
    assert p.card_sides == {}
    assert sorted((d.for_whom, d.rule_id) for d in p.dropped) == [
        ("동생", "2025.card.user_basis"),
        ("부자아버지", "2025.card.no_claimant_family"),
    ]


def test_claimed_child_card_still_follows_claimant(rules):
    # 기본공제 받는 가족의 카드는 지금처럼 그 사람 쪽(고르지 않음)
    kid = child("초등학생", 2016)
    house = _with(
        members=(*NOBODY_CLAIMS.members, kid), cards=(CardSpend(user="초등학생", credit=1),)
    )
    assert evaluate(house, {"초등학생": "wife"}, rules).card_sides == {}
    workers, _ = to_workers(house, {"초등학생": "wife"}, Rulebook(rules))
    assert [c.user for c in workers["wife"].card_usage] == ["child"]
    assert workers["husband"].card_usage == ()
