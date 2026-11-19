"""검사 규칙: 잡아야 할 것과 잡으면 안 되는 것."""

from taxsplit.extract.validate import check_doc, strip_fence


def _doc(items, totals=None, year=2025):
    return {"tax_year": year, "worker_name": "가", "items": items, "totals": totals or []}


def _item(amount, name="가", group="medical", mark="none"):
    return {"group": group, "kind": "일반", "person_name": name, "amount": amount, "mark": mark}


def test_total_mismatch_reports_group_in_korean():
    doc, errors = check_doc(_doc([_item(100)], [{"group": "medical", "amount": 300}]))
    assert doc is None
    assert errors == [
        "totals[0].amount: 의료비 합계가 맞지 않습니다(PDF 합계 300원, 항목 합 100원)"
    ]


def test_no_total_is_not_a_failure():
    doc, errors = check_doc(_doc([_item(100), _item(200)]))
    assert errors == [] and doc is not None


def test_zero_amount_line_passes():
    doc, errors = check_doc(_doc([_item(0)], [{"group": "medical", "amount": 0}]))
    assert errors == [] and doc.items[0].amount == 0


def test_same_person_same_amount_lines_are_kept_apart():
    doc, errors = check_doc(_doc([_item(500), _item(500)], [{"group": "medical", "amount": 1000}]))
    assert errors == [] and len(doc.items) == 2


def test_subtract_line_is_not_in_group_total():
    items = [_item(1000), _item(400, mark="subtract")]
    doc, errors = check_doc(_doc(items, [{"group": "medical", "amount": 1000}]))
    assert errors == [] and doc is not None


def test_negative_amount_points_to_field():
    _, errors = check_doc(_doc([_item(100), _item(-5)]))
    assert errors == ["items[1].amount: 0 이상이어야 합니다"]


def test_blank_person_name_points_to_field():
    _, errors = check_doc(_doc([_item(100, name="  ")]))
    assert errors == ["items[0].person_name: 비어 있으면 안 됩니다"]


def test_broken_json_reason_in_korean():
    _, errors = check_doc('{"tax_year": 2025,')
    assert len(errors) == 1 and errors[0].startswith("(전체): JSON 형식이 깨졌습니다")


def test_top_level_must_be_object():
    _, errors = check_doc("[1, 2]")
    assert errors == ["(전체): JSON 최상위가 객체({…})여야 합니다"]


def test_code_fence_is_stripped():
    assert strip_fence('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_fence('{"a": 1}') == '{"a": 1}'


def test_prior_year_is_set_by_code_not_by_input():
    doc, _ = check_doc({**_doc([]), "prior_year": True})
    assert doc.prior_year is False and doc.notes == []
