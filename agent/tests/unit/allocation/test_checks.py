"""중복공제 검사: "잡을 것" 5종은 각각 잡히고, "잡으면 안 되는 것" 3종은 경고 없이 지나간다."""

import pytest

from allocation.households import CARD_NEAR_THRESHOLD, SIMILAR_WITH_KIDS, WIDE_GAP_PARENTS
from taxsplit.allocation import Claim, check_claims, compare_allocations


def C(who, kind, target, amount=0):  # noqa: N802 - 표를 짧게 쓰려는 이름
    return Claim(who=who, kind=kind, target=target, amount=amount)


# 종류 이름 → (가구, 신청 목록, 잡혀야 할 경고 코드, 근거 규칙 ID)
CATCH = {
    "같은 부양가족을 둘 다 기본공제": (
        SIMILAR_WITH_KIDS,
        (C("husband", "basic", "큰아이"), C("wife", "basic", "큰아이")),
        "double_basic",
        "2025.dependent.double_claim",
    ),
    "맞벌이 배우자를 상대가 기본공제": (
        SIMILAR_WITH_KIDS,
        (C("husband", "basic", "wife"),),
        "spouse_basic",
        "2025.dependent.basic",
    ),
    "같은 의료비를 둘 다 입력": (
        SIMILAR_WITH_KIDS,
        (
            C("wife", "basic", "작은아이"),
            C("wife", "medical", "작은아이", 2_500_000),
            C("husband", "medical", "작은아이", 2_500_000),
        ),
        "double_expense",
        "2025.dependent.double_claim",
    ),
    "자녀세액공제를 기본공제 안 받은 쪽이 신청": (
        SIMILAR_WITH_KIDS,
        (C("husband", "basic", "큰아이"), C("wife", "child_credit", "큰아이")),
        "credit_without_basic",
        "2025.dependent.additional.claimant",
    ),
    "추가공제를 기본공제 안 받은 쪽이 신청": (
        WIDE_GAP_PARENTS,
        (C("husband", "basic", "남편아버지"), C("wife", "additional", "남편아버지")),
        "credit_without_basic",
        "2025.dependent.additional.claimant",
    ),
    "기본공제 안 받은 쪽이 낸 부양가족 의료비": (
        WIDE_GAP_PARENTS,
        (C("husband", "basic", "아내어머니"), C("wife", "medical", "아내어머니", 3_000_000)),
        "medical_not_claimant",
        "2025.medical.couple_rule",
    ),
}

# 종류 이름 → (가구, 신청 목록)
PASS = {
    "자녀 둘을 하나씩 나눠 공제": (
        SIMILAR_WITH_KIDS,
        (
            C("husband", "basic", "큰아이"),
            C("husband", "child_credit", "큰아이"),
            C("husband", "education", "큰아이", 600_000),
            C("wife", "basic", "작은아이"),
            C("wife", "medical", "작은아이", 2_500_000),
        ),
    ),
    "각자 카드·가족카드를 쓴 사람 기준으로": (
        CARD_NEAR_THRESHOLD,
        (
            C("husband", "card", "husband", 15_500_000),
            C("wife", "card", "wife", 10_500_000),
            C("wife", "card", "wife", 2_000_000),
            C("wife", "basic", "중학생"),
            C("wife", "card", "중학생", 3_000_000),
        ),
    ),
    "소득 있는 배우자 의료비를 낸 사람이 공제": (
        SIMILAR_WITH_KIDS,
        (C("husband", "medical", "wife", 3_000_000), C("wife", "medical", "wife", 500_000)),
    ),
}


@pytest.mark.parametrize("kind", CATCH)
def test_catches(kind, rules):
    house, claims, code, rule_id = CATCH[kind]
    warnings = check_claims(house, claims, rules)
    hit = [w for w in warnings if w.code == code]
    assert hit, warnings
    assert rule_id in hit[0].rule_ids


@pytest.mark.parametrize("kind", PASS)
def test_passes_without_warning(kind, rules):
    house, claims = PASS[kind]
    assert check_claims(house, claims, rules) == ()


def test_child_credit_warning_also_cites_child_credit_rule(rules):
    (_, claims, _, _) = CATCH["자녀세액공제를 기본공제 안 받은 쪽이 신청"]
    (w,) = check_claims(SIMILAR_WITH_KIDS, claims, rules)
    assert w.rule_ids == ("2025.dependent.additional.claimant", "2025.child.credit.base")


def test_compare_runs_checks_when_claims_given(rules):
    house, claims, code, _ = CATCH["같은 부양가족을 둘 다 기본공제"]
    r = compare_allocations(house, rules, claims=claims)
    assert [w.code for w in r.warnings] == [code]
