"""도구 결과 = 엔진 출력 그대로: 가상 가구 5개로 compare_allocations 직접 호출과 비교."""

import json

import pytest
from allocation.households import HOUSEHOLDS, NOBODY_CLAIMS

from taxsplit.allocation import compare_allocations
from taxsplit.allocation.candidates import candidates
from taxsplit.engine import Rulebook
from taxsplit.tools import ToolStatus

CHECK, COMPARE = "check_eligibility", "compare_allocations"


def _as_args(household) -> dict:
    # AI가 보낸 것처럼 JSON을 한 번 거친 dict(모든 칸이 적혀 있어 소득 명시 검사도 통과)
    return json.loads(household.model_dump_json())


@pytest.mark.parametrize("name", HOUSEHOLDS)
def test_compare_tool_amounts_equal_direct_call(name, guard, rules):
    household = HOUSEHOLDS[name]
    args = _as_args(household)
    assert guard.call(CHECK, args).status == ToolStatus.OK
    r = guard.call(COMPARE, args)
    assert r.status == ToolStatus.OK
    direct = compare_allocations(household, rules)
    assert r.result["best"] == direct.best.model_dump(mode="json")
    assert r.result["common"] == [c.model_dump(mode="json") for c in direct.common]
    assert r.result["headline_saving"] == direct.headline_saving
    assert r.result["plan_count"] == direct.plan_count
    assert r.result["warnings"] == [w.model_dump(mode="json") for w in direct.warnings]
    assert set(direct.best.rule_ids) <= set(r.result["rule_ids"])
    # AI에게 주는 글도 같은 결과다
    assert json.loads(r.message) == r.result


@pytest.mark.parametrize("household", [*HOUSEHOLDS.values(), NOBODY_CLAIMS])
def test_check_tool_equals_candidates(household, guard, rules):
    r = guard.call(CHECK, _as_args(household))
    cands = candidates(household, Rulebook(rules))
    got = {row["name"]: tuple(row["claimable_by"]) for row in r.result["dependents"]}
    assert got == cands
    assert all(row["reason"] for row in r.result["dependents"])
    assert r.result["rule_ids"]


def test_check_tool_gives_reason_when_not_eligible(guard):
    r = guard.call(CHECK, _as_args(NOBODY_CLAIMS))
    rows = r.result["dependents"]
    assert all(not row["eligible"] and row["claimable_by"] == [] for row in rows)
    assert {row["reason"] for row in rows} == {"나이요건 미충족"}
