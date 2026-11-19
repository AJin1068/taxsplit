"""국세청 「2025년 원천징수의무자를 위한 연말정산 신고안내」 confirmed 사례와 엔진 단계값 비교.

안 맞으면 테스트 실패로 그대로 둔다(지우거나 건너뛰지 않음). 사례 파일은 고치지 않는다.
"""

import pytest

from cases.case_compare import all_rows, all_runs, load_cases
from taxsplit.engine import compute_tax
from taxsplit.rules.loader import load_rules

SOURCE = "국세청 사례"
COMPARED = [r for r in all_rows() if r.source == SOURCE and r.kind == "compare"]


def test_only_confirmed_cases_are_used():
    cases = load_cases()
    assert cases, "confirmed 사례가 하나도 없음"
    assert all(c["status"] == "confirmed" for _, c in cases)


def test_has_comparisons():
    assert COMPARED


@pytest.mark.parametrize("row", COMPARED, ids=lambda r: f"{r.case}:{r.stage}")
def test_stage_matches_case(row):
    assert row.actual == row.expected


def test_case_rule_ids_exist_in_table():
    # 사례 입력 전부의 결과에 나온 규칙 ID가 규칙표에 있다
    rules = load_rules(2025)
    for _, run in all_runs():
        if run.worker is None:
            continue
        used = compute_tax(run.worker, rules).rules_used
        assert {i for ids in used.values() for i in ids} <= set(rules), run.label


def test_every_stage_is_linked():
    # 사례 단계가 모두 비교·입력으로 씀·범위 밖·제외 중 하나다(엔진 값과 연결 안 된 단계 없음)
    assert [f"{r.case}:{r.stage}" for r in all_rows() if r.kind == "unknown"] == []


def test_determined_tax_compared_for_every_household_run():
    # 결정세액은 가구 사례마다 비교한다(홈택스 가구 2 배분안 B 아내는 제외 줄)
    det = [r for r in all_rows() if r.stage == "determined_tax"]
    assert det and all(r.kind in ("compare", "excluded") for r in det)
