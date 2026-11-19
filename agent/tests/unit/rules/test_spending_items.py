"""로더가 "공제 대상이 아닌 지출" 항목의 모양을 검사하는지: 잘못된 TOML 조각으로 확인."""

import pytest

from taxsplit.rules.loader import RuleTableError, parse_rules

BASE = (
    '[[rule]]\nid = "2025.medical.rate"\nyear = 2025\ngroup = "medical"\nsummary = "s"\n'
    'statute = "소법 §59의4 ②"\npages = ["p169"]\nstatus = "sourced"\n'
    '[rule.value]\nrate = "0.15"\n'
)


def _rule(items: str, rule_id: str = "2025.medical.excluded_spending") -> str:
    head = (
        f'[[rule]]\nid = "{rule_id}"\nyear = 2025\ngroup = "medical"\nsummary = "s"\n'
        'statute = "소득세법 시행령 제118조의5 제1항"\npages = ["p176"]\nstatus = "sourced"\n'
        '[rule.value]\nused_by = "input_stage"\n'
    )
    return BASE + head + items


def _item(name="보약", kind="exclude", pages='["p176"]', extra=""):
    pages_line = f"pages = {pages}\n" if pages is not None else ""
    return f'[[rule.items]]\nname = "{name}"\nkind = "{kind}"\n{pages_line}{extra}'


def test_valid_items_load():
    rules = parse_rules(_rule(_item() + _item(name="실손", kind="subtract")), 2025)
    items = rules["2025.medical.excluded_spending"].items
    assert [(i.name, i.kind, i.pages) for i in items] == [
        ("보약", "exclude", ("p176",)),
        ("실손", "subtract", ("p176",)),
    ]


def test_item_without_pages_rejected():
    with pytest.raises(RuleTableError, match="pages"):
        parse_rules(_rule(_item(pages=None)), 2025)


def test_item_with_empty_pages_rejected():
    with pytest.raises(RuleTableError, match="쪽수가 없음"):
        parse_rules(_rule(_item(pages="[]")), 2025)


def test_item_with_bad_page_format_rejected():
    with pytest.raises(RuleTableError, match="쪽수 형식"):
        parse_rules(_rule(_item(pages='["176쪽"]')), 2025)


@pytest.mark.parametrize("kind", ["include", "EXCLUDE", ""])
def test_item_kind_outside_three_rejected(kind):
    with pytest.raises(RuleTableError, match="kind"):
        parse_rules(_rule(_item(kind=kind)), 2025)


def test_item_unknown_field_rejected():
    with pytest.raises(RuleTableError, match="page"):
        parse_rules(_rule(_item(extra='page = "p176"\n')), 2025)


def test_item_blank_name_rejected():
    with pytest.raises(RuleTableError, match="이름이 비어"):
        parse_rules(_rule(_item(name=" ")), 2025)


def test_excluded_spending_rule_without_items_rejected():
    with pytest.raises(RuleTableError, match="items가 비어"):
        parse_rules(_rule(""), 2025)


def test_see_must_point_to_existing_rule():
    ok = _item(extra='see = "2025.medical.rate"\n')
    assert parse_rules(_rule(ok), 2025)
    bad = _item(extra='see = "2025.medical.nothing"\n')
    with pytest.raises(RuleTableError, match="see"):
        parse_rules(_rule(bad), 2025)


def test_other_rules_may_have_no_items():
    # 엔진이 읽는 보통 규칙은 items 칸이 없어도 된다
    assert parse_rules(BASE, 2025)["2025.medical.rate"].items == ()
