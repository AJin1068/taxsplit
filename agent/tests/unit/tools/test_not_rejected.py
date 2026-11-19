"""잡으면 안 되는 것 6가지: 정상 호출을 거절하지 않는다(거짓 거절 0건)."""

from taxsplit.tools import ToolStatus
from tools.household_args import household_args

CHECK, COMPARE = "check_eligibility", "compare_allocations"


def _check_and_compare(guard, args):
    return [guard.call(CHECK, args).status, guard.call(COMPARE, args).status]


def test_no_dependents(guard):
    args = household_args()
    args.update(members=[], medical=[], education=[])
    assert _check_and_compare(guard, args) == [ToolStatus.OK, ToolStatus.OK]


def test_zero_spending(guard):
    args = household_args()
    args["medical"][0]["amount"] = 0
    args["education"][0]["amount"] = 0
    args["cards"] = [{"user": "husband"}, {"user": "wife", "credit": 0}]
    assert _check_and_compare(guard, args) == [ToolStatus.OK, ToolStatus.OK]


def test_large_salary(guard):
    args = household_args()
    args["husband"]["gross_salary"] = 300_000_000
    args["medical"][0]["amount"] = 40_000_000
    assert _check_and_compare(guard, args) == [ToolStatus.OK, ToolStatus.OK]


def test_compare_again_after_amount_change(guard):
    assert _check_and_compare(guard, household_args()) == [ToolStatus.OK, ToolStatus.OK]
    args = household_args()
    args["medical"][0]["amount"] = 4_000_000
    args["cards"][1]["credit"] = 25_000_000
    args["education"] = []
    assert guard.call(COMPARE, args).status == ToolStatus.OK


def test_explicit_zero_income(guard):
    # 기본 가구는 어머니 income_amount=0, 아이 wage_only_gross=0을 직접 적었다
    args = household_args()
    assert args["members"][0]["dependent"]["income_amount"] == 0
    assert _check_and_compare(guard, args) == [ToolStatus.OK, ToolStatus.OK]


def test_check_twice_in_same_turn(guard):
    assert guard.call(CHECK, household_args()).status == ToolStatus.OK
    assert guard.call(CHECK, household_args()).status == ToolStatus.OK
    assert guard.call(COMPARE, household_args()).status == ToolStatus.OK
