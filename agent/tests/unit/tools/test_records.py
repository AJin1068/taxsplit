"""호출마다 기록 1건, 칸은 PR 8 tool_calls 표와 같다."""

from uuid import UUID

from taxsplit.tools import (
    InMemoryToolCallRepository,
    ToolCallGuard,
    ToolCallRecord,
    ToolStatus,
)
from tools.household_args import household_args

CHECK, COMPARE = "check_eligibility", "compare_allocations"
FIELDS = {
    "id",
    "conversation_id",
    "turn",
    "step",
    "tool",
    "args",
    "status",
    "errors",
    "result",
    "latency_ms",
    "created_at",
}


def test_record_fields_match_tool_calls_table():
    assert set(ToolCallRecord.model_fields) == FIELDS


def test_one_record_per_call(guard, repo):
    bad = household_args()
    bad["wife"]["gross_salary"] = "모름"
    guard.call("nope", {})
    guard.call(COMPARE, household_args())
    guard.call(CHECK, bad)
    guard.call(CHECK, household_args())
    guard.call(COMPARE, household_args())
    records = repo.list()
    assert [r.status for r in records] == [
        ToolStatus.UNKNOWN_TOOL,
        ToolStatus.ORDER_VIOLATION,
        ToolStatus.INVALID_ARGS,
        ToolStatus.OK,
        ToolStatus.OK,
    ]
    assert [r.step for r in records] == [1, 2, 3, 4, 5]
    assert len({r.id for r in records}) == 5


def test_record_contents(guard, repo):
    bad = household_args()
    bad["wife"]["gross_salary"] = "모름"
    guard.call(CHECK, bad)
    ok = guard.call(CHECK, household_args()).record
    failed = repo.list()[0]
    # AI가 보낸 그대로의 인자를 남긴다(고치지 않음)
    assert failed.args == bad and failed.result is None
    assert failed.errors and failed.errors[0].startswith("wife.gross_salary: 정수(원)여야 함")
    assert ok.errors == [] and ok.result is not None
    assert isinstance(ok.id, UUID) and ok.created_at.tzinfo is not None
    assert ok.latency_ms >= 0 and ok.turn == 1 and ok.conversation_id is None


def test_record_serializes_to_json(guard):
    rec = guard.call(CHECK, household_args()).record
    data = rec.model_dump(mode="json")
    assert data["status"] == "ok" and set(data) == FIELDS


def test_conversation_id_and_list_filter(rules):
    repo = InMemoryToolCallRepository()
    ToolCallGuard(rules, repo, conversation_id=7).call(CHECK, household_args())
    ToolCallGuard(rules, repo).call(CHECK, household_args())
    assert len(repo.list()) == 2
    assert [r.conversation_id for r in repo.list(7)] == [7]
