"""기본세율 8구간 경계(바로 아래·같음·바로 위)."""

import math

import pytest

from taxsplit.engine.income import computed_tax


def _cuts(rules):
    rows = rules["2025.base.tax_rate"].value["brackets"]
    return list(zip(rows, rows[1:], strict=False))


@pytest.mark.parametrize("i", range(7))
def test_bracket_boundaries(rules, book, i):
    prev, nxt = _cuts(rules)[i]
    over = nxt["over"]
    assert computed_tax(over, book) == nxt["base"]
    below = prev["base"] + (over - 1 - prev["over"]) * prev["rate"]
    assert computed_tax(over - 1, book) == math.floor(below)
    assert computed_tax(over + 1, book) == math.floor(nxt["base"] + nxt["rate"])


def test_zero(book):
    assert computed_tax(0, book) == 0


def test_tax_rate_is_sourced(rules):
    rule = rules["2025.base.tax_rate"]
    assert rule.status == "sourced"
    assert rule.statute == "소법 §55 ①"
