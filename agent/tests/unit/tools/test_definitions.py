"""도구 정의: 이름 3개(PR 9 두 개 + PR 24 빈 곳 찾기), JSON 직렬화, 스키마에 부양가족 소득 칸."""

import json

from taxsplit.tools import TOOL_NAMES, tool_definitions


def test_two_tools_in_call_order():
    # PR 9의 두 도구는 부르는 순서(요건 확인 → 배분 비교) 그대로 앞에 있다
    names = [d.name for d in tool_definitions()]
    assert names[:2] == ["check_eligibility", "compare_allocations"]
    assert TOOL_NAMES[:2] == ("check_eligibility", "compare_allocations")


def test_find_missing_deductions_added_with_own_schema():
    names = [d.name for d in tool_definitions()]
    assert names == [*TOOL_NAMES] and names[2] == "find_missing_deductions"
    schema = tool_definitions()[2].input_schema
    assert {"family", "household", "picks"} <= set(schema["properties"])
    assert schema["required"] == ["family"]


def test_definitions_serialize_to_json():
    for d in tool_definitions():
        data = json.loads(json.dumps(d.model_dump(), ensure_ascii=False))
        assert data["name"] == d.name
        assert data["description"]
        assert data["input_schema"]["type"] == "object"


def test_schema_has_dependent_income_fields():
    schema = tool_definitions()[0].input_schema
    dependent = schema["$defs"]["Dependent"]["properties"]
    assert "income_amount" in dependent
    assert "wage_only_gross" in dependent
    assert {"husband", "wife"} <= set(schema["required"])


def test_description_asks_for_income():
    for d in tool_definitions():
        assert "income_amount" in d.description
        assert "사용자에게 묻는다" in d.description
