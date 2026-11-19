"""설정값 storage로 deps.py가 메모리/Postgres 구현을 고르는지 본다 (DB에는 붙지 않음)."""

from collections.abc import Iterator

import pytest

from taxsplit.api import deps
from taxsplit.core.config import get_settings
from taxsplit.db.repositories import SqlConversationRepository, SqlLlmCallRepository
from taxsplit.llm.call_log import InMemoryLlmCallRepository
from taxsplit.repositories.memory import InMemoryConversationRepository

_CACHED = (
    get_settings,
    deps.get_engine,
    deps.get_conversation_repo,
    deps.get_llm_call_repo,
    deps.get_llm_client,
)


@pytest.fixture
def fresh_deps() -> Iterator[None]:
    # lru_cache로 한 번 만든 싱글톤을 비워 바꾼 설정값이 반영되게 한다
    for fn in _CACHED:
        fn.cache_clear()
    yield
    for fn in _CACHED:
        fn.cache_clear()


def test_memory_storage_picks_in_memory(fresh_deps, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE", "memory")

    assert isinstance(deps.get_conversation_repo(), InMemoryConversationRepository)
    assert isinstance(deps.get_llm_call_repo(), InMemoryLlmCallRepository)


def test_postgres_storage_picks_sql(fresh_deps, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@localhost:5432/x")

    assert isinstance(deps.get_conversation_repo(), SqlConversationRepository)
    assert isinstance(deps.get_llm_call_repo(), SqlLlmCallRepository)
    assert deps.get_engine().dialect.name == "postgresql"
