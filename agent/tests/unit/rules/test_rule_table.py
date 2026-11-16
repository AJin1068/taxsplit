"""실제 2025년 규칙표 검사: 출처 표시, ID, 연도, 구간표 이음매."""

from decimal import Decimal

import pytest

from taxsplit.rules.loader import GROUPS, TODO_MARK, load_rules, rules_path, summary

# 규칙 ID는 바꾸지 않는다(PR 4~6 결과, PR 13 근거 검색이 이 ID로 조문을 찾는다).
# 이름이 바뀌거나 빠지면 이 테스트가 깨진다.
EXPECTED_IDS = {
    "2025.base.earned_income_deduction",
    "2025.base.tax_rate",
    "2025.base.earned_income_tax_credit",
    "2025.base.earned_income_tax_credit.limit",
    "2025.base.combined_deduction_limit",
    "2025.dependent.basic",
    "2025.dependent.additional.elderly",
    "2025.dependent.additional.disabled",
    "2025.dependent.additional.woman",
    "2025.dependent.additional.single_parent",
    "2025.dependent.judgment_date",
    "2025.dependent.double_claim",
    "2025.child.credit.base",
    "2025.child.credit.birth",
    "2025.medical.threshold",
    "2025.medical.rate",
    "2025.medical.limit.others",
    "2025.medical.sublimit",
    "2025.medical.couple_rule",
    "2025.education.rate",
    "2025.education.limit",
    "2025.education.sublimit",
    "2025.card.threshold",
    "2025.card.rate",
    "2025.card.min_usage_order",
    "2025.card.limit",
    "2025.card.additional_limit",
}


@pytest.fixture(scope="module")
def rules():
    return load_rules(2025)


def test_all_expected_ids_present_and_nothing_else(rules):
    assert set(rules) == EXPECTED_IDS


def test_ids_unique_in_file():
    # 로더는 dict로 모으므로, 파일 글자에서도 한 번 더 센다
    text = rules_path(2025).read_text(encoding="utf-8")
    ids = [line.split('"')[1] for line in text.splitlines() if line.startswith("id = ")]
    assert len(ids) == len(set(ids)) == len(EXPECTED_IDS)


def test_only_year_2025(rules):
    assert {r.year for r in rules.values()} == {2025}
    assert all(r.id.startswith("2025.") for r in rules.values())


def test_every_rule_has_source_or_todo(rules):
    for r in rules.values():
        has_source = bool(r.pages) and bool(r.statute)
        assert has_source or r.todo.startswith(TODO_MARK), r.id
        if r.status == "todo":
            assert r.todo.startswith(TODO_MARK), r.id


def test_every_group_has_rules(rules):
    table = summary(rules)
    assert set(table) == set(GROUPS)
    assert all(c["sourced"] + c["todo"] > 0 for c in table.values())


def test_known_todos(rules):
    # Issue #48 정해진 결정: 조문 확인 필요·책자 안 불일치는 TODO로 둔다
    todos = {r.id for r in rules.values() if r.status == "todo"}
    assert todos == {"2025.base.tax_rate", "2025.child.credit.base", "2025.medical.sublimit"}


def test_rates_are_decimal(rules):
    assert rules["2025.card.threshold"].value["gross_rate"] == Decimal("0.25")
    assert isinstance(rules["2025.dependent.basic"].value["amount"], int)


@pytest.mark.parametrize(
    "rule_id",
    [
        "2025.base.earned_income_deduction",
        "2025.base.tax_rate",
        "2025.base.earned_income_tax_credit",
    ],
)
def test_bracket_seams_continuous(rules, rule_id):
    # 구간표 오타 잡기: 앞 구간을 끝까지 채운 값 = 다음 구간의 base
    brackets = rules[rule_id].value["brackets"]
    assert brackets[0]["over"] == 0 and brackets[0]["base"] == 0
    for prev, nxt in zip(brackets, brackets[1:], strict=False):
        assert nxt["over"] > prev["over"]
        assert prev["base"] + (nxt["over"] - prev["over"]) * prev["rate"] == nxt["base"], nxt


def test_tax_credit_limit_segments_continuous(rules):
    # 한도 = max(floor, base - (총급여 - over) × slope). 앞 구간 끝 값 = 다음 구간 base
    segs = rules["2025.base.earned_income_tax_credit.limit"].value["segments"]
    for prev, nxt in zip(segs, segs[1:], strict=False):
        end = max(prev["floor"], prev["base"] - (nxt["over"] - prev["over"]) * prev["slope"])
        assert end == nxt["base"], nxt
    assert [s["floor"] for s in segs] == [740_000, 660_000, 500_000, 200_000]
