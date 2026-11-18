"""사례 단계 이름 → 엔진 결과에서 그 값을 읽는 함수."""

from collections.abc import Callable
from typing import Any

from taxsplit.engine import TaxResult

Getter = Callable[[TaxResult], Any]
# 사람 전체 값을 읽는 단계
TOTAL_STAGES: dict[str, Getter] = {
    "gross_salary": lambda r: r.gross_salary,
    "earned_income_deduction": lambda r: r.earned_income_deduction,
    "earned_income_amount": lambda r: r.earned_income_amount,
    "basic_deduction_count": lambda r: r.personal.basic_count,
    "basic_deduction_total": lambda r: r.personal.basic_total,
    "basic_deduction_self": lambda r: r.personal.basic_self,
    "basic_deduction_dependents_count": lambda r: r.personal.basic_count - 1,
    "basic_deduction_dependents": lambda r: r.personal.basic_dependents,
    "additional_deduction_elderly_count": lambda r: r.personal.elderly_count,
    "additional_deduction_elderly": lambda r: r.personal.elderly,
    "additional_deduction_disabled_count": lambda r: r.personal.disabled_count,
    "additional_deduction_disabled": lambda r: r.personal.disabled,
    "additional_deduction_woman": lambda r: r.personal.woman,
    "personal_deduction_total": lambda r: r.personal.total,
    "pension_insurance_deduction": lambda r: r.pension_insurance_deduction,
    "insurance_premium_deduction": lambda r: r.insurance_premium_deduction,
    "earned_income_credit_limit": lambda r: r.earned_income_credit.limit,
    "child_credit_age8plus_count": lambda r: r.child_credit.age8plus_count,
    "child_credit_age8plus": lambda r: r.child_credit.age8plus,
    "child_credit_birth_count": lambda r: r.child_credit.birth_count,
    "child_credit_birth": lambda r: r.child_credit.birth,
    "child_credit": lambda r: r.child_credit.total,
    # PR 5: 소득공제 합계·과세표준·세액
    "special_income_deduction_total": lambda r: r.special_income_deduction_total,
    "comprehensive_income_deduction": lambda r: r.comprehensive_income_deduction,
    "income_after_deductions": lambda r: r.income_after_deductions,
    "other_income_deduction": lambda r: r.other_income_deduction,
    "comprehensive_limit_target": lambda r: r.combined_limit_target,
    "comprehensive_limit_excess": lambda r: r.combined_limit_excess,
    "income_deduction_total": lambda r: r.income_deduction_total,
    "taxable_income": lambda r: r.taxable_income,
    "computed_tax": lambda r: r.computed_tax,
    "earned_income_credit_before_limit": lambda r: r.earned_income_credit.before_limit,
    "earned_income_credit": lambda r: r.earned_income_credit.amount,
    "special_tax_credit_total": lambda r: r.special_tax_credit_total,
    "tax_credit_total": lambda r: r.tax_credit_total,
    "determined_tax": lambda r: r.determined_tax,
}
# 의료비·교육비·카드 단계. 항목 사례에서도 같은 이름(r.medical 등)으로 읽는다
ITEM_STAGES: dict[str, Getter] = {
    "medical_threshold": lambda r: r.medical.threshold,
    "medical_base_general": lambda r: r.medical.base_others,
    "medical_base_special": lambda r: r.medical.base_special,
    "medical_base_infertility": lambda r: r.medical.base_infertility,
    "medical_credit_base": lambda r: r.medical.base,
    "medical_credit": lambda r: r.medical.amount,
    "education_base_self": lambda r: r.education.base_self,
    "education_base_children": lambda r: r.education.base_children,
    "education_base_siblings": lambda r: r.education.base_siblings,
    "education_credit_base": lambda r: r.education.base,
    "education_credit": lambda r: r.education.amount,
    "card_minimum_spend": lambda r: r.card.minimum_spend,
    "card_part_credit": lambda r: r.card.part_credit,
    "card_part_cash_debit": lambda r: r.card.part_cash_debit,
    "card_part_culture_sports": lambda r: r.card.part_culture,
    "card_part_traditional_market": lambda r: r.card.part_market,
    "card_part_public_transport": lambda r: r.card.part_transit,
    "card_minimum_spend_deduction": lambda r: r.card.minimum_spend_deduction,
    "card_deductible_before_limit": lambda r: r.card.before_limit,
    "card_limit": lambda r: r.card.limit,
    "card_deduction": lambda r: r.card.amount,
}
TOTAL_STAGES.update(ITEM_STAGES)
# 부양가족 한 명의 값을 묻는 사례(p99·p100)에서 그 사람 값을 읽는 단계
TARGET_STAGES = {
    "basic_deduction_person": lambda d: d.basic,
    "additional_deduction_disabled": lambda d: d.disabled,
    "additional_deduction_elderly": lambda d: d.elderly,
    "personal_deduction_person_total": lambda d: d.basic + d.elderly + d.disabled,
    "spouse_basic_deduction_eligible": lambda d: d.eligible,
}
# 이번 범위 밖이라 비교하지 않는 단계(Issue #14 "하지 않을 것": 환급·납부세액, 세액감면 없음)
OUT_OF_SCOPE_STAGES = {"refund_or_payment", "tax_reduction_total", "marginal_rate_percent"}
