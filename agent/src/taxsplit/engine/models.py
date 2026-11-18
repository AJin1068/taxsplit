"""계산 엔진의 입력·출력 모델.

금액은 모두 원 단위 정수(int)다. float는 쓰지 않는다(Issue #13 "금액 타입").
입력은 근로자 한 명이다. 맞벌이 배분(PR 6)은 부부 각자에게 엔진을 한 번씩 부른다.
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 0 이상 정수만 받는다. "100"(글자)이나 1.5(소수)는 거절한다
Won = Annotated[int, Field(ge=0, strict=True)]

# 부양가족 관계. child = 자녀·입양자(직계비속), lineal_ascendant = 부모·배우자의 부모 등
Relation = Literal["spouse", "child", "lineal_ascendant", "sibling"]

# 5그룹 밖 금액의 범주. 이름은 규칙 2025.base.standard_tax_credit의 applies_when_none_of와 같다
OutOfScopeCategory = Literal[
    "special_income_deduction", "special_tax_credit", "monthly_rent_credit", "other"
]
OUT_OF_SCOPE_NOTE = "범위 밖, 입력값 그대로"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Dependent(_Frozen):
    """이 근로자가 공제받겠다고 넣은 부양가족 한 명."""

    name: str
    relation: Relation
    birth_year: int
    # 연 소득금액 합계. 근로소득만 있으면 아래 wage_only_gross를 채운다
    income_amount: Won = 0
    # 근로소득만 있을 때의 총급여. 채우면 소득요건을 총급여 기준으로 본다
    wage_only_gross: Won | None = None
    disabled: bool = False
    # 혼인·입양처럼 관계가 생긴 날. 판정일보다 늦으면 그 해에는 공제대상이 아니다
    relation_start: date | None = None
    death_date: date | None = None
    # 그 해에 출산·입양한 자녀면 몇째인지(1, 2, 3...)
    birth_or_adoption_order: int | None = Field(default=None, ge=1)


class SelfInfo(_Frozen):
    """근로자 본인 정보(부녀자·한부모·경로우대·장애인 판정용)."""

    sex: Literal["male", "female"]
    birth_year: int
    has_spouse: bool
    head_of_household: bool = False
    disabled: bool = False


class OutOfScopeItem(_Frozen):
    """5그룹 밖 공제 금액. 엔진은 계산하지 않고 그대로 쓴다(주택자금, 기부금, 연금계좌 등)."""

    name: str
    kind: Literal["income_deduction", "tax_credit"]
    category: OutOfScopeCategory
    amount: Won

    @model_validator(mode="after")
    def _kind_matches_category(self) -> OutOfScopeItem:
        # 특별소득공제는 소득공제, 특별세액공제·월세세액공제는 세액공제여야 한다
        if self.category == "special_income_deduction" and self.kind != "income_deduction":
            raise ValueError("special_income_deduction은 income_deduction이어야 함")
        if self.category in ("special_tax_credit", "monthly_rent_credit") and (
            self.kind != "tax_credit"
        ):
            raise ValueError(f"{self.category}는 tax_credit이어야 함")
        return self


class WorkerInput(_Frozen):
    """근로자 한 명의 입력."""

    gross_salary: Won
    person: SelfInfo
    dependents: tuple[Dependent, ...] = ()
    # 근로자 본인 부담분 보험료
    national_pension: Won = 0
    health_insurance: Won = 0
    employment_insurance: Won = 0
    long_term_care_insurance: Won = 0
    out_of_scope: tuple[OutOfScopeItem, ...] = ()


class DependentResult(_Frozen):
    name: str
    eligible: bool
    reason: str
    basic: int
    elderly: int
    disabled: int


class PersonalDeduction(_Frozen):
    """인적공제(기본·추가). 인원 수는 본인을 포함한다."""

    basic_count: int
    basic_self: int
    basic_dependents: int
    basic_total: int
    elderly_count: int
    elderly: int
    disabled_count: int
    disabled: int
    woman: int
    single_parent: int
    total: int
    dependents: tuple[DependentResult, ...]


class EarnedIncomeCredit(_Frozen):
    before_limit: int
    limit: int
    amount: int


class ChildCredit(_Frozen):
    age8plus_count: int
    age8plus: int
    birth_count: int
    birth: int
    total: int


class OutOfScopeResult(_Frozen):
    item: OutOfScopeItem
    # 표준세액공제를 고르면 특별공제 범주 금액은 쓰지 않는다
    applied: bool
    note: str = OUT_OF_SCOPE_NOTE


class TaxResult(_Frozen):
    """결정세액과 단계별 중간값, 단계마다 쓴 규칙 ID, 확인 필요 목록."""

    gross_salary: int
    earned_income_deduction: int
    earned_income_amount: int
    personal: PersonalDeduction
    pension_insurance_deduction: int
    insurance_premium_deduction: int
    out_of_scope_income_deduction: int
    # 소득공제 합계가 근로소득금액을 넘어 공제되지 못한 금액
    deduction_excess: int
    taxable_income: int
    computed_tax: int
    earned_income_credit: EarnedIncomeCredit
    child_credit: ChildCredit
    standard_tax_credit: int
    standard_credit_chosen: bool
    # 고르지 않은 쪽(특별공제 ↔ 표준세액공제)의 결정세액. 왜 골랐는지 설명할 때 쓴다
    other_option_determined_tax: int
    out_of_scope_tax_credit: int
    determined_tax: int
    out_of_scope: tuple[OutOfScopeResult, ...]
    rules_used: dict[str, tuple[str, ...]]
    needs_check: tuple[str, ...]
