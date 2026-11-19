"""맞벌이 배분 비교와 중복공제 검사(PR 6). 계산은 engine/을 부르기만 한다."""

from taxsplit.allocation.checks import Claim, check_claims
from taxsplit.allocation.compare import compare_allocations, evaluate
from taxsplit.allocation.models import (
    AllocationResult,
    AllocWarning,
    CardSpend,
    CommonPlan,
    Dropped,
    Earner,
    EducationSpend,
    Household,
    MedicalSpend,
    Member,
    PlanResult,
)

__all__ = [
    "AllocWarning",
    "AllocationResult",
    "CardSpend",
    "Claim",
    "CommonPlan",
    "Dropped",
    "Earner",
    "EducationSpend",
    "Household",
    "MedicalSpend",
    "Member",
    "PlanResult",
    "check_claims",
    "compare_allocations",
    "evaluate",
]
