"""AI에게 줄 도구 정의(이름, 한국어 설명, 입력 JSON 스키마).

스키마는 입력 모델 Household에서 만든다. 검사도 같은 모델로 해서 기준이 하나다.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict

from taxsplit.allocation.models import Household
from taxsplit.gaps.models import GapRequest

CHECK_ELIGIBILITY = "check_eligibility"
COMPARE_ALLOCATIONS = "compare_allocations"
# 간소화에 안 나오는 공제 찾기(PR 24). 앞 두 도구와 달리 입력이 가족 목록(+가구)이다
# TODO(사람 확인): docs/assumptions.md A-062
FIND_MISSING_DEDUCTIONS = "find_missing_deductions"
TOOL_NAMES: tuple[str, ...] = (CHECK_ELIGIBILITY, COMPARE_ALLOCATIONS, FIND_MISSING_DEDUCTIONS)

# 두 도구 설명에 같이 붙는 입력 규칙. 소득 칸 기본값(0원)으로 "소득 없음"이 되는 것을 막는다
_INPUT_RULES = (
    "금액은 모두 원 단위 정수로 넣는다(예: 3000000). '약 300만'처럼 추측한 값을 넣지 않는다. "
    "부양가족마다 올해 소득(income_amount, 근로소득만 있으면 wage_only_gross)을 꼭 적는다. "
    "모르면 사용자에게 묻는다. 소득이 없다고 확인했으면 0을 적는다. "
    "지출 대상(for_whom)과 카드 사용자(user)는 'husband', 'wife' 또는 members의 이름이어야 한다."
)

_DESCRIPTIONS = {
    CHECK_ELIGIBILITY: (
        "부양가족마다 남편·아내 중 누가 기본공제를 받을 수 있는지와 안 되는 이유를 돌려준다. "
        "compare_allocations보다 먼저 같은 가족 구성으로 불러야 한다. " + _INPUT_RULES
    ),
    COMPARE_ALLOCATIONS: (
        "부양가족을 남편·아내에게 나누는 모든 경우를 계산 엔진으로 계산해 최적안, "
        "흔한 방식 A·B, 흔한 방식 대비 추가 환급액, 경고, 쓴 규칙 ID를 돌려준다. "
        "같은 가족 구성으로 check_eligibility가 성공한 뒤에만 실행된다. "
        "답에 쓰는 금액은 이 결과에 있는 값만 쓴다. " + _INPUT_RULES
    ),
    FIND_MISSING_DEDUCTIONS: (
        "간소화 자료에 안 나와 놓치기 쉬운 공제를 찾아 알림 카드 목록을 돌려준다. "
        "family에는 사용자가 답한 가족(부모님·자녀·같이 사는 가족, 태어난 해)과 "
        "이미 물은 질문 ID를 넣는다. 간소화 추출 결과는 서버가 넣으니 보내지 않는다. "
        "사용자가 금액 칸을 고르면 picks에 "
        "선택지 금액 그대로 넣고, household도 넣으면 놓칠 금액(estimate)을 계산 엔진으로 낸다. "
        "household를 넣을 때는 같은 입력 규칙을 따른다. " + _INPUT_RULES
    ),
}

_SCHEMAS = {FIND_MISSING_DEDUCTIONS: GapRequest}


class ToolDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, Any]


def household_schema() -> dict[str, Any]:
    """도구 입력(가구 하나)의 JSON 스키마."""
    return Household.model_json_schema()


def tool_definitions() -> tuple[ToolDefinition, ...]:
    """도구 3개 정의. 앞 두 개는 부르는 순서(요건 확인 → 배분 비교)와 같다."""
    household = household_schema()
    return tuple(
        ToolDefinition(
            name=n,
            description=_DESCRIPTIONS[n],
            input_schema=_SCHEMAS[n].model_json_schema() if n in _SCHEMAS else household,
        )
        for n in TOOL_NAMES
    )
