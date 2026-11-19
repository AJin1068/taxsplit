"""Postgres 표 5개 정의 (SQLAlchemy Core). 마이그레이션 0001과 같은 모양이어야 한다.

테스트는 Postgres 없이 SQLite로 돌기 때문에 칸 타입은 두 DB에서 다 되는 모양을 쓴다.
"""

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

# 도구 호출 결과 상태 6개 (PR 9 #18과 같은 값). DB 제약으로 이 값만 받는다
TOOL_CALL_STATUSES = (
    "ok",
    "invalid_args",  # 인자 검사 실패
    "order_violation",  # 요건 확인 전 계산 등 순서 위반
    "unknown_tool",
    "step_limit",  # 최대 호출 수 초과로 거절
    "error",  # 도구 실행 중 예외
)

# Postgres에서는 jsonb, SQLite에서는 JSON
Json = JSON().with_variant(JSONB(), "postgresql")
# SQLite는 INTEGER PRIMARY KEY만 자동 번호를 붙이므로 SQLite에서만 Integer로 바꾼다
BigId = BigInteger().with_variant(Integer(), "sqlite")


def _ts(name: str) -> Column:
    return Column(name, DateTime(timezone=True), nullable=False)


metadata = MetaData()

households = Table(
    "households",
    metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("tax_year", Integer, nullable=False),
    # 배분 비교 입력 Household를 model_dump(mode="json")한 것
    Column("data", Json, nullable=False),
    Column("source", Text, nullable=False),
    _ts("created_at"),
    _ts("updated_at"),
)

conversations = Table(
    "conversations",
    metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("title", Text, nullable=False),
    Column("household_id", BigId, ForeignKey("households.id"), nullable=True),
    Column("self_role", Text, nullable=True),
    _ts("created_at"),
    _ts("updated_at"),
)

messages = Table(
    "messages",
    metadata,
    Column("id", BigId, primary_key=True, autoincrement=True),
    Column("conversation_id", BigId, ForeignKey("conversations.id"), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    _ts("created_at"),
    UniqueConstraint("conversation_id", "seq", name="uq_messages_conversation_seq"),
)

tool_calls = Table(
    "tool_calls",
    metadata,
    Column("id", Uuid, primary_key=True),
    # 평가 하네스 단독 실행이면 대화가 없다
    Column("conversation_id", BigId, ForeignKey("conversations.id"), nullable=True),
    Column("turn", Integer, nullable=False),  # 몇 번째 사용자 메시지에 대한 호출인가
    Column("step", Integer, nullable=False),  # 그 턴 안 몇 번째 호출인가
    Column("tool", Text, nullable=False),
    Column("args", Json, nullable=False),  # 모델이 보낸 그대로
    Column("status", Text, nullable=False),
    Column("errors", Json, nullable=True),
    Column("result", Json, nullable=True),
    Column("latency_ms", Integer, nullable=False),
    _ts("created_at"),
    CheckConstraint(
        "status IN (" + ", ".join(f"'{s}'" for s in TOOL_CALL_STATUSES) + ")",
        name="ck_tool_calls_status",
    ),
)

# llm/call_log.py의 LlmCall 칸 그대로 + conversation_id. 프롬프트·답 본문은 넣지 않는다
llm_calls = Table(
    "llm_calls",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("conversation_id", BigId, ForeignKey("conversations.id"), nullable=True),
    Column("kind", Text, nullable=False),
    Column("provider", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("streamed", Boolean, nullable=False),
    Column("status", Text, nullable=False),
    Column("latency_ms", Integer, nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cache_creation_input_tokens", Integer, nullable=False),
    Column("cache_read_input_tokens", Integer, nullable=False),
    Column("cost_usd", Numeric(12, 6), nullable=True),
    Column("stop_reason", Text, nullable=True),
    Column("error_type", Text, nullable=True),
    Column("status_code", Integer, nullable=True),
    Column("request_id", Text, nullable=True),
    _ts("created_at"),
)
