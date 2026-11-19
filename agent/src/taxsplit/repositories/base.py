from typing import Protocol

from taxsplit.domain.models import Conversation, Message, StoredHousehold


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
