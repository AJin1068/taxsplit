from typing import Protocol

from taxsplit.domain.models import Conversation, Message, StoredHousehold
from taxsplit.tools.records import ToolCallRecord


class ConversationRepository(Protocol):
    async def save(self, conversation: Conversation) -> Conversation:
        """id가 없으면 새 id를 붙여 저장하고, id가 채워진 객체를 돌려준다."""
        ...

    async def get(self, conversation_id: int) -> Conversation | None: ...


class MessageRepository(Protocol):
    async def add(self, message: Message) -> Message:
        """메시지를 더한다. 같은 대화에 같은 seq가 있으면 예외를 낸다."""
        ...

    async def list_for(self, conversation_id: int) -> list[Message]:
        """seq 순서로 돌려준다."""
        ...


class HouseholdRepository(Protocol):
    async def save(self, household: StoredHousehold) -> StoredHousehold: ...

    async def get(self, household_id: int) -> StoredHousehold | None: ...


class AsyncToolCallRepository(Protocol):
    """도구 호출 기록 저장소(비동기). 에이전트 루프가 턴 동안 모아 두었다가 턴 끝에 한꺼번에 넣는다.

    검사기(tools/guard.py)는 동기 저장소(tools/records.py)에 쓰고, 루프가 그 목록을 여기로 옮긴다.
    """

    async def add_many(self, records: list[ToolCallRecord]) -> None: ...

    async def list_for(self, conversation_id: int) -> list[ToolCallRecord]:
        """그 대화의 기록을 (턴, 순번) 순서로."""
        ...
