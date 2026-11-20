"""대화에 첫 화면에서 고른 공제 대상 자녀 수 칸(conversations.child_count)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-20

FR-10 첫 화면 설정. 칸 하나만 더한다. 빈 값 허용(고르지 않고 시작할 수 있다).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("child_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "child_count")
