from dataclasses import replace

from taxsplit.domain.models import Conversation, Message, StoredHousehold


class DuplicateMessageSeq(Exception):
    """같은 대화에 같은 순번 메시지를 또 넣으려 할 때 (DB의 유일 제약과 같은 뜻)."""


class InMemoryConversationRepository:
    """dict에 저장하는 구현체. Protocol을 상속하지 않고 메서드 모양만 맞춘다."""

    def __init__(self) -> None:
        self._items: dict[int, Conversation] = {}
        self._next_id = 1

    async def save(self, conversation: Conversation) -> Conversation:
        if conversation.id is None:
            # 원본을 바꾸지 않고 id만 채운 복사본을 만든다
            conversation = replace(conversation, id=self._next_id)
            self._next_id += 1
        assert conversation.id is not None
        self._items[conversation.id] = conversation
        return conversation

    async def get(self, conversation_id: int) -> Conversation | None:
        return self._items.get(conversation_id)


class InMemoryMessageRepository:
    def __init__(self) -> None:
        self._items: list[Message] = []

    async def add(self, message: Message) -> Message:
        if any(
            m.conversation_id == message.conversation_id and m.seq == message.seq
            for m in self._items
        ):
            raise DuplicateMessageSeq(f"{message.conversation_id}/{message.seq}")
        message = replace(message, id=len(self._items) + 1)
        self._items.append(message)
        return message

    async def list_for(self, conversation_id: int) -> list[Message]:
        found = [m for m in self._items if m.conversation_id == conversation_id]
        return sorted(found, key=lambda m: m.seq)


class InMemoryHouseholdRepository:
    def __init__(self) -> None:
        self._items: dict[int, StoredHousehold] = {}
        self._next_id = 1

    async def save(self, household: StoredHousehold) -> StoredHousehold:
        if household.id is None:
            household = replace(household, id=self._next_id)
            self._next_id += 1
        assert household.id is not None
        self._items[household.id] = household
        return household

    async def get(self, household_id: int) -> StoredHousehold | None:
        return self._items.get(household_id)
