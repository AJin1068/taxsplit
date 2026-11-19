"""마이그레이션 0002를 DB 없이 SQL 글로 뽑아(`--sql`) vector 확장과 rag_chunks 표를 본다."""

import io
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from taxsplit.core.config import Settings
from taxsplit.rag.pg_store import chunk_table

AGENT_DIR = Path(__file__).resolve().parents[3]


def _config(out: io.StringIO) -> Config:
    cfg = Config(str(AGENT_DIR / "alembic.ini"), output_buffer=out)
    # 접속하지 않는 Postgres 주소. --sql 모드는 SQL 글만 만든다
    cfg.set_main_option("sqlalchemy.url", "postgresql+asyncpg://x:x@localhost:5432/x")
    return cfg


@pytest.fixture(scope="module")
def upgrade_sql() -> str:
    out = io.StringIO()
    command.upgrade(_config(out), "0001:0002", sql=True)
    return out.getvalue()


def _block(sql: str) -> str:
    match = re.search(r"CREATE TABLE rag_chunks \((.*?)\n\);", sql, re.S)
    assert match, "rag_chunks 표가 없음"
    return match.group(1)


def test_vector_extension_before_table(upgrade_sql: str) -> None:
    ext = upgrade_sql.index("CREATE EXTENSION IF NOT EXISTS vector")
    assert ext < upgrade_sql.index("CREATE TABLE rag_chunks")


def test_chunk_table_columns(upgrade_sql: str) -> None:
    block = _block(upgrade_sql)
    assert "embedding VECTOR(384) NOT NULL" in block
    assert "tax_year INTEGER NOT NULL" in block
    assert "PRIMARY KEY (id)" in block
    assert "CREATE INDEX ix_rag_chunks_tax_year ON rag_chunks (tax_year)" in upgrade_sql


def test_migration_matches_store_table(upgrade_sql: str) -> None:
    # 저장소 코드(pg_store.py)가 쓰는 칸과 마이그레이션이 만드는 칸이 같아야 한다
    lines = _block(upgrade_sql).strip().splitlines()
    columns = [line.split()[0] for line in lines if not line.strip().startswith("PRIMARY")]
    assert columns == [c.name for c in chunk_table(384).columns]


def test_dimension_matches_default_setting() -> None:
    assert Settings(_env_file=None).rag_embedding_dim == 384


def test_downgrade_drops_chunk_table() -> None:
    out = io.StringIO()
    command.downgrade(_config(out), "0002:0001", sql=True)
    assert "DROP TABLE rag_chunks;" in out.getvalue()
