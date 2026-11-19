"""호출 검사기의 운영값. 세법 숫자가 아니라 실제 대화를 본 뒤 고칠 값이다(Issue #18).

core/config.py는 고치지 않는다(PR 8과 같은 파일을 건드리지 않게, Issue #18 "정해진 결정").
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolPolicy:
    # 한 턴(사용자 메시지 하나)에 도구를 부를 수 있는 최대 횟수. 거절된 호출도 센다
    max_calls_per_turn: int = 8
    # 같은 도구가 invalid_args로 연속 실패해도 다시 부르게 하는 횟수. 넘으면 멈춤 신호
    max_invalid_retries: int = 2
