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
