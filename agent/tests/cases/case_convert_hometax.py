"""홈택스 모의계산 사례 → 엔진 입력. 보충 입력을 더한 입력만 읽는다(case_inputs.engine_inputs)."""

from cases.case_convert_items import hometax_spending
from cases.case_inputs import engine_inputs, usable
from cases.case_run import Run, person_of, worker_of
from taxsplit.engine import Dependent


def hometax_runs(case: dict) -> list[Run]:
    """홈택스 사례: 부부를 따로 계산한다(그 사람이 실제로 넣은 부양가족 기준)."""
    if not usable(case):
        return [Run(case["id"], [], missing=case["expected"])]
    inputs = engine_inputs(case)
    family = inputs["family"]
    people = {c["name"]: (c, "child") for c in family.get("children", [])}
    if "mother_in_law" in family:
        people["시어머니"] = (family["mother_in_law"], "lineal_ascendant")
    claimant: dict[str, list[Dependent]] = {"husband": [], "wife": []}
    claimed_rows: dict[str, dict[str, dict]] = {"husband": {}, "wife": {}}
    for key, who in case["allocation"].items():
        name = key.split("(")[0]
        if "기본공제" in key and name in people:
            row, relation = people[name]
            dep = Dependent(
                name=name,
                relation=relation,
                birth_year=2025 - row["age"],
                income_amount=row["income"],
            )
            claimant[who].append(dep)
            claimed_rows[who][name] = row
    runs = []
    for who in ("husband", "wife"):
        rows = [e for e in case["expected"] if e["person"] == who]
        kept = [e for e in rows if not e.get("not_from_this_run")]
        dropped = [e for e in rows if e.get("not_from_this_run")]
        if not kept:
            runs.append(Run(f"{case['id']}/{who}", [], excluded=dropped))
            continue
        me = inputs[who]
        entered = sum(me.get("dependents_entered", {}).values())
        assert entered == len(claimant[who]), (case["id"], who, "부양가족 수가 입력과 다름")
        worker = worker_of(
            me["gross_salary"],
            person_of(me),
            claimant[who],
            national_pension=me["national_pension"],
            health_insurance=me["health_insurance"],
            employment_insurance=me["employment_insurance"],
            **hometax_spending(me, claimed_rows[who]),
        )
        runs.append(Run(f"{case['id']}/{who}", kept, worker, excluded=dropped))
    return runs
