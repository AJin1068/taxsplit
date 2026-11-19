"""도구 호출 결과 상태 6개. PR 8(#17) `tool_calls.status` DB 제약과 같은 값이다.

값을 바꾸면 PR 8의 제약도 함께 바꿔야 한다(Issue #18 "정해진 결정").
"""

from enum import StrEnum


class ToolStatus(StrEnum):
    OK = "ok"
    # 인자 검사 실패(숫자 자리에 글자, 필수 칸 빠짐, 부양가족 소득 안 적음 등)
    INVALID_ARGS = "invalid_args"
    # 요건 확인 전에 배분 비교를 부르는 등 순서 위반
    ORDER_VIOLATION = "order_violation"
    UNKNOWN_TOOL = "unknown_tool"
    # 한 턴 최대 호출 수를 넘어 거절
    STEP_LIMIT = "step_limit"
    # 도구 실행 중 예외
    ERROR = "error"
