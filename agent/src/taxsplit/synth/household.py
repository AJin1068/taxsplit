"""시드로 맞벌이 가상 가구를 만든다(PR 7).

같은 시드면 언제나 같은 가구가 나온다. `random.Random(seed)` 하나로만 고르기 때문이다.
요건(나이·소득)을 일부러 넘는 부양가족도 섞여 나온다. 요건 판정은 엔진이 한다.
"""

import random
from dataclasses import dataclass
from typing import Literal

from taxsplit.engine import (
    CardUsage,
    Dependent,
    EducationExpense,
    MedicalExpense,
    SelfInfo,
    WorkerInput,
)
from taxsplit.synth import ranges as R

Spouse = Literal["husband", "wife"]
SPOUSES: tuple[Spouse, Spouse] = ("husband", "wife")


@dataclass(frozen=True)
class SynthHousehold:
    """가상 가구 하나. 부양가족은 claimants에 적힌 사람(남편/아내)이 공제받는다."""

    seed: int
    husband: WorkerInput
    wife: WorkerInput
    dependents: tuple[Dependent, ...]
    claimants: tuple[Spouse, ...]

    def worker(self, who: Spouse) -> WorkerInput:
        return self.husband if who == "husband" else self.wife


def _amount(rng: random.Random, top: int, unit: int = R.AMOUNT_UNIT) -> int:
    """0~top 사이 금액을 unit 단위로 고른다."""
    return rng.randint(0, top // unit) * unit


def _split(rng: random.Random, total: int, parts: int) -> list[int]:
    """total을 무작위 비율로 parts칸에 나눈다(1,000원 단위, 합은 total 이하)."""
    weights = [rng.random() for _ in range(parts)]
    whole = sum(weights) or 1.0
    return [int(total * w / whole) // R.AMOUNT_UNIT * R.AMOUNT_UNIT for w in weights]


def _income(rng: random.Random) -> dict[str, int | None]:
    # 70%는 소득 없음. 나머지는 요건을 넘는 경우가 섞이도록 넓게 고른다
    if rng.random() < R.NO_INCOME_RATIO:
        return {"income_amount": 0, "wage_only_gross": None}
    amount = _amount(rng, R.INCOME_MAX)
    if rng.random() < R.WAGE_ONLY_RATIO:
        return {"income_amount": 0, "wage_only_gross": amount}
    return {"income_amount": amount, "wage_only_gross": None}


def _dependents(rng: random.Random) -> tuple[Dependent, ...]:
    """자녀 0~3명, 부모 0~2명(합계 최대 4명). 자녀는 나이 많은 순서로 이름을 붙인다."""
    n_child = rng.randint(0, R.CHILDREN_MAX)
    n_parent = rng.randint(0, min(R.PARENTS_MAX, R.DEPENDENTS_MAX - n_child))
    child_ages = sorted((rng.randint(*R.CHILD_AGE) for _ in range(n_child)), reverse=True)
    out = []
    for i, age in enumerate(child_ages):
        out.append(
            Dependent(
                name=f"자녀{i + 1}",
                relation="child",
                birth_year=R.YEAR - age,
                disabled=rng.random() < R.DISABLED_RATIO,
                # 그 해 태어난 자녀는 몇째인지 적는다(출산·입양 세액공제 입력)
                birth_or_adoption_order=i + 1 if age == 0 else None,
                **_income(rng),
            )
        )
    for i in range(n_parent):
        out.append(
            Dependent(
                name=f"부모{i + 1}",
                relation="lineal_ascendant",
                birth_year=R.YEAR - rng.randint(*R.PARENT_AGE),
                disabled=rng.random() < R.DISABLED_RATIO,
                **_income(rng),
            )
        )
    return tuple(out)


def _school_level(age: int) -> str:
    if age <= R.PRESCHOOL_MAX_AGE:
        return "preschool"
    return "school" if age <= R.SCHOOL_MAX_AGE else "university"


def _card(rng: random.Random, gross: int) -> tuple[CardUsage, ...]:
    """총급여의 0~70%를 신용·현금체크·문화체육·전통시장·대중교통에 나눈다."""
    total = int(gross * rng.uniform(0, R.CARD_GROSS_RATIO_MAX))
    credit, cash, culture, market, transit = _split(rng, total, len(R.CARD_KINDS))
    culture_credit = int(culture * rng.random()) // R.AMOUNT_UNIT * R.AMOUNT_UNIT
    return (
        CardUsage(
            credit=credit,
            cash_debit=cash,
            culture_credit=culture_credit,
            culture_cash_debit=culture - culture_credit,
            market=market,
            transit=transit,
        ),
    )


def _worker(rng: random.Random, sex: Literal["male", "female"]) -> dict:
    """부부 한 사람의 기본 입력(부양가족·부양가족 지출 제외)."""
    gross = rng.randint(R.GROSS_MIN // R.GROSS_UNIT, R.GROSS_MAX // R.GROSS_UNIT) * R.GROSS_UNIT
    insurance = int(gross * rng.uniform(0, R.INSURANCE_GROSS_RATIO_MAX))
    pension, health, employment = _split(rng, insurance, 3)
    education = []
    if rng.random() < R.SELF_EDUCATION_RATIO:
        education.append(
            EducationExpense(level="university", amount=_amount(rng, R.SELF_EDUCATION_MAX))
        )
    return {
        "gross_salary": gross,
        "person": SelfInfo(
            sex=sex, birth_year=R.YEAR - rng.randint(*R.WORKER_AGE), has_spouse=True
        ),
        "national_pension": pension,
        "health_insurance": health,
        "employment_insurance": employment,
        "medical": [MedicalExpense(amount=_amount(rng, R.MEDICAL_MAX))],
        "education": education,
        "card_usage": _card(rng, gross),
        "dependents": [],
    }


def make_household(seed: int) -> SynthHousehold:
    """시드 하나로 가구 하나. 부양가족과 그 의료비·교육비는 정해진 공제자에게 붙는다."""
    rng = random.Random(seed)
    parts = {"husband": _worker(rng, "male"), "wife": _worker(rng, "female")}
    deps = _dependents(rng)
    claimants: list[Spouse] = []
    for dep in deps:
        who = rng.choice(SPOUSES)
        claimants.append(who)
        part = parts[who]
        part["dependents"].append(dep)
        part["medical"].append(
            MedicalExpense(for_name=dep.name, amount=_amount(rng, R.MEDICAL_MAX))
        )
        if dep.relation == "child":
            level = _school_level(R.YEAR - dep.birth_year)
            amount = _amount(rng, R.CHILD_EDUCATION_MAX)
            part["education"].append(
                EducationExpense(for_name=dep.name, level=level, amount=amount)
            )
    workers = {
        who: WorkerInput(**{k: tuple(v) if isinstance(v, list) else v for k, v in part.items()})
        for who, part in parts.items()
    }
    return SynthHousehold(
        seed=seed,
        husband=workers["husband"],
        wife=workers["wife"],
        dependents=deps,
        claimants=tuple(claimants),
    )


def make_households(n: int, seed: int = 0) -> list[SynthHousehold]:
    """가구 n개. i번째 가구의 시드는 seed + i라, 어긴 가구를 시드 하나로 다시 만든다."""
    return [make_household(seed + i) for i in range(n)]
