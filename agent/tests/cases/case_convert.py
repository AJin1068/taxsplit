"""사례 파일 inputs → 엔진 입력 변환. 테스트 쪽에만 둔다(처리 코드는 사례 파일을 읽지 않는다).

사례에 없는 본인 정보(성별·출생연도)는 비교하는 단계에 영향이 없는 값으로 채운다.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from taxsplit.engine import Dependent, OutOfScopeItem, SelfInfo, WorkerInput

# 사례에 본인 출생연도가 없을 때 쓰는 값(경로우대 70세 미만이면 비교 단계에 영향 없음)
_ANY_BIRTH_YEAR = 1985
# "20세 미만", "60세 이상"처럼 나이가 범위로만 적힌 경우, 범위를 만족하는 가장 가까운 나이
_AGE_NOTES = {"20세 미만": 19, "60세 이상": 60}
_RELATIONS = {
    "spouse": "spouse",
    "child": "child",
    "lineal_ascendant": "lineal_ascendant",
    "spouse_lineal_ascendant": "lineal_ascendant",
}


@dataclass
class Run:
    """엔진 실행 한 번(사람 한 명 또는 질문 하나)과 그에 딸린 기대값 줄."""

    label: str
    expected: list[dict[str, Any]]
    worker: WorkerInput | None = None
    # 이 부양가족 한 명의 값을 묻는 사례(p99·p100)면 그 이름
    target: str | None = None
    # 사례가 산출세액·총급여를 입력으로 주는 경우(p162): 근로소득세액공제만 비교
    credit_inputs: tuple[int, int] | None = None
    gross_is_input: bool = False
    excluded: list[dict[str, Any]] = field(default_factory=list)


def _worker(gross: int, deps=(), sex="male", birth_year=_ANY_BIRTH_YEAR, **kw) -> WorkerInput:
    person = SelfInfo(sex=sex, birth_year=birth_year, has_spouse=True)
    return WorkerInput(gross_salary=gross, person=person, dependents=tuple(deps), **kw)


def _age(row: dict) -> int:
    return row["age"] if "age" in row else _AGE_NOTES[row["age_note"]]


def _family_dep(i: int, row: dict) -> Dependent:
    return Dependent(
        name=row.get("label", f"{row['relation']}{i}"),
        relation=_RELATIONS[row["relation"]],
        birth_year=2025 - _age(row) if "age" in row or "age_note" in row else 1985,
        income_amount=row.get("income", 0),
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
    inputs, expected = case["inputs"], case["expected"]
    page = case["source"]["printed_pages"][0]
    if case["kind"] == "household":
        return [_nts_household(case)]
    if page == 95:
        gross = _expected_value(case, "gross_salary")
        return [Run(case["id"], expected, _worker(gross), gross_is_input=True)]
    if page == 162:
        credit = (inputs["computed_tax"], inputs["gross_salary"])
        return [Run(case["id"], expected, credit_inputs=credit)]
    if page in (97, 99):
        deps = [_family_dep(i, r) for i, r in enumerate(inputs["family"])]
        target = deps[0].name if page == 99 else None
        return [Run(case["id"], expected, _worker(0, deps), target=target)]
    if page == 100:
        q1 = inputs["q1"]
        spouse = Dependent(
            name="배우자",
            relation="spouse",
            birth_year=_ANY_BIRTH_YEAR,
            relation_start=date.fromisoformat(q1["marriage_date"]),
        )
        q2 = [_family_dep(i, r) for i, r in enumerate(inputs["q2"]["family"])]
        by_q = {q: [e for e in expected if e.get("sub_question") == q] for q in ("q1", "q2")}
        return [
            Run(f"{case['id']}#q1", by_q["q1"], _worker(0, [spouse]), target="배우자"),
            Run(f"{case['id']}#q2", by_q["q2"], _worker(0, q2), target=inputs["q2"]["asked_about"]),
        ]
    # 의료비·교육비·카드 항목 사례: 이번 PR은 실행하지 않고 모두 PR 5로 센다
    return [Run(case["id"], expected)]


def _nts_household(case: dict) -> Run:
    inputs = case["inputs"]
    deps = []
    for row in inputs["family"]:
        relation = "spouse" if row["role"] == "spouse" else "child"
        order = {"첫째": 1, "둘째": 2, "셋째": 3}.get(row.get("birth_order", ""))
        deps.append(
            Dependent(
                name=row["role"],
                relation=relation,
                birth_year=_yymmdd_year(row["birth_yymmdd"]),
                income_amount=row.get("business_income_amount", 0),
                birth_or_adoption_order=order,
            )
        )
    paid = {e["item"]: e["amount"] for e in inputs["expenses"] if e["for"] == "worker"}
    housing = sum(e["amount"] for e in inputs["expenses"] if e["category"] == "housing")
    oos = (
        OutOfScopeItem(
            name="주택자금",
            kind="income_deduction",
            category="special_income_deduction",
            amount=housing,
        ),
    )
    worker = _worker(
        _expected_value(case, "gross_salary"),
        deps,
        birth_year=_yymmdd_year(inputs["worker"]["birth_yymmdd"]),
        national_pension=paid.get("국민연금", 0),
        health_insurance=paid.get("건강보험료", 0),
        long_term_care_insurance=paid.get("노인장기요양보험료", 0),
        out_of_scope=oos,
    )
    return Run(case["id"], case["expected"], worker, gross_is_input=True)


def hometax_runs(case: dict) -> list[Run]:
    """홈택스 사례: 부부를 따로 계산한다(그 사람이 실제로 넣은 부양가족 기준)."""
    family = case["inputs"]["family"]
    people = {c["name"]: (c, "child") for c in family.get("children", [])}
    if "mother_in_law" in family:
        people["시어머니"] = (family["mother_in_law"], "lineal_ascendant")
    claimant: dict[str, list[Dependent]] = {"husband": [], "wife": []}
    for key, who in case["allocation"].items():
        name = key.split("(")[0]
        if "기본공제" in key and name in people:
            row, relation = people[name]
            dep = Dependent(
                name=name,
                relation=relation,
                birth_year=2025 - row["age"],
                income_amount=row.get("income", 0),
            )
            claimant[who].append(dep)
    runs = []
    for who, sex in (("husband", "male"), ("wife", "female")):
        rows = [e for e in case["expected"] if e["person"] == who]
        kept = [e for e in rows if not e.get("not_from_this_run")]
        dropped = [e for e in rows if e.get("not_from_this_run")]
        if not kept:
            runs.append(Run(f"{case['id']}/{who}", [], excluded=dropped))
            continue
        me = case["inputs"][who]
        entered = sum(me.get("dependents_entered", {}).values())
        assert entered == len(claimant[who]), (case["id"], who, "부양가족 수가 입력과 다름")
        worker = _worker(
            me["gross_salary"],
            claimant[who],
            sex=sex,
            national_pension=me["national_pension"],
            health_insurance=me["health_insurance"],
            employment_insurance=me["employment_insurance"],
        )
        runs.append(Run(f"{case['id']}/{who}", kept, worker, excluded=dropped))
    return runs
