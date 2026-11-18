"""홈택스 사례(confirmed)의 가구별 두 배분안을 배분 비교에 넣어 사례와 맞춰 본다(PR 6).

- 안별 부부 합계 결정세액이 사례와 같은가
- 가구마다 "어느 안이 적은가"가 사례와 같은가
- 기본공제 받지 않은 쪽이 낸 부양가족 의료비는 공제 0인가(가구 2 배분안 B 아내)
"""

from collections import defaultdict

import pytest

from cases.case_household import hometax_plans

PLANS = hometax_plans()


def _by_household():
    out = defaultdict(list)
    for p in PLANS:
        out[p.household].append(p)
    return dict(out)


def test_has_two_plans_per_household():
    groups = _by_household()
    assert groups and all(len(v) == 2 for v in groups.values())


@pytest.mark.parametrize("p", PLANS, ids=lambda p: p.case_id)
def test_plan_total_matches_case(p):
    assert p.result.husband_tax == p.expected["husband"]
    assert p.result.wife_tax == p.expected["wife"]
    assert p.result.total == sum(p.expected.values())


@pytest.mark.parametrize("household", sorted(_by_household()))
def test_cheaper_plan_matches_case(household):
    plans = _by_household()[household]
    expected = min(plans, key=lambda p: sum(p.expected.values())).plan
    actual = min(plans, key=lambda p: p.result.total).plan
    assert actual == expected


def test_medical_paid_by_non_claimant_is_zero():
    # 사례 중 "낸 사람 ≠ 기본공제 받은 사람"인 줄(not_run)이 있는 안: 그 사람 의료비 공제 0
    (p,) = [p for p in PLANS if p.not_run]
    for who in p.not_run:
        tax = getattr(p.result, who)
        assert tax.medical.amount == 0
        assert any(
            d.payer == who and d.rule_id == "2025.medical.couple_rule" for d in p.result.dropped
        )
