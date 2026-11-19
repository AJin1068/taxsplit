"""도구 호출 기록 1건과 저장소. 칸은 PR 8(#17) `tool_calls` 표와 같은 이름이다.

Postgres에 쓰는 구현은 PR 10이 이 Protocol 모양에 맞춰 붙인다.
"""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from taxsplit.tools.status import ToolStatus


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    # 평가 하네스 단독 실행처럼 대화가 없으면 빈 값
    conversation_id: int | None = None
    # 몇 번째 사용자 메시지에 대한 호출인가
    turn: int
    # 그 턴 안에서 몇 번째 호출인가(거절된 호출도 센다)
    step: int
    tool: str
    # AI가 보낸 그대로. dict가 아닐 수도 있어 Any로 둔다
    args: Any
    status: ToolStatus
    # 검사 실패 이유 목록("칸 경로: 이유")
    errors: list[str] = Field(default_factory=list)
    # 성공했을 때 도구 결과(엔진 출력 그대로)
    result: dict[str, Any] | None = None
    latency_ms: int
    created_at: datetime


class ToolCallRepository(Protocol):
    def add(self, record: ToolCallRecord) -> None: ...

    def list(self, conversation_id: int | None = None) -> list[ToolCallRecord]:
        """conversation_id가 None이면 전부, 아니면 그 대화의 기록만 넣은 순서대로."""
        ...


class InMemoryToolCallRepository:
    """list에 쌓는 구현체. Protocol을 상속하지 않고 메서드 모양만 맞춘다."""

    def __init__(self) -> None:
        self._items: list[ToolCallRecord] = []

    def add(self, record: ToolCallRecord) -> None:
        self._items.append(record)

    def list(self, conversation_id: int | None = None) -> list[ToolCallRecord]:
        if conversation_id is None:
            return list(self._items)
        return [r for r in self._items if r.conversation_id == conversation_id]
