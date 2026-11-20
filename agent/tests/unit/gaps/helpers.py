"""빈 곳 찾기 테스트용 손으로 만든 가족·간소화 자료(eval/ 사례와 무관)."""

from typing import Any

from taxsplit.allocation.models import Household
from taxsplit.gaps.family import FIRST_IDS
from taxsplit.gaps.models import FamilyAnswer, FamilyMember, GapCard


def m(name: str, relation: str, birth_year: int, **kw: Any) -> FamilyMember:
    return FamilyMember(name=name, relation=relation, birth_year=birth_year, **kw)


def fam(*members: FamilyMember, answered: tuple[str, ...] = FIRST_IDS) -> FamilyAnswer:
    """기본은 첫 질문 묶음에 답을 받은 뒤의 가족."""
    return FamilyAnswer(members=members, answered=answered)


def item(group: str, person: str, kind: str = "일반", amount: int = 100_000) -> dict[str, Any]:
    return {"group": group, "kind": kind, "person_name": person, "amount": amount}


def doc(*items: dict[str, Any], worker: str = "남편") -> dict[str, Any]:
    """간소화 추출 결과 한 부(PR 12 형식). 근로자 본인 카드 한 줄은 늘 있다."""
    return {"tax_year": 2025, "worker_name": worker, "items": [item("card", worker), *items]}


def ids(cards: list[GapCard]) -> list[str]:
    return [c.id for c in cards]


def of(cards: list[GapCard], gap_id: str) -> list[GapCard]:
    return [c for c in cards if c.id == gap_id]


def household(
    *, members: list[dict[str, Any]] = (), medical: list[dict[str, Any]] = (), wife_gross=30_000_000
) -> Household:
    """맞벌이 가구(남편 8,000만 원, 아내 기본 3,000만 원). 부양가족 소득은 0원으로 적는다."""
    return Household.model_validate(
        {
            "husband": {"gross_salary": 80_000_000, "sex": "male", "birth_year": 1980},
            "wife": {"gross_salary": wife_gross, "sex": "female", "birth_year": 1982},
            "members": list(members),
            "medical": list(medical),
        }
    )


def parent(name: str = "엄마", family_of: str = "wife") -> dict[str, Any]:
    return {
        "dependent": {
            "name": name,
            "relation": "lineal_ascendant",
            "birth_year": 1950,
            "income_amount": 0,
        },
        "family_of": family_of,
    }
