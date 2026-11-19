"""JSON 업로드 길: AI 답과 같은 검사를 거친다."""

import copy
import json

import pytest

from taxsplit.extract import from_json_upload

from .conftest import DOC_NAMES


@pytest.mark.parametrize("name", DOC_NAMES)
def test_answer_json_passes_as_is(name, answers):
    result = from_json_upload(json.dumps(answers[name], ensure_ascii=False))
    assert result.ok and result.fallback is None
    assert result.doc.model_dump() == answers[name]


@pytest.mark.parametrize(
    ("path", "value", "expected_field"),
    [
        (("items", 2, "amount"), -1000, "items[2].amount"),
        (("items", 0, "group"), "보험", "items[0].group"),
        (("items", 1, "person_name"), "", "items[1].person_name"),
        (("tax_year",), "2025", "tax_year"),
    ],
)
@pytest.mark.parametrize("name", DOC_NAMES)
def test_one_wrong_field_is_pointed_out(name, answers, path, value, expected_field):
    data = copy.deepcopy(answers[name])
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result = from_json_upload(data)
    assert not result.ok and result.fallback == "json_upload"
    assert result.errors and all(e.startswith(f"{expected_field}: ") for e in result.errors)


def test_changed_amount_breaks_group_total(answers):
    data = copy.deepcopy(answers["doc1_2025"])
    data["items"][0]["amount"] += 1  # 금액만 바꾸면 그 그룹 합계가 안 맞는다
    result = from_json_upload(data)
    assert not result.ok
    assert len(result.errors) == 1 and "합계가 맞지 않습니다" in result.errors[0]


def test_missing_field_is_pointed_out(answers):
    data = copy.deepcopy(answers["doc1_2025"])
    del data["worker_name"]
    result = from_json_upload(data)
    assert result.errors == ["worker_name: 칸이 없습니다"]
