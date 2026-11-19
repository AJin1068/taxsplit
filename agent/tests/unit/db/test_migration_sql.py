"""마이그레이션을 DB 없이 SQL 글로 뽑아(`alembic upgrade head --sql`) Postgres 표 모양을 본다."""

import io
import re
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from taxsplit.db.tables import TOOL_CALL_STATUSES, metadata

AGENT_DIR = Path(__file__).resolve().parents[3]
TABLES = ("households", "conversations", "messages", "tool_calls", "llm_calls")


def _config(out: io.StringIO) -> Config:
    # output_buffer: --sql 모드가 만든 SQL 글을 화면 대신 여기에 쓴다
    cfg = Config(str(AGENT_DIR / "alembic.ini"), output_buffer=out)
    # 접속하지 않는 Postgres 주소. --sql 모드는 SQL 글만 만든다
    cfg.set_main_option("sqlalchemy.url", "postgresql+asyncpg://x:x@localhost:5432/x")
    # pytest의 로그 설정을 alembic.ini가 덮어쓰지 않게 한다
    cfg.attributes["configure_logger"] = False
    return cfg


def _upgrade_sql() -> str:
    out = io.StringIO()
    command.upgrade(_config(out), "head", sql=True)
    return out.getvalue()


def _downgrade_sql() -> str:
    out = io.StringIO()
    command.downgrade(_config(out), "head:base", sql=True)
    return out.getvalue()


@pytest.fixture(scope="module")
def upgrade_sql() -> str:
    return _upgrade_sql()


def _create_block(sql: str, table: str) -> str:
    match = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", sql, re.S)
    assert match, f"{table} 표가 없음"
    return match.group(1)


def test_creates_five_tables(upgrade_sql: str) -> None:
    for table in TABLES:
        _create_block(upgrade_sql, table)


def test_foreign_keys(upgrade_sql: str) -> None:
    assert "REFERENCES households (id)" in _create_block(upgrade_sql, "conversations")
    for table in ("messages", "tool_calls", "llm_calls"):
        assert "REFERENCES conversations (id)" in _create_block(upgrade_sql, table)


def test_message_seq_unique(upgrade_sql: str) -> None:
    assert "UNIQUE (conversation_id, seq)" in _create_block(upgrade_sql, "messages")


def test_tool_call_status_check_has_six_values(upgrade_sql: str) -> None:
    block = _create_block(upgrade_sql, "tool_calls")
    values = ", ".join(f"'{s}'" for s in TOOL_CALL_STATUSES)
    assert f"CHECK (status IN ({values}))" in block
    assert len(TOOL_CALL_STATUSES) == 6


def test_postgres_types(upgrade_sql: str) -> None:
    assert "data JSONB NOT NULL" in _create_block(upgrade_sql, "households")
    assert "cost_usd NUMERIC(12, 6)" in _create_block(upgrade_sql, "llm_calls")
    assert "TIMESTAMP WITH TIME ZONE" in _create_block(upgrade_sql, "messages")


def test_migration_matches_table_definitions(upgrade_sql: str) -> None:
    # db/tables.py(코드가 쓰는 표)와 마이그레이션(DB에 만드는 표)의 칸 이름이 같아야 한다
    for table in TABLES:
        block = _create_block(upgrade_sql, table)
        columns = [line.split()[0] for line in block.strip().splitlines()]
        columns = [c for c in columns if c.islower() and c not in ("constraint",)]
        # 뒤 리비전이 ALTER TABLE로 더한 칸은 CREATE TABLE 뒤에 붙는다
        columns += re.findall(rf"ALTER TABLE {table} ADD COLUMN (\w+)", upgrade_sql)
        assert columns == [c.name for c in metadata.tables[table].columns], table


def test_downgrade_drops_five_tables() -> None:
    sql = _downgrade_sql()
    for table in TABLES:
        assert f"DROP TABLE {table};" in sql


def test_online_upgrade_downgrade_upgrade_on_sqlite(tmp_path: Path) -> None:
    # 실제 DB에 적용·되돌리기·다시 적용이 되는지 SQLite 파일로 본다(Postgres 적용은 맥북에서 사람이)
    cfg = Config(str(AGENT_DIR / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{tmp_path / 'm.db'}")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    con = sqlite3.connect(tmp_path / "m.db")
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert set(TABLES) <= names
