"""대화에 간소화 PDF 추출 결과 칸(conversations.documents)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19

표를 새로 만들지 않고 칸 하나만 더한다. 빈 값 허용(추출 결과 없이 대화를 시작할 수 있다).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres에서는 jsonb, SQLite(테스트)에서는 JSON
    op.add_column(
        "conversations",
        sa.Column("documents", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "documents")
