"""사례 입력 합치기(case_inputs.py): 보충 입력·공제 대상 여부를 사례 파일에서 읽는지 본다.

Issue #14 정해진 결정(2026-11-18 보충 입력, 2026-11-19 공제 대상 여부).
"""

import copy

import pytest

import cases.case_convert_items as items
from cases.case_compare import all_rows, load_cases
from cases.case_convert import nts_runs
from cases.case_inputs import engine_inputs, set_pointer, usable


def _case(**extra) -> dict:
    base = {
        "id": "fake",
        "inputs": {
            "family": [{"age_note": "60세 이상"}],
            "expenses": [{"a": 1}, {"b": 2}, {"c": 3}],
        },
    }
    return {**base, **extra}


def _sup(status="confirmed", values=None) -> dict:
    values = values or [{"path": "/self/sex", "value": "male"}]
    return {"status": status, "values": values}


def test_supplement_values_are_added_with_missing_parents():
    values = [{"path": "/self/sex", "value": "male"}, {"path": "/family/0/age", "value": 60}]
    merged = engine_inputs(_case(supplement=_sup(values=values)))
    assert merged["self"] == {"sex": "male"}
    assert merged["family"][0] == {"age_note": "60세 이상", "age": 60}


def test_supplement_never_overwrites_document_value():
    doc = {"family": [{"age": 20}]}
    with pytest.raises(ValueError):
        set_pointer(doc, "/family/0/age", 19)


def test_original_case_is_not_changed():
    case = _case(supplement=_sup())
    before = copy.deepcopy(case)
    engine_inputs(case)
    assert case == before


def test_input_filtered_rows_are_dropped_engine_rows_kept():
    rows = [
        {"path": "/expenses/0", "deductible": False, "filtered_by": "input"},
        {"path": "/expenses/1", "deductible": False, "filtered_by": "engine"},
        {"path": "/expenses/2", "deductible": False, "filtered_by": "input"},
    ]
    merged = engine_inputs(_case(eligibility={"status": "confirmed", "rows": rows}))
    # input 줄은 빠지고, engine 줄은 엔진이 0으로 만들도록 남는다
    assert merged["expenses"] == [{"b": 2}]


@pytest.mark.parametrize("section", ["supplement", "eligibility"])
def test_draft_section_makes_case_unusable(section):
    case = _case(**{section: {"status": "draft", "values": [], "rows": []}})
    assert not usable(case)
    with pytest.raises(ValueError):
        engine_inputs(case)


def test_draft_supplement_case_counts_as_missing_input():
    # 진짜 사례 하나를 draft로 바꾸면 그 사례의 기대값 줄이 모두 "입력 부족"이 된다
    case = copy.deepcopy(next(c for _, c in load_cases() if "p097" in c["id"]))
    case["supplement"]["status"] = "draft"
    (run,) = nts_runs(case)
    assert run.worker is None and run.expected == []
    assert run.missing == case["expected"]


def test_no_not_eligible_list_in_test_code():
    # "대상 아님" 판단은 사례 파일(eligibility)에만 둔다
    assert not hasattr(items, "NOT_ELIGIBLE_ITEMS")


def test_confirmed_cases_have_no_missing_input():
    assert [r.case for r in all_rows() if r.kind == "missing_input"] == []
