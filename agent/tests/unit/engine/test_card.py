"""신용카드 등 소득공제: 25% 문턱, 최저사용금액 채우는 순서, 7천만원 경계, 형제자매 제외,
소득공제 종합한도. 경계값은 규칙표에서 읽는다."""

from decimal import Decimal

import pytest

from taxsplit.engine import CardUsage, OutOfScopeItem, Rulebook, compute_tax
from taxsplit.engine.card import card_deduction

GROSS = 40_000_000


def _v(rules, name):
    return rules[f"2025.card.{name}"].value


def _min_spend(rules, gross=GROSS):
    return int(gross * Decimal(_v(rules, "threshold")["gross_rate"]))


@pytest.fixture
def run(rules, make_worker):
    def go(*uses, gross=GROSS):
        book = Rulebook(rules)
        return card_deduction(make_worker(gross, card_usage=uses), book), book

    return go


@pytest.mark.parametrize("delta", [-1, 0, 1, 1_000])
def test_threshold_boundary(rules, run, delta):
    # 현금·체크(30%)만 쓴 경우: 공제가능금액 = (사용액 − 총급여 25%) × 30%
    m = _min_spend(rules)
    c, _ = run(CardUsage(cash_debit=m + delta))
    rate = Decimal(_v(rules, "rate")["cash_debit"])
    assert c.minimum_spend == m
    assert c.before_limit == int((m + delta) * rate) - int(min(m, m + delta) * rate)
    assert c.before_limit == (int(delta * rate) if delta > 0 else 0)


def test_minimum_spend_filled_credit_first(rules, run):
    # 최저사용금액은 신용카드분부터 채우고, 모자라면 현금·체크분으로 채운다
    r = _v(rules, "rate")
    m = _min_spend(rules)
    c, book = run(CardUsage(credit=m // 2, cash_debit=m))
    expected = (m // 2) * Decimal(r["credit"]) + (m - m // 2) * Decimal(r["cash_debit"])
    assert c.minimum_spend_deduction == int(expected)
    assert "2025.card.min_usage_order" in book.rules_used()["card_deduction"]


def test_minimum_spend_reaches_market_transit(rules, run):
    r = _v(rules, "rate")
    m = _min_spend(rules)
    c, _ = run(CardUsage(credit=1_000_000, culture_cash_debit=1_000_000, market=m))
    rest = m - 2_000_000
    expected = (
        1_000_000 * Decimal(r["credit"])
        + 1_000_000 * Decimal(r["culture"])
        + rest * Decimal(r["market"])
    )
    assert c.minimum_spend_deduction == int(expected)


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_gross_70m_boundary_limit_and_culture(rules, run, delta):
    # 총급여 7천만원 이하: 기본 한도 300만원, 문화체육 30%
    # 초과: 기본 한도 250만원, 문화체육은 결제 수단(신용 15%)으로 돌림
    split = _v(rules, "limit")["gross_split"]
    assert split == _v(rules, "rate")["culture_gross_limit"]
    gross = split + delta
    c, book = run(CardUsage(credit=gross, culture_credit=1_000_000), gross=gross)
    above = delta > 0
    lim = _v(rules, "limit")
    r = _v(rules, "rate")
    culture = 1_000_000 * Decimal(r["credit" if above else "culture"])
    assert c.part_culture == (0 if above else int(culture))
    credit_use = gross + (1_000_000 if above else 0)
    assert c.part_credit == int(credit_use * Decimal(r["credit"]))
    # 한도 = 기본 한도 + 추가 한도(문화체육 몫, 7천만원 초과면 없음)
    base = lim["above"] if above else lim["at_or_below"]
    assert c.limit == base + c.part_culture
    assert c.amount == min(c.before_limit, c.limit)
    used = book.rules_used()["card_deduction"]
    assert ("2025.card.culture_over_limit" in used) == above


@pytest.mark.parametrize("delta", [0, 1])
def test_additional_limit_by_gross(rules, run, delta):
    # 전통시장 사용이 커서 추가 한도까지 차는 경우: 7천만원 이하 300만원, 초과 200만원
    add = _v(rules, "additional_limit")
    lim = _v(rules, "limit")
    gross = add["gross_split"] + delta
    c, _ = run(CardUsage(credit=gross, market=50_000_000), gross=gross)
    key = "above" if delta else "at_or_below"
    assert c.limit == lim[key] + add[key]
    assert c.amount == c.limit


def test_sibling_usage_excluded(rules, run):
    c, book = run(CardUsage(credit=GROSS), CardUsage(user="sibling", credit=GROSS))
    alone, _ = run(CardUsage(credit=GROSS))
    assert c == alone
    assert "2025.card.user_basis" in book.rules_used()["card_deduction"]


def test_won_floor_by_card_rounding(rules, run):
    # 원 미만만 버린다(2025.card.rounding, p242). 7원 × 15% = 1.05원 → 1원
    m = _min_spend(rules)
    c, book = run(CardUsage(credit=m + 7))
    assert c.before_limit == 1
    assert "2025.card.rounding" in book.rules_used()["card_deduction"]


def test_combined_limit_excess(rules, make_worker):
    # 카드 공제 + 종합한도 대상 5그룹 밖 소득공제가 2,500만원을 넘으면 넘는 만큼 뺀다
    limit = rules["2025.base.combined_deduction_limit"].value["limit"]
    big = OutOfScopeItem(
        name="주택자금",
        kind="income_deduction",
        category="special_income_deduction",
        amount=limit,
        in_combined_limit=True,
    )
    w = make_worker(60_000_000, card_usage=(CardUsage(credit=40_000_000),), out_of_scope=(big,))
    r = compute_tax(w, rules)
    assert r.card.amount > 0
    assert r.combined_limit_target == limit + r.card.amount
    assert r.combined_limit_excess == r.card.amount
    assert r.income_deduction_total == (
        r.earned_income_deduction
        + r.comprehensive_income_deduction
        + r.other_income_deduction
        - r.combined_limit_excess
    )
