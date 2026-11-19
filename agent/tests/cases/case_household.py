"""홈택스 사례 → 배분 비교 입력(가구 + 배분안). 테스트 쪽에만 둔다(처리 코드는 사례를 읽지 않는다).

사례 하나 = 가구 하나의 배분안 하나. 지출은 사례에서 그 사람이 홈택스에 넣은 쪽을 낸 사람으로 본다.
"""

from dataclasses import dataclass
from functools import cache

from cases.case_compare import load_cases
from cases.case_convert_items import hometax_card
from taxsplit.allocation import (
    CardSpend,
    Earner,
    EducationSpend,
    Household,
    MedicalSpend,
    Member,
    PlanResult,
    evaluate,
)
from taxsplit.engine import Dependent
from taxsplit.rules.loader import load_rules

# 사례에 본인 출생연도가 없을 때 쓰는 값(경로우대 70세 미만이면 결정세액에 영향 없음)
_ANY_BIRTH_YEAR = 1985
_LEVELS = {"preschool": "preschool", "elementary_to_high": "school"}
_SEX = {"husband": "male", "wife": "female"}


@dataclass(frozen=True)
class CasePlan:
    case_id: str
    household: str
    plan: str
    # 사례의 부부 결정세액(not_from_this_run 줄 포함)
    expected: dict[str, int]
    # 홈택스 결과가 아닌 값(문서 근거로 가져온 값)이 있는 사람
    not_run: tuple[str, ...]
    result: PlanResult


def _family(case: dict) -> dict[str, tuple[dict, Member]]:
    family = case["inputs"]["family"]
    out = {}
    for row in family.get("children", []):
        dep = Dependent(name=row["name"], relation="child", birth_year=2025 - row["age"])
        out[row["name"]] = (row, Member(dependent=dep))
    if "mother_in_law" in family:
        row = family["mother_in_law"]
        dep = Dependent(
            name="시어머니",
            relation="lineal_ascendant",
            birth_year=2025 - row["age"],
            income_amount=row.get("income", 0),
        )
        out["시어머니"] = (row, Member(dependent=dep, family_of="husband"))
    return out


def household_of(case: dict) -> tuple[Household, dict[str, str]]:
    """사례 → (가구, 배분안). 배분안은 allocation의 "기본공제" 줄에서 읽는다."""
    family = _family(case)
    medical, education, cards = [], [], []
    earners = {}
    for who in ("husband", "wife"):
        me = case["inputs"][who]
        for amount in me.get("medical", {}).values():
            name = next(n for n, (r, _) in family.items() if r.get("medical") == amount)
            medical.append(MedicalSpend(payer=who, for_whom=name, amount=amount))
        if "medical_paid_but_not_deductible" in me:
            paid = me["medical_paid_but_not_deductible"]
            name = "시어머니" if paid["for"] == "mother_in_law" else paid["for"]
            medical.append(MedicalSpend(payer=who, for_whom=name, amount=paid["amount"]))
        for key, amount in me.get("education", {}).items():
            name = next(
                n for n, (r, _) in family.items() if r.get("education", {}).get("amount") == amount
            )
            education.append(
                EducationSpend(payer=who, for_whom=name, level=_LEVELS[key], amount=amount)
            )
        for c in hometax_card(me.get("card", {})):
            cards.append(CardSpend(user=who, credit=c.credit, cash_debit=c.cash_debit))
        earners[who] = Earner(
            gross_salary=me["gross_salary"],
            sex=_SEX[who],
            birth_year=_ANY_BIRTH_YEAR,
            national_pension=me["national_pension"],
            health_insurance=me["health_insurance"],
            employment_insurance=me["employment_insurance"],
        )
    plan = {
        key.split("(")[0]: who
        for key, who in case["allocation"].items()
        if "기본공제" in key and key.split("(")[0] in family
    }
    house = Household(
        husband=earners["husband"],
        wife=earners["wife"],
        members=tuple(m for _, m in family.values()),
        medical=tuple(medical),
        education=tuple(education),
        cards=tuple(cards),
    )
    return house, plan


@cache
def hometax_plans() -> tuple[CasePlan, ...]:
    rules = load_rules(2025)
    out = []
    for folder, case in load_cases():
        if folder != "hometax-2025":
            continue
        house, plan = household_of(case)
        det = [e for e in case["expected"] if e["stage"] == "determined_tax"]
        out.append(
            CasePlan(
                case_id=case["id"],
                household=case["household"],
                plan=case["plan"],
                expected={e["person"]: e["value"] for e in det},
                not_run=tuple(e["person"] for e in det if e.get("not_from_this_run")),
                result=evaluate(house, plan, rules),
            )
        )
    return tuple(out)
