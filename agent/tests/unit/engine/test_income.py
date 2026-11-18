"""근로소득공제 구간 경계(바로 아래·같음·바로 위)와 한도 2,000만원."""

import math

import pytest

from taxsplit.engine.income import earned_income_deduction


def _cuts(rules):
    rows = rules["2025.base.earned_income_deduction"].value["brackets"]
    return list(zip(rows, rows[1:], strict=False))


@pytest.mark.parametrize("i", range(4))
def test_bracket_boundaries(rules, book, i):
    prev, nxt = _cuts(rules)[i]
    over = nxt["over"]
    # 같음: 앞 구간을 끝까지 채운 값 = 다음 구간 base
    assert earned_income_deduction(over, book) == nxt["base"]
    # 바로 아래: 앞 구간 식, 바로 위: 다음 구간 식(원 미만 버림)
    below = prev["base"] + (over - 1 - prev["over"]) * prev["rate"]
    assert earned_income_deduction(over - 1, book) == math.floor(below)
    assert earned_income_deduction(over + 1, book) == math.floor(nxt["base"] + nxt["rate"])


def test_zero_and_first_won(book):
    assert earned_income_deduction(0, book) == 0
    assert earned_income_deduction(1, book) == 0  # 0.7원 → 원 미만 버림


def test_limit(rules, book):
    v = rules["2025.base.earned_income_deduction"].value
    last = v["brackets"][-1]
    # 마지막 구간 식이 한도에 닿는 총급여
    at_limit = last["over"] + int((v["limit"] - last["base"]) / last["rate"])
    assert earned_income_deduction(at_limit, book) == v["limit"]
    assert earned_income_deduction(at_limit - 100, book) < v["limit"]
    assert earned_income_deduction(at_limit + 1_000_000, book) == v["limit"]


def test_rule_ids_recorded(book):
    earned_income_deduction(30_000_000, book)
    assert book.rules_used()["earned_income_deduction"] == (
        "2025.base.earned_income_deduction",
        "2025.base.rounding",
    )
