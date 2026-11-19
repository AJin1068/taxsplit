"""배분 비교 테스트 준비물과, 끝난 뒤 가상 가구 5개 표 출력(uv run pytest tests/unit/allocation)."""

import time

import pytest

from allocation.households import HOUSEHOLDS
from taxsplit.allocation import compare_allocations
from taxsplit.rules.loader import load_rules

_NAMES = {"husband": "남", "wife": "아"}


@pytest.fixture(scope="session")
def rules():
    return load_rules(2025)


def plan_label(assignment: dict) -> str:
    """배분안을 "큰아이→남, 작은아이→아"처럼 짧게. 부양가족 없으면 "-"."""
    return ", ".join(f"{n}→{_NAMES[w]}" for n, w in assignment.items()) or "-"


def pytest_terminal_summary(terminalreporter):
    rules = load_rules(2025)
    tr = terminalreporter
    tr.section("가상 가구 5개 배분 비교 (PR 6)")
    tr.write_line("| 가구 | 안 수 | 최적안 | 최적 합계 | A 합계 | A 차이 | B 합계 | B 차이 | 초 |")
    tr.write_line("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, household in HOUSEHOLDS.items():
        start = time.perf_counter()
        r = compare_allocations(household, rules)
        sec = time.perf_counter() - start
        a, b = r.common
        tr.write_line(
            f"| {name} | {r.plan_count} | {plan_label(r.best.assignment)} | {r.best.total:,} "
            f"| {a.plan.total:,} | {a.saving:,} | {b.plan.total:,} | {b.saving:,} | {sec:.2f} |"
        )
