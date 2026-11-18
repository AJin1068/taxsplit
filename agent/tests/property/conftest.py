"""성질 테스트 준비물: 가구 1,000개를 한 번만 만들고 확인한다. 끝에 표를 출력한다."""

import time

import pytest

from property import report
from property.checks import check_household
from taxsplit.rules.loader import load_rules
from taxsplit.synth import make_households

# 가구 수와 첫 시드. 위반이 나와도 개수를 줄이지 않는다(Issue #16)
N_HOUSEHOLDS = 1_000
BASE_SEED = 0


@pytest.fixture(scope="session")
def rules():
    return load_rules(2025)


@pytest.fixture(scope="session")
def households():
    return make_households(N_HOUSEHOLDS, BASE_SEED)


@pytest.fixture(scope="session")
def violations(households, rules):
    """가구마다 성질 5개를 확인하고, 걸린 시간과 위반 표를 남긴다."""
    start = time.perf_counter()
    found = [v for hh in households for v in check_household(hh, rules)]
    seconds = time.perf_counter() - start
    report.LINES.extend(report.violation_table(found, len(households), seconds))
    report.LINES.append("")
    return found


def pytest_terminal_summary(terminalreporter):
    """성질별 위반 건수 표와 분포 표를 pytest 출력 끝에 붙인다."""
    if report.LINES:
        terminalreporter.section("property report")
        for line in report.LINES:
            terminalreporter.write_line(line)
