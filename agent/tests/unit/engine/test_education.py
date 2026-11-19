"""교육비 세액공제: 과정별 한도, 세부 한도, 공제 안 되는 사람·과정. 경계값은 규칙표에서 읽는다."""

from decimal import Decimal

import pytest

from taxsplit.engine import Dependent, EducationExpense, Rulebook
from taxsplit.engine.education import education_credit


def _v(rules, name):
    return rules[f"2025.education.{name}"].value


@pytest.fixture
def run(rules, make_worker):
    def go(*expenses, deps=()):
        w = make_worker(50_000_000, dependents=deps, education=expenses)
        book = Rulebook(rules)
        return education_credit(w, book), book

    return go


CHILD = Dependent(name="c", relation="child", birth_year=2010)


@pytest.mark.parametrize("level", ["preschool", "school", "university"])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_level_limit_boundary(rules, run, level, delta):
    limit = _v(rules, "limit")[level]
    e, _ = run(EducationExpense(for_name="c", level=level, amount=limit + delta), deps=(CHILD,))
    assert e.base_children == min(limit, limit + delta)
    assert e.amount == int(e.base * Decimal(_v(rules, "rate")["rate"]))


def test_self_has_no_limit_and_graduate_ok(rules, run):
    big = _v(rules, "limit")["university"] * 3
    e, _ = run(EducationExpense(level="graduate", amount=big))
    assert e.base_self == big


def test_graduate_of_dependent_excluded(run):
    sib = Dependent(name="s", relation="sibling", birth_year=1999)
    e, book = run(EducationExpense(for_name="s", level="graduate", amount=5_000_000), deps=(sib,))
    assert e.base == 0
    assert "2025.education.graduate_self_only" in book.rules_used()["education_credit"]


@pytest.mark.parametrize("over", [0, 1])
def test_spouse_with_income_excluded(rules, run, over):
    # 소득이 있는 배우자 = 연 소득금액 100만원 초과(기본공제 소득요건, p389·p180)
    income = rules["2025.dependent.basic"].value["income_limit"] + over
    spouse = Dependent(name="s", relation="spouse", birth_year=1985, income_amount=income)
    e, _ = run(EducationExpense(for_name="s", level="university", amount=1_000_000), deps=(spouse,))
    assert e.base == (0 if over else 1_000_000)


def test_lineal_ascendant_excluded_except_special_education(run):
    parent = Dependent(name="p", relation="lineal_ascendant", birth_year=1950, disabled=True)
    e, _ = run(
        EducationExpense(for_name="p", level="university", amount=1_000_000),
        EducationExpense(for_name="p", item="disabled_special_education", amount=2_000_000),
        deps=(parent,),
    )
    # 장애인특수교육비는 한도 없이 공제
    assert e.base == 2_000_000 and e.base_others == 2_000_000


def test_field_trip_and_uniform_sublimits(rules, run):
    sub = _v(rules, "sublimit")
    e, _ = run(
        EducationExpense(for_name="c", item="field_trip", amount=sub["field_trip_per_year"] + 1),
        EducationExpense(
            for_name="c", item="uniform", amount=sub["uniform_middle_high_per_year"] + 1
        ),
        deps=(CHILD,),
    )
    assert e.base == sub["field_trip_per_year"] + sub["uniform_middle_high_per_year"]


def test_sublimit_then_level_limit(rules, run):
    # 세부 한도를 먼저 걸고, 그 합계에 과정 한도(초중고 300만원)를 건다
    limit = _v(rules, "limit")["school"]
    e, _ = run(
        EducationExpense(for_name="c", amount=limit - 100_000),
        EducationExpense(for_name="c", item="field_trip", amount=1_000_000),
        deps=(CHILD,),
    )
    assert e.base == limit


def test_relation_groups(run):
    sib = Dependent(name="s", relation="sibling", birth_year=2000)
    e, _ = run(
        EducationExpense(amount=1_000_000),
        EducationExpense(for_name="c", amount=2_000_000),
        EducationExpense(for_name="s", level="university", amount=3_000_000),
        deps=(CHILD, sib),
    )
    assert (e.base_self, e.base_children, e.base_siblings, e.base_others) == (
        1_000_000,
        2_000_000,
        3_000_000,
        0,
    )
