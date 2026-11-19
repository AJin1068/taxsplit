"""빈 곳 찾기의 입력(가족 목록)과 출력(알림 카드) 모델(Issue #126).

카드 칸 이름은 SSE `gaps` 이벤트 약속이다: id, kind, person, title, why, todo,
source_pages, question, estimate. 화면(PR 14b)이 이 모양 그대로 그린다.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from taxsplit.allocation.models import Household, Who

Won = Annotated[int, Field(ge=0, strict=True)]

# 가족 관계. 부모만 따로 살아도 부양하면 공제 대상이 될 수 있다(인쇄 97쪽).
# 형제자매·손주·위탁아동은 같이 살아야 한다(인쇄 10쪽 요건표, 96~97쪽)
FamilyRelation = Literal["parent", "child", "sibling", "grandchild", "foster_child"]
# 같이 살아야 공제 대상이 되는 관계
MUST_LIVE_TOGETHER: frozenset[str] = frozenset({"sibling", "grandchild", "foster_child"})


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FamilyMember(_Frozen):
    """가족 한 명(첫 질문 답 + 간소화 추출 결과에서 AI가 옮긴다)."""

    name: str = Field(description="간소화 자료의 대상자 이름과 같게 적는다")
    relation: FamilyRelation
    birth_year: int = Field(description="태어난 해. 나이는 코드가 계산한다")
    # 누구 쪽 가족인가(부모·형제자매). 자녀처럼 부부 공동이면 null
    family_of: Who | None = None
    # 같이 사나. 모르면 null(형제자매·손주·위탁아동은 같이 살 때만 공제 대상으로 본다)
    lives_with: bool | None = None
    # 다른 형제가 이 부모님을 공제받나. 모르면 null
    claimed_by_sibling: bool | None = None
    # 간소화 명단에 "소득 기준 초과" 표시가 있나(인쇄 26쪽)
    listed_over_income: bool = False
    # 장애인이거나 암·희귀질환처럼 계속 치료받나
    disabled_or_severe: bool = False
    # 올해 태어난 아이가 몇째인지. 모르면 null
    birth_order: int | None = Field(default=None, ge=1)


class FamilyAnswer(_Frozen):
    """첫 질문 묶음의 답. answered에 든 질문 ID는 다시 묻지 않는다."""

    members: tuple[FamilyMember, ...] = ()
    answered: tuple[str, ...] = Field(default=(), description="이미 물어 답을 받은 질문 ID(gap.*)")


class Option(_Frozen):
    label: str
    # 놓칠 금액 질문의 선택지면 그 금액(원). 사용자가 고르는 입력 예시일 뿐 세법 숫자가 아니다
    amount: int | None = None


class Question(_Frozen):
    text: str
    options: tuple[Option, ...] = ()


class Estimate(_Frozen):
    """놓칠 금액: 고른 금액을 넣었을 때와 안 넣었을 때 부부 합산 결정세액 차이."""

    label: str
    chosen_amount: int
    payer: Who
    # 차이가 0원이면 None이고 no_difference가 True
    saving: int | None
    no_difference: bool
    message: str


class GapCard(_Frozen):
    id: str
    kind: str
    # 누구 일인가(가족 이름). 가구 전체에 묻는 질문이면 None
    person: str | None
    title: str
    why: str
    todo: str
    source_pages: tuple[str, ...]
    question: Question | None = None
    estimate: Estimate | None = None
    # 동의 안내 문구(카카오톡으로 그대로 보낼 글). 동의 카드에만 있다
    consent_message: str | None = None


class Pick(_Frozen):
    """놓칠 금액 질문에서 사용자가 고른 칸."""

    person: str
    amount: Won = Field(description="사용자가 고른 선택지의 금액. 선택지 금액만 받는다")
    payer: Who | None = Field(
        default=None, description="그 가족 병원비를 낸 사람. 모르면 null(그 가족 쪽 배우자)"
    )


class GapRequest(_Frozen):
    """도구 find_missing_deductions 입력."""

    family: FamilyAnswer
    # 있으면 놓칠 금액·"누가 냈나" 판단에 쓴다. check_eligibility와 같은 가구 모양
    household: Household | None = None
    picks: tuple[Pick, ...] = ()


class CardAnswer(_Frozen):
    """화면이 질문 카드의 선택지를 눌렀을 때 메시지와 함께 보내는 구조화된 답."""

    gap_id: str = Field(pattern=r"^gap\.[a-z_]+$")
    person: str | None = None
    choice: str = Field(min_length=1, max_length=100)
    # 놓칠 금액 질문이면 고른 칸의 금액
    amount: int | None = Field(default=None, ge=0)

    def as_text(self) -> str:
        """AI에게 넘길 한 줄. 금액은 사용자 글로 들어가 답에 다시 써도 된다(금액 센서)."""
        who = f" / {self.person}" if self.person else ""
        amount = f" / {self.amount:,}원" if self.amount is not None else ""
        return f"[카드 답] {self.gap_id}{who}: {self.choice}{amount}"
