"""채팅 API가 SSE로 보내는 이벤트. 이름·순서는 PR 11(평가)·PR 14a(화면)와의 약속이다(Issue #19).

순서: status(0번 이상) → delta(1번 이상) → gaps(0~1) → allocation(0~1) → evidence(0~1)
→ done(늘 마지막 1번). gaps는 PR 24가 더했다(기존 이벤트 모양은 그대로).
AI 호출이 실패하면: status… → error → done(ended="error")
"""

import json
from dataclasses import dataclass
from typing import Any, Literal

type EventName = Literal["status", "delta", "gaps", "allocation", "evidence", "error", "done"]
# answered: 정상 / guard_stop: 검사기 멈춤 신호·한 턴 AI 호출 수 초과
# sensor_stop: 센서 두 번 실패 / error: AI 호출 실패
type Ended = Literal["answered", "guard_stop", "sensor_stop", "error"]

# 정해진 문구들. 사용자에게 그대로 보인다
SENSOR_STOP_TEXT = (
    "계산 결과와 맞지 않는 내용이 있어 답을 보내지 않았어요. "
    "확인 필요: 같은 질문을 다시 해 주시거나 입력한 정보를 확인해 주세요."
)
# TODO(사람 확인): docs/assumptions.md A-031
GUARD_STOP_TEXT = (
    "입력 값을 확인하지 못해 계산을 멈췄어요. 확인 필요: 가족 정보와 금액을 다시 한 번 알려 주세요."
)

# delta 한 조각의 글자 수(운영값). 센서를 통과한 답을 이 길이로 나눠 보낸다
DELTA_CHARS = 30


@dataclass(frozen=True)
class Event:
    name: EventName
    data: dict[str, Any]

    def to_sse(self) -> str:
        """SSE 한 덩어리: `event: 이름` + `data: JSON` + 빈 줄."""
        body = json.dumps(self.data, ensure_ascii=False)
        return f"event: {self.name}\ndata: {body}\n\n"


def text_chunks(text: str, size: int = DELTA_CHARS) -> list[str]:
    """답을 delta 조각으로 나눈다. 빈 답이어도 조각 하나는 보낸다."""
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def parse_sse(raw: str) -> list[Event]:
    """SSE 글을 이벤트 목록으로(테스트·평가 하네스용)."""
    events = []
    for block in raw.split("\n\n"):
        name = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        if name is not None and data is not None:
            events.append(Event(name, data))  # type: ignore[arg-type]
    return events
