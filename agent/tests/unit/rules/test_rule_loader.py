"""로더가 규칙을 어긴 표를 막는지: 잘못된 TOML 조각으로 확인."""

from decimal import Decimal

import pytest

from taxsplit.rules.loader import RuleTableError, load_rules, parse_rules, summary


def _row(
    rule_id="2025.card.threshold",
    year=2025,
    group="card",
    status="sourced",
    statute="조특법 §126의2",
    pages='["p132"]',
    todo="",
):
    todo_line = f'todo = "{todo}"\n' if todo else ""
    return (
        f'[[rule]]\nid = "{rule_id}"\nyear = {year}\ngroup = "{group}"\nsummary = "s"\n'
        f'statute = "{statute}"\npages = {pages}\nstatus = "{status}"\n{todo_line}'
        f'[rule.value]\ngross_rate = "0.25"\n'
    )


def test_valid_row_loads_and_converts_rate():
    rules = parse_rules(_row(), 2025)
    assert rules["2025.card.threshold"].value["gross_rate"] == Decimal("0.25")


def test_duplicate_id_rejected():
    with pytest.raises(RuleTableError, match="중복"):
        parse_rules(_row() + _row(), 2025)


def test_other_year_rejected():
    with pytest.raises(RuleTableError, match="귀속연도"):
        parse_rules(_row(rule_id="2024.card.threshold", year=2024), 2025)


def test_id_must_show_year_and_group():
    with pytest.raises(RuleTableError, match="형식"):
        parse_rules(_row(rule_id="card.threshold"), 2025)
    with pytest.raises(RuleTableError, match="형식"):
        parse_rules(_row(rule_id="2025.medical.threshold"), 2025)


def test_sourced_without_statute_rejected():
    with pytest.raises(RuleTableError, match="조문"):
        parse_rules(_row(statute=""), 2025)


def test_sourced_without_page_rejected():
    with pytest.raises(RuleTableError, match="쪽수"):
        parse_rules(_row(pages="[]"), 2025)


def test_todo_needs_todo_mark():
    with pytest.raises(RuleTableError, match="TODO"):
        parse_rules(_row(status="todo", statute=""), 2025)
    ok = parse_rules(_row(status="todo", statute="", todo="TODO(확인 필요): 조문 없음"), 2025)
    assert ok["2025.card.threshold"].status == "todo"


def test_bad_page_format_rejected():
    with pytest.raises(RuleTableError, match="쪽수 형식"):
        parse_rules(_row(pages='["94쪽"]'), 2025)


def test_unknown_group_and_extra_field_rejected():
    with pytest.raises(RuleTableError):
        parse_rules(_row(rule_id="2025.pension.x", group="pension"), 2025)
    with pytest.raises(RuleTableError):
        parse_rules(_row().replace('summary = "s"', 'summary = "s"\nextra = 1'), 2025)


def test_missing_year_file_rejected():
    with pytest.raises(RuleTableError, match="2026"):
        load_rules(2026)


def test_summary_counts_by_group():
    table = summary(parse_rules(_row(), 2025))
    assert table["card"] == {"sourced": 1, "todo": 0}
    assert table["medical"] == {"sourced": 0, "todo": 0}
