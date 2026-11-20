"""SQL 저장소가 첫 화면 설정(self_role·child_count)을 저장하고 그대로 읽는다."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

from taxsplit.db.repositories import SqlConversationRepository
from taxsplit.domain.models import Conversation

NOW = datetime(2026, 11, 20, tzinfo=UTC)


def test_setup_values_roundtrip_and_update(engine) -> None:
    repo = SqlConversationRepository(engine)

    async def go():
        saved = await repo.save(
            Conversation(title="t", created_at=NOW, self_role="wife", child_count=2)
        )
        first = await repo.get(saved.id)
        await repo.save(replace(saved, child_count=0))
        return first, await repo.get(saved.id)

    first, updated = asyncio.run(go())
    assert first.self_role == "wife" and first.child_count == 2
    # 0명은 "고르지 않음"(None)과 다르게 저장된다
    assert updated.child_count == 0


def test_setup_values_default_to_none(engine) -> None:
    repo = SqlConversationRepository(engine)

    async def go():
        saved = await repo.save(Conversation(title="t", created_at=NOW))
        return await repo.get(saved.id)

    got = asyncio.run(go())
    assert got.self_role is None and got.child_count is None
