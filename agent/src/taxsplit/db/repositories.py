"""Postgres 저장소 4개 (대화·메시지·가구·LLM 호출). 메모리 구현과 같은 메서드 모양이다.

도구 호출(tool_calls) 저장소는 에이전트 루프와 잇는 PR 10(#19)에서 만든다.
"""

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from taxsplit.allocation.models import Household
from taxsplit.db.tables import conversations, households, llm_calls, messages
from taxsplit.domain.models import Conversation, Message, StoredHousehold
from taxsplit.llm.base import CallKind
from taxsplit.llm.call_log import LlmCall


def _utc(value: datetime) -> datetime:
    # SQLite는 시간대를 저장하지 않는다. 우리는 늘 UTC로 넣으므로 읽을 때 UTC를 다시 붙인다
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class SqlConversationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, conversation: Conversation) -> Conversation:
        values: dict[str, Any] = {
            "title": conversation.title,
            "household_id": conversation.household_id,
            "self_role": conversation.self_role,
        }
        # engine.begin(): 블록이 끝나면 커밋, 예외면 롤백
        async with self._engine.begin() as conn:
            if conversation.id is None:
                stmt = insert(conversations).values(
                    **values,
                    created_at=conversation.created_at,
                    updated_at=conversation.created_at,
                )
                new_id = (await conn.execute(stmt.returning(conversations.c.id))).scalar_one()
                return replace(conversation, id=new_id)
            stmt = (
                update(conversations)
                .where(conversations.c.id == conversation.id)
                .values(**values, updated_at=datetime.now(UTC))
            )
            await conn.execute(stmt)
            return conversation

    async def get(self, conversation_id: int) -> Conversation | None:
        async with self._engine.connect() as conn:
            query = select(conversations).where(conversations.c.id == conversation_id)
            row = (await conn.execute(query)).mappings().first()
        if row is None:
            return None
        return Conversation(
            title=row["title"],
            created_at=_utc(row["created_at"]),
            id=row["id"],
            household_id=row["household_id"],
            self_role=row["self_role"],
        )


class SqlMessageRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def add(self, message: Message) -> Message:
        # 같은 대화에 같은 seq면 DB 유일 제약이 IntegrityError를 낸다
        async with self._engine.begin() as conn:
            stmt = insert(messages).values(
                conversation_id=message.conversation_id,
                seq=message.seq,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
            )
            new_id = (await conn.execute(stmt.returning(messages.c.id))).scalar_one()
        return replace(message, id=new_id)

    async def list_for(self, conversation_id: int) -> list[Message]:
        query = (
            select(messages)
            .where(messages.c.conversation_id == conversation_id)
            .order_by(messages.c.seq)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).mappings().all()
        return [
            Message(
                conversation_id=r["conversation_id"],
                seq=r["seq"],
                role=r["role"],
                content=r["content"],
                created_at=_utc(r["created_at"]),
                id=r["id"],
            )
            for r in rows
        ]


class SqlHouseholdRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, household: StoredHousehold) -> StoredHousehold:
        # 가구는 JSON 글자로 바꿔 넣고, 읽을 때 Household로 되살린다
        values = {
            "tax_year": household.tax_year,
            "data": household.data.model_dump(mode="json"),
            "source": household.source,
            "updated_at": household.updated_at,
        }
        async with self._engine.begin() as conn:
            if household.id is None:
                stmt = insert(households).values(**values, created_at=household.created_at)
                new_id = (await conn.execute(stmt.returning(households.c.id))).scalar_one()
                return replace(household, id=new_id)
            stmt = update(households).where(households.c.id == household.id).values(**values)
            await conn.execute(stmt)
            return household

    async def get(self, household_id: int) -> StoredHousehold | None:
        async with self._engine.connect() as conn:
            query = select(households).where(households.c.id == household_id)
            row = (await conn.execute(query)).mappings().first()
        if row is None:
            return None
        return StoredHousehold(
            tax_year=row["tax_year"],
            data=Household.model_validate(row["data"]),
            source=row["source"],
            created_at=_utc(row["created_at"]),
            updated_at=_utc(row["updated_at"]),
            id=row["id"],
        )


class SqlLlmCallRepository:
    """LlmCallRepository(llm/call_log.py)의 Postgres 구현. 대화 id는 PR 10이 잇는다."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def add(self, call: LlmCall) -> None:
        row = {name: getattr(call, name) for name in _LLM_CALL_FIELDS}
        row["kind"] = call.kind.value
        async with self._engine.begin() as conn:
            await conn.execute(insert(llm_calls).values(**row))

    async def get(self, call_id: uuid.UUID) -> LlmCall | None:
        async with self._engine.connect() as conn:
            query = select(llm_calls).where(llm_calls.c.id == call_id)
            row = (await conn.execute(query)).mappings().first()
        if row is None:
            return None
        data = {name: row[name] for name in _LLM_CALL_FIELDS}
        data["kind"] = CallKind(row["kind"])
        data["created_at"] = _utc(row["created_at"])
        return LlmCall(**data)


# LlmCall과 llm_calls 표에 같이 있는 칸 (conversation_id는 표에만 있음)
_LLM_CALL_FIELDS = tuple(c.name for c in llm_calls.columns if c.name != "conversation_id")
