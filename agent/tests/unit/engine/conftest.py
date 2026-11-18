"""엔진 단위 테스트 공용 준비물. 경계값은 사례가 아니라 규칙표에서 읽는다."""

import pytest

from taxsplit.engine import Rulebook, SelfInfo, WorkerInput
from taxsplit.rules.loader import load_rules


@pytest.fixture(scope="session")
def rules():
    return load_rules(2025)


@pytest.fixture
def book(rules):
    return Rulebook(rules)


@pytest.fixture
def make_worker():
    """기본값: 배우자 있는 남성, 1985년생, 부양가족 없음."""

    def make(gross: int = 0, **kw) -> WorkerInput:
        person = kw.pop("person", SelfInfo(sex="male", birth_year=1985, has_spouse=True))
        return WorkerInput(gross_salary=gross, person=person, **kw)

    return make
