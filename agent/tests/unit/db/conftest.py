import asyncio
from collections.abc import Iterator

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from taxsplit.db.tables import metadata


@pytest.fixture
def engine() -> Iterator[AsyncEngine]:
    # SQLite 메모리 DB. CI에 Postgres가 없어서 저장소 코드는 이걸로 확인한다(Issue #17 정해진 결정)
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")

    # SQLite는 기본으로 FK·CHECK 중 FK를 검사하지 않는다. Postgres와 같게 켠다
    @event.listens_for(eng.sync_engine, "connect")
    def _fk_on(dbapi_conn, _record) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def setup() -> None:
        async with eng.begin() as conn:
            await conn.run_sync(metadata.create_all)

    asyncio.run(setup())
    yield eng
    asyncio.run(eng.dispose())
