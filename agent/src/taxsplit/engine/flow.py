"""근로자 한 명의 2025년 귀속 세금 계산 흐름.

총급여 → 근로소득공제 → 근로소득금액
→ 종합소득공제(인적공제, 연금보험료공제, 특별소득공제) → 그 밖의 소득공제(카드 등)
→ 소득공제 종합한도(2,500만원) → 과세표준 → 기본세율 → 산출세액
→ 세액공제(근로소득·자녀·특별세액공제(의료비·교육비) 또는 표준) → 결정세액

순수 함수다. DB·LLM·네트워크를 부르지 않는다. 숫자는 모두 규칙표(rules)에서 읽는다.
표준세액공제는 근로자가 고르는 것이라, "특별공제를 받는 경우"와 "표준세액공제를 받는
경우"를 둘 다 계산해 결정세액이 적은 쪽을 고른다(Issue #13, p170).
"""

from typing import get_args

from taxsplit.engine.card import card_deduction
from taxsplit.engine.credits import child_tax_credit, earned_income_tax_credit, standard_credit_rule
from taxsplit.engine.education import education_credit
from taxsplit.engine.income import computed_tax, earned_income_deduction
from taxsplit.engine.insurance import (
    check_pension_excess_rule,
    insurance_premium_deduction,
    pension_deduction,
)
from taxsplit.engine.medical import medical_credit
from taxsplit.engine.models import OutOfScopeCategory, OutOfScopeResult, TaxResult, WorkerInput
from taxsplit.engine.models_items import ZERO_EDUCATION, ZERO_MEDICAL
from taxsplit.engine.personal import personal_deduction
from taxsplit.engine.rulebook import Rulebook, RuleValueError
from taxsplit.rules.loader import Rule

_SPECIAL_INCOME = "special_income_deduction"
_SPECIAL_CREDIT = "special_tax_credit"
COMBINED_LIMIT = "base.combined_deduction_limit"


def compute_tax(worker: WorkerInput, rules: dict[str, Rule]) -> TaxResult:
    """두 경우를 다 계산하고 결정세액이 적은 쪽을 돌려준다. 같으면 표준세액공제 쪽."""
    special = _run(worker, rules, use_standard=False)
    standard = _run(worker, rules, use_standard=True)
    chosen, other = (
        (standard, special)
        if standard.determined_tax <= special.determined_tax
        else (special, standard)
    )
    return chosen.model_copy(update={"other_option_determined_tax": other.determined_tax})


def _run(worker: WorkerInput, rules: dict[str, Rule], use_standard: bool) -> TaxResult:
    book = Rulebook(rules)
    gross = worker.gross_salary

    # 1) 근로소득금액
    eid = earned_income_deduction(gross, book)
    income = gross - eid

    # 2) 종합소득공제. 근로소득만 있으므로 종합소득금액 = 근로소득금액
    personal = personal_deduction(worker, income, book)
    pension = pension_deduction(worker, book)
    std_amount, special_names = standard_credit_rule(book)
    unknown = special_names - set(get_args(OutOfScopeCategory))
    if unknown:
        raise RuleValueError(f"표준세액공제 범주 이름을 모름: {sorted(unknown)}")
    # 표준세액공제를 고르면 특별소득공제(보험료공제 포함)·특별세액공제·월세세액공제를 안 받는다
    dropped = special_names if use_standard else frozenset()
    premium = 0
    if _SPECIAL_INCOME not in dropped:
        premium = insurance_premium_deduction(worker, book)
    oos = tuple(
        OutOfScopeResult(item=item, applied=item.category not in dropped)
        for item in worker.out_of_scope
    )
    applied = [r.item for r in oos if r.applied]
    oos_deduction = sum(i.amount for i in applied if i.kind == "income_deduction")
    special_income = premium + sum(
        i.amount for i in applied if i.kind == "income_deduction" and i.category == _SPECIAL_INCOME
    )
    comprehensive = personal.total + pension + special_income

    # 3) 그 밖의 소득공제(카드)와 소득공제 종합한도(조특법 §132의2, p147)
    card = card_deduction(worker, book)
    # 5그룹 밖 소득공제 중 특별소득공제가 아닌 것은 "그 밖의 소득공제"로 들어간다
    other = card.amount + oos_deduction - (special_income - premium)
    target = card.amount + sum(i.amount for i in applied if i.in_combined_limit)
    combined_limit = book.value(COMBINED_LIMIT, "combined_limit")["limit"]
    combined_excess = max(0, target - combined_limit)

    # 4) 과세표준. 공제 합계가 종합소득금액을 넘는 부분은 없는 것으로 본다(p103)
    check_pension_excess_rule(book, "taxable_income")
    deductions = comprehensive + other - combined_excess
    taxable = max(0, income - deductions)
    excess = max(0, deductions - income)

    # 5) 산출세액과 세액공제. 표준세액공제를 고르면 의료비·교육비(특별세액공제)를 안 받는다
    tax = computed_tax(taxable, book)
    earned_credit = earned_income_tax_credit(tax, gross, book)
    child = child_tax_credit(worker, book)
    use_special = _SPECIAL_CREDIT not in dropped
    medical = medical_credit(worker, book) if use_special else ZERO_MEDICAL
    education = education_credit(worker, book) if use_special else ZERO_EDUCATION
    special_credit = (
        medical.amount
        + education.amount
        + sum(i.amount for i in applied if i.kind == "tax_credit" and i.category == _SPECIAL_CREDIT)
    )
    standard = std_amount if use_standard else 0
    oos_credit = sum(i.amount for i in applied if i.kind == "tax_credit")
    credits = earned_credit.amount + child.total + standard + medical.amount + education.amount
    credits += oos_credit
    # TODO(확인 필요): 세액공제 합계가 산출세액을 넘을 때 어느 공제부터 깎는지 출처 확인 전.
    # 지금은 결정세액이 0원 아래로 내려가지 않게만 한다
    determined = max(0, tax - credits)

    return TaxResult(
        gross_salary=gross,
        earned_income_deduction=eid,
        earned_income_amount=income,
        personal=personal,
        pension_insurance_deduction=pension,
        insurance_premium_deduction=premium,
        out_of_scope_income_deduction=oos_deduction,
        special_income_deduction_total=special_income,
        comprehensive_income_deduction=comprehensive,
        income_after_deductions=max(0, income - comprehensive),
        card=card,
        other_income_deduction=other,
        combined_limit_target=target,
        combined_limit_excess=combined_excess,
        income_deduction_total=eid + deductions,
        deduction_excess=excess,
        taxable_income=taxable,
        computed_tax=tax,
        earned_income_credit=earned_credit,
        child_credit=child,
        medical=medical,
        education=education,
        special_tax_credit_total=special_credit,
        standard_tax_credit=standard,
        standard_credit_chosen=use_standard,
        other_option_determined_tax=0,
        out_of_scope_tax_credit=oos_credit,
        tax_credit_total=credits,
        determined_tax=determined,
        out_of_scope=oos,
        rules_used=book.rules_used(),
        needs_check=tuple(book.needs_check),
    )
