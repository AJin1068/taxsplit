"""가구 생성기 테스트: 같은 시드 → 같은 가구, 범위 안, 요건 미달 부양가족이 섞임. 분포 표 출력."""

from property import report
from taxsplit.engine import Rulebook, basic_eligibility
from taxsplit.synth import make_household, make_households
from taxsplit.synth import ranges as R


def test_same_seed_same_household():
    assert make_household(42) == make_household(42)
    assert make_households(5, seed=7) == make_households(5, seed=7)


def test_different_seed_different_household():
    assert make_household(1) != make_household(2)


def test_household_seed_is_base_plus_index():
    # i번째 가구는 seed + i로 따로 다시 만들 수 있어야 한다(위반 가구 재현)
    many = make_households(3, seed=100)
    assert [hh.seed for hh in many] == [100, 101, 102]
    assert many[2] == make_household(102)


def test_values_within_ranges(households):
    for hh in households:
        assert len(hh.dependents) <= R.DEPENDENTS_MAX
        assert len(hh.claimants) == len(hh.dependents)
        for w in (hh.husband, hh.wife):
            assert R.GROSS_MIN <= w.gross_salary <= R.GROSS_MAX
            assert w.gross_salary % R.GROSS_UNIT == 0
            insurance = w.national_pension + w.health_insurance + w.employment_insurance
            assert insurance <= w.gross_salary * R.INSURANCE_GROSS_RATIO_MAX
            card = w.card_usage[0]
            spent = card.credit + card.cash_debit + card.market + card.transit
            spent += card.culture_credit + card.culture_cash_debit
            assert spent <= w.gross_salary * R.CARD_GROSS_RATIO_MAX
            assert all(m.amount <= R.MEDICAL_MAX for m in w.medical)


def test_dependents_go_to_their_claimant(households):
    # 부양가족과 그 의료비·교육비는 공제자 한 사람에게만 붙는다
    for hh in households:
        for dep, who in zip(hh.dependents, hh.claimants, strict=True):
            other = hh.wife if who == "husband" else hh.husband
            assert dep in hh.worker(who).dependents
            assert dep not in other.dependents
            assert all(m.for_name != dep.name for m in other.medical)


def test_mixes_ineligible_dependents(households, rules):
    """요건(나이·소득)에 안 맞는 부양가족이 섞여 엔진의 요건 판정을 지나간다."""
    book = Rulebook(rules)
    reasons = {basic_eligibility(d, book)[1] for hh in households for d in hh.dependents}
    assert "기본공제 대상" in reasons
    assert "소득요건 초과" in reasons
    assert "나이요건 미충족" in reasons


def test_distribution_table(households, rules):
    lines = report.distribution_table(households, rules)
    report.LINES.extend(lines)
    assert any("요건 미달 부양가족" in line for line in lines)
