"""기본공제 요건(나이·소득·판정일)과 추가공제(경로우대·장애인·부녀자·한부모)."""

from datetime import date

import pytest

from taxsplit.engine import Dependent, SelfInfo, basic_eligibility, is_spouse_with_income
from taxsplit.engine.personal import judgment_date, personal_deduction


def _dep(relation="child", age=10, **kw):
    return Dependent(name="d", relation=relation, birth_year=2025 - age, **kw)


@pytest.fixture
def basic(rules):
    return rules["2025.dependent.basic"].value


def test_child_age_boundary(book, basic):
    top = basic["lineal_descendant_max_age"]
    assert basic_eligibility(_dep(age=top), book)[0]
    assert not basic_eligibility(_dep(age=top + 1), book)[0]


def test_ascendant_age_boundary(book, basic):
    low = basic["lineal_ascendant_min_age"]
    assert basic_eligibility(_dep("lineal_ascendant", low), book)[0]
    assert not basic_eligibility(_dep("lineal_ascendant", low - 1), book)[0]


def test_sibling_age_boundaries(book, basic):
    young, old = basic["sibling_max_age"], basic["sibling_min_age"]
    assert basic_eligibility(_dep("sibling", young), book)[0]
    assert not basic_eligibility(_dep("sibling", young + 1), book)[0]
    assert not basic_eligibility(_dep("sibling", old - 1), book)[0]
    assert basic_eligibility(_dep("sibling", old), book)[0]


def test_disabled_has_no_age_limit(book, basic):
    assert basic_eligibility(
        _dep(age=basic["lineal_descendant_max_age"] + 10, disabled=True), book
    )[0]


def test_income_boundary(book, basic):
    limit = basic["income_limit"]
    assert basic_eligibility(_dep(income_amount=limit), book)[0]
    assert basic_eligibility(_dep(income_amount=limit + 1), book) == (False, "소득요건 초과")


def test_wage_only_gross_boundary(book, basic):
    limit = basic["wage_only_gross_limit"]
    assert basic_eligibility(_dep(wage_only_gross=limit), book)[0]
    assert not basic_eligibility(_dep(wage_only_gross=limit + 1), book)[0]


def test_spouse_with_income(book, basic):
    # 소득이 있는 배우자 = 기본공제 소득요건을 넘는 배우자(p389, p180)
    assert is_spouse_with_income(_dep("spouse", 40, income_amount=basic["income_limit"] + 1), book)
    assert not is_spouse_with_income(_dep("spouse", 40, income_amount=basic["income_limit"]), book)
    over = basic["wage_only_gross_limit"] + 1
    assert is_spouse_with_income(_dep("spouse", 40, wage_only_gross=over), book)
    assert not is_spouse_with_income(_dep("child", 10, income_amount=10**8), book)


def test_judgment_date_dec31_and_day_before_death(book):
    assert judgment_date(_dep(), book) == date(2025, 12, 31)
    assert judgment_date(_dep(death_date=date(2025, 10, 30)), book) == date(2025, 10, 29)


def test_relation_must_exist_on_judgment_date(book):
    assert basic_eligibility(_dep("spouse", 30, relation_start=date(2025, 12, 31)), book)[0]
    assert not basic_eligibility(_dep("spouse", 30, relation_start=date(2026, 1, 1)), book)[0]


def test_elderly_and_disabled_additional(rules, book, make_worker):
    elderly = rules["2025.dependent.additional.elderly"].value
    disabled = rules["2025.dependent.additional.disabled"].value["amount"]
    deps = (
        _dep("lineal_ascendant", elderly["min_age"]),
        _dep("lineal_ascendant", elderly["min_age"] - 1),
        _dep("child", 30, disabled=True),
    )
    p = personal_deduction(make_worker(dependents=deps), 0, book)
    assert (p.elderly_count, p.elderly) == (1, elderly["amount"])
    assert (p.disabled_count, p.disabled) == (1, disabled)
    assert p.basic_count == 4
    assert p.total == p.basic_total + p.elderly + p.disabled


def test_ineligible_dependent_gets_no_additional(book, make_worker):
    p = personal_deduction(
        make_worker(dependents=(_dep("lineal_ascendant", 80, income_amount=10**8),)), 0, book
    )
    assert (p.basic_count, p.elderly_count) == (1, 0)


def test_woman_deduction_income_boundary(rules, book, make_worker):
    v = rules["2025.dependent.additional.woman"].value
    me = SelfInfo(sex="female", birth_year=1985, has_spouse=True)
    w = make_worker(person=me)
    assert personal_deduction(w, v["income_limit"], book).woman == v["amount"]
    assert personal_deduction(w, v["income_limit"] + 1, book).woman == 0


def test_woman_single_head_of_household(rules, book, make_worker):
    v = rules["2025.dependent.additional.woman"].value
    me = SelfInfo(sex="female", birth_year=1985, has_spouse=False, head_of_household=True)
    parent = _dep("lineal_ascendant", 65)
    assert (
        personal_deduction(make_worker(person=me, dependents=(parent,)), 0, book).woman
        == v["amount"]
    )
    assert personal_deduction(make_worker(person=me), 0, book).woman == 0


def test_single_parent_wins_over_woman(rules, book, make_worker):
    me = SelfInfo(sex="female", birth_year=1985, has_spouse=False, head_of_household=True)
    p = personal_deduction(make_worker(person=me, dependents=(_dep("child", 5),)), 0, book)
    assert p.single_parent == rules["2025.dependent.additional.single_parent"].value["amount"]
    assert p.woman == 0
