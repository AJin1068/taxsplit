"""Alembic 실행 장치. 온라인(DB에 직접 적용)과 오프라인(`--sql`, SQL 글만 뽑기) 둘 다 된다.

DB 주소는 alembic.ini에 없으면 설정값(DATABASE_URL)에서 읽는다. 테스트는 ini에 주소를 넣어 준다.
"""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from taxsplit.db.tables import metadata

config = context.config


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    from taxsplit.core.config import get_settings

    return get_settings().database_url


def run_migrations_offline() -> None:
    # DB에 붙지 않고 SQL 글만 만든다 (pytest가 이 모드로 표 모양을 검사함)
    context.configure(url=_url(), target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
