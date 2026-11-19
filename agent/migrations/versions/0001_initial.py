"""표 5개: 가구, 대화, 메시지, 도구 호출, LLM 호출

Revision ID: 0001
Revises:
Create Date: 2026-11-19

마이그레이션은 그 시점 모양을 얼려 두는 것이라 db/tables.py를 import하지 않고 손으로 적는다.
둘이 어긋나지 않는지는 tests/unit/db/test_migration_sql.py가 본다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PR 9(#18)와 같은 도구 호출 상태 6개
_TOOL_CALL_STATUSES = (
    "ok",
    "invalid_args",
    "order_violation",
    "unknown_tool",
    "step_limit",
    "error",
)

_JSON = sa.JSON().with_variant(JSONB(), "postgresql")
_BIGID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("id", _BIGID, primary_key=True, autoincrement=True),
        sa.Column("tax_year", sa.Integer, nullable=False),
        sa.Column("data", _JSON, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_table(
        "conversations",
        sa.Column("id", _BIGID, primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("household_id", _BIGID, sa.ForeignKey("households.id"), nullable=True),
        sa.Column("self_role", sa.Text, nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_table(
        "messages",
        sa.Column("id", _BIGID, primary_key=True, autoincrement=True),
        sa.Column("conversation_id", _BIGID, sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        _ts("created_at"),
        sa.UniqueConstraint("conversation_id", "seq", name="uq_messages_conversation_seq"),
    )
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("conversation_id", _BIGID, sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("turn", sa.Integer, nullable=False),
        sa.Column("step", sa.Integer, nullable=False),
        sa.Column("tool", sa.Text, nullable=False),
        sa.Column("args", _JSON, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("errors", _JSON, nullable=True),
        sa.Column("result", _JSON, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        _ts("created_at"),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in _TOOL_CALL_STATUSES) + ")",
            name="ck_tool_calls_status",
        ),
    )
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("conversation_id", _BIGID, sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("streamed", sa.Boolean, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("cache_creation_input_tokens", sa.Integer, nullable=False),
        sa.Column("cache_read_input_tokens", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("stop_reason", sa.Text, nullable=True),
        sa.Column("error_type", sa.Text, nullable=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("request_id", sa.Text, nullable=True),
        _ts("created_at"),
    )


def downgrade() -> None:
    # FK가 가리키는 쪽을 나중에 지운다
    for name in ("llm_calls", "tool_calls", "messages", "conversations", "households"):
        op.drop_table(name)
