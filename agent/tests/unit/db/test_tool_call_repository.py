"""도구 호출 기록 Postgres 저장소(SQLite로)와 llm_calls.conversation_id, conversations.documents."""

import asyncio
import uuid
from datetime import UTC, datetime

from taxsplit.db.repositories import SqlConversationRepository, SqlLlmCallRepository
from taxsplit.db.tool_call_repository import SqlToolCallRepository
from taxsplit.domain.models import Conversation
from taxsplit.llm.base import CallKind
from taxsplit.llm.call_log import LlmCall
from taxsplit.tools.records import ToolCallRecord
from taxsplit.tools.status import ToolStatus

NOW = datetime(2026, 11, 19, 9, 30, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


def _conversation(engine, documents=None) -> int:
    saved = run(
        SqlConversationRepository(engine).save(
            Conversation(title="t", created_at=NOW, documents=documents)
        )
    )
    return saved.id


def _record(cid: int, turn: int, step: int, status: ToolStatus) -> ToolCallRecord:
    return ToolCallRecord(
        conversation_id=cid,
        turn=turn,
        step=step,
        tool="check_eligibility",
        args={"members": [], "bad": "글자"},
        status=status,
        errors=["husband.gross_salary: 정수여야 합니다"] if status != ToolStatus.OK else [],
        result={"rule_ids": ["a"]} if status == ToolStatus.OK else None,
        latency_ms=3,
        created_at=NOW,
    )


def test_tool_call_roundtrip_in_turn_step_order(engine) -> None:
    cid = _conversation(engine)
    other = _conversation(engine)
    repo = SqlToolCallRepository(engine)
    later = _record(cid, 2, 1, ToolStatus.OK)
    first = _record(cid, 1, 1, ToolStatus.INVALID_ARGS)
    run(repo.add_many([later, first]))
    run(repo.add_many([_record(other, 1, 1, ToolStatus.OK)]))
    run(repo.add_many([]))  # 빈 목록은 아무것도 하지 않는다

    assert run(repo.list_for(cid)) == [first, later]
    assert len(run(repo.list_for(other))) == 1


def test_llm_call_keeps_conversation_id(engine) -> None:
    cid = _conversation(engine)
    repo = SqlLlmCallRepository(engine)
    call = LlmCall(
        kind=CallKind.MAIN_AGENT,
        provider="fake",
        model="fake",
        streamed=False,
        status="ok",
        latency_ms=1,
        conversation_id=cid,
        id=uuid.uuid4(),
        created_at=NOW,
    )
    run(repo.add(call))
    assert run(repo.get(call.id)).conversation_id == cid


def test_conversation_documents_roundtrip(engine) -> None:
    docs = [{"tax_year": 2024, "worker_name": "남편", "items": []}]
    repo = SqlConversationRepository(engine)
    assert run(repo.get(_conversation(engine, docs))).documents == docs
    assert run(repo.get(_conversation(engine))).documents is None
