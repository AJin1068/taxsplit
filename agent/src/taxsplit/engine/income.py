"""근로소득공제, 근로소득금액, 기본세율(산출세액)."""

from taxsplit.engine.money import bracket_amount
from taxsplit.engine.rulebook import Rulebook

EARNED_INCOME_DEDUCTION = "base.earned_income_deduction"
TAX_RATE = "base.tax_rate"


def earned_income_deduction(gross_salary: int, book: Rulebook) -> int:
    """근로소득공제 = 구간표 값, 한도 2,000만원(소법 §47, p94). 총급여보다 클 수 없다."""
    stage = "earned_income_deduction"
    v = book.value(EARNED_INCOME_DEDUCTION, stage)
    amount = min(bracket_amount(gross_salary, v["brackets"]), v["limit"], gross_salary)
    return book.floor(amount, stage)


def computed_tax(taxable_income: int, book: Rulebook) -> int:
    """산출세액 = 과세표준 × 기본세율(소법 §55 ①, 8구간)."""
    stage = "computed_tax"
    v = book.value(TAX_RATE, stage)
    return book.floor(bracket_amount(taxable_income, v["brackets"]), stage)
