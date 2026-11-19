"""홈택스 모의계산 confirmed 사례와 엔진 단계값 비교. 부부를 따로 계산한다.

not_from_this_run 줄(홈택스 결과가 아닌 값)은 비교에서 뺀다.
"""

import pytest

from cases.case_compare import all_rows

SOURCE = "홈택스"
ROWS = [r for r in all_rows() if r.source == SOURCE]
COMPARED = [r for r in ROWS if r.kind == "compare"]


def test_has_comparisons():
    assert COMPARED


def test_not_from_this_run_rows_are_excluded():
    excluded = [r for r in ROWS if r.kind == "excluded"]
    assert excluded and all(r.actual is None for r in excluded)


@pytest.mark.parametrize("row", COMPARED, ids=lambda r: f"{r.case}:{r.stage}")
def test_stage_matches_case(row):
    assert row.actual == row.expected
