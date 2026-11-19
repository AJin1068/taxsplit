"""국세청 항목 사례(카드 p137, 의료비 p177, 교육비 p185) → 엔진 입력.

항목 사례는 그 항목 계산만 비교한다. 문서에 없는 부양가족 나이·소득은 사례 파일의
보충 입력(supplement)에서 온다. 여기서 값을 채우지 않는다(없으면 KeyError).
"""

from typing import Any

from cases.case_convert_items import education_expenses, medical_expenses, nts_card
from taxsplit.engine import Dependent

# p177 사례의 지출 대상 → 관계
_MEDICAL_PEOPLE = {"father": "lineal_ascendant", "mother": "lineal_ascendant", "spouse": "spouse"}


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
    """지출 대상마다 한 사람. 나이는 그 사람의 지출 줄 중 나이가 적힌 줄(보충 입력)에서 읽는다."""
    rows = inputs["expenses"]
    ages = {}
    for row in rows:
        if "age" in row:
            ages.setdefault(row["for"], row["age"])
    deps = {}
    for row in rows:
        who = row["for"]
        if who not in deps:
            deps[who] = Dependent(
                name=who,
                relation=_MEDICAL_PEOPLE[who],
                birth_year=2025 - ages[who],
                income_amount=inputs["family_income"][who],
                disabled=any(r.get("disabled", False) for r in rows if r["for"] == who),
            )
    return list(deps.values()), {"medical": medical_expenses(rows)}


def _education(inputs: dict) -> tuple[list[Dependent], dict]:
    """같은 관계의 여러 사람(자녀 셋, 처남 둘)을 줄마다 다른 이름으로 나눈다."""
    income = {"child": inputs["children_income"], "sibling": inputs["siblings_income"]}
    deps, rows, levels = [], [], {"self": "graduate"}
    for i, row in enumerate(inputs["expenses"]):
        name = "self" if row["for"] == "self" else f"{row.get('label', row['for'])}{i}"
        if name != "self":
            relation = "sibling" if row["for"] == "sibling" else "child"
            deps.append(
                Dependent(
                    name=name,
                    relation=relation,
                    birth_year=2025 - row["age"],
                    income_amount=income[row["for"]],
                )
            )
            levels[name] = _school_level(row["school"])
        rows.append({"for": name, "item": row.get("item", "교육비"), "amount": row["amount"]})
    return deps, {"education": education_expenses(rows, levels)}


def nts_item_inputs(group: str, inputs: dict) -> tuple[str, int, list[Dependent], dict[str, Any]]:
    """(항목 이름, 총급여, 부양가족, 지출 입력). inputs는 보충 입력을 더한 것."""
    # 총급여는 문서(p137·p177)에 있거나, 없으면 보충 입력의 self.gross_salary(p185)
    gross = inputs["gross_salary"] if "gross_salary" in inputs else inputs["self"]["gross_salary"]
    if group == "card":
        return "card", gross, [], {"card_usage": nts_card(inputs["card_usage"])}
    if group == "medical":
        return ("medical", gross, *_medical(inputs))
    if group == "education":
        return ("education", gross, *_education(inputs))
    raise ValueError(f"모르는 항목 사례 그룹: {group}")
