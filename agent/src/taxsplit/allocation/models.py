"""맞벌이 배분 비교의 입력(가구)과 출력(배분안·흔한 방식·경고) 모델.

금액은 모두 원 단위 정수다. 지출의 주인(누가 냈나·누가 썼나)은 입력 그대로 쓴다(Issue #15).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from taxsplit.engine import Dependent, OutOfScopeItem, TaxResult
from taxsplit.engine.models_items import EducationItem, MedicalItem, SchoolLevel

Won = Annotated[int, Field(ge=0, strict=True)]

# 부부 두 사람. 지출 대상·카드 사용자 칸에서는 이 글자가 "그 배우자 본인"을 뜻한다
Who = Literal["husband", "wife"]
WHO: tuple[Who, Who] = ("husband", "wife")


def other(who: Who) -> Who:
    return "wife" if who == "husband" else "husband"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Earner(_Frozen):
    """부부 중 한 사람(근로소득만 있음)."""

    gross_salary: Won
    sex: Literal["male", "female"]
    birth_year: int
    disabled: bool = False
    national_pension: Won = 0
    health_insurance: Won = 0
    employment_insurance: Won = 0
    long_term_care_insurance: Won = 0
    out_of_scope: tuple[OutOfScopeItem, ...] = ()


class Member(_Frozen):
    """부양가족 한 명. 누가 기본공제 받을지는 배분안이 정한다."""

    dependent: Dependent
    # 누구의 가족인가(부모·형제자매). 자녀처럼 부부 공동이면 None. 흔한 방식 B에 쓴다
    family_of: Who | None = None

    @property
    def name(self) -> str:
        return self.dependent.name


class MedicalSpend(_Frozen):
    """의료비 한 줄. for_whom = "husband" | "wife" | 부양가족 이름."""

    payer: Who
    for_whom: str
    item: MedicalItem = "general"
    amount: Won
    insurance_special_case: bool = False


class EducationSpend(_Frozen):
    payer: Who
    for_whom: str
    level: SchoolLevel = "school"
    item: EducationItem = "general"
    amount: Won


class CardSpend(_Frozen):
    """카드 등 사용금액 한 묶음. 공제는 결제자가 아니라 쓴 사람(user) 기준이다."""

    user: str
    # 가족카드처럼 결제자가 다르면 적는다. 계산에는 쓰지 않는다(2025.card.user_basis)
    payer: Who | None = None
    credit: Won = 0
    cash_debit: Won = 0
    culture_credit: Won = 0
    culture_cash_debit: Won = 0
    market: Won = 0
    transit: Won = 0


class Household(_Frozen):
    """맞벌이 가구 하나."""

    husband: Earner
    wife: Earner
    members: tuple[Member, ...] = ()
    medical: tuple[MedicalSpend, ...] = ()
    education: tuple[EducationSpend, ...] = ()
    cards: tuple[CardSpend, ...] = ()

    def earner(self, who: Who) -> Earner:
        return self.husband if who == "husband" else self.wife

    def member(self, name: str) -> Member:
        return next(m for m in self.members if m.name == name)

    @model_validator(mode="after")
    def _names_known(self) -> Household:
        # 부양가족 이름은 겹치면 안 되고, 부부를 뜻하는 글자와도 달라야 한다
        names = [m.name for m in self.members]
        if len(set(names)) != len(names) or set(names) & set(WHO):
            raise ValueError(f"부양가족 이름이 겹침: {names}")
        if any(m.dependent.relation == "spouse" for m in self.members):
            raise ValueError("배우자는 부양가족 목록이 아니라 husband·wife로 넣는다")
        known = set(names) | set(WHO)
        targets = [s.for_whom for s in (*self.medical, *self.education)]
        targets += [c.user for c in self.cards]
        unknown = sorted(set(targets) - known)
        if unknown:
            raise ValueError(f"가구에 없는 지출 대상: {unknown}")
        return self


# 배분안 = 부양가족 이름 → 그 사람을 기본공제 받는 쪽(요건이 안 되는 부양가족은 빠진다)
Assignment = dict[str, Who]


class Dropped(_Frozen):
    """이 배분안에서 공제되지 않는 지출 한 줄과 그 근거."""

    kind: Literal["medical", "education", "card"]
    for_whom: str
    payer: Who | None
    amount: int
    rule_id: str
    reason: str


class AllocWarning(_Frozen):
    """중복공제·공제 안 됨·범위 밖 경고, 문서가 정하지 않은 해석 표시."""

    code: str
    message: str
    rule_ids: tuple[str, ...]


class PlanResult(_Frozen):
    """배분안 하나의 계산 결과."""

    assignment: Assignment
    husband_tax: int
    wife_tax: int
    total: int
    husband: TaxResult
    wife: TaxResult
    dropped: tuple[Dropped, ...]
    # 이 안에서 쓴 규칙 ID 전부(엔진 단계 + 배분 규칙)
    rule_ids: tuple[str, ...]
    # 아무도 기본공제 받지 않는 가족의 카드를 넣은 쪽(두 쪽을 계산해 합계가 작은 쪽, Issue #15)
    card_sides: dict[str, Who] = Field(default_factory=dict)
    # 이 안의 결과 설명에 붙일 표시(문서가 정하지 않은 해석 등)
    notes: tuple[AllocWarning, ...] = ()


class CommonPlan(_Frozen):
    """흔한 방식 한 가지와 최적안 대비 차이(= 추가로 돌려받을 수 있는 금액)."""

    name: Literal["A", "B"]
    description: str
    plan: PlanResult
    # 흔한 방식 합계 − 최적안 합계. 기납부세액은 배분과 상관없어 이 차이가 곧 환급액 차이다
    saving: int


class AllocationResult(_Frozen):
    plans: tuple[PlanResult, ...]
    # 계산한 안의 수(화면의 "m가지 경우를 모두 계산했어요")
    plan_count: int
    best: PlanResult
    # 합계가 최적안과 같은 안 전부
    best_plans: tuple[PlanResult, ...]
    common: tuple[CommonPlan, ...]
    # 화면의 "흔한 방식 대비 +n원": 과장하지 않으려고 A·B 중 차이가 작은 쪽
    headline_saving: int
    larger_earner: Who
    # 총급여가 원 단위까지 같아 과세표준(그것도 같으면 남편)으로 정했는지
    equal_gross: bool
    warnings: tuple[AllocWarning, ...]
