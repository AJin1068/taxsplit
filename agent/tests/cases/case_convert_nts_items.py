"""국세청 항목 사례(카드 p137, 의료비 p177, 교육비 p185) → 엔진 입력.

항목 사례는 그 항목 계산만 비교한다. 사례에 없는 부양가족 정보(출생연도 등)는
그 항목 결과에 영향이 없는 값으로 채운다.
"""

from typing import Any

from cases.case_convert_items import education_expenses, medical_expenses, nts_card
from taxsplit.engine import Dependent

_ANY_BIRTH_YEAR = 1985
# p177 사례의 지출 대상 → 관계. 나이는 age_note("65세 이상")가 있을 때만 쓴다
_MEDICAL_PEOPLE = {"father": "lineal_ascendant", "mother": "lineal_ascendant", "spouse": "spouse"}
_AGE_NOTES = {"65세 이상": 65}


def _school_level(text: str) -> str:
    """사례의 학교 글자 → 교육 과정."""
    if "대학원" in text:
        return "graduate"
    if "취학 전" in text:
        return "preschool"
    if "대학" in text:
        return "university"
    return "school"


def _medical(inputs: dict) -> tuple[list[Dependent], dict]:
    rows = inputs["expenses"]
    deps = {}
    for row in rows:
        who = row["for"]
        age = _AGE_NOTES.get(row.get("age_note", ""))
        birth = 2025 - age if age is not None else _ANY_BIRTH_YEAR
        if who not in deps or age is not None:
            deps[who] = Dependent(
                name=who,
                relation=_MEDICAL_PEOPLE[who],
                birth_year=birth,
                disabled=row.get("disabled", False),
            )
    return list(deps.values()), {"medical": medical_expenses(rows)}


def _education(inputs: dict) -> tuple[list[Dependent], dict]:
    """같은 관계의 여러 사람(자녀 셋, 처남 둘)을 줄마다 다른 이름으로 나눈다."""
    deps, rows, levels = [], [], {"self": "graduate"}
    for i, row in enumerate(inputs["expenses"]):
        name = "self" if row["for"] == "self" else f"{row.get('label', row['for'])}{i}"
        if name != "self":
            relation = "sibling" if row["for"] == "sibling" else "child"
            age = row.get("age")
            birth = 2025 - age if age is not None else _ANY_BIRTH_YEAR
            deps.append(Dependent(name=name, relation=relation, birth_year=birth))
            levels[name] = _school_level(row["school"])
        rows.append({"for": name, "item": row.get("item", "교육비"), "amount": row["amount"]})
    return deps, {"education": education_expenses(rows, levels)}


def nts_item_inputs(case: dict) -> tuple[str, int, list[Dependent], dict[str, Any]]:
    """(항목 이름, 총급여, 부양가족, 지출 입력)."""
    inputs = case["inputs"]
    group = case["groups"][0]
    gross = inputs.get("gross_salary", 0)
    if group == "card":
        return "card", gross, [], {"card_usage": nts_card(inputs["card_usage"])}
    if group == "medical":
        return ("medical", gross, *_medical(inputs))
    if group == "education":
        return ("education", gross, *_education(inputs))
    raise ValueError(f"모르는 항목 사례 그룹: {group}")
