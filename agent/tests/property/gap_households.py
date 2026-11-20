"""가상 가구(PR 7 synth) → 빈 곳 찾기 입력(가족 목록·간소화 자료·배분 가구).

시드 하나로 "동의한 성인 가족"과 "같이 사는 형제자매·손주", "소득 초과 표시"를 정한다.
19세 미만 자녀 자료는 동의 없이 늘 보인다(인쇄 378쪽).
"""

import random
from dataclasses import dataclass
from typing import Any

from taxsplit.allocation.models import (
    CardSpend,
    EducationSpend,
    Household,
    MedicalSpend,
    Member,
)
from taxsplit.gaps.family import ADULT_AGE, FIRST_IDS
from taxsplit.gaps.models import FamilyAnswer, FamilyMember
from taxsplit.synth import SynthHousehold

YEAR = 2025
# 성인 가족이 동의했을 확률, 형제자매·손주를 더할 확률(가구를 고르게 섞으려는 값, 세법 숫자 아님)
CONSENT_RATIO = 0.5
EXTRA_RATIO = 0.4
OVER_INCOME_RATIO = 0.1


@dataclass(frozen=True)
class GapCase:
    seed: int
    family: FamilyAnswer
    documents: list[dict[str, Any]]
    household: Household


def _earner(w) -> dict[str, Any]:
    return {
        "gross_salary": w.gross_salary,
        "sex": w.person.sex,
        "birth_year": w.person.birth_year,
        "national_pension": w.national_pension,
        "health_insurance": w.health_insurance,
        "employment_insurance": w.employment_insurance,
    }


def _household(hh: SynthHousehold) -> Household:
    members, medical, education, cards = [], [], [], []
    for who in ("husband", "wife"):
        w = hh.worker(who)
        for e in w.medical:
            medical.append(
                MedicalSpend(payer=who, for_whom=_target(e.for_name, who), amount=e.amount)
            )
        for e in w.education:
            target = _target(e.for_name, who)
            education.append(
                EducationSpend(payer=who, for_whom=target, level=e.level, amount=e.amount)
            )
        cards += [CardSpend(user=who, **c.model_dump(exclude={"user"})) for c in w.card_usage]
    for dep, who in zip(hh.dependents, hh.claimants, strict=True):
        family_of = who if dep.relation == "lineal_ascendant" else None
        members.append(Member(dependent=dep, family_of=family_of))
    return Household(
        husband=_earner(hh.husband),
        wife=_earner(hh.wife),
        members=tuple(members),
        medical=tuple(medical),
        education=tuple(education),
        cards=tuple(cards),
    )


def _target(name: str, who: str) -> str:
    return who if name == "self" else name


def _item(group: str, person: str, amount: int) -> dict[str, Any]:
    return {"group": group, "kind": "일반", "person_name": person, "amount": amount}


def make_case(hh: SynthHousehold) -> GapCase:
    rng = random.Random(hh.seed)
    household = _household(hh)
    members: list[FamilyMember] = []
    items: list[dict[str, Any]] = [_item("card", "husband", 1_000), _item("card", "wife", 1_000)]
    for dep in hh.dependents:
        relation = "child" if dep.relation == "child" else "parent"
        adult = YEAR - dep.birth_year >= ADULT_AGE
        over = adult and rng.random() < OVER_INCOME_RATIO
        members.append(
            FamilyMember(
                name=dep.name,
                relation=relation,
                birth_year=dep.birth_year,
                listed_over_income=over,
                disabled_or_severe=dep.disabled,
            )
        )
        # 미성년 자녀는 늘 보이고, 성인은 동의했을 때만 그 사람 이름의 줄이 있다
        if not adult or rng.random() < CONSENT_RATIO:
            for s in (*household.medical, *household.education):
                if s.for_whom == dep.name:
                    group = "medical" if isinstance(s, MedicalSpend) else "education"
                    items.append(_item(group, dep.name, s.amount))
    for i in range(2):
        if rng.random() < EXTRA_RATIO:
            relation = rng.choice(("sibling", "grandchild", "foster_child"))
            lives = rng.choice((True, False, None))
            members.append(
                FamilyMember(
                    name=f"{relation}{i}",
                    relation=relation,
                    birth_year=YEAR - rng.randint(0, 60),
                    lives_with=lives,
                )
            )
    if any(s.for_whom in ("husband", "wife") and s.amount for s in household.medical):
        items.append(_item("medical", "husband", 1_000))
    family = FamilyAnswer(members=tuple(members), answered=FIRST_IDS)
    doc = {"tax_year": YEAR, "worker_name": "husband", "items": items}
    return GapCase(hh.seed, family, [doc], household)
