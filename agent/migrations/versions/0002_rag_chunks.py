"""근거 검색 조각 표(rag_chunks)와 pgvector 확장

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19

Postgres에서는 `vector` 확장을 켜고 embedding 칸을 vector(384)로 만든다.
384 = 설정 기본 모델(intfloat/multilingual-e5-small)의 차원.
모델을 바꿔 차원이 달라지면 새 리비전을 낸다.
SQLite(테스트의 적용·되돌리기 확인)에는 vector 타입이 없어 embedding을 JSON으로 둔다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    is_pg = op.get_context().dialect.name == "postgresql"
    if is_pg:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    embedding_type = Vector(EMBEDDING_DIM) if is_pg else sa.JSON()
    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("tax_year", sa.Integer, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("page", sa.Text, nullable=False),
        sa.Column("print_page", sa.Integer, nullable=True),
        sa.Column("pdf_page", sa.Integer, nullable=True),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
    )
    # 모든 검색이 귀속연도로 먼저 거르므로 연도 색인을 둔다(설계 원칙 3)
    op.create_index("ix_rag_chunks_tax_year", "rag_chunks", ["tax_year"])


def downgrade() -> None:
    # 확장(vector)은 다른 표가 쓸 수 있어 지우지 않는다
    op.drop_index("ix_rag_chunks_tax_year", table_name="rag_chunks")
    op.drop_table("rag_chunks")
