"""근로소득세액공제·한도 경계, 자녀세액공제 인원·출산 순서."""

import math

import pytest

from taxsplit.engine import Dependent
from taxsplit.engine.credits import child_tax_credit, earned_income_tax_credit

LOW_GROSS = 10_000  # 한도가 첫 구간(74만원)인 낮은 총급여


def test_credit_bracket_boundary(rules, book):
    prev, nxt = rules["2025.base.earned_income_tax_credit"].value["brackets"]
    over = nxt["over"]
    assert earned_income_tax_credit(over, LOW_GROSS, book).before_limit == nxt["base"]
    below = math.floor((over - 1) * prev["rate"])
    assert earned_income_tax_credit(over - 1, LOW_GROSS, book).before_limit == below
    above = math.floor(nxt["base"] + nxt["rate"])
    assert earned_income_tax_credit(over + 1, LOW_GROSS, book).before_limit == above


def _limit_by_table(seg, gross):
    return math.floor(max(seg["floor"], seg["base"] - (gross - seg["over"]) * seg["slope"]))


@pytest.mark.parametrize("i", range(3))
def test_limit_segment_boundaries(rules, book, i):
    segs = rules["2025.base.earned_income_tax_credit.limit"].value["segments"]
    prev, nxt = segs[i], segs[i + 1]
    over = nxt["over"]
    assert earned_income_tax_credit(0, over, book).limit == nxt["base"]
    assert earned_income_tax_credit(0, over - 1, book).limit == _limit_by_table(prev, over - 1)
    assert earned_income_tax_credit(0, over + 1, book).limit == _limit_by_table(nxt, over + 1)


def test_limit_floor_far_above(rules, book):
    segs = rules["2025.base.earned_income_tax_credit.limit"].value["segments"]
    assert earned_income_tax_credit(0, 10**10, book).limit == segs[-1]["floor"]


def test_credit_is_min_of_amount_and_limit(book):
    c = earned_income_tax_credit(10_000_000, 60_000_000, book)
    assert c.amount == min(c.before_limit, c.limit) == c.limit


def _kids(*ages, births=()):
    kids = [
        Dependent(name=f"k{i}", relation="child", birth_year=2025 - a) for i, a in enumerate(ages)
    ]
    for order in births:
        kids.append(
            Dependent(
                name=f"b{order}", relation="child", birth_year=2025, birth_or_adoption_order=order
            )
        )
    return tuple(kids)


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4])
def test_child_credit_age8plus(rules, book, make_worker, n):
    v = rules["2025.child.credit.base"].value
    expected = {0: 0, 1: v["one"], 2: v["two"]}.get(
        n, v["two"] + (n - 2) * v["extra_per_child_over_two"]
    )
    c = child_tax_credit(make_worker(dependents=_kids(*[10] * n)), book)
    assert (c.age8plus_count, c.age8plus) == (n, expected)


def test_child_credit_min_age_boundary(rules, book, make_worker):
    min_age = rules["2025.child.credit.base"].value["min_age"]
    c = child_tax_credit(make_worker(dependents=_kids(min_age - 1, min_age)), book)
    assert c.age8plus_count == 1


def test_child_credit_birth_order(rules, book, make_worker):
    v = rules["2025.child.credit.birth"].value
    c = child_tax_credit(make_worker(dependents=_kids(births=(1, 2, 3, 4))), book)
    assert c.birth_count == 4
    assert c.birth == v["first"] + v["second"] + 2 * v["third_or_more"]
    assert c.total == c.age8plus + c.birth


def test_ineligible_child_gets_no_credit(book, make_worker):
    rich = Dependent(name="k", relation="child", birth_year=2010, income_amount=5_000_000)
    assert child_tax_credit(make_worker(dependents=(rich,)), book).total == 0
