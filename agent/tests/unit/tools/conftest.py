"""도구·호출 검사기 테스트 준비물."""

import pytest

from taxsplit.rules.loader import load_rules
from taxsplit.tools import InMemoryToolCallRepository, ToolCallGuard


@pytest.fixture(scope="session")
def rules():
    return load_rules(2025)


@pytest.fixture
def repo():
    return InMemoryToolCallRepository()


@pytest.fixture
def guard(rules, repo):
    return ToolCallGuard(rules, repo)
