"""결과에 나오는 규칙 ID(안마다 쓴 규칙, 공제 안 됨 근거, 경고 근거)가 모두 규칙표에 있다."""

import pytest

from allocation.households import HOUSEHOLDS
from allocation.test_checks import CATCH
from taxsplit.allocation import check_claims, compare_allocations


@pytest.mark.parametrize("name", HOUSEHOLDS)
def test_plan_rule_ids_exist(name, rules):
    r = compare_allocations(HOUSEHOLDS[name], rules)
    for p in r.plans:
        ids = set(p.rule_ids) | {d.rule_id for d in p.dropped}
        assert ids and ids <= set(rules), ids - set(rules)
        # 배분 규칙(맞벌이 의료비·카드 사용자 기준)은 모든 안에 적힌다
        assert {"2025.medical.couple_rule", "2025.card.user_basis"} <= set(p.rule_ids)


def test_warning_rule_ids_exist(rules):
    for house, claims, _, _ in CATCH.values():
        for w in check_claims(house, claims, rules):
            assert set(w.rule_ids) <= set(rules)
