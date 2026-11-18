"""의료비 세액공제: 총급여 3% 문턱, 문턱 빼는 순서, ㉣ 700만원 한도, 세부 한도, 대상 나눔.

경계값은 사례가 아니라 규칙표에서 읽는다(바로 아래·같음·바로 위).
"""

from decimal import Decimal

import pytest

from taxsplit.engine import Dependent, MedicalExpense, Rulebook
from taxsplit.engine.medical import medical_credit

GROSS = 40_000_000


def _v(rules, name):
    return rules[f"2025.medical.{name}"].value


def _threshold(rules, gross=GROSS):
    return int(gross * Decimal(_v(rules, "threshold")["gross_rate"]))


def _others_age(rules):
    # 한도 없는 나이(65세 이상·6세 이하) 사이에 있는 "그 외 부양가족" 나이
    lim = _v(rules, "limit.others")
    return lim["age_6_or_under_max_age"] + 1


@pytest.fixture
def run(rules, make_worker):
    def go(*expenses, deps=(), gross=GROSS):
        w = make_worker(gross, dependents=deps, medical=expenses)
        book = Rulebook(rules)
        return medical_credit(w, book), book

    return go


@pytest.fixture
def parent(rules):
    return Dependent(name="p", relation="lineal_ascendant", birth_year=2025 - _others_age(rules))


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_threshold_boundary(rules, run, parent, delta):
    # 그 외 부양가족 의료비가 총급여 3%보다 1원 적음·같음·1원 많음
    t = _threshold(rules)
    m, _ = run(MedicalExpense(for_name="p", amount=t + delta), deps=(parent,))
    assert m.threshold == t
    assert m.base_others == max(0, delta)
    assert m.amount == int(max(0, delta) * Decimal(_v(rules, "rate")["general"]))


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_others_limit_boundary(rules, run, parent, delta):
    # ㉣는 문턱을 뺀 뒤 700만원 한도
    limit = _v(rules, "limit.others")["limit"]
    m, _ = run(
        MedicalExpense(for_name="p", amount=_threshold(rules) + limit + delta), deps=(parent,)
    )
    assert m.base_others == min(limit, limit + delta)


def test_threshold_taken_from_others_first_then_self(rules, run, parent):
    # 그 외 부양가족 의료비가 문턱보다 적으면 나머지를 본인 의료비에서 뺀다
    t = _threshold(rules)
    m, book = run(
        MedicalExpense(for_name="p", amount=t // 3),
        MedicalExpense(amount=5_000_000),
        deps=(parent,),
    )
    assert m.base_others == 0
    assert m.base_special == 5_000_000 - (t - t // 3)
    assert "2025.medical.threshold_order" in book.rules_used()["medical_credit"]


def test_threshold_then_premature_then_infertility(rules, run):
    # ㉣·㉢가 없으면 ㉡(미숙아) → ㉠(난임) 순서로 뺀다
    t = _threshold(rules)
    m, _ = run(
        MedicalExpense(item="infertility", amount=t),
        MedicalExpense(item="premature_congenital", amount=t // 2),
    )
    assert (m.base_premature, m.base_infertility) == (0, t // 2)
    assert m.amount == int((t // 2) * Decimal(_v(rules, "rate")["infertility"]))


def test_rates_by_bucket(rules, run):
    # 문턱이 0원(총급여 0)이면 공제액 = ㉢×15% + ㉡×20% + ㉠×30%
    r = _v(rules, "rate")
    m, _ = run(
        MedicalExpense(amount=1_000_000),
        MedicalExpense(item="premature_congenital", amount=1_000_000),
        MedicalExpense(item="infertility", amount=1_000_000),
        gross=0,
    )
    expected = 1_000_000 * sum(
        Decimal(r[k]) for k in ("general", "premature_congenital", "infertility")
    )
    assert m.amount == int(expected)
    assert m.base == 3_000_000


@pytest.mark.parametrize(
    ("age_key", "offset", "bucket"),
    [
        ("age_65_plus_min_age", 0, "special"),
        ("age_65_plus_min_age", -1, "others"),
        ("age_6_or_under_max_age", 0, "special"),
        ("age_6_or_under_max_age", 1, "others"),
    ],
)
def test_age_decides_unlimited_bucket(rules, run, age_key, offset, bucket):
    age = _v(rules, "limit.others")[age_key] + offset
    dep = Dependent(name="d", relation="child", birth_year=2025 - age)
    m, _ = run(MedicalExpense(for_name="d", amount=1_000_000), deps=(dep,), gross=0)
    assert getattr(m, f"base_{bucket}") == 1_000_000


def test_disabled_dependent_is_unlimited(rules, run):
    dep = Dependent(name="d", relation="sibling", birth_year=1990, disabled=True)
    m, _ = run(MedicalExpense(for_name="d", amount=1_000_000), deps=(dep,), gross=0)
    assert m.base_special == 1_000_000


def test_spouse_with_income_expense_counts_for_payer(rules, run):
    # 소득이 있는 배우자를 위해 낸 의료비는 낸 사람이 공제한다(p389). 배우자는 ㉣
    spouse = Dependent(name="s", relation="spouse", birth_year=1985, income_amount=10**7)
    m, _ = run(MedicalExpense(for_name="s", amount=1_000_000), deps=(spouse,), gross=0)
    assert m.base_others == 1_000_000


def test_sublimits_glasses_and_postnatal(rules, run):
    sub = _v(rules, "sublimit")
    m, book = run(
        MedicalExpense(item="glasses", amount=sub["glasses_per_person"] // 2),
        MedicalExpense(item="glasses", amount=sub["glasses_per_person"]),
        MedicalExpense(item="postnatal_care", amount=sub["postnatal_care_per_birth"] + 1),
        gross=0,
    )
    assert m.base_special == sub["glasses_per_person"] + sub["postnatal_care_per_birth"]
    # 세부 한도는 값이 있는 todo라 "확인 필요"에 오른다
    assert "2025.medical.sublimit" in book.needs_check


def test_unknown_dependent_name_fails(run):
    with pytest.raises(ValueError, match="부양가족 목록에 없는"):
        run(MedicalExpense(for_name="없는사람", amount=1))


def test_no_expense_is_zero(run):
    m, book = run()
    assert m.amount == 0 and book.rules_used() == {}
