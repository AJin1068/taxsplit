"""계산 엔진: 근로자 한 명의 세금을 규칙표대로 계산한다(LLM은 계산하지 않는다, ADR-0003)."""

from taxsplit.engine.flow import compute_tax
from taxsplit.engine.models import (
    Dependent,
    OutOfScopeItem,
    SelfInfo,
    TaxResult,
    WorkerInput,
)
from taxsplit.engine.models_items import CardUsage, EducationExpense, MedicalExpense
from taxsplit.engine.personal import basic_eligibility, is_spouse_with_income
from taxsplit.engine.rulebook import Rulebook, RuleNotReadyError, RuleValueError

__all__ = [
    "CardUsage",
    "EducationExpense",
    "MedicalExpense",
    "Dependent",
    "OutOfScopeItem",
    "RuleNotReadyError",
    "RuleValueError",
    "Rulebook",
    "SelfInfo",
    "TaxResult",
    "WorkerInput",
    "basic_eligibility",
    "compute_tax",
    "is_spouse_with_income",
]
