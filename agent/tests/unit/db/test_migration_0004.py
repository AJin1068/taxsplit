"""마이그레이션 0004(conversations.child_count 칸): SQL 모양과 SQLite 올리기·내리기·올리기."""

import io
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

AGENT_DIR = Path(__file__).resolve().parents[3]


def _offline_sql(revisions: str, *, downgrade: bool = False) -> str:
    out = io.StringIO()
    cfg = Config(str(AGENT_DIR / "alembic.ini"), output_buffer=out)
    cfg.set_main_option("sqlalchemy.url", "postgresql+asyncpg://x:x@localhost:5432/x")
    cfg.attributes["configure_logger"] = False
    (command.downgrade if downgrade else command.upgrade)(cfg, revisions, sql=True)
    return out.getvalue()


def test_0004_adds_nullable_integer_column_only() -> None:
    sql = _offline_sql("0003:0004")
    assert "ALTER TABLE conversations ADD COLUMN child_count INTEGER;" in sql
    assert "CREATE TABLE" not in sql


def test_0004_downgrade_drops_only_the_column() -> None:
    sql = _offline_sql("0004:0003", downgrade=True)
    assert "ALTER TABLE conversations DROP COLUMN child_count;" in sql
    assert "DROP TABLE" not in sql


def _columns(db: Path) -> set[str]:
    con = sqlite3.connect(db)
    names = {r[1] for r in con.execute("PRAGMA table_info(conversations)")}
    con.close()
    return names


def test_sqlite_upgrade_downgrade_upgrade_0004(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    cfg = Config(str(AGENT_DIR / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db}")
    command.upgrade(cfg, "head")
    assert "child_count" in _columns(db)
    command.downgrade(cfg, "0003")
    cols = _columns(db)
    # 0003의 documents 칸은 그대로 두고 child_count만 지운다
    assert "child_count" not in cols and "documents" in cols
    command.upgrade(cfg, "head")
    assert "child_count" in _columns(db)
