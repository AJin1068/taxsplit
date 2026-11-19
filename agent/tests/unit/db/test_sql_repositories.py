"""Postgres 저장소를 SQLite 메모리 DB로 확인한다: 저장 → 읽기 왕복, 없는 id, 순번 중복."""

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from allocation.households import NO_DEPENDENTS
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from taxsplit.db.repositories import (
    SqlConversationRepository,
    SqlHouseholdRepository,
    SqlLlmCallRepository,
    SqlMessageRepository,
)
from taxsplit.db.tables import TOOL_CALL_STATUSES, tool_calls
from taxsplit.domain.models import Conversation, Message, StoredHousehold
from taxsplit.llm.base import CallKind
from taxsplit.llm.call_log import LlmCall

NOW = datetime(2026, 11, 19, 9, 30, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


def _household() -> StoredHousehold:
    return StoredHousehold(
        tax_year=2025, data=NO_DEPENDENTS, source="json", created_at=NOW, updated_at=NOW
    )


# --- households ---


def test_household_roundtrip(engine) -> None:
    repo = SqlHouseholdRepository(engine)
    saved = run(repo.save(_household()))

    assert saved.id is not None
    assert run(repo.get(saved.id)) == saved


def test_household_missing_is_none(engine) -> None:
    assert run(SqlHouseholdRepository(engine).get(999)) is None


def test_household_update_keeps_id(engine) -> None:
    repo = SqlHouseholdRepository(engine)
    saved = run(repo.save(_household()))
    changed = run(repo.save(StoredHousehold(**{**saved.__dict__, "source": "chat"})))

    assert run(repo.get(saved.id)).source == "chat"
    assert changed.id == saved.id


# --- conversations ---


def test_conversation_roundtrip_with_household_and_role(engine) -> None:
    household = run(SqlHouseholdRepository(engine).save(_household()))
    repo = SqlConversationRepository(engine)
    saved = run(
        repo.save(
            Conversation(
                title="첫 상담", created_at=NOW, household_id=household.id, self_role="wife"
            )
        )
    )

    assert saved.id is not None
    assert run(repo.get(saved.id)) == saved


def test_conversation_missing_is_none(engine) -> None:
    assert run(SqlConversationRepository(engine).get(999)) is None


def test_conversation_rejects_unknown_household(engine) -> None:
    repo = SqlConversationRepository(engine)
    with pytest.raises(IntegrityError):
        run(repo.save(Conversation(title="x", created_at=NOW, household_id=999)))


# --- messages ---


def _conversation_id(engine) -> int:
    saved = run(SqlConversationRepository(engine).save(Conversation(title="t", created_at=NOW)))
    assert saved.id is not None
    return saved.id


def test_messages_roundtrip_in_seq_order(engine) -> None:
    cid = _conversation_id(engine)
    repo = SqlMessageRepository(engine)
    second = run(repo.add(Message(cid, 2, "assistant", "남편에게 넣으세요", NOW)))
    first = run(repo.add(Message(cid, 1, "user", "의료비는 누구에게?", NOW)))

    assert run(repo.list_for(cid)) == [first, second]


def test_messages_missing_conversation_is_empty(engine) -> None:
    assert run(SqlMessageRepository(engine).list_for(999)) == []


def test_messages_duplicate_seq_fails(engine) -> None:
    cid = _conversation_id(engine)
    repo = SqlMessageRepository(engine)
    run(repo.add(Message(cid, 1, "user", "a", NOW)))

    with pytest.raises(IntegrityError):
        run(repo.add(Message(cid, 1, "user", "b", NOW)))


# --- llm_calls ---


def test_llm_call_roundtrip(engine) -> None:
    repo = SqlLlmCallRepository(engine)
    call = LlmCall(
        kind=CallKind.MAIN_AGENT,
        provider="anthropic",
        model="claude-sonnet-5-5",
        streamed=True,
        status="ok",
        latency_ms=1234,
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=7,
        cost_usd=Decimal("0.012345"),
        stop_reason="end_turn",
        request_id="req_1",
        created_at=NOW,
    )
    run(repo.add(call))

    assert run(repo.get(call.id)) == call


def test_llm_call_missing_is_none(engine) -> None:
    assert run(SqlLlmCallRepository(engine).get(uuid.uuid4())) is None


# --- tool_calls (저장소는 PR 10. 여기서는 표 모양과 status 제약만) ---


def _tool_call(status: str) -> dict:
    return {
        "id": uuid.uuid4(),
        "conversation_id": None,
        "turn": 1,
        "step": 1,
        "tool": "compare_allocations",
        "args": {"household_id": 1},
        "status": status,
        "errors": None,
        "result": {"ok": True},
        "latency_ms": 12,
        "created_at": NOW,
    }


def test_tool_call_roundtrip_and_status_check(engine) -> None:
    async def go():
        async with engine.begin() as conn:
            for status in TOOL_CALL_STATUSES:
                await conn.execute(insert(tool_calls).values(**_tool_call(status)))
        async with engine.connect() as conn:
            return (await conn.execute(select(tool_calls.c.status, tool_calls.c.args))).all()

    rows = run(go())
    assert sorted(r.status for r in rows) == sorted(TOOL_CALL_STATUSES)
    assert all(r.args == {"household_id": 1} for r in rows)


def test_tool_call_rejects_unknown_status(engine) -> None:
    async def go():
        async with engine.begin() as conn:
            await conn.execute(insert(tool_calls).values(**_tool_call("weird")))

    with pytest.raises(IntegrityError):
        run(go())
