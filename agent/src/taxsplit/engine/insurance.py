"""연금보험료공제(소법 §51의3, p103)와 보험료공제(소법 §52 ①, p107).

둘 다 근로자 본인이 낸 금액 전액이다. 부부가 서로 옮길 수 없는 각자의 공제라
맞벌이 배분 비교 대상은 아니지만 결정세액을 바꾸므로 계산에 넣는다(Issue #13).
"""

from taxsplit.engine.models import WorkerInput
from taxsplit.engine.rulebook import Rulebook, RuleValueError

PENSION = "base.pension_insurance_deduction"
PREMIUM = "base.insurance_premium_deduction"

# 규칙표 items 이름 → 입력 칸
_PREMIUM_FIELDS = {
    "national_health": "health_insurance",
    "employment": "employment_insurance",
    "long_term_care": "long_term_care_insurance",
}


def _check_payer(book: Rulebook, name: str, v: dict) -> None:
    # 입력은 근로자 본인 부담분만 받는다. 규칙이 다른 부담자를 말하면 멈춘다
    if v["payer"] != "employee":
        raise RuleValueError(f"{book.full_id(name)}: 모르는 payer {v['payer']!r}")


def pension_deduction(worker: WorkerInput, book: Rulebook) -> int:
    v = book.value(PENSION, "pension_insurance_deduction")
    _check_payer(book, PENSION, v)
    return worker.national_pension


def check_pension_excess_rule(book: Rulebook, stage: str) -> None:
    """공제 합계가 종합소득금액을 넘는 부분은 없는 것으로 본다(p103). 계산은 flow에서 한다."""
    v = book.value(PENSION, stage)
    if v["excess_over"] != "comprehensive_income_amount":
        raise RuleValueError(f"{book.full_id(PENSION)}: 모르는 excess_over {v['excess_over']!r}")


def insurance_premium_deduction(worker: WorkerInput, book: Rulebook) -> int:
    v = book.value(PREMIUM, "insurance_premium_deduction")
    _check_payer(book, PREMIUM, v)
    unknown = set(v["items"]) - set(_PREMIUM_FIELDS)
    if unknown:
        raise RuleValueError(f"{book.full_id(PREMIUM)}: 모르는 보험 {sorted(unknown)}")
    return sum(getattr(worker, _PREMIUM_FIELDS[item]) for item in v["items"])
