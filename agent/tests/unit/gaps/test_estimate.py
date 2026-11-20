"""놓칠 금액 = 배분 비교를 직접 두 번 부른 차이(원 단위까지). 0원이면 "차이 없음"."""

import pytest

from gaps.helpers import household, parent
from taxsplit.allocation.compare import compare_allocations
from taxsplit.allocation.models import MedicalSpend
from taxsplit.gaps import ESTIMATE_OPTIONS, estimate_missing
from taxsplit.gaps.estimate import LABEL, NO_DIFFERENCE
from taxsplit.rules.loader import load_rules

RULES = load_rules(2025)
# 남편 본인 병원비 500만 원(문턱을 넘어 의료비 공제가 이미 잡히는 가구)
OWN = [{"payer": "husband", "for_whom": "husband", "amount": 5_000_000}]


def _direct(hh, person, amount, payer):
    """테스트가 배분 비교를 직접 두 번 부른다(넣기 전 / 넣은 뒤)."""
    without = compare_allocations(hh, RULES).best.total
    row = MedicalSpend(payer=payer, for_whom=person, amount=amount)
    with_ = compare_allocations(
        hh.model_copy(update={"medical": (*hh.medical, row)}), RULES
    ).best.total
    return without - with_


@pytest.mark.parametrize("option", ESTIMATE_OPTIONS, ids=lambda o: str(o.amount))
@pytest.mark.parametrize("payer", ["husband", "wife"])
@pytest.mark.parametrize("own", [(), OWN], ids=["no_medical", "own_medical"])
def test_estimate_equals_two_compare_calls(option, payer, own):
    hh = household(members=[parent(family_of="wife")], medical=list(own))
    est = estimate_missing(hh, "엄마", option.amount, RULES, payer)
    diff = _direct(hh, "엄마", option.amount, payer)
    assert est.label == LABEL and est.chosen_amount == option.amount and est.payer == payer
    if diff > 0:
        assert est.saving == diff and not est.no_difference
        assert f"{diff:,}원" in est.message
    else:
        assert est.saving is None and est.no_difference and est.message == NO_DIFFERENCE


@pytest.mark.parametrize("option", ESTIMATE_OPTIONS, ids=lambda o: str(o.amount))
def test_difference_when_medical_already_counts(option):
    # 남편 본인 병원비가 이미 문턱을 넘은 가구: 어머니 병원비를 넣으면 차이가 난다
    hh = household(members=[parent(family_of="husband")], medical=OWN)
    est = estimate_missing(hh, "엄마", option.amount, RULES)
    assert est.saving is not None and est.saving > 0
    assert est.saving == _direct(hh, "엄마", option.amount, "husband")


def test_zero_difference_says_no_difference():
    # 30만 원은 의료비 문턱을 못 넘어 차이가 없다. 금액 대신 "차이 없음", 더 쓰라는 말 없음
    hh = household(members=[parent(family_of="husband")])
    est = estimate_missing(hh, "엄마", 300_000, RULES)
    assert est.no_difference and est.saving is None
    assert est.message == "지금 자료로는 공제 차이가 없어요."
    assert "더 쓰" not in est.message and "늘" not in est.message


def test_default_payer_is_that_family_side():
    hh = household(members=[parent(family_of="wife")])
    assert estimate_missing(hh, "엄마", 300_000, RULES).payer == "wife"
