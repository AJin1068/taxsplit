"""사례 파일 inputs → 엔진 입력 변환. 테스트 쪽에만 둔다(처리 코드는 사례 파일을 읽지 않는다).

문서에 없는 값(본인 성별·출생연도·총급여, 범위로만 적힌 나이 등)은 테스트가 채우지 않는다.
사례 파일의 보충 입력(supplement)을 더한 입력만 읽는다(case_inputs.engine_inputs).
보충 입력·공제 대상 여부가 confirmed가 아니면 그 사례의 단계는 "입력 부족"으로 센다.
"""

from datetime import date

from cases.case_convert_items import (
    education_expenses,
    medical_expenses,
    nts_card,
    nts_out_of_scope,
)
from cases.case_convert_nts_items import nts_item_inputs
from cases.case_inputs import engine_inputs, usable
from cases.case_run import Run, person_of, worker_of
from taxsplit.engine import Dependent

_RELATIONS = {
    "spouse": "spouse",
    "child": "child",
    "lineal_ascendant": "lineal_ascendant",
    "spouse_lineal_ascendant": "lineal_ascendant",
}


def _family_dep(i: int, row: dict) -> Dependent:
    return Dependent(
        name=row.get("label", f"{row['relation']}{i}"),
        relation=_RELATIONS[row["relation"]],
        birth_year=2025 - row["age"],
        income_amount=row["income"],
        disabled=row.get("disabled", False),
        death_date=date.fromisoformat(row["death_date"]) if "death_date" in row else None,
    )


def _yymmdd_year(text: str) -> int:
    yy = int(text[:2])
    return 2000 + yy if yy <= 25 else 1900 + yy


def _expected_value(case: dict, stage: str) -> int:
    return next(e["value"] for e in case["expected"] if e["stage"] == stage)


def nts_runs(case: dict) -> list[Run]:
    """국세청 책자 사례. 총급여는 사례의 gross_salary 기대값을 입력으로 쓴다(계획 결정 2)."""
    expected = case["expected"]
    if not usable(case):
        return [Run(case["id"], [], missing=expected)]
    inputs = engine_inputs(case)
    page = case["source"]["printed_pages"][0]
    if case["kind"] == "household":
        return [_nts_household(case, inputs)]
    if page == 95:
        gross = _expected_value(case, "gross_salary")
        worker = worker_of(gross, person_of(inputs["self"]))
        return [Run(case["id"], expected, worker, gross_is_input=True)]
    if page == 162:
        credit = (inputs["computed_tax"], inputs["gross_salary"])
        return [Run(case["id"], expected, credit_inputs=credit)]
    me = inputs.get("self", {})
    if page in (97, 99):
        deps = [_family_dep(i, r) for i, r in enumerate(inputs["family"])]
        target = deps[0].name if page == 99 else None
        worker = worker_of(me["gross_salary"], person_of(me), deps)
        return [Run(case["id"], expected, worker, target=target)]
    if page == 100:
        q1 = inputs["q1"]
        spouse = Dependent(
            name="배우자",
            relation="spouse",
            birth_year=q1["spouse_birth_year"],
            income_amount=q1["spouse_income"],
            relation_start=date.fromisoformat(q1["marriage_date"]),
        )
        q2 = [_family_dep(i, r) for i, r in enumerate(inputs["q2"]["family"])]
        by_q = {q: [e for e in expected if e.get("sub_question") == q] for q in ("q1", "q2")}
        gross, person = me["gross_salary"], person_of(me)
        return [
            Run(
                f"{case['id']}#q1", by_q["q1"], worker_of(gross, person, [spouse]), target="배우자"
            ),
            Run(
                f"{case['id']}#q2",
                by_q["q2"],
                worker_of(gross, person, q2),
                target=inputs["q2"]["asked_about"],
            ),
        ]
    # 의료비·교육비·카드 항목 사례: 그 계산만 부른다(공제 선택과 무관하게 그 단계 값을 본다)
    item, gross, deps, spend = nts_item_inputs(case["groups"][0], inputs)
    return [Run(case["id"], expected, worker_of(gross, person_of(me), deps, **spend), item=item)]


def _nts_household(case: dict, inputs: dict) -> Run:
    deps = []
    for row in inputs["family"]:
        relation = "spouse" if row["role"] == "spouse" else "child"
        order = {"첫째": 1, "둘째": 2, "셋째": 3}.get(row.get("birth_order", ""))
        deps.append(
            Dependent(
                name=row["role"],
                relation=relation,
                birth_year=_yymmdd_year(row["birth_yymmdd"]),
                # 배우자는 문서의 사업소득금액, 자녀는 보충 입력의 소득(0원)
                income_amount=row.get("business_income_amount", row.get("income")),
                birth_or_adoption_order=order,
            )
        )
    expenses = inputs["expenses"]
    paid = {e["item"]: e["amount"] for e in expenses if e["for"] == "worker"}
    levels = {"self": "graduate"}
    for row in inputs["family"]:
        levels[row["role"]] = "preschool" if "취학전" in row.get("note", "") else "school"
    me = {**inputs["worker"], "birth_year": _yymmdd_year(inputs["worker"]["birth_yymmdd"])}
    has_spouse = any(row["role"] == "spouse" for row in inputs["family"])
    worker = worker_of(
        _expected_value(case, "gross_salary"),
        person_of(me, family_has_spouse=has_spouse),
        deps,
        national_pension=paid.get("국민연금", 0),
        health_insurance=paid.get("건강보험료", 0),
        long_term_care_insurance=paid.get("노인장기요양보험료", 0),
        medical=medical_expenses(expenses),
        education=education_expenses(expenses, levels),
        card_usage=nts_card(inputs["card_usage"]),
        out_of_scope=nts_out_of_scope(case),
    )
    return Run(case["id"], case["expected"], worker, gross_is_input=True)
