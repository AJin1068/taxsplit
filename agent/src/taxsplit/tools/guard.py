"""도구 호출 검사기: AI가 보낸 호출 하나를 실행 전에 검사하고, 실행하거나 거절한다.

검사 순서: 없는 도구 → 턴 최대 호출 수 → 인자 → 순서(요건 확인 먼저) → 실행.
호출마다 기록 1건을 저장소에 넣는다. 대화 하나에 검사기 하나를 쓴다(PR 10이 루프와 잇는다).
"""

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from taxsplit.rules.loader import Rule
from taxsplit.tools.definitions import CHECK_ELIGIBILITY, COMPARE_ALLOCATIONS, TOOL_NAMES
from taxsplit.tools.handlers import HANDLERS
from taxsplit.tools.policy import ToolPolicy
from taxsplit.tools.records import ToolCallRecord, ToolCallRepository
from taxsplit.tools.status import ToolStatus
from taxsplit.tools.validation import ArgError, family_fingerprint, validate_household

# 같은 도구가 invalid_args로 정해진 횟수를 넘게 실패하면 이 문구로 끝낸다(design.md 5장)
STOP_MESSAGE = (
    "입력 값을 확인하지 못해 계산을 멈춥니다. 확인 필요: 아래 칸을 사용자에게 다시 물어 주세요."
)


@dataclass(frozen=True)
class GuardResult:
    status: ToolStatus
    # AI에게 돌려줄 글(tool_result 본문)
    message: str
    # True면 루프가 더 부르지 말고 정해진 문구로 답을 끝내야 한다
    stop: bool
    record: ToolCallRecord
    result: dict[str, Any] | None = None


class ToolCallGuard:
    def __init__(
        self,
        rules: dict[str, Rule],
        repository: ToolCallRepository,
        policy: ToolPolicy | None = None,
        conversation_id: int | None = None,
    ) -> None:
        self._rules = rules
        self._repo = repository
        self._policy = policy or ToolPolicy()
        self._conversation_id = conversation_id
        self._turn = 1
        self._step = 0
        # 도구별 invalid_args 연속 횟수(턴마다 0으로)
        self._invalid: dict[str, int] = {}
        # 요건 확인이 성공한 가족 지문. 턴이 바뀌어도 대화 안에서는 유지한다
        self._checked: set[str] = set()

    @property
    def turn(self) -> int:
        return self._turn

    def next_turn(self) -> None:
        """새 사용자 메시지. 호출 수와 연속 실패 수를 0으로 되돌린다."""
        self._turn += 1
        self._step = 0
        self._invalid.clear()

    def call(self, tool: str, args: Any) -> GuardResult:
        """호출 하나를 검사·실행하고 기록을 남긴다. 거절된 호출도 턴 호출 수에 센다."""
        start = time.perf_counter()
        self._step += 1
        status, message, stop, errors, result = self._decide(tool, args)
        record = ToolCallRecord(
            conversation_id=self._conversation_id,
            turn=self._turn,
            step=self._step,
            tool=tool,
            args=args,
            status=status,
            errors=[str(e) for e in errors],
            result=result,
            latency_ms=int((time.perf_counter() - start) * 1000),
            created_at=datetime.now(UTC),
        )
        self._repo.add(record)
        return GuardResult(status, message, stop, record, result)

    def _decide(
        self, tool: str, args: Any
    ) -> tuple[ToolStatus, str, bool, list[ArgError], dict[str, Any] | None]:
        if tool not in HANDLERS:
            msg = f"없는 도구 {tool!r}. 쓸 수 있는 도구: {', '.join(TOOL_NAMES)}"
            return ToolStatus.UNKNOWN_TOOL, msg, False, [], None
        limit = self._policy.max_calls_per_turn
        if self._step > limit:
            msg = (
                f"이번 턴 도구 호출이 {limit}번을 넘었습니다. 더 부르지 말고 "
                "지금까지 받은 결과로 답하거나, 확인이 필요하다고 답하세요."
            )
            return ToolStatus.STEP_LIMIT, msg, True, [], None

        household, errors = validate_household(args)
        if household is None:
            return self._invalid_args(tool, errors)
        # 인자가 맞게 왔으니 연속 실패는 끊긴다
        self._invalid[tool] = 0

        fingerprint = family_fingerprint(household)
        if tool == COMPARE_ALLOCATIONS and fingerprint not in self._checked:
            if self._checked:
                msg = "가족 정보가 바뀌었으니 요건 확인(check_eligibility)을 다시 부르세요."
            else:
                msg = "먼저 같은 가구로 요건 확인(check_eligibility)을 부르세요."
            return ToolStatus.ORDER_VIOLATION, msg, False, [], None

        try:
            result = HANDLERS[tool](household, self._rules)
        except Exception as e:  # 실행 중 예외는 모두 error로 기록하고 AI에게 알린다
            msg = f"도구 실행 중 오류: {type(e).__name__}: {e}. 금액을 짐작해 답하지 마세요."
            return ToolStatus.ERROR, msg, False, [], None
        if tool == CHECK_ELIGIBILITY:
            self._checked.add(fingerprint)
        return ToolStatus.OK, json.dumps(result, ensure_ascii=False), False, [], result

    def _invalid_args(
        self, tool: str, errors: list[ArgError]
    ) -> tuple[ToolStatus, str, bool, list[ArgError], None]:
        count = self._invalid.get(tool, 0) + 1
        self._invalid[tool] = count
        reasons = "\n".join(f"- {e}" for e in errors)
        # 정해진 횟수까지는 고쳐서 다시 부르게 하고, 넘으면 멈춤 신호
        if count > self._policy.max_invalid_retries:
            return ToolStatus.INVALID_ARGS, f"{STOP_MESSAGE}\n{reasons}", True, errors, None
        msg = f"인자 검사 실패. 아래 칸을 고쳐 다시 부르세요. 값을 짐작하지 마세요.\n{reasons}"
        return ToolStatus.INVALID_ARGS, msg, False, errors, None
