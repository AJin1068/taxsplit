"""의료비·교육비·카드 입력과 결과 모델(PR 5).

엔진은 "공제 대상인 지출"만 받는다. 학원비·보약처럼 대상이 아닌 지출을 거르는 일은
입력 쪽(간소화 PDF 추출 등)이 한다(Issue #14 [계획] 정할 것 2).
금액은 모두 원 단위 정수다.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Won = Annotated[int, Field(ge=0, strict=True)]

# 지출 대상: 근로자 본인이면 "self", 부양가족이면 Dependent.name
SELF = "self"

# 의료비 항목. 세부 한도(안경·산후조리원)와 공제율(난임·미숙아)이 항목에 따라 달라진다
MedicalItem = Literal["general", "glasses", "postnatal_care", "infertility", "premature_congenital"]
# 교육 과정. 한도는 과정별(취학 전·초중고·대학), 대학원은 본인만
SchoolLevel = Literal["preschool", "school", "university", "graduate"]
# 교육비 항목. 체험학습·교복은 세부 한도가 있다
EducationItem = Literal["general", "field_trip", "uniform", "disabled_special_education"]
CardUser = Literal["self", "spouse", "child", "lineal_ascendant", "sibling"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MedicalExpense(_Frozen):
    """이 근로자가 공제받는 의료비 한 줄. 산후조리원은 출산 한 번마다 한 줄로 넣는다."""

    for_name: str = SELF
    item: MedicalItem = "general"
    amount: Won
    # 건강보험 산정특례자(중증질환 등)면 한도 없는 쪽(㉢)으로 센다
    insurance_special_case: bool = False


class EducationExpense(_Frozen):
    """이 근로자가 공제받는 교육비 한 줄."""

    for_name: str = SELF
    level: SchoolLevel = "school"
    item: EducationItem = "general"
    amount: Won


class CardUsage(_Frozen):
    """사용자 한 명의 카드 등 사용금액. 칸마다 다른 칸과 겹치지 않는 금액을 넣는다.

    예: 신용카드 3,200만원 중 대중교통 200만원 → credit 3,000만, transit 200만.
    """

    user: CardUser = "self"
    credit: Won = 0
    cash_debit: Won = 0
    # 문화체육 사용분은 결제 수단별로 따로 받는다(총급여 7천만원 초과면 결제 수단으로 돌림)
    culture_credit: Won = 0
    culture_cash_debit: Won = 0
    market: Won = 0
    transit: Won = 0


class MedicalCredit(_Frozen):
    """의료비 세액공제. base_* 는 문턱·한도를 뺀 뒤의 대상금액."""

    threshold: int
    base_others: int
    base_special: int
    base_premature: int
    base_infertility: int
    base: int
    amount: int


class EducationCredit(_Frozen):
    base_self: int
    base_children: int
    base_siblings: int
    base_others: int
    base: int
    amount: int


class CardDeduction(_Frozen):
    """신용카드 등 소득공제. 단계 이름은 국세청 계산식 ①~⑥을 따른다."""

    minimum_spend: int
    part_credit: int
    part_cash_debit: int
    part_culture: int
    part_market: int
    part_transit: int
    minimum_spend_deduction: int
    before_limit: int
    limit: int
    amount: int


ZERO_MEDICAL = MedicalCredit(
    threshold=0,
    base_others=0,
    base_special=0,
    base_premature=0,
    base_infertility=0,
    base=0,
    amount=0,
)
ZERO_EDUCATION = EducationCredit(
    base_self=0, base_children=0, base_siblings=0, base_others=0, base=0, amount=0
)
