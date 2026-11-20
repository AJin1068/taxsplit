"""도구 호출 기록(tool_calls 표)의 Postgres 저장소. 메모리 구현과 같은 메서드 모양이다."""

from datetime import UTC, datetime

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from taxsplit.db.tables import tool_calls
from taxsplit.tools.records import ToolCallRecord
from taxsplit.tools.status import ToolStatus


def _utc(value: datetime) -> datetime:
    # SQLite는 시간대를 저장하지 않는다. 늘 UTC로 넣으므로 읽을 때 UTC를 다시 붙인다
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class SqlToolCallRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def add_many(self, records: list[ToolCallRecord]) -> None:
        if not records:
            return
        rows = [
            {
                "id": r.id,
                "conversation_id": r.conversation_id,
                "turn": r.turn,
                "step": r.step,
                "tool": r.tool,
                "args": r.args,
                "status": r.status.value,
                "errors": r.errors,
                "result": r.result,
                "latency_ms": r.latency_ms,
                "created_at": r.created_at,
            }
            for r in records
        ]
        # 한 턴의 기록은 한 트랜잭션으로 넣는다(일부만 들어가지 않게)
        async with self._engine.begin() as conn:
            await conn.execute(insert(tool_calls), rows)

    async def list_for(self, conversation_id: int) -> list[ToolCallRecord]:
        query = (
            select(tool_calls)
            .where(tool_calls.c.conversation_id == conversation_id)
            .order_by(tool_calls.c.turn, tool_calls.c.step)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).mappings().all()
        return [
            ToolCallRecord(
                id=r["id"],
                conversation_id=r["conversation_id"],
                turn=r["turn"],
                step=r["step"],
                tool=r["tool"],
                args=r["args"],
                status=ToolStatus(r["status"]),
                errors=r["errors"] or [],
                result=r["result"],
                latency_ms=r["latency_ms"],
                created_at=_utc(r["created_at"]),
            )
            for r in rows
        ]
