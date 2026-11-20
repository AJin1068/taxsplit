import asyncio

import pytest

from taxsplit.domain.models import ConversationNotFound
from taxsplit.repositories.memory import InMemoryConversationRepository
from taxsplit.services.conversation_service import ConversationService


@pytest.fixture
def service() -> ConversationService:
    return ConversationService(InMemoryConversationRepository())


def test_create_assigns_id(service: ConversationService) -> None:
    conversation = asyncio.run(service.create("hello"))

    assert conversation.id == 1
    assert conversation.title == "hello"


def test_get_returns_created(service: ConversationService) -> None:
    async def go():
        created = await service.create("hello")
        return created, await service.get(1)

    created, fetched = asyncio.run(go())
    assert fetched == created


def test_get_missing_raises(service: ConversationService) -> None:
    with pytest.raises(ConversationNotFound) as exc_info:
        asyncio.run(service.get(999))

    assert exc_info.value.conversation_id == 999


def test_chat_service_create_keeps_setup_values() -> None:
    # 대화 만들기(ChatService.create)가 첫 화면 설정을 저장한다
    from taxsplit.services.chat_service import ChatService

    repo = InMemoryConversationRepository()
    chat = ChatService(repo, None, None, None, {}, None)  # type: ignore[arg-type]
    created = asyncio.run(chat.create("t", [], self_role="husband", child_count=3))
    assert created.self_role == "husband" and created.child_count == 3
    assert asyncio.run(repo.get(created.id)) == created
