"""질문 표: 21개가 모두 근거 쪽을 가졌고, 근거가 빠진 표는 로더가 거부한다."""

import pytest

from taxsplit.gaps import DETECTORS, GapTableError, load_questions, parse_questions
from taxsplit.gaps.loader import questions_path

HEAD = """
tax_year = 2025
source_doc = "2025년 원천징수의무자를 위한 연말정산 신고안내"
"""
ROW = """
[[question]]
no = 1
id = "gap.example"
kind = "가"
when = "늘"
title = "예시"
why = "이유"
todo = "할 일"
pages = ["10"]
"""
GOOD = HEAD + ROW


def test_table_has_21_items_with_sources():
    table = load_questions(2025)
    assert len(table) == 21
    assert sorted(q.no for q in table.values()) == list(range(1, 22))
    for q in table.values():
        assert q.id.startswith("gap.")
        assert q.pages and all(p.isdigit() for p in q.pages)
        assert q.source_doc == "2025년 원천징수의무자를 위한 연말정산 신고안내"


def test_every_item_has_a_detector():
    assert set(load_questions(2025)) == set(DETECTORS)


def test_year_is_in_file_name_and_field():
    assert questions_path(2025).name == "questions_2025.toml"
    with pytest.raises(GapTableError, match="귀속연도"):
        parse_questions(GOOD, 2024)


def test_good_table_parses():
    assert list(parse_questions(GOOD, 2025)) == ["gap.example"]


@pytest.mark.parametrize(
    ("broken", "match"),
    [
        (GOOD.replace('pages = ["10"]', "pages = []"), "빠진 칸"),
        (GOOD.replace('pages = ["10"]\n', ""), "빠진 칸"),
        (
            GOOD.replace('source_doc = "2025년 원천징수의무자를 위한 연말정산 신고안내"', ""),
            "source_doc",
        ),
        (GOOD.replace('id = "gap.example"', 'id = "2025.medical.x"'), "gap."),
        (GOOD.replace('kind = "가"', 'kind = "라"'), "종류"),
        (GOOD + ROW, "겹침"),
    ],
    ids=["empty_pages", "no_pages", "no_source_doc", "rule_id", "bad_kind", "duplicate"],
)
def test_loader_rejects(broken, match):
    with pytest.raises(GapTableError, match=match):
        parse_questions(broken, 2025)


def test_missing_year_file_rejected():
    with pytest.raises(GapTableError, match="질문 표가 없음"):
        load_questions(2024)
