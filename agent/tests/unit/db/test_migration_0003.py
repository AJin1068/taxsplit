"""마이그레이션 0003(conversations.documents 칸)과 alembic 로그 줄."""

import io
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

AGENT_DIR = Path(__file__).resolve().parents[3]


def _sql(*revisions: str, downgrade: bool = False) -> str:
    out = io.StringIO()
    cfg = Config(str(AGENT_DIR / "alembic.ini"), output_buffer=out)
    cfg.set_main_option("sqlalchemy.url", "postgresql+asyncpg://x:x@localhost:5432/x")
    cfg.attributes["configure_logger"] = False
    if downgrade:
        command.downgrade(cfg, ":".join(revisions), sql=True)
    else:
        command.upgrade(cfg, ":".join(revisions), sql=True)
    return out.getvalue()


def test_0003_adds_nullable_jsonb_column() -> None:
    sql = _sql("0002", "0003")
    assert "ALTER TABLE conversations ADD COLUMN documents JSONB;" in sql
    # 새 표를 만들지 않는다
    assert "CREATE TABLE" not in sql


def test_0003_downgrade_drops_only_the_column() -> None:
    sql = _sql("0003", "0002", downgrade=True)
    assert "ALTER TABLE conversations DROP COLUMN documents;" in sql
    assert "DROP TABLE" not in sql


def _columns(db: Path) -> set[str]:
    con = sqlite3.connect(db)
    names = {r[1] for r in con.execute("PRAGMA table_info(conversations)")}
    con.close()
    return names


def test_sqlite_upgrade_downgrade_upgrade_0003(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    cfg = Config(str(AGENT_DIR / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db}")
    command.upgrade(cfg, "head")
    assert "documents" in _columns(db)
    command.downgrade(cfg, "0002")
    assert "documents" not in _columns(db)
    command.upgrade(cfg, "head")
    assert "documents" in _columns(db)


def test_alembic_cli_prints_running_upgrade(tmp_path: Path) -> None:
    # 명령줄 alembic이 alembic.ini 로그 설정을 써서 "Running upgrade" 줄을 찍는지(묶음 2 코멘트)
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'cli.db'}"}
    done = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=AGENT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Running upgrade  -> 0001" in done.stderr
    assert "Running upgrade 0002 -> 0003" in done.stderr
