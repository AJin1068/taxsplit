"""재시도와 멈춤, 한 턴 최대 호출 수 경계."""

from taxsplit.tools import STOP_MESSAGE, ToolCallGuard, ToolPolicy, ToolStatus
from tools.household_args import household_args

CHECK, COMPARE = "check_eligibility", "compare_allocations"


def _bad_args() -> dict:
    args = household_args()
    args["wife"]["gross_salary"] = "4천5백"
    return args


def test_two_invalid_then_valid_is_ok(guard):
    for _ in range(2):
        r = guard.call(CHECK, _bad_args())
        assert r.status == ToolStatus.INVALID_ARGS and not r.stop
    assert guard.call(CHECK, household_args()).status == ToolStatus.OK


def test_third_invalid_stops_with_fixed_message(guard):
    guard.call(CHECK, _bad_args())
    guard.call(CHECK, _bad_args())
    r = guard.call(CHECK, _bad_args())
    assert r.status == ToolStatus.INVALID_ARGS and r.stop
    assert r.message.startswith(STOP_MESSAGE)
    assert "wife.gross_salary" in r.message


def test_streak_counts_per_tool(guard):
    # 다른 도구의 실패는 연속 수에 더하지 않는다
    guard.call(CHECK, _bad_args())
    guard.call(CHECK, _bad_args())
    assert not guard.call(COMPARE, _bad_args()).stop


def test_streak_resets_after_valid_call(guard):
    guard.call(CHECK, _bad_args())
    guard.call(CHECK, _bad_args())
    guard.call(CHECK, household_args())
    assert not guard.call(CHECK, _bad_args()).stop


def test_streak_resets_on_next_turn(guard):
    guard.call(CHECK, _bad_args())
    guard.call(CHECK, _bad_args())
    guard.next_turn()
    assert not guard.call(CHECK, _bad_args()).stop


def test_eighth_call_runs_ninth_is_step_limit(guard):
    results = [guard.call(CHECK, household_args()) for _ in range(9)]
    assert [r.status for r in results[:8]] == [ToolStatus.OK] * 8
    assert results[8].status == ToolStatus.STEP_LIMIT and results[8].stop


def test_rejected_calls_count_toward_limit(guard):
    for _ in range(8):
        guard.call("no_such_tool", {})
    assert guard.call(CHECK, household_args()).status == ToolStatus.STEP_LIMIT


def test_next_turn_resets_call_count(guard):
    for _ in range(8):
        guard.call(CHECK, household_args())
    guard.next_turn()
    r = guard.call(COMPARE, household_args())
    # 요건 확인은 지난 턴에 했으므로 순서 위반도 아니다
    assert r.status == ToolStatus.OK and r.record.step == 1 and r.record.turn == 2


def test_policy_values_are_adjustable(rules, repo):
    guard = ToolCallGuard(rules, repo, ToolPolicy(max_calls_per_turn=2, max_invalid_retries=0))
    assert guard.call(CHECK, _bad_args()).stop
    guard.call(CHECK, household_args())
    assert guard.call(CHECK, household_args()).status == ToolStatus.STEP_LIMIT


def test_default_policy():
    assert ToolPolicy() == ToolPolicy(max_calls_per_turn=8, max_invalid_retries=2)
