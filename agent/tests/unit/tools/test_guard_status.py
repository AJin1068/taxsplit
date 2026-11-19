"""호출 검사기: 상태 6개마다 일부러 만든 잘못된 호출이 그 상태로 잡힌다."""

import pytest

from taxsplit.tools import ToolStatus
from tools.household_args import household_args

CHECK, COMPARE = "check_eligibility", "compare_allocations"


def test_ok_check_then_compare(guard):
    first = guard.call(CHECK, household_args())
    second = guard.call(COMPARE, household_args())
    assert (first.status, second.status) == (ToolStatus.OK, ToolStatus.OK)
    assert not first.stop and not second.stop


@pytest.mark.parametrize("tool", ["calculate_tax", "check_eligibility_v2", ""])
def test_unknown_tool(guard, tool):
    r = guard.call(tool, household_args())
    assert r.status == ToolStatus.UNKNOWN_TOOL
    assert "check_eligibility" in r.message


@pytest.mark.parametrize("tool", [CHECK, COMPARE])
def test_invalid_args_message_has_path(guard, tool):
    args = household_args()
    args["members"][0]["dependent"]["income_amount"] = "약 300만"
    r = guard.call(tool, args)
    assert r.status == ToolStatus.INVALID_ARGS
    assert "members[0].dependent.income_amount: 정수(원)여야 함" in r.message
    assert r.result is None


def test_invalid_args_beats_order_check(guard):
    # 요건 확인 전이라도 인자가 틀리면 인자 오류를 먼저 알려 준다
    args = household_args()
    del args["husband"]
    assert guard.call(COMPARE, args).status == ToolStatus.INVALID_ARGS


def test_order_violation_compare_first(guard):
    r = guard.call(COMPARE, household_args())
    assert r.status == ToolStatus.ORDER_VIOLATION
    assert "check_eligibility" in r.message and r.result is None


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("members", 0, "dependent", "income_amount"), 30_000_000),
        (("members", 1, "dependent", "birth_year"), 2000),
        (("husband", "gross_salary"), 70_000_000),
    ],
)
def test_order_violation_family_changed(guard, path, value):
    guard.call(CHECK, household_args())
    args = household_args()
    node = args
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    r = guard.call(COMPARE, args)
    assert r.status == ToolStatus.ORDER_VIOLATION
    assert "가족 정보가 바뀌었으니" in r.message


def test_order_violation_member_added(guard):
    guard.call(CHECK, household_args())
    args = household_args()
    dep = {"name": "동생", "relation": "sibling", "birth_year": 2010, "income_amount": 0}
    args["members"].append({"dependent": dep})
    assert guard.call(COMPARE, args).status == ToolStatus.ORDER_VIOLATION


def test_step_limit_ninth_call(guard):
    for _ in range(8):
        guard.call(CHECK, household_args())
    r = guard.call(CHECK, household_args())
    assert r.status == ToolStatus.STEP_LIMIT and r.stop


def test_error_when_handler_raises(guard, monkeypatch):
    from taxsplit.tools import handlers

    def boom(household, rules):
        raise RuntimeError("규칙표 읽기 실패")

    monkeypatch.setitem(handlers.HANDLERS, CHECK, boom)
    r = guard.call(CHECK, household_args())
    assert r.status == ToolStatus.ERROR
    assert "RuntimeError" in r.message and r.result is None


def test_error_does_not_mark_family_checked(guard, monkeypatch):
    from taxsplit.tools import handlers

    monkeypatch.setitem(handlers.HANDLERS, CHECK, lambda h, r: 1 / 0)
    guard.call(CHECK, household_args())
    monkeypatch.undo()
    assert guard.call(COMPARE, household_args()).status == ToolStatus.ORDER_VIOLATION
