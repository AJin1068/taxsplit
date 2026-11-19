"""신용카드 등 사용금액 소득공제(조특법 §126의2, 국세청 신고안내 인쇄 p132~p138).

계산식(p133):
  ①~⑤ 결제 수단별 사용금액 × 공제율 (신용, 현금·체크, 문화체육, 전통시장, 대중교통)
  ⑥ 최저사용금액(총급여 25%)을 정해진 순서로 채운 금액 × 그 공제율
  공제가능금액 = ①+②+③+④+⑤ − ⑥
  한도 = 기본 한도 + min(공제가능금액 − 기본 한도, ③+④+⑤, 추가 한도)
  공제액 = min(공제가능금액, 한도)
끝수는 카드 전용 규칙(2025.card.rounding, 원 미만 버림)으로 단계마다 버린다.
"""

from decimal import Decimal

from taxsplit.engine.models import WorkerInput
from taxsplit.engine.models_items import CardDeduction
from taxsplit.engine.rulebook import Rulebook, RuleValueError

THRESHOLD = "card.threshold"
RATE = "card.rate"
ORDER = "card.min_usage_order"
LIMIT = "card.limit"
ADDITIONAL = "card.additional_limit"
USER_BASIS = "card.user_basis"
CULTURE_OVER = "card.culture_over_limit"
ROUNDING = "card.rounding"
STAGE = "card_deduction"

KINDS = ("credit", "cash_debit", "culture", "market", "transit")
# 최저사용금액 채우는 순서의 묶음 이름 → 그 안의 결제 수단
_TIERS = {
    "credit": ("credit",),
    "cash_debit_culture": ("cash_debit", "culture"),
    "market_transit": ("market", "transit"),
}

ZERO_CARD = CardDeduction(
    minimum_spend=0,
    part_credit=0,
    part_cash_debit=0,
    part_culture=0,
    part_market=0,
    part_transit=0,
    minimum_spend_deduction=0,
    before_limit=0,
    limit=0,
    amount=0,
)


def _amounts(worker: WorkerInput, rate: dict, book: Rulebook) -> dict[str, int]:
    """결제 수단별 사용금액. 형제자매 사용분은 빼고, 7천만원 초과면 문화체육을 결제 수단으로."""
    excluded = book.value(USER_BASIS, STAGE)["excluded_relations"]
    uses = [u for u in worker.card_usage if u.user not in excluded]
    plain = ("credit", "cash_debit", "market", "transit")
    out = {k: sum(getattr(u, k) for u in uses) for k in plain}
    culture_credit = sum(u.culture_credit for u in uses)
    culture_cash = sum(u.culture_cash_debit for u in uses)
    if worker.gross_salary > rate["culture_gross_limit"]:
        over = book.value(CULTURE_OVER, STAGE)
        if (over["rate_by"], over["min_usage_by"]) != ("payment_method", "payment_method"):
            raise RuleValueError(f"{book.full_id(CULTURE_OVER)}: 모르는 처리 방식")
        out["credit"] += culture_credit
        out["cash_debit"] += culture_cash
        out["culture"] = 0
    else:
        out["culture"] = culture_credit + culture_cash
    return out


def _minimum_spend_deduction(min_spend: int, amounts: dict, rate: dict, book: Rulebook) -> int:
    """⑥: 최저사용금액을 신용 → 현금·체크·문화체육 → 전통시장·대중교통 순서로 채운다."""
    order = book.value(ORDER, STAGE)["order"]
    if sorted(order) != sorted(_TIERS):
        raise RuleValueError(f"{book.full_id(ORDER)}: 모르는 순서 {order!r}")
    left = min_spend
    total = Decimal(0)
    for tier in order:
        for kind in _TIERS[tier]:
            taken = min(left, amounts[kind])
            total += taken * Decimal(rate[kind])
            left -= taken
    return book.floor(total, STAGE, ROUNDING)


def _split(v: dict, gross: int) -> int:
    """총급여가 gross_split 이하면 at_or_below, 넘으면 above."""
    return v["at_or_below"] if gross <= v["gross_split"] else v["above"]


def card_deduction(worker: WorkerInput, book: Rulebook) -> CardDeduction:
    """신용카드 등 소득공제액과 계산식 단계 값."""
    if not worker.card_usage:
        return ZERO_CARD
    gross = worker.gross_salary
    rate = book.value(RATE, STAGE)
    amounts = _amounts(worker, rate, book)

    # ①~⑤ 결제 수단별 공제율 금액
    parts = {k: book.floor(amounts[k] * Decimal(rate[k]), STAGE, ROUNDING) for k in KINDS}
    # ⑥ 최저사용금액 = 총급여 × 25%
    min_rate = Decimal(book.value(THRESHOLD, STAGE)["gross_rate"])
    min_spend = book.floor(gross * min_rate, STAGE, ROUNDING)
    min_deduction = _minimum_spend_deduction(min_spend, amounts, rate, book)
    before = max(0, sum(parts.values()) - min_deduction)

    # 한도: 기본 한도 + 추가 한도(전통시장·대중교통·문화체육 몫만큼)
    base_limit = _split(book.value(LIMIT, STAGE), gross)
    add = book.value(ADDITIONAL, STAGE)
    add_source = parts["market"] + parts["transit"]
    if not (gross > add["gross_split"] and add["culture_excluded_above"]):
        add_source += parts["culture"]
    additional = min(max(0, before - base_limit), add_source, _split(add, gross))
    limit = base_limit + additional

    return CardDeduction(
        minimum_spend=min_spend,
        part_credit=parts["credit"],
        part_cash_debit=parts["cash_debit"],
        part_culture=parts["culture"],
        part_market=parts["market"],
        part_transit=parts["transit"],
        minimum_spend_deduction=min_deduction,
        before_limit=before,
        limit=limit,
        amount=min(before, limit),
    )
